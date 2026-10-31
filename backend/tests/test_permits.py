"""Phase 2 Digital Tourist ID (SPEC 17), simulated: the ID number is never stored or sent to the AI, the upgraded pass
is signed and checkable offline, expired permits and revoked passes are refused, and restricted zones are permit-aware."""
import asyncio
import json
import time

from fastapi.testclient import TestClient
from sqlmodel import select

from app import core, permits
from app.ai import features
from app.ai.validators import validate_permit
from app.models import EventLog, LlmCall, Pass, PermitRecord
from app.security import verify_pass


def _trip(s, route="sikkim"):
    permits._lookups.clear()
    t, _ = core.create_trip(s, {"name": "Mia", "route_id": route, "language": "en", "consent": True})
    core.start_trip(s, t)
    return t, s.exec(select(Pass).where(Pass.trip_id == t.id)).one()


def test_lookup_keeps_only_last4_and_a_hash(s):
    t, _ = _trip(s)
    r = permits.lookup(s, t, "evisa", "ev2026 in 0042137")  # spaces and case don't matter
    assert r["found"] and r["permit"]["id_last4"] == "2137" and r["permit"]["covers_route"]
    rec = s.exec(select(PermitRecord)).one()
    dump = json.dumps(rec.model_dump(), default=str)
    assert "EV2026IN0042137" not in dump and "0042137" not in dump  # the full number is nowhere in the row
    assert rec.id_hash == permits.id_hash("evisa", "EV2026IN0042137")
    assert permits.lookup(s, t, "evisa", "EV0000000000")["reason"] == "not_found"
    assert permits.lookup(s, t, "pan", "ABCDE1234F")["reason"] == "unknown_id_type"


def test_upgrade_signs_a_permit_aware_pass_and_logs_it(s):
    t, ps = _trip(s)
    rec_id = permits.lookup(s, t, "digilocker", "DL-SK-NS-2026-1129")["permit"]["record_id"]
    r = permits.upgrade(s, t, ps, rec_id)
    assert r["ok"] and r["pass"]["kyc_level"] == "verified" and r["pass"]["permitted_zone_ids"] == ["Z-SKM-R1"]
    v = verify_pass(r["pass_qr"])
    assert v["valid"] and v["payload"]["permit_type"].startswith("North Sikkim") and v["payload"]["id_last4"] == "1129"
    assert permits.check(s, v, "Z-SKM-R1")["zone_ok"] is True  # Indian North Sikkim permit: Zero Point road allowed
    logged = s.exec(select(EventLog).where(EventLog.type == "pass.upgraded")).one()
    assert "1129" not in json.dumps(logged.payload)  # not even the last 4 go into the chain


def test_foreign_rap_is_not_permitted_beyond_yumthang(s):
    t, ps = _trip(s)
    rec_id = permits.lookup(s, t, "evisa", "EV2026IN0042137")["permit"]["record_id"]
    qr = permits.upgrade(s, t, ps, rec_id)["pass_qr"]
    res = permits.check(s, verify_pass(qr), "Z-SKM-R1")
    assert res["valid"] and res["zone_ok"] is False and "Yumthang" in res["zone_name"]


def test_expired_permit_cannot_upgrade_and_revocation_wins(s):
    t, ps = _trip(s, route="kedarnath")
    old = permits.lookup(s, t, "evisa", "EV2025IN0007788")["permit"]
    assert old["expired"] and permits.upgrade(s, t, ps, old["record_id"])["reason"] == "permit_expired"
    assert permits.revoke(s, ps.id, "lost pass reported", "responder")["ok"]
    assert permits.check(s, verify_pass(ps.qr))["reason"] == "revoked"
    assert [r["pass_id"] for r in permits.revocations(s, since=time.time() - 60)] == [ps.id]
    rec_id = permits.lookup(s, t, "yatra", "UK-YATRA-2026-551023")["permit"]["record_id"]
    assert permits.upgrade(s, t, ps, rec_id)["reason"] == "pass_revoked"


def test_aadhaar_is_optional_masked_and_never_a_permit(s):
    t, ps = _trip(s, route="kedarnath")
    r = permits.lookup(s, t, "aadhaar_masked", "1234 5678 9012")
    assert r["found"] and r["permit"]["id_last4"] == "9012" and r["permit"]["permitted_zone_ids"] == []
    up = permits.upgrade(s, t, ps, r["permit"]["record_id"])
    assert up["pass"]["kyc_level"] == "self_declared"


def test_lookups_are_rate_limited(s):
    t, _ = _trip(s)
    reasons = [permits.lookup(s, t, "visa", f"X{i:07d}")["reason"] for i in range(permits.LOOKUPS_PER_HOUR + 1)]
    assert reasons[-1] == "too_many_lookups"


def test_permit_card_uses_standard_text_without_ai_and_never_sees_the_id(s):
    t, ps = _trip(s)
    rec_id = permits.lookup(s, t, "evisa", "EV2026IN0042137")["permit"]["record_id"]
    permits.upgrade(s, t, ps, rec_id)
    card = asyncio.run(features.build_permit_card(t.id))
    assert card["source"] == "template" and "Yumthang" in card["content"]["allows"][0]
    assert not any("0042137" in (c.prompt_preview or "") for c in s.exec(select(LlmCall)).all())
    inp = permits.explainer_input(t, s.get(PermitRecord, rec_id))
    assert "0042137" not in json.dumps(inp)
    _, errs = validate_permit({"title": "Your permit", "allows": ["Valid for 45 days"], "not_allowed": [], "carry": []}, inp)
    assert errs  # a number that isn't in the official text is rejected


def test_api_requires_the_right_tokens(s):
    from app.main import app

    c = TestClient(app)
    t, ps = _trip(s)
    assert c.post("/api/permits/lookup", json={"trip_id": t.id, "id_type": "evisa", "id_number": "EV2026IN0042137"}).status_code == 401
    h = {"Authorization": f"Bearer {t.tourist_token}"}
    r = c.post("/api/permits/lookup", json={"trip_id": t.id, "id_type": "evisa", "id_number": "EV2026IN0042137"}, headers=h).json()
    up = c.post(f"/api/passes/{ps.id}/upgrade", json={"trip_id": t.id, "record_id": r["permit"]["record_id"]}, headers=h)
    assert up.status_code == 200 and up.json()["pass"]["kyc_level"] == "verified"
    assert c.post(f"/api/passes/{ps.id}/revoke", json={"reason": "x"}, headers=h).status_code == 401  # tourists can't revoke
    v = c.post("/api/passes/verify", json={"qr": up.json()["pass_qr"], "zone_id": "Z-SKM-R1"}).json()
    assert v["valid"] and v["zone_ok"] is False
