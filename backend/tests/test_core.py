import asyncio
import json
import time
import uuid

import httpx
import openai
from sqlmodel import select

from app import core, eventlog
from app.ai import jobs, prompts, prune_client, validators
from app.ai.pii import find_pii
from app.ai.templates import zone_text
from app.models import EventLog, SosEvent
from app.security import b64u, b64u_dec, canonical, issue_pass, verify_pass
from app.seeddata import route_facts

LAT, LON = 30.6960, 79.0470  # Kedarnath segment S3


def make_trip(s, name="Aarav Sharma", phone="9876543210", **kw):
    trip, qr = core.create_trip(s, {"name": name, "phone": phone, "emergency_contact_phone": "9123456780",
                                    "route_id": kw.pop("route_id", "kedarnath"), **kw})
    core.start_trip(s, trip)
    return trip, qr


def sos(s, trip, lat=LAT, lon=LON, kind="stuck", bucket="1", note=None, client_id=None):
    return core.receive_sos(s, trip, {"client_id": client_id or uuid.uuid4().hex, "kind": kind, "people_bucket": bucket,
                                      "note": note, "lat": lat, "lon": lon, "accuracy_m": 10,
                                      "created_at_device": time.time()})


def test_sos_is_idempotent(s):
    trip, _ = make_trip(s)
    cid = uuid.uuid4().hex
    a = sos(s, trip, client_id=cid)
    b = sos(s, trip, client_id=cid)
    assert not a["duplicate"] and b["duplicate"]
    assert len(s.exec(select(SosEvent).where(SosEvent.client_id == cid)).all()) == 1


def test_flood_is_flagged_and_merged(s):
    trip, _ = make_trip(s)
    results = [sos(s, trip) for _ in range(8)]
    assert sum("flood" in r["flags"] for r in results) == 3
    assert len({r["incident_id"] for r in results}) == 1


def test_cluster_counts_are_computed_exactly(s):
    t1, _ = make_trip(s, name="A")
    t2, _ = make_trip(s, name="B")
    t3, _ = make_trip(s, name="C")
    sos(s, t1, kind="injured", bucket="1")
    sos(s, t2, kind="lost", bucket="2-5", lat=LAT + 0.0003)
    r = sos(s, t3, kind="medical", bucket="6+", lon=LON + 0.0003)
    from app.models import Incident
    inc = s.get(Incident, r["incident_id"])
    s.refresh(inc)
    assert inc.type == "cluster" and inc.trip_count == 3
    assert inc.people_total == 1 + 3 + 8
    assert inc.injured_total == 2
    assert inc.priority == "P1"
    assert inc.cluster_summary and "12" in inc.cluster_summary["summary"]


def test_far_sos_makes_separate_incidents(s):
    t1, _ = make_trip(s)
    t2, _ = make_trip(s)
    a = sos(s, t1)
    b = sos(s, t2, lat=LAT + 0.01)  # ~1.1 km away
    assert a["incident_id"] != b["incident_id"]


def test_pack_validator_rejects_invented_phone_numbers():
    facts = route_facts("kedarnath")
    from app.ai.templates import pack_template
    good = pack_template("kedarnath", "en", "standard")
    _, errs = validators.validate_pack(good, facts)
    assert errs == []
    bad = json.loads(json.dumps(good))
    bad["briefing"][0] = "Call 9876543210 for help"
    _, errs = validators.validate_pack(bad, facts)
    assert any("9876543210" in e for e in errs)
    bad2 = json.loads(json.dumps(good))
    bad2["segments"][0]["nearest_help_id"] = "MP-FAKE"
    assert validators.validate_pack(bad2, facts)[1]


def test_cluster_validator_requires_exact_counts():
    counts = {"people_total": 12, "injured_reports": 2, "sos_reports": 3, "groups": 3, "by_kind": {"injured": 1}}
    ok = {"summary": "12 people, 2 injured reports near Linchauli", "needs": ["stretcher"], "notes_to_check": []}
    assert validators.validate_cluster(ok, counts)[1] == []
    bad = {**ok, "summary": "15 people, 4 injured near Linchauli"}
    assert validators.validate_cluster(bad, counts)[1]
    assert validators.validate_cluster({**ok, "needs": ["helicopter"]}, counts)[1]


def test_report_validator_blocks_invented_injuries():
    inp = {"kind": "lost", "note_text": "we cannot find the path", "people_bucket": "1"}
    out = {"headline": "Tourist lost near Linchauli", "what_we_know": ["One person is injured and bleeding"],
           "unknowns": [], "translated_note": "we cannot find the path", "suggested_questions": [],
           "priority_suggestion": "P2"}
    assert validators.validate_report(out, inp)[1]
    out["what_we_know"] = ["Tourist reports being lost"]
    assert validators.validate_report(out, inp)[1] == []


def test_copilot_drops_fake_sop_ids():
    cleaned, errs = validators.clean_copilot({"steps": [{"text": "Do X", "sop_id": "FAKE-1"}]}, {"INJ-1"}, set())
    assert cleaned["steps"] == [] and errs
    cleaned, errs = validators.clean_copilot({"steps": [{"text": "Send a team", "sop_id": "INJ-1"}]}, {"INJ-1"}, set())
    assert len(cleaned["steps"]) == 1 and not errs


def test_no_personal_data_in_prompts(s):
    trip, _ = make_trip(s, name="Aarav Sharma", phone="9876543210")
    r = sos(s, trip, kind="injured", note="my friend fell near the bridge")
    from app.ai.features import report_input
    from app.models import Incident
    inc = s.get(Incident, r["incident_id"])
    row = s.exec(select(SosEvent).where(SosEvent.incident_id == inc.id)).first()
    msgs = prompts.report_messages(report_input(s, inc, row))
    msgs += prompts.pack_messages(route_facts("kedarnath"), "en", "hi", trip.profile_bucket)
    msgs += prompts.cluster_messages({"people_total": 3}, "Linchauli", [row.note_text], 2)
    text = json.dumps(msgs, ensure_ascii=False)
    assert find_pii(text, ["Aarav", "Sharma", "9876543210", "9123456780", trip.id, trip.tourist_token]) == []


def test_event_log_detects_tampering(s):
    for i in range(3):
        eventlog.append("test.event", "test", "x", {"i": i})
    assert eventlog.verify_chain(s)["ok"]
    row = s.exec(select(EventLog).where(EventLog.entity_type == "test")).all()[1]
    row.payload = {"i": 99}
    s.add(row)
    s.commit()
    res = eventlog.verify_chain(s)
    assert not res["ok"] and res["broken_seq"] == row.seq


def test_pass_signature_and_expiry():
    payload, qr = issue_pass("T1234", "hall", time.time() - 60, time.time() + 3600)
    assert verify_pass(qr)["valid"]
    body, sig = qr.split(".")
    p = json.loads(b64u_dec(body))
    p["route_id"] = "kedarnath"
    assert verify_pass(b64u(canonical(p)) + "." + sig)["reason"] == "forged"
    _, old = issue_pass("T1234", "hall", time.time() - 7200, time.time() - 60)
    assert verify_pass(old)["reason"] == "expired"


def test_impossible_travel_is_flagged(s):
    trip, _ = make_trip(s)
    now = time.time()
    res = core.ingest_pings(s, trip, [{"lat": LAT, "lon": LON, "ts_device": now - 30},
                                      {"lat": LAT + 0.45, "lon": LON, "ts_device": now}])
    assert res["accepted"] == 1 and res["flagged"]
    s.refresh(trip)
    assert abs(trip.last_lat - LAT) < 1e-6  # position not updated from the flagged ping


def test_family_status_never_has_coordinates(s):
    trip, _ = make_trip(s)
    core.ingest_pings(s, trip, [{"lat": LAT, "lon": LON, "ts_device": time.time()}])
    out = core.family_status(s, trip)
    assert not any(k in out for k in ("lat", "lon", "last_lat", "last_lon", "polygon"))
    assert "9876543210" not in json.dumps(out)


# ------------------------------------------------------------------------------------------ Prune handling

def _status_error(status: int, code: str, retry_after: str | None = None):
    headers = {"x-prune-shield-code": code}
    if retry_after:
        headers["retry-after"] = retry_after
    resp = httpx.Response(status, request=httpx.Request("POST", "https://api.withprune.com/v1/chat/completions"),
                          headers=headers, json={"error": {"code": code}})
    return openai.APIStatusError(f"{status} {code}", response=resp, body={"error": {"code": code}})


class _Raw:
    status_code = 200

    def __init__(self, content, headers=None, meta=None):
        self.headers = headers or {"x-prune-cache-hit": "true", "x-prune-route-applied": "false"}
        self._content, self._meta = content, meta or {"cost_with_prune_usd": 0.0001, "receipt_signature": "sig"}

    def parse(self):
        content, meta = self._content, self._meta

        class _P:
            choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]

            def model_dump(self_inner):
                return {"prune_metadata": meta, "usage": {"prompt_tokens": 10, "completion_tokens": 5}, "model": "m"}
        return _P()


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.chat = self
        self.completions = self
        self.with_raw_response = self

    def with_options(self, **_):
        return self

    def create(self, **_):
        self.calls += 1
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


def _run_chat(client, monkeypatch):
    monkeypatch.setattr(prune_client, "_client", lambda key: client)
    real_sleep = asyncio.sleep
    monkeypatch.setattr(prune_client.asyncio, "sleep", lambda *_: real_sleep(0))
    return asyncio.run(prune_client.chat(job_key="t", run_id="t", feature="advisory", route_id="hall", model="m",
                                         tier="small", messages=[{"role": "user", "content": "hi"}], max_tokens=50,
                                         budget_usd=0.01, max_steps=3))


def test_run_budget_429_is_never_retried(monkeypatch):
    client = FakeClient([_status_error(429, "run_budget")])
    try:
        _run_chat(client, monkeypatch)
        assert False, "expected AIUnavailable"
    except prune_client.AIUnavailable as e:
        assert e.code == "run_budget" and e.is_budget_stop
    assert client.calls == 1


def test_fail_closed_503_retries_once_then_succeeds(monkeypatch):
    client = FakeClient([_status_error(503, "shield_unavailable", "1"), _Raw('{"ok": 1}')])
    r = _run_chat(client, monkeypatch)
    assert client.calls == 2 and r.content == '{"ok": 1}' and r.cache_hit is True
    assert r.cost_with_prune_usd == 0.0001


def test_402_blocks_ai_but_reports_template(monkeypatch):
    client = FakeClient([_status_error(402, "plan_limit")])
    try:
        _run_chat(client, monkeypatch)
    except prune_client.AIUnavailable as e:
        assert e.code == "plan_limit"
    assert prune_client._plan_blocked


def _job(validate_out, monkeypatch, replies):
    monkeypatch.setattr(jobs, "configured", lambda key="ops": True)
    seq = list(replies)

    async def fake_chat(**kw):
        c = seq.pop(0)
        if isinstance(c, Exception):
            raise c
        return prune_client.ChatResult(content=c, llm_call_id=1, cache_hit=False, cost_with_prune_usd=0.0001,
                                       estimated_cost_usd=0.0001, model_used="m", shield_code=None)
    monkeypatch.setattr(jobs, "chat", fake_chat)
    inp = {"zone_kind": "landslide", "severity": "danger", "segment_name": "Linchauli", "language": "en"}
    return asyncio.run(jobs.run_job(job_key=f"adv_test_{uuid.uuid4().hex}", feature="advisory", route_id="hall",
                                    run_id="adv_test", messages=prompts.advisory_messages(inp),
                                    validate=lambda o: validators.validate_advisory(o, inp),
                                    template=lambda: zone_text("en", "landslide", "Linchauli")))


def test_job_uses_ai_output_when_valid(monkeypatch):
    res = _job(None, monkeypatch, ['{"title": "Landslide ahead", "body": "The path near Linchauli is blocked.", '
                                   '"action": "Turn back now"}'])
    assert res.source == "ai" and res.output["title"] == "Landslide ahead"


def test_job_repairs_then_falls_back_to_template(monkeypatch):
    res = _job(None, monkeypatch, ["not json", '{"title": "x"}'])
    assert res.source == "template" and res.output == zone_text("en", "landslide", "Linchauli")


def test_job_budget_stop_uses_template(monkeypatch):
    res = _job(None, monkeypatch, [prune_client.AIUnavailable("run_budget", 429)])
    assert res.source == "template" and res.stopped_by == "run_budget"


def test_demo_scenario_fills_every_screen(s, monkeypatch):
    from app import stage
    from app.models import Incident, SafetyCheck

    async def no_crowd(*a, **k):
        return None
    monkeypatch.setattr(stage, "crowd_surge", no_crowd)
    res = asyncio.run(stage.demo_scenario("kedarnath"))
    cluster = s.get(Incident, res["cluster_incident_id"])
    assert cluster.type == "cluster" and cluster.trip_count == 4
    assert cluster.people_total == 3 + 8 + 1 + 1 and cluster.injured_total == 2 and cluster.priority == "P1"
    assert any(i.status == "accepted" for i in s.exec(select(Incident)).all())
    t = core.tally(s, s.exec(select(SafetyCheck)).all()[-1])
    assert t["asked"] >= 8 and t["safe"] == 3 and t["need_help"] == 1


def test_ai_not_configured_uses_template():
    inp = {"zone_kind": "landslide", "severity": "danger", "segment_name": "Linchauli", "language": "en"}
    res = asyncio.run(jobs.run_job(job_key="adv_nokey", feature="advisory", route_id="hall", run_id="adv_nokey",
                                   messages=prompts.advisory_messages(inp),
                                   validate=lambda o: validators.validate_advisory(o, inp),
                                   template=lambda: zone_text("en", "landslide", "Linchauli")))
    assert res.source == "template" and res.stopped_by == "ai_not_configured"
