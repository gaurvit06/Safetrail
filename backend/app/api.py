"""REST API (SPEC Section 7). Base path /api."""
import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from . import core, eventlog, events, stage
from .ai import features
from .ai.jobs import spawn
from .config import settings
from .db import get_session
from .engines import latest_heat, latest_public_heat
from .geo import polygon_area_m2
from .models import (BreakItAttempt, Checkpoint, HelpPoint, Incident, LlmCall, Route, SafetyCheck, SosEvent, Trip,
                     Zone)
from .seeddata import route_facts, route_seed, templates
from .security import check_role_token, log_signer, make_role_token, pass_signer, verify_pass

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------------------------------ auth helpers

def token_from(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return request.query_params.get("token")


def require_role(*roles: str):
    def dep(request: Request) -> str:
        role = check_role_token(token_from(request))
        if role is None:
            raise HTTPException(401, "Log in as a responder first")
        if role not in roles:
            raise HTTPException(403, "Your role can't do this")
        return role
    return dep


def tourist_trip(request: Request, s: Session, trip_id: str | None = None) -> Trip:
    tok = token_from(request)
    trip = s.exec(select(Trip).where(Trip.tourist_token == tok)).first() if tok else None
    if trip is None or (trip_id and trip.id != trip_id):
        raise HTTPException(401, "Unknown trip token")
    return trip


RESP = require_role("responder", "presenter")
PRES = require_role("presenter")


# ------------------------------------------------------------------------------------------ public

@router.get("/health")
def health():
    from .ai.prune_client import configured
    return {"ok": True, "ai_configured": configured("ops"), "time": time.time()}


@router.get("/config")
def config():
    return {"public_url": settings.public_url, "sms_number": settings.sos_sms_number or None,
            "advisory_langs": settings.advisory_langs, "approach_m": settings.approach_m,
            "sms_offer_after_s": settings.sms_offer_after_s, "usd_inr": settings.usd_inr,
            "pass_pubkey": pass_signer().public_b64, "log_pubkey": log_signer().public_b64,
            "log_key_id": log_signer().key_id}


def route_detail(s: Session, r: Route) -> dict:
    seed = route_seed(r.id)
    facts = route_facts(r.id)
    return {"id": r.id, "name": r.name, "region": r.region, "line": r.line, "bbox": r.bbox, "center": r.center,
            "simulated": r.simulated, "local_lang": r.local_lang,
            "segments": [{"id": sg["id"], "name": sg["name"], "coords": sg["coords"],
                          **{k: v for k, v in next((f for f in facts["segments"] if f["id"] == sg["id"]), {}).items()
                             if k in ("risky", "length_km", "nearest_help_id")}} for sg in seed.get("segments", [])],
            "help_points": [hp.model_dump() for hp in s.exec(select(HelpPoint).where(HelpPoint.route_id == r.id)).all()],
            "checkpoints": [cp.model_dump() for cp in s.exec(select(Checkpoint).where(Checkpoint.route_id == r.id)).all()],
            "zones": [core.zone_public(s, z) for z in core.active_zones(s, r.id)],
            "facts": {k: facts.get(k) for k in ("route_name", "distance_km", "emergency_number", "control_room_label",
                                                 "alternates", "crowd_wait_min", "segment_capacity", "altitude_m")}}


@router.get("/routes")
def routes(s: Session = Depends(get_session)):
    return [{"id": r.id, "name": r.name, "region": r.region, "center": r.center, "bbox": r.bbox,
             "simulated": r.simulated, "distance_km": route_facts(r.id).get("distance_km")}
            for r in s.exec(select(Route)).all()]


@router.get("/routes/{route_id}")
def route(route_id: str, s: Session = Depends(get_session)):
    r = s.get(Route, route_id)
    if not r:
        raise HTTPException(404, "Unknown route")
    return route_detail(s, r)


# ------------------------------------------------------------------------------------------ trips

class TripIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    phone: str = ""
    emergency_contact_name: str = ""
    emergency_contact_phone: str = ""
    language: str = "en"
    route_id: str
    start_at: float | None = None
    end_at: float | None = None
    group_size: int = 1
    profile_bucket: str = "standard"
    consent: bool
    consent_version: str = "v1"


def trip_created(trip: Trip, qr: str) -> dict:
    base = settings.public_url.rstrip("/")
    return {"trip": core.trip_public(trip), "pass_qr": qr, "tourist_token": trip.tourist_token,
            "family_url": f"{base}/f/{trip.family_token}" if base else f"/f/{trip.family_token}",
            "family_token": trip.family_token}


@router.post("/trips")
def create_trip(body: TripIn, s: Session = Depends(get_session)):
    if not body.consent:
        raise HTTPException(400, "Consent is required to share location during the trip")
    if not s.get(Route, body.route_id):
        raise HTTPException(400, "Unknown route")
    trip, qr = core.create_trip(s, body.model_dump())
    return trip_created(trip, qr)


class JoinIn(BaseModel):
    name: str | None = None
    language: str = "en"
    consent: bool = True


@router.post("/join")
def judge_join(body: JoinIn, s: Session = Depends(get_session)):
    """Stage quick-join: a trip on the hall demo route, named Judge-N unless a name is given."""
    if not body.consent:
        raise HTTPException(400, "Consent is required")
    n = len(s.exec(select(Trip).where(Trip.route_id == "hall", Trip.kind == "tourist")).all()) + 1
    trip, qr = core.create_trip(s, {"name": (body.name or f"Judge-{n}").strip()[:24], "route_id": "hall",
                                    "language": body.language, "consent_version": "v1-stage"})
    return trip_created(trip, qr)


def ui_templates(lang: str) -> dict:
    t = templates(lang)
    return {k: t[k] for k in ("zone", "approach", "crowd_inside", "crowd_ahead", "check", "kind", "phrases", "ui",
                              "message_to_group", "weather")}


@router.get("/weather")
async def route_weather(route_id: str):
    """Live weather per route section (Open-Meteo). Public: no personal data."""
    import asyncio
    from . import weather
    return await asyncio.to_thread(weather.get, route_id)


@router.post("/trips/{trip_id}/start")
def start(trip_id: str, request: Request, s: Session = Depends(get_session)):
    trip = tourist_trip(request, s, trip_id)
    core.start_trip(s, trip)
    pack = features.current_pack(s, trip.route_id, trip.language, trip.profile_bucket)
    if pack["pending"]:
        spawn(features.build_pack(trip.route_id, trip.language, trip.profile_bucket))
    ps = s.exec(select(core.Pass).where(core.Pass.trip_id == trip.id)).first()
    from . import weather
    w = weather.cached(trip.route_id)
    if not w:  # never block trip start on the network: fetch in the background, the phone gets weather.updated
        import threading
        from .engines import weather_tick
        threading.Thread(target=weather_tick, daemon=True).start()
    return {"trip": core.trip_public(trip), "route": route_detail(s, s.get(Route, trip.route_id)), "pack": pack,
            "templates": ui_templates(trip.language), "server_pubkey": pass_signer().public_b64,
            "pass_qr": ps.qr if ps else None, "pass": ps.payload if ps else None,
            "family_token": trip.family_token, "config": config(), "weather": w}


@router.get("/trips/{trip_id}")
def get_trip(trip_id: str, request: Request, s: Session = Depends(get_session)):
    trip = tourist_trip(request, s, trip_id)
    return {"trip": core.trip_public(trip), "sos": core.trip_sos_status(s, trip),
            "checks_pending": core.pending_checks(s, trip)}


@router.post("/trips/{trip_id}/sharing")
def sharing(trip_id: str, body: dict, request: Request, s: Session = Depends(get_session)):
    trip = tourist_trip(request, s, trip_id)
    trip.sharing = bool(body.get("on"))
    s.add(trip)
    s.commit()
    events.publish("trip.position", core.position_event(trip), events.OPS, route_id=trip.route_id)
    return core.trip_public(trip)


@router.post("/trips/{trip_id}/end")
def end_trip(trip_id: str, request: Request, s: Session = Depends(get_session)):
    trip = tourist_trip(request, s, trip_id)
    trip.status, trip.sharing, trip.end_at = "ended", False, time.time()
    s.add(trip)
    s.commit()
    eventlog.append("trip.ended", "trip", trip.id, {})
    events.publish("trip.ended", {"trip_label": trip.label, "route_id": trip.route_id}, events.OPS,
                   route_id=trip.route_id)
    return {"trip": core.trip_public(trip), "pings_deleted_after": trip.end_at + settings.ping_retention_days * 86400}


class PingIn(BaseModel):
    lat: float
    lon: float
    accuracy_m: float = 20
    ts_device: float | None = None
    source: str = "gps"


@router.post("/trips/{trip_id}/pings")
def pings(trip_id: str, body: list[PingIn], request: Request, s: Session = Depends(get_session)):
    trip = tourist_trip(request, s, trip_id)
    if not trip.sharing:
        return {"accepted": 0, "flagged": [], "sharing": False}
    return core.ingest_pings(s, trip, [p.model_dump() for p in body])


@router.post("/trips/{trip_id}/events")
def trip_events(trip_id: str, body: list[dict], request: Request, s: Session = Depends(get_session)):
    trip = tourist_trip(request, s, trip_id)
    for e in body[:50]:
        if e.get("type") in ("zone_enter", "approach") and e.get("zone_id"):
            events.publish("zone.entered" if e["type"] == "zone_enter" else "zone.approach",
                           {"trip_label": trip.label, "zone_id": e["zone_id"], "kind": e.get("kind"),
                            "ts_device": e.get("ts_device")}, events.OPS, route_id=trip.route_id)
    return {"ok": True}


@router.get("/trips/{trip_id}/sync")
def sync(trip_id: str, request: Request, s: Session = Depends(get_session)):
    trip = tourist_trip(request, s, trip_id)
    from . import weather
    return {"trip": core.trip_public(trip), "zones": [core.zone_public(s, z) for z in core.active_zones(s, trip.route_id)],
            "checks_pending": core.pending_checks(s, trip), "sos": core.trip_sos_status(s, trip),
            "weather": weather.cached(trip.route_id), "heat": latest_public_heat.get(trip.route_id)}


@router.get("/checkpoints/{checkpoint_id}")
def checkpoint(checkpoint_id: str, s: Session = Depends(get_session)):
    cp = s.get(Checkpoint, checkpoint_id)
    if not cp:
        raise HTTPException(404, "Unknown checkpoint")
    return cp.model_dump()


@router.get("/packs")
def packs(route_id: str, lang: str = "en", bucket: str = "standard", s: Session = Depends(get_session)):
    pack = features.current_pack(s, route_id, lang, bucket)
    if pack["pending"]:
        spawn(features.build_pack(route_id, lang, bucket))
    return pack


# ------------------------------------------------------------------------------------------ zones + crowd

@router.get("/zones")
def zones(route_id: str, s: Session = Depends(get_session)):
    return [core.zone_public(s, z) for z in core.active_zones(s, route_id)]


class ZoneIn(BaseModel):
    route_id: str
    kind: str
    severity: str = "danger"
    polygon: dict
    note: str | None = Field(default=None, max_length=200)
    expires_in_min: int | None = None


@router.post("/zones")
def create_zone(body: ZoneIn, role: str = Depends(RESP), s: Session = Depends(get_session)):
    if body.kind not in ("landslide", "closed_trail", "restricted", "wildlife_core", "flood", "red_zone", "custom"):
        raise HTTPException(400, "Unknown zone kind")
    ring = (body.polygon.get("coordinates") or [[]])[0]
    if body.polygon.get("type") != "Polygon" or len(ring) < 4 or ring[0] != ring[-1] or len(ring) > 201:
        raise HTTPException(400, "Draw a closed shape with 3 to 200 points")
    area = polygon_area_m2(body.polygon)
    if not 100 <= area <= 50_000_000:
        raise HTTPException(400, f"Zone area must be between 100 m² and 50 km² (got {int(area)} m²)")
    z = Zone(id="Z-" + uuid.uuid4().hex[:8], route_id=body.route_id, kind=body.kind,
             severity=body.severity if body.severity in ("warn", "danger") else "danger", polygon=body.polygon,
             source="drawn", note=body.note, simulated=True, created_by=role,
             expires_at=time.time() + body.expires_in_min * 60 if body.expires_in_min else None)
    data = core.publish_zone(s, z, role)
    targets = sum(1 for t in s.exec(select(Trip).where(Trip.route_id == body.route_id, Trip.sharing == True,  # noqa: E712
                                                       Trip.kind != "sim")).all())
    return {"zone": data, "phones_notified": targets}


@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: str, role: str = Depends(RESP), s: Session = Depends(get_session)):
    z = s.get(Zone, zone_id)
    if not z:
        raise HTTPException(404, "Unknown zone")
    core.remove_zone(s, z, role)
    return {"ok": True}


@router.get("/crowd/heat")
def crowd_heat(route_id: str, role: str = Depends(RESP)):
    return latest_heat.get(route_id, {"route_id": route_id, "cells": [], "ts": None})


# ------------------------------------------------------------------------------------------ SOS + incidents

class SosIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=64)
    trip_id: str
    kind: str
    people_bucket: str = "1"
    note: str | None = Field(default=None, max_length=280)
    lat: float
    lon: float
    accuracy_m: float = 20
    created_at_device: float
    channel: str = "data"


@router.post("/sos")
def sos(body: SosIn, request: Request, s: Session = Depends(get_session)):
    trip = tourist_trip(request, s, body.trip_id)
    channel = body.channel if body.channel in ("data", "sms", "checkpoint") else "data"
    return core.receive_sos(s, trip, body.model_dump(), channel)


@router.post("/sos/{client_id}/cancel")
def cancel(client_id: str, request: Request, s: Session = Depends(get_session)):
    r = s.exec(select(SosEvent).where(SosEvent.client_id == client_id)).first()
    if not r:
        raise HTTPException(404, "Unknown SOS")
    tourist_trip(request, s, r.trip_id)
    core.cancel_sos(s, r)
    return {"ok": True}


@router.post("/sms/inbound")
async def sms_inbound(request: Request, s: Session = Depends(get_session)):
    """SMS gateway webhook (SPEC 5.6). Secret in the X-SafeTrail-Secret header or ?secret=. Accepts JSON
    {from, text} or a form post (Twilio-style From/Body). Never drops an SOS: unmatched SMS go to responders."""
    import hmac
    from urllib.parse import parse_qs

    from . import sms
    if not settings.sms_webhook_secret:
        raise HTTPException(503, "SMS webhook not configured: set SMS_WEBHOOK_SECRET in .env")
    given = request.headers.get("x-safetrail-secret") or request.query_params.get("secret") or ""
    if not hmac.compare_digest(given.encode(), settings.sms_webhook_secret.encode()):
        raise HTTPException(401, "Wrong webhook secret")
    raw = await request.body()
    if "json" in request.headers.get("content-type", ""):
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            raise HTTPException(400, "Body is not JSON") from None
    else:
        data = {k: v[0] for k, v in parse_qs(raw.decode("utf-8", "replace")).items()}
    pick = lambda *keys: next((str(data[k]) for k in keys if data.get(k)), "")  # noqa: E731
    sender, text = pick("from", "From", "sender", "msisdn"), pick("text", "Body", "body", "message", "Text")
    if not text:
        raise HTTPException(400, "No SMS text")
    return sms.handle(s, sender, text)


@router.get("/incidents")
def incidents(status: str | None = None, route_id: str | None = None, include_merged: bool = False,
              role: str = Depends(RESP), s: Session = Depends(get_session)):
    q = select(Incident).order_by(Incident.id.desc())
    if route_id:
        q = q.where(Incident.route_id == route_id)
    if status:
        q = q.where(Incident.status == status)
    rows = s.exec(q).all()
    if not include_merged:
        rows = [i for i in rows if not any(str(f).startswith("merged_into") for f in (i.flags or []))]
    return [core.incident_summary(s, i) for i in rows]


@router.get("/incidents/{incident_id}")
def incident(incident_id: int, role: str = Depends(RESP), s: Session = Depends(get_session)):
    inc = s.get(Incident, incident_id)
    if not inc:
        raise HTTPException(404, "Unknown incident")
    return core.incident_detail(s, inc)


class StatusIn(BaseModel):
    status: str
    team: str | None = None


@router.post("/incidents/{incident_id}/status")
def incident_status(incident_id: int, body: StatusIn, role: str = Depends(RESP), s: Session = Depends(get_session)):
    inc = s.get(Incident, incident_id)
    if not inc:
        raise HTTPException(404, "Unknown incident")
    try:
        return core.set_incident_status(s, inc, body.status, role, body.team)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/incidents/{incident_id}/brief")
def brief(incident_id: int, role: str = Depends(RESP), s: Session = Depends(get_session)):
    inc = s.get(Incident, incident_id)
    if not inc:
        raise HTTPException(404, "Unknown incident")
    spawn(features.build_brief(incident_id))
    return {"pending": True, "brief": inc.brief, "source": inc.brief_source}


def _entry(r) -> dict:
    return {"seq": r.seq, "ts_server": r.ts_server, "type": r.type, "entity_type": r.entity_type,
            "entity_id": r.entity_id, "payload": r.payload, "payload_hash": r.payload_hash, "prev_hash": r.prev_hash,
            "hash": r.hash, "signature": r.signature, "key_id": r.key_id}


@router.get("/incidents/{incident_id}/timeline")
def timeline(incident_id: int, role: str = Depends(RESP), s: Session = Depends(get_session)):
    inc = s.get(Incident, incident_id)
    if not inc:
        raise HTTPException(404, "Unknown incident")
    rows = core.incident_timeline(s, inc)
    return {"entries": [_entry(r) for r in rows], "pubkey": log_signer().public_b64, "key_id": log_signer().key_id,
            "entries_check": eventlog.verify_rows(rows), "chain_check": eventlog.verify_chain(s)}


@router.get("/log/verify")
def log_verify(entity_type: str, entity_id: str, role: str = Depends(RESP), s: Session = Depends(get_session)):
    rows = eventlog.entity_entries(s, entity_type, entity_id)
    return {"entries": [_entry(r) for r in rows], "pubkey": log_signer().public_b64,
            "entries_check": eventlog.verify_rows(rows), "chain_check": eventlog.verify_chain(s)}


# ------------------------------------------------------------------------------------------ safety checks

class CheckIn(BaseModel):
    route_id: str
    zone_id: str | None = None
    polygon: dict | None = None
    message_key: str = "check_landslide"


@router.post("/safety-checks")
def create_check(body: CheckIn, role: str = Depends(RESP), s: Session = Depends(get_session)):
    chk = core.send_check(s, body.route_id, role, zone_id=body.zone_id, polygon=body.polygon,
                          message_key=body.message_key)
    return core.tally(s, chk)


@router.get("/safety-checks")
def checks(route_id: str | None = None, role: str = Depends(RESP), s: Session = Depends(get_session)):
    q = select(SafetyCheck).order_by(SafetyCheck.id.desc()).limit(10)
    if route_id:
        q = q.where(SafetyCheck.route_id == route_id)
    return [core.tally(s, c) for c in s.exec(q).all()]


@router.get("/safety-checks/{check_id}")
def check(check_id: int, role: str = Depends(RESP), s: Session = Depends(get_session)):
    chk = s.get(SafetyCheck, check_id)
    if not chk:
        raise HTTPException(404, "Unknown check")
    return core.tally(s, chk)


class AnswerIn(BaseModel):
    trip_id: str
    answer: str


@router.post("/safety-checks/{check_id}/answer")
def answer(check_id: int, body: AnswerIn, request: Request, s: Session = Depends(get_session)):
    trip = tourist_trip(request, s, body.trip_id)
    chk = s.get(SafetyCheck, check_id)
    if not chk or body.answer not in ("safe", "need_help"):
        raise HTTPException(400, "Unknown check or answer")
    core.answer_check(s, chk, trip, body.answer)
    return {"ok": True}


# ------------------------------------------------------------------------------------------ family + passes

@router.get("/family/{token}")
def family(token: str, s: Session = Depends(get_session)):
    trip = s.exec(select(Trip).where(Trip.family_token == token)).first()
    if not trip or trip.family_revoked or (trip.end_at and trip.status == "ended" and time.time() > trip.end_at + 86400):
        raise HTTPException(404, "This link has expired or was turned off")
    return core.family_status(s, trip)


@router.post("/family/{trip_id}/revoke")
def revoke(trip_id: str, request: Request, s: Session = Depends(get_session)):
    trip = tourist_trip(request, s, trip_id)
    trip.family_revoked = True
    s.add(trip)
    s.commit()
    return {"ok": True}


class QrIn(BaseModel):
    qr: str
    zone_id: str | None = None  # Phase 2: "checking entry to this zone"


@router.post("/passes/verify")
def pass_verify(body: QrIn, s: Session = Depends(get_session)):
    from . import permits
    return permits.check(s, verify_pass(body.qr), body.zone_id)


# ------------------------------------------------------------------------------------------ Phase 2: permits (simulated)

class PermitLookupIn(BaseModel):
    trip_id: str
    id_type: str
    id_number: str = Field(min_length=1, max_length=40)


@router.post("/permits/lookup")
def permit_lookup(body: PermitLookupIn, request: Request, s: Session = Depends(get_session)):
    """Mock registry (SPEC 17.2). The number is hashed at once; only its last 4 characters are kept."""
    from . import permits
    trip = tourist_trip(request, s, body.trip_id)
    return permits.lookup(s, trip, body.id_type, body.id_number)


class UpgradeIn(BaseModel):
    trip_id: str
    record_id: int


@router.post("/passes/{pass_id}/upgrade")
def pass_upgrade(pass_id: str, body: UpgradeIn, request: Request, s: Session = Depends(get_session)):
    from . import permits
    from .models import Pass
    trip = tourist_trip(request, s, body.trip_id)
    ps = s.get(Pass, pass_id)
    if not ps or ps.trip_id != trip.id:
        raise HTTPException(404, "Unknown pass")
    r = permits.upgrade(s, trip, ps, body.record_id)
    if not r["ok"]:
        raise HTTPException(400, r["reason"])
    return r


class RevokeIn(BaseModel):
    reason: str = ""


@router.post("/passes/{pass_id}/revoke")
def pass_revoke(pass_id: str, body: RevokeIn, role: str = Depends(RESP), s: Session = Depends(get_session)):
    from . import permits
    r = permits.revoke(s, pass_id, body.reason, role)
    if not r["ok"]:
        raise HTTPException(404, r["reason"])
    return r


@router.get("/passes/revocations")
def pass_revocations(since: float = 0, role: str = Depends(RESP), s: Session = Depends(get_session)):
    """For checkpoint devices to sync while online, so they can refuse revoked passes offline."""
    from . import permits
    return permits.revocations(s, since)


@router.get("/trips/{trip_id}/permit-card")
async def permit_card(trip_id: str, request: Request, s: Session = Depends(get_session)):
    trip = tourist_trip(request, s, trip_id)
    card = await features.build_permit_card(trip.id)
    if card is None:
        raise HTTPException(404, "No permit linked to this trip")
    return card


# ------------------------------------------------------------------------------------------ AI & cost

@router.get("/ai/stats")
def ai_stats(route_id: str | None = None, since: float | None = None, role: str = Depends(RESP),
             s: Session = Depends(get_session)):
    return core.ai_stats(s, route_id, since)


@router.get("/ai/calls")
def ai_calls(feature: str | None = None, limit: int = 100, role: str = Depends(RESP), s: Session = Depends(get_session)):
    q = select(LlmCall).where(LlmCall.benchmark_run_id == None).order_by(LlmCall.id.desc()).limit(min(limit, 500))  # noqa: E711
    if feature:
        q = q.where(LlmCall.feature == feature)
    return [{**core._call_brief(c), "job_key": c.job_key, "run_id": c.run_id, "route_reason": c.route_reason,
             "prompt_tokens": c.prompt_tokens, "completion_tokens": c.completion_tokens, "tokens_saved": c.tokens_saved,
             "key_used": c.key_used, "optimizations_applied": c.optimizations_applied} for c in s.exec(q).all()]


@router.get("/ai/receipts")
def ai_receipts(job_key: str | None = None, role: str = Depends(RESP), s: Session = Depends(get_session)):
    q = select(LlmCall).where(LlmCall.receipt_signature != None)  # noqa: E711
    if job_key:
        q = q.where(LlmCall.job_key == job_key)
    return [{"call_id": c.id, "job_key": c.job_key, "feature": c.feature, "created_at": c.created_at,
             "receipt_signature": c.receipt_signature, "receipt_signing_key_id": c.receipt_signing_key_id,
             "prune_metadata": c.raw_metadata} for c in s.exec(q).all()]


@router.get("/benchmark")
def benchmark_results():
    """Latest results of scripts/benchmark.py (docs/benchmark_results.json). Public: simulated scenario, costs only."""
    import json

    from .config import REPO_DIR
    path = REPO_DIR / "docs" / "benchmark_results.json"
    if not path.exists():
        return {"status": "not_run", "runs": {}, "waterfall": None}
    return {"status": "ok", **json.loads(path.read_text(encoding="utf-8"))}


# ------------------------------------------------------------------------------------------ auth + stage

class LoginIn(BaseModel):
    role: str
    pin: str


@router.post("/auth/login")
def login(body: LoginIn):
    pins = {"responder": settings.responder_pin, "presenter": settings.presenter_pin}
    if body.role not in pins or body.pin != pins[body.role]:
        raise HTTPException(401, "Wrong PIN")
    return {"token": make_role_token(body.role), "role": body.role}


class ScenarioIn(BaseModel):
    action: str
    lat: float | None = None
    lon: float | None = None
    route_id: str = "hall"


@router.post("/stage/scenario")
async def scenario(body: ScenarioIn, role: str = Depends(PRES)):
    from .db import session_scope
    if body.action == "landslide":
        with session_scope() as s:
            return {"zone": stage.landslide(s, body.lat, body.lon, body.route_id)}
    if body.action == "crowd_surge":
        spawn(stage.crowd_surge(body.lat, body.lon, body.route_id))
        return {"ok": True, "message": "Adding 40 simulated people over 20 seconds"}
    if body.action == "safety_check":
        with session_scope() as s:
            return stage.safety_check(s, body.route_id)
    if body.action == "budget_stress":
        return await stage.budget_stress()
    if body.action == "demo_data":
        return await stage.demo_scenario("kedarnath" if body.route_id == "hall" else body.route_id)
    if body.action == "walk_sim":
        spawn(stage.walk_sim(body.lat, body.lon, body.route_id))
        return {"ok": True}
    if body.action == "reset":
        with session_scope() as s:
            return stage.reset_demo(s)
    if body.action == "next_round":
        with session_scope() as s:
            return stage.next_round(s)
    raise HTTPException(400, "Unknown action")


class CsedIn(BaseModel):
    action: str


@router.post("/stage/csed")
async def csed(body: CsedIn, role: str = Depends(RESP)):
    """The CSED block demo, from the responder portal or from stage control."""
    from .db import session_scope
    if body.action == "flag":
        with session_scope() as s:
            return stage.flag_csed(s, role)
    if body.action == "clear":
        with session_scope() as s:
            return stage.clear_csed(s, role)
    if body.action == "crowd":
        spawn(stage.csed_crowd())
        return {"ok": True, "message": "Simulated crowd building around the CSED block"}
    if body.action == "crowd_stop":
        with session_scope() as s:
            return stage.stop_csed_crowd(s)
    raise HTTPException(400, "Unknown action")


@router.get("/stage/round")
def stage_round(role: str = Depends(RESP), s: Session = Depends(get_session)):
    return stage.round_state(s)


@router.get("/stage/state")
def stage_state(route_id: str = "hall", role: str = Depends(RESP), s: Session = Depends(get_session)):
    trips = s.exec(select(Trip).where(Trip.route_id == route_id, Trip.status != "ended")).all()
    t = time.time()
    on_trail = [tr for tr in trips if tr.kind == "tourist" and tr.sharing and tr.last_ping_at and tr.last_ping_at > t - 300]
    last_check = s.exec(select(SafetyCheck).where(SafetyCheck.route_id == route_id).order_by(SafetyCheck.id.desc())).first()
    stats = core.ai_stats(s)
    return {"on_trail": len(on_trail), "sim": sum(1 for tr in trips if tr.kind == "sim"),
            "sos": len(s.exec(select(SosEvent).join(Trip, SosEvent.trip_id == Trip.id).where(Trip.route_id == route_id)).all()),
            "open_incidents": len([i for i in s.exec(select(Incident).where(Incident.route_id == route_id,
                                                                            Incident.status.in_(core.OPEN))).all()]),
            "check": core.tally(s, last_check) if last_check else None,
            "positions": [core.position_event(tr) for tr in trips if tr.last_lat is not None and tr.sharing],
            "ai": {k: stats[k] for k in ("calls", "cost_usd", "cost_inr", "cache_hits", "routed", "template_fallbacks",
                                         "ai_configured")},
            "board": [stage.board_row(a) for a in s.exec(select(BreakItAttempt).order_by(BreakItAttempt.id.desc()).limit(12)).all()],
            "recent": events.recent(12), "join_url": (settings.public_url.rstrip("/") + "/j") if settings.public_url else "/j"}


class TrickIn(BaseModel):
    nickname: str = "Anonymous"
    consent: bool = False
    trick: str
    detail: dict = {}


@router.post("/breakit/attempts")
def breakit(body: TrickIn, request: Request, s: Session = Depends(get_session)):
    try:
        return stage.run_trick(s, body.trick, body.nickname, body.consent, body.detail,
                               request.headers.get("x-device-id", ""), request.client.host if request.client else "")
    except PermissionError as e:
        raise HTTPException(429, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/breakit/attempts/{attempt_id}/self-report")
def self_report(attempt_id: int, body: dict, s: Session = Depends(get_session)):
    a = s.get(BreakItAttempt, attempt_id)
    if not a or a.trick != "custom":
        raise HTTPException(400, "Only custom attempts can be self-reported")
    a.self_report = bool(body.get("flagged"))
    s.add(a)
    s.commit()
    return stage.board_row(a)


@router.get("/breakit/board")
def board(s: Session = Depends(get_session)):
    return [stage.board_row(a) for a in s.exec(select(BreakItAttempt).order_by(BreakItAttempt.id.desc()).limit(30)).all()]
