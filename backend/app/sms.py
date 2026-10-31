"""SMS inbound (SPEC 5.6 "SMS inbound", 5.8.6): an SOS that couldn't use mobile data still gets through.

- Coded SMS, written by the app when data is down ("SOS T4821 30.73520 79.06690 INJ 2-5 1131 1a2b3c4d"), is parsed
  with a regex. No AI. It becomes a normal SOS with channel=sms, and the same SOS arriving later over data (or the
  other way round) is recognised as a duplicate from the first 8 characters of its id.
- Free-text SMS from a phone number registered on an active trip becomes an SOS at once (kind unknown, flagged
  "call back"); only then does the sms_parse AI job try to read the kind, the number of people and a place from the
  text. The AI can never lower the priority and can only quote a place that is written in the SMS.
- An SMS that can't be linked to a trip is never dropped: it goes to the responders as a call-back request.
"""
import datetime as dt
import hashlib
import hmac
import re
import time
from types import SimpleNamespace

from sqlmodel import Session, select

from . import core, eventlog, events
from .config import settings
from .models import Route, SmsInbound, SosEvent, Trip

CODED = re.compile(r"^\s*SOS\s+(?P<label>[A-Z]{1,3}\d{2,6})\s+(?P<lat>-?\d{1,2}\.\d{2,7})\s+(?P<lon>-?\d{1,3}\.\d{2,7})"
                   r"\s+(?P<kind>INJ|LOST|STK|MED|UNS|SOS)\s+(?P<people>2-5|6\+|\d{1,3})\s+(?P<hhmm>\d{4})"
                   r"\s+(?P<cid>[0-9a-f]{8})\b", re.I)
KIND = {"INJ": "injured", "LOST": "lost", "STK": "stuck", "MED": "medical", "UNS": "unsafe", "SOS": "unknown"}
RANK = {"P1": 1, "P2": 2, "P3": 3}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))  # all pilot routes are in India


def people_bucket(raw: str) -> str:
    if raw in ("1", "2-5", "6+"):
        return raw
    n = int(raw) if raw.isdigit() else 1
    return "1" if n <= 1 else "2-5" if n <= 5 else "6+"


def device_time(hhmm: str, now: float | None = None) -> float:
    """The phone's HH:MM (Indian time) as the latest matching moment not in the future (5 min of clock slack)."""
    now = now or time.time()
    h, m = int(hhmm[:2]), int(hhmm[2:])
    if h > 23 or m > 59:
        return now
    today = dt.datetime.fromtimestamp(now, IST).replace(hour=h, minute=m, second=0, microsecond=0)
    t = today.timestamp()
    return t - 86400 if t > now + 300 else t


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")[-10:]


def _hash(phone: str) -> str:
    return hmac.new(settings.token_secret.encode(), _digits(phone).encode(), hashlib.sha256).hexdigest()


def _trip_by_phone(s: Session, phone: str) -> Trip | None:
    d = _digits(phone)
    if len(d) < 6:
        return None
    trips = s.exec(select(Trip).where(Trip.status != "ended").order_by(Trip.consent_at.desc())).all()
    return next((t for t in trips if _digits(t.phone) == d), None)


def _existing(s: Session, trip_id: str, cid: str) -> SosEvent | None:
    rows = s.exec(select(SosEvent).where(SosEvent.trip_id == trip_id)).all()
    return next((r for r in rows if r.client_id.startswith(cid) or r.client_id == f"sms-{cid}"), None)


def handle(s: Session, sender: str, text: str) -> dict:
    text = (text or "").strip()[:480]
    row = SmsInbound(from_hash=_hash(sender), from_last4=_digits(sender)[-4:], text=text)
    m = CODED.match(text)
    if m:
        trip = s.exec(select(Trip).where(Trip.label == m["label"].upper(), Trip.status != "ended")).first()
        if trip:
            cid = m["cid"].lower()
            row.trip_id = trip.id
            dup = _existing(s, trip.id, cid)
            if dup:
                row.parsed_via, row.sos_client_id = "duplicate", dup.client_id
                s.add(row)
                s.commit()
                return {"ok": True, "parsed_via": "duplicate", "incident_id": dup.incident_id}
            body = {"client_id": f"sms-{cid}", "kind": KIND[m["kind"].upper()], "people_bucket": people_bucket(m["people"]),
                    "note": None, "lat": float(m["lat"]), "lon": float(m["lon"]), "accuracy_m": 50,
                    "created_at_device": device_time(m["hhmm"])}
            res = core.receive_sos(s, trip, body, channel="sms")
            row.parsed_via, row.sos_client_id = "coded", body["client_id"]
            s.add(row)
            s.commit()
            return {"ok": True, "parsed_via": "coded", "incident_id": res["incident_id"]}
    trip = _trip_by_phone(s, sender)
    if not trip:
        row.parsed_via = "unmatched"
        s.add(row)
        s.commit()
        s.refresh(row)
        eventlog.append("sms.unmatched", "sms", row.id, {"from_last4": row.from_last4})
        events.publish("sms.unmatched", {"sms_id": row.id, "from_last4": row.from_last4, "text": text[:160],
                                         "received_at": row.received_at}, events.OPS)
        return {"ok": True, "parsed_via": "unmatched", "incident_id": None}
    # free text from a registered phone: the SOS exists before any AI runs
    lat, lon, flags = trip.last_lat, trip.last_lon, ["sms_free_text", "call_back", "people_unknown"]
    if lat is None or lon is None:
        route = s.get(Route, trip.route_id)
        lon, lat = route.center if route and route.center else (0.0, 0.0)
        flags.append("location_unknown")
    cid = f"sms-{hashlib.sha256(f'{row.from_hash}{row.received_at}'.encode()).hexdigest()[:8]}"
    res = core.receive_sos(s, trip, {"client_id": cid, "kind": "unknown", "people_bucket": "1", "note": text[:280],
                                     "lat": lat, "lon": lon, "accuracy_m": trip.last_accuracy_m or 5000,
                                     "created_at_device": row.received_at}, channel="sms")
    sos = s.exec(select(SosEvent).where(SosEvent.client_id == cid)).first()
    sos.flags = sorted(set(sos.flags or []) | set(flags))
    s.add(sos)
    row.parsed_via, row.trip_id, row.sos_client_id = "free_text", trip.id, cid
    s.add(row)
    s.commit()
    s.refresh(row)
    inc = s.get(core.Incident, res["incident_id"])
    core.recompute_incident(s, inc)
    events.publish("incident.updated", core.incident_summary(s, inc), events.OPS, route_id=trip.route_id)
    from .ai import features
    from .ai.jobs import spawn
    spawn(features.build_sms_parse(row.id))
    return {"ok": True, "parsed_via": "free_text", "incident_id": res["incident_id"]}


def _priority(kind: str, bucket: str, trip: Trip, created: float) -> str:
    row = SimpleNamespace(kind=kind, people_bucket=bucket, trip_id=trip.id, created_at_device=created)
    return core.rules_priority([row], {trip.id: trip})


def apply_parse(s: Session, sms_id: int, out: dict, source: str) -> dict:
    """Use what the AI read, but only to fill fields that are still unknown, and never if it would lower the
    rules-based priority. A known kind or head count is never overwritten."""
    row = s.get(SmsInbound, sms_id)
    sos = s.exec(select(SosEvent).where(SosEvent.client_id == row.sos_client_id)).first()
    trip = s.get(Trip, row.trip_id)
    row.ai_source, row.ai_result = source, out
    s.add(row)
    applied = {}
    if sos and trip:
        before = _priority(sos.kind, sos.people_bucket, trip, sos.created_at_device)
        flags = set(sos.flags or [])
        kind = out["kind"] if sos.kind == "unknown" and out.get("kind") not in (None, "", "unknown") else sos.kind
        bucket = out["people_bucket"] if "people_unknown" in flags and out.get("people_bucket") not in (None, "", "unknown") \
            else sos.people_bucket
        for k, b in ((kind, bucket), (sos.kind, bucket), (kind, sos.people_bucket)):
            if (k, b) != (sos.kind, sos.people_bucket) and RANK[_priority(k, b, trip, sos.created_at_device)] <= RANK[before]:
                applied = {"kind": k, "people_bucket": b}
                if b != sos.people_bucket:
                    flags.discard("people_unknown")
                sos.kind, sos.people_bucket = k, b
                break
        sos.flags = sorted(flags)
        if out.get("place_hint"):
            sos.flags = sorted(set(sos.flags or []) | {"place_mentioned"})
        s.add(sos)
        s.commit()
        inc = s.get(core.Incident, sos.incident_id)
        if inc:
            core.recompute_incident(s, inc)
            events.publish("incident.updated", core.incident_summary(s, inc), events.OPS, route_id=inc.route_id)
    s.commit()
    events.publish("sms.parsed", {"sms_id": sms_id, "incident_id": sos.incident_id if sos else None, "source": source,
                                  "kind": out.get("kind"), "people_bucket": out.get("people_bucket"),
                                  "place_hint": out.get("place_hint"), "applied": applied}, events.OPS,
                   route_id=trip.route_id if trip else None)
    return applied
