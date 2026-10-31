"""SMS inbound (SPEC 5.6, 5.8.6): coded SMS without AI, no duplicates across SMS and data, free text never waits
for the AI, the AI can't lower priority or invent a place, and an unknown sender still reaches the responders."""
import time

from fastapi.testclient import TestClient
from sqlmodel import select

from app import core, sms
from app.ai.validators import validate_sms
from app.models import Incident, SmsInbound, SosEvent


def _trip(s, phone="+91 98765 43210", lat=30.6972, lon=79.0595):
    t, _ = core.create_trip(s, {"name": "Asha", "route_id": "kedarnath", "phone": phone, "consent": True})
    core.start_trip(s, t)
    t.last_lat, t.last_lon, t.last_ping_at = lat, lon, time.time()
    s.add(t)
    s.commit()
    return t


def test_coded_sms_becomes_an_sos_without_ai(s):
    t = _trip(s)
    r = sms.handle(s, "+919876543210", f"SOS {t.label} 30.69726 79.05954 INJ 2-5 1131 1a2b3c4d")
    assert r["parsed_via"] == "coded" and r["incident_id"]
    row = s.exec(select(SosEvent).where(SosEvent.client_id == "sms-1a2b3c4d")).one()
    assert (row.kind, row.people_bucket, row.channel) == ("injured", "2-5", "sms")
    assert s.get(Incident, row.incident_id).priority == "P1"


def test_same_sos_by_sms_and_data_is_counted_once(s):
    t = _trip(s)
    sms.handle(s, "x", f"SOS {t.label} 30.69726 79.05954 STK 1 0915 deadbeef")
    later = core.receive_sos(s, t, {"client_id": "deadbeef-0000-4000-8000-000000000000", "kind": "stuck",
                                    "people_bucket": "1", "lat": 30.69726, "lon": 79.05954, "created_at_device": time.time()})
    assert later["duplicate"] is True
    t2 = _trip(s, phone="")
    core.receive_sos(s, t2, {"client_id": "cafe1234-0000-4000-8000-000000000000", "kind": "lost", "people_bucket": "1",
                             "lat": 30.68, "lon": 79.04, "created_at_device": time.time()})
    again = sms.handle(s, "x", f"SOS {t2.label} 30.68000 79.04000 LOST 1 0915 cafe1234")
    assert again["parsed_via"] == "duplicate"
    assert len(s.exec(select(SosEvent).where(SosEvent.trip_id == t2.id)).all()) == 1


def test_free_text_from_a_registered_phone_is_an_sos_before_any_ai(s):
    t = _trip(s)
    r = sms.handle(s, "098765 43210", "help my friend slipped near Bhimbali, 3 of us")
    assert r["parsed_via"] == "free_text"
    sos_row = s.exec(select(SosEvent).where(SosEvent.trip_id == t.id)).one()
    assert sos_row.kind == "unknown" and {"sms_free_text", "call_back"} <= set(sos_row.flags)
    assert (sos_row.lat, sos_row.lon) == (t.last_lat, t.last_lon)
    m = s.exec(select(SmsInbound).where(SmsInbound.trip_id == t.id)).one()
    assert m.from_last4 == "3210" and "98765" not in m.from_hash  # the number itself is never stored


def test_ai_reading_never_lowers_priority_or_invents_a_place(s):
    t = _trip(s)
    sms.handle(s, "+919876543210", "we are 3 people, one is hurt near Bhimbali")
    m = s.exec(select(SmsInbound)).first()
    out, errs = validate_sms({"kind": "injured", "people_bucket": "2-5", "place_hint": "Kedarnath temple"}, m.text)
    assert errs  # a place that isn't in the SMS is rejected
    out, errs = validate_sms({"kind": "injured", "people_bucket": "2-5", "place_hint": "near bhimbali"}, m.text)
    assert not errs
    assert sms.apply_parse(s, m.id, out, "ai") == {"kind": "injured", "people_bucket": "2-5"}  # P2 -> P1: allowed
    sos_row = s.exec(select(SosEvent).where(SosEvent.trip_id == t.id)).one()
    assert s.get(Incident, sos_row.incident_id).priority == "P1" and "place_mentioned" in sos_row.flags
    assert sms.apply_parse(s, m.id, {"kind": "lost", "people_bucket": "1", "place_hint": ""}, "ai") == {}  # would lower
    assert s.exec(select(SosEvent).where(SosEvent.trip_id == t.id)).one().kind == "injured"


def test_unknown_sender_goes_to_responders_not_the_bin(s):
    r = sms.handle(s, "+447700900123", "accident on the road, please call")
    assert r["parsed_via"] == "unmatched" and r["incident_id"] is None
    m = s.exec(select(SmsInbound)).one()
    assert m.from_last4 == "0123" and m.text.startswith("accident")


def test_webhook_needs_the_secret(monkeypatch, s):
    from app.config import settings
    from app.main import app

    c = TestClient(app)
    monkeypatch.setattr(settings, "sms_webhook_secret", "")
    assert c.post("/api/sms/inbound", json={"from": "1", "text": "SOS"}).status_code == 503
    monkeypatch.setattr(settings, "sms_webhook_secret", "s3cret")
    assert c.post("/api/sms/inbound", json={"from": "1", "text": "SOS"}).status_code == 401
    t = _trip(s)
    ok = c.post("/api/sms/inbound?secret=s3cret", data={"From": "+15550001111", "Body": f"SOS {t.label} 30.69 79.05 MED 1 0800 abcdef12"})
    assert ok.status_code == 200 and ok.json()["parsed_via"] == "coded"


def test_device_time_and_people_codes():
    assert sms.people_bucket("3") == "2-5" and sms.people_bucket("9") == "6+" and sms.people_bucket("6+") == "6+"
    now = time.time()
    assert now - 86400 - 300 <= sms.device_time("0000", now) <= now + 300
