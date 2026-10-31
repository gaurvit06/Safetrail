"""Core safety logic (SPEC 5.1-5.7, 5.9, 5.15, 5.16). No LLM here: everything safety-critical is plain code.
AI jobs are only *spawned* from here and never awaited, so the AI is never in the emergency path."""
import re
import secrets
import time
import uuid
from collections import Counter

from sqlmodel import Session, select

from . import events, eventlog
from .ai import features
from .ai.jobs import spawn
from .ai.templates import cluster_template, report_template, zone_text
from .config import settings
from .geo import centroid, haversine_m, point_in_polygon
from .models import (AiJob, CheckResponse, Incident, LlmCall, Pass, Ping, SafetyCheck, SosEvent, Trip, Zone,
                     ZoneAdvisory)
from .seeddata import route_facts, segment_for, templates
from .security import issue_pass

PEOPLE_MID = {"1": 1, "2-5": 3, "6+": 8}
OPEN = ("new", "accepted", "en_route")
SOS_KINDS = {"injured", "lost", "stuck", "medical", "unsafe", "unknown"}

INJECTION_RE = re.compile(
    r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+instructions"
    r"|mark\s+(this|it|all|everything)\s+(as\s+)?(resolved|safe|closed|false alarm)"
    r"|system\s+prompt|you\s+are\s+(an?\s+)?(ai|assistant|llm|language model)"
    r"|disregard\s+(the\s+)?(rules|instructions)|override\s+(the\s+)?(priority|rules)", re.I)
HIDDEN_RE = re.compile("[​-‏‪-‮⁠-⁤﻿]")


def now() -> float:
    return time.time()


def scan_injection(text: str | None) -> list[str]:
    if not text:
        return []
    hits = []
    if INJECTION_RE.search(text):
        hits.append("instruction_text")
    if HIDDEN_RE.search(text):
        hits.append("hidden_characters")
    return hits


# ------------------------------------------------------------------------------------------ zones

def zone_public(s: Session, z: Zone) -> dict:
    advs = s.exec(select(ZoneAdvisory).where(ZoneAdvisory.zone_id == z.id)).all()
    return {"id": z.id, "route_id": z.route_id, "kind": z.kind, "severity": z.severity, "polygon": z.polygon,
            "source": z.source, "note": z.note, "segment_name": z.segment_name, "simulated": z.simulated,
            "active": z.active, "created_at": z.created_at, "expires_at": z.expires_at,
            "advisories": {a.lang: {"title": a.title, "body": a.body, "action": a.action, "source": a.source}
                           for a in advs}}


def active_zones(s: Session, route_id: str) -> list[Zone]:
    t = now()
    return [z for z in s.exec(select(Zone).where(Zone.route_id == route_id, Zone.active == True)).all()  # noqa: E712
            if not z.expires_at or z.expires_at > t]


def publish_zone(s: Session, z: Zone, actor: str, *, ai: bool = True) -> dict:
    if not z.segment_name:
        lat, lon = centroid(z.polygon)
        seg, _ = segment_for(z.route_id, lat, lon)
        z.segment_name = seg["name"] if seg else ""
    s.add(z)
    s.commit()
    have = {a.lang for a in s.exec(select(ZoneAdvisory).where(ZoneAdvisory.zone_id == z.id)).all()}
    for lang in settings.advisory_langs:
        if lang not in have:
            s.add(ZoneAdvisory(zone_id=z.id, lang=lang, source="template", **zone_text(lang, z.kind, z.segment_name)))
    s.commit()
    eventlog.append("zone.published", "zone", z.id, {"kind": z.kind, "severity": z.severity, "route_id": z.route_id,
                                                      "source": z.source, "by": actor})
    data = zone_public(s, z)
    events.publish("zone.published", {"zone": data}, events.ALL, route_id=z.route_id)
    if ai:
        spawn(features.build_advisories(z.id, scanner=lambda t: bool(scan_injection(t))))
    return data


def remove_zone(s: Session, z: Zone, actor: str) -> None:
    z.active = False
    s.add(z)
    s.commit()
    eventlog.append("zone.removed", "zone", z.id, {"by": actor})
    events.publish("zone.removed", {"zone_id": z.id, "kind": z.kind}, events.ALL, route_id=z.route_id)


# ------------------------------------------------------------------------------------------ trips

def new_label(s: Session) -> str:
    while True:
        label = f"T{secrets.randbelow(9000) + 1000}"
        if not s.exec(select(Trip).where(Trip.label == label)).first():
            return label


def trip_public(t: Trip) -> dict:
    return {"id": t.id, "label": t.label, "name": t.name, "language": t.language, "route_id": t.route_id,
            "group_size": t.group_size, "profile_bucket": t.profile_bucket, "start_at": t.start_at, "end_at": t.end_at,
            "status": t.status, "sharing": t.sharing, "last_ping_at": t.last_ping_at, "kind": t.kind}


def create_trip(s: Session, body: dict, kind: str = "tourist") -> tuple[Trip, str]:
    t0 = now()
    trip = Trip(id=uuid.uuid4().hex[:12], label=new_label(s), name=(body.get("name") or "Traveller").strip()[:60],
                phone=(body.get("phone") or "").strip()[:20],
                emergency_contact_name=(body.get("emergency_contact_name") or "").strip()[:60],
                emergency_contact_phone=(body.get("emergency_contact_phone") or "").strip()[:20],
                language=body.get("language") if body.get("language") in ("en", "hi", "as", "ne", "bn", "ta") else "en",
                route_id=body["route_id"], group_size=max(1, min(int(body.get("group_size") or 1), 50)),
                profile_bucket=body.get("profile_bucket") if body.get("profile_bucket") in
                ("standard", "senior", "with_children", "medical_note") else "standard",
                start_at=body.get("start_at"), end_at=body.get("end_at"),
                family_token=secrets.token_urlsafe(16), tourist_token=secrets.token_urlsafe(24),
                consent_version=body.get("consent_version") or "v1", consent_at=t0, kind=kind)
    valid_to = (trip.end_at or t0 + 2 * 86400) + 12 * 3600
    payload, qr = issue_pass(trip.label, trip.route_id, trip.start_at or t0, valid_to)
    s.add(trip)
    s.add(Pass(id=payload["pass_id"], trip_id=trip.id, payload=payload, qr=qr, valid_from=payload["valid_from"],
               valid_to=payload["valid_to"]))
    s.commit()
    eventlog.append("pass.issued", "trip", trip.id, {"pass_id": payload["pass_id"], "valid_to": payload["valid_to"]})
    return trip, qr


def start_trip(s: Session, trip: Trip) -> None:
    trip.status, trip.sharing = "active", True
    trip.start_at = trip.start_at or now()
    s.add(trip)
    s.commit()
    eventlog.append("trip.started", "trip", trip.id, {"route_id": trip.route_id})
    events.publish("trip.started", {"trip_label": trip.label, "route_id": trip.route_id, "kind": trip.kind},
                   events.OPS, route_id=trip.route_id)


# ------------------------------------------------------------------------------------------ pings

_last_pos_pub: dict[str, float] = {}
_inside: dict[str, set[str]] = {}


def position_event(trip: Trip, flags: list[str] | None = None, lat=None, lon=None) -> dict:
    return {"trip_label": trip.label, "name": trip.name if trip.kind != "tourist" else trip.name.split(" ")[0],
            "lat": lat if lat is not None else trip.last_lat, "lon": lon if lon is not None else trip.last_lon,
            "accuracy_m": trip.last_accuracy_m, "status": trip.status, "flags": flags or [], "kind": trip.kind,
            "route_id": trip.route_id, "last_ping_at": trip.last_ping_at}


def ingest_pings(s: Session, trip: Trip, pings: list[dict]) -> dict:
    accepted, flagged = 0, []
    zones = active_zones(s, trip.route_id)
    last = (trip.last_lat, trip.last_lon, trip.last_ping_at)
    for p in sorted(pings, key=lambda x: x.get("ts_device") or 0)[:200]:
        lat, lon = float(p["lat"]), float(p["lon"])
        ts = float(p.get("ts_device") or now())
        src = p.get("source") if p.get("source") in ("gps", "checkpoint", "sim") else "gps"
        flags = []
        if last[0] is not None and last[2] and src != "checkpoint":
            dt = max(ts - last[2], 1.0)
            d = haversine_m(last[0], last[1], lat, lon)
            if (d > 200 and d / dt * 3.6 > settings.max_trek_speed_kmh) or (d > 5000 and dt < 120):
                flags.append("impossible_travel")
        s.add(Ping(trip_id=trip.id, lat=lat, lon=lon, accuracy_m=float(p.get("accuracy_m") or 20), ts_device=ts,
                   source=src, flags=flags))
        if flags:
            flagged.append({"lat": lat, "lon": lon, "ts_device": ts, "flags": flags})
            events.publish("trip.position", position_event(trip, flags, lat, lon), events.OPS, route_id=trip.route_id)
            continue
        accepted += 1
        last = (lat, lon, ts)
        trip.last_lat, trip.last_lon, trip.last_accuracy_m = lat, lon, float(p.get("accuracy_m") or 20)
        seg, _ = segment_for(trip.route_id, lat, lon)
        trip.last_segment = seg["name"] if seg else ""
        inside_now = {z.id for z in zones if point_in_polygon(lat, lon, z.polygon)}
        for zid in inside_now - _inside.get(trip.id, set()):
            z = next(z for z in zones if z.id == zid)
            events.publish("zone.entered", {"trip_label": trip.label, "zone_id": zid, "kind": z.kind},
                           events.OPS, route_id=trip.route_id)
        _inside[trip.id] = inside_now
    if accepted:
        trip.last_ping_at = now()
        if trip.status in ("quiet", "quiet_red", "planned"):
            trip.status = "active"
    s.add(trip)
    s.commit()
    if accepted and now() - _last_pos_pub.get(trip.id, 0) >= 2:
        _last_pos_pub[trip.id] = now()
        events.publish("trip.position", position_event(trip), events.OPS, route_id=trip.route_id)
    return {"accepted": accepted, "flagged": flagged}


# ------------------------------------------------------------------------------------------ SOS + incidents

def rules_priority(rows: list[SosEvent], trips: dict[str, Trip]) -> str:
    if any(r.kind in ("medical", "injured") or r.people_bucket == "6+" for r in rows):
        return "P1"
    if any(r.kind in ("stuck", "unsafe", "unknown") for r in rows):
        return "P2"
    for r in rows:  # lost: P3 only if the trip had contact within 30 min of the SOS
        t = trips.get(r.trip_id)
        if not (t and t.last_ping_at and r.created_at_device - t.last_ping_at <= 1800):
            return "P2"
    return "P3"


def recompute_incident(s: Session, inc: Incident) -> None:
    rows = s.exec(select(SosEvent).where(SosEvent.incident_id == inc.id).order_by(SosEvent.id)).all()
    live = [r for r in rows if r.cancelled_at is None]
    if not live:
        inc.status = "cancelled"
        s.add(inc)
        s.commit()
        return
    latest: dict[str, SosEvent] = {}
    for r in live:
        latest[r.trip_id] = r
    lr = list(latest.values())
    trips = {t.id: t for t in s.exec(select(Trip).where(Trip.id.in_(list(latest)))).all()}
    inc.people_breakdown = dict(Counter(r.people_bucket for r in lr))
    inc.people_total = sum(PEOPLE_MID.get(r.people_bucket, 1) for r in lr)
    inc.count_by_kind = dict(Counter(r.kind for r in lr))
    inc.injured_total = sum(1 for r in lr if r.kind in ("injured", "medical"))
    inc.center_lat = sum(r.lat for r in lr) / len(lr)
    inc.center_lon = sum(r.lon for r in lr) / len(lr)
    inc.radius_m = max(haversine_m(inc.center_lat, inc.center_lon, r.lat, r.lon) for r in lr)
    seg, _ = segment_for(inc.route_id, inc.center_lat, inc.center_lon)
    inc.segment_name = seg["name"] if seg else ""
    inc.member_count, inc.trip_count = len(live), len(lr)
    inc.type = "cluster" if len(lr) >= 2 else "single"
    inc.priority = rules_priority(lr, trips)
    keep = {f for f in (inc.flags or []) if f in ("prune_injection_signal",) or f.startswith("merged")}
    inc.flags = sorted({f for r in live for f in (r.flags or [])} | keep)
    inc.first_sos_at = min(r.received_at_server for r in live)
    inc.last_sos_at = max(r.received_at_server for r in live)
    if inc.report is None:
        r = lr[-1]
        inc.report = report_template("en", r.kind, r.people_bucket, inc.segment_name, None, None, r.note_text)
        inc.report_source = "template"
    if inc.type == "cluster" and (inc.cluster_summary is None or inc.summary_source == "template"):
        inc.cluster_summary = cluster_template("en", inc.people_total, inc.injured_total, inc.segment_name)
        inc.summary_source = "template"
    s.add(inc)
    s.commit()


def attach_to_incident(s: Session, sos: SosEvent, trip: Trip) -> tuple[Incident, bool]:
    cutoff = now() - 1800
    open_incs = s.exec(select(Incident).where(Incident.route_id == trip.route_id, Incident.status.in_(OPEN),
                                              Incident.last_sos_at >= cutoff)).all()
    best, best_d = None, None
    for inc in open_incs:
        d = haversine_m(inc.center_lat, inc.center_lon, sos.lat, sos.lon)
        if d <= settings.cluster_eps_m and (best_d is None or d < best_d):
            best, best_d = inc, d
    is_new = best is None
    if is_new:
        best = Incident(route_id=trip.route_id, center_lat=sos.lat, center_lon=sos.lon,
                        first_sos_at=sos.received_at_server, last_sos_at=sos.received_at_server)
        s.add(best)
        s.commit()
        s.refresh(best)
        eventlog.append("incident.created", "incident", best.id, {"route_id": trip.route_id})
    sos.incident_id = best.id
    s.add(sos)
    s.commit()
    for other in open_incs:
        if other.id != best.id and haversine_m(best.center_lat, best.center_lon, other.center_lat,
                                               other.center_lon) <= settings.cluster_eps_m:
            for r in s.exec(select(SosEvent).where(SosEvent.incident_id == other.id)).all():
                r.incident_id = best.id
                s.add(r)
            other.status, other.flags = "cancelled", sorted(set(other.flags or []) | {f"merged_into_{best.id}"})
            s.add(other)
            s.commit()
            eventlog.append("incident.merged", "incident", other.id, {"into": best.id})
            events.publish("incident.updated", incident_summary(s, other), events.OPS, route_id=other.route_id)
    recompute_incident(s, best)
    return best, is_new


def receive_sos(s: Session, trip: Trip, body: dict, channel: str = "data") -> dict:
    existing = s.exec(select(SosEvent).where(SosEvent.client_id == body["client_id"])).first() or \
        s.exec(select(SosEvent).where(SosEvent.trip_id == trip.id,  # the same SOS that already arrived by SMS
                                      SosEvent.client_id == f"sms-{str(body['client_id'])[:8]}")).first()
    if existing:
        if "duplicate_seen" not in (existing.flags or []):
            existing.flags = (existing.flags or []) + ["duplicate_seen"]
            s.add(existing)
            s.commit()
        return {"received_at": existing.received_at_server, "incident_id": existing.incident_id, "duplicate": True,
                "flags": existing.flags}
    t = now()
    flags = []
    recent = s.exec(select(SosEvent).where(SosEvent.trip_id == trip.id, SosEvent.received_at_server >= t - 600)).all()
    if len(recent) >= 5:
        flags.append("flood")
    note = (body.get("note") or "").strip()[:280] or None
    if scan_injection(note):
        flags.append("suspicious_text")
    if trip.kind == "breakit":
        flags.append("breakit")
    kind = body.get("kind") if body.get("kind") in SOS_KINDS else "unknown"
    bucket = body.get("people_bucket") if body.get("people_bucket") in PEOPLE_MID else "1"
    created = float(body.get("created_at_device") or t)
    sos = SosEvent(client_id=body["client_id"], trip_id=trip.id, kind=kind, people_bucket=bucket, note_text=note,
                   lat=float(body["lat"]), lon=float(body["lon"]), accuracy_m=float(body.get("accuracy_m") or 20),
                   created_at_device=created, received_at_server=t, channel=channel, flags=flags)
    s.add(sos)
    s.commit()
    s.refresh(sos)
    eventlog.append("sos.created_device", "sos", sos.client_id, {"trip_label": trip.label, "kind": kind,
                                                                  "people": bucket, "created_at_device": created})
    eventlog.append("sos.received", "sos", sos.client_id, {"channel": channel, "delay_s": round(t - created, 1)})
    inc, is_new = attach_to_incident(s, sos, trip)
    trip.status = "sos"
    s.add(trip)
    s.commit()
    events.publish("sos.received", {"incident_id": inc.id, "trip_label": trip.label, "kind": kind,
                                    "people_bucket": bucket, "channel": channel, "delay_s": round(t - created, 1),
                                    "flags": flags, "lat": sos.lat, "lon": sos.lon, "trip_kind": trip.kind},
                   events.OPS, route_id=trip.route_id)
    events.publish("incident.updated", incident_summary(s, inc), events.OPS, route_id=trip.route_id)
    key = "public" if "breakit" in (inc.flags or []) else "ops"
    if "flood" not in flags:  # floods never fan out AI calls
        if inc.type == "single":
            spawn(features.build_report(inc.id, key=key))
        else:
            spawn(features.build_cluster_summary(inc.id, key=key))
    return {"received_at": t, "incident_id": inc.id, "duplicate": False, "flags": flags}


def cancel_sos(s: Session, sos: SosEvent) -> None:
    sos.cancelled_at = now()
    s.add(sos)
    s.commit()
    eventlog.append("sos.cancelled", "sos", sos.client_id, {})
    if sos.incident_id:
        inc = s.get(Incident, sos.incident_id)
        recompute_incident(s, inc)
        events.publish("incident.updated", incident_summary(s, inc), events.OPS, route_id=inc.route_id)


def incident_trip_ids(s: Session, inc: Incident) -> list[str]:
    return sorted({r.trip_id for r in s.exec(select(SosEvent).where(SosEvent.incident_id == inc.id)).all()})


def incident_summary(s: Session, inc: Incident) -> dict:
    report = inc.report or {}
    summary = inc.cluster_summary or {}
    return {"id": inc.id, "route_id": inc.route_id, "type": inc.type, "status": inc.status, "priority": inc.priority,
            "center_lat": inc.center_lat, "center_lon": inc.center_lon, "radius_m": inc.radius_m,
            "segment_name": inc.segment_name, "member_count": inc.member_count, "trip_count": inc.trip_count,
            "people_total": inc.people_total, "people_breakdown": inc.people_breakdown,
            "count_by_kind": inc.count_by_kind, "injured_total": inc.injured_total,
            "first_sos_at": inc.first_sos_at, "last_sos_at": inc.last_sos_at, "flags": inc.flags,
            "headline": summary.get("summary") if inc.type == "cluster" else report.get("headline"),
            "headline_source": inc.summary_source if inc.type == "cluster" else inc.report_source,
            "team": inc.team, "accepted_at": inc.accepted_at, "en_route_at": inc.en_route_at,
            "resolved_at": inc.resolved_at}


def _call_brief(c: LlmCall) -> dict:
    return {"id": c.id, "feature": c.feature, "tier": c.tier, "requested_model": c.requested_model,
            "routed_model": c.routed_model,
            "route_applied": c.route_applied, "cache_hit": c.cache_hit, "cost_with_prune_usd": c.cost_with_prune_usd,
            "cost_without_prune_usd": c.cost_without_prune_usd, "latency_ms": c.latency_ms, "status": c.status,
            "error_code": c.error_code, "shield_code": c.shield_code, "escalated": c.escalated,
            "receipt_signature": c.receipt_signature, "receipt_signing_key_id": c.receipt_signing_key_id,
            "created_at": c.created_at}


def incident_detail(s: Session, inc: Incident) -> dict:
    rows = s.exec(select(SosEvent).where(SosEvent.incident_id == inc.id).order_by(SosEvent.id)).all()
    trips = {t.id: t for t in s.exec(select(Trip).where(Trip.id.in_([r.trip_id for r in rows]))).all()}
    ids = list(inc.report_llm_call_ids or []) + list(inc.summary_llm_call_ids or [])
    calls = s.exec(select(LlmCall).where(LlmCall.id.in_(ids))).all() if ids else []
    return {**incident_summary(s, inc),
            "sos": [{"client_id": r.client_id, "trip_label": trips[r.trip_id].label if r.trip_id in trips else "?",
                     "name": trips[r.trip_id].name if r.trip_id in trips else "", "kind": r.kind,
                     "people_bucket": r.people_bucket, "note_text": r.note_text, "lat": r.lat, "lon": r.lon,
                     "accuracy_m": r.accuracy_m, "channel": r.channel, "flags": r.flags,
                     "created_at_device": r.created_at_device, "received_at_server": r.received_at_server,
                     "delay_s": round(r.received_at_server - r.created_at_device, 1), "cancelled_at": r.cancelled_at}
                    for r in rows],
            "report": inc.report, "report_source": inc.report_source, "cluster_summary": inc.cluster_summary,
            "summary_source": inc.summary_source, "brief": inc.brief, "brief_source": inc.brief_source,
            "llm_calls": [_call_brief(c) for c in calls]}


STATUS_ORDER = ["new", "accepted", "en_route", "resolved"]


def set_incident_status(s: Session, inc: Incident, status: str, actor: str, team: str | None = None) -> dict:
    if status not in STATUS_ORDER or STATUS_ORDER.index(status) <= STATUS_ORDER.index(inc.status if inc.status in STATUS_ORDER else "new"):
        raise ValueError(f"cannot move from {inc.status} to {status}")
    t = now()
    inc.status = status
    inc.team = team or inc.team or "Rescue team (simulated)"
    if status == "accepted":
        inc.accepted_at, inc.accepted_by = t, actor
    elif status == "en_route":
        inc.en_route_at = t
    elif status == "resolved":
        inc.resolved_at = t
    s.add(inc)
    s.commit()
    eventlog.append(f"incident.{status}", "incident", inc.id, {"by": actor, "team": inc.team})
    trip_ids = incident_trip_ids(s, inc)
    if status == "resolved":
        for tr in s.exec(select(Trip).where(Trip.id.in_(trip_ids))).all():
            tr.status = "safe"
            s.add(tr)
        s.commit()
    msg = (inc.cluster_summary or {}).get("message_to_group") if inc.type == "cluster" else None
    events.publish("incident.status", {"incident_id": inc.id, "status": status, "team": inc.team, "at": t,
                                       "message": msg},
                   events.OPS | {f"trip:{tid}" for tid in trip_ids}, route_id=inc.route_id)
    return incident_summary(s, inc)


def incident_timeline(s: Session, inc: Incident) -> list:
    rows = eventlog.entity_entries(s, "incident", inc.id)
    for r in s.exec(select(SosEvent).where(SosEvent.incident_id == inc.id)).all():
        rows += eventlog.entity_entries(s, "sos", r.client_id)
    return sorted(rows, key=lambda r: r.seq)


def trip_sos_status(s: Session, trip: Trip) -> list[dict]:
    out = []
    for r in s.exec(select(SosEvent).where(SosEvent.trip_id == trip.id).order_by(SosEvent.id.desc()).limit(5)).all():
        inc = s.get(Incident, r.incident_id) if r.incident_id else None
        out.append({"client_id": r.client_id, "received_at": r.received_at_server, "incident_id": r.incident_id,
                    "incident_status": inc.status if inc else None, "accepted_at": inc.accepted_at if inc else None,
                    "team": inc.team if inc else None, "cancelled_at": r.cancelled_at})
    return out


# ------------------------------------------------------------------------------------------ safety checks

def send_check(s: Session, route_id: str, actor: str, zone_id: str | None = None, polygon: dict | None = None,
               message_key: str = "check_landslide") -> SafetyCheck:
    if zone_id:
        z = s.get(Zone, zone_id)
        polygon, route_id = z.polygon, z.route_id
    cutoff = now() - 7200
    trips = s.exec(select(Trip).where(Trip.route_id == route_id, Trip.kind.in_(["tourist", "breakit"]),
                                      Trip.status != "ended")).all()
    targets = []
    for t in trips:
        if polygon is None:
            hit = t.sharing
        elif t.last_lat is not None and point_in_polygon(t.last_lat, t.last_lon, polygon):
            hit = True
        else:
            hit = any(point_in_polygon(p.lat, p.lon, polygon) for p in
                      s.exec(select(Ping).where(Ping.trip_id == t.id, Ping.ts_server >= cutoff)).all())
        if hit:
            targets.append(t)
    chk = SafetyCheck(route_id=route_id, zone_id=zone_id, polygon=polygon, message_key=message_key,
                      targets=[t.id for t in targets], sent_by=actor)
    s.add(chk)
    s.commit()
    s.refresh(chk)
    eventlog.append("check.sent", "check", chk.id, {"targets": len(targets), "by": actor, "zone_id": zone_id})
    for t in targets:
        msgs = templates(t.language)["check"]
        events.publish("check.prompt", {"check_id": chk.id, "message": msgs.get(message_key, msgs["check_generic"]),
                                        "message_key": message_key}, {f"trip:{t.id}"}, trip_id=t.id)
    publish_tally(s, chk)
    return chk


def tally(s: Session, chk: SafetyCheck) -> dict:
    latest = {}
    for r in s.exec(select(CheckResponse).where(CheckResponse.check_id == chk.id).order_by(CheckResponse.id)).all():
        latest[r.trip_id] = r.answer
    targets = chk.targets or []
    trips = {t.id: t for t in s.exec(select(Trip).where(Trip.id.in_(targets))).all()} if targets else {}
    overdue = now() - chk.sent_at > settings.check_no_answer_min * 60
    return {"check_id": chk.id, "asked": len(targets), "safe": sum(1 for a in latest.values() if a == "safe"),
            "need_help": sum(1 for a in latest.values() if a == "need_help"),
            "no_answer": len([t for t in targets if t not in latest]),
            "no_answer_trip_labels": [trips[t].label for t in targets if t not in latest and t in trips],
            "overdue": overdue, "sent_at": chk.sent_at, "zone_id": chk.zone_id}


def publish_tally(s: Session, chk: SafetyCheck) -> None:
    events.publish("check.tally", tally(s, chk), events.OPS, route_id=chk.route_id)


def answer_check(s: Session, chk: SafetyCheck, trip: Trip, answer: str) -> None:
    s.add(CheckResponse(check_id=chk.id, trip_id=trip.id, answer=answer))
    s.commit()
    eventlog.append("check.answered", "check", chk.id, {"trip_label": trip.label, "answer": answer})
    publish_tally(s, chk)


def pending_checks(s: Session, trip: Trip) -> list[dict]:
    out = []
    for chk in s.exec(select(SafetyCheck).where(SafetyCheck.sent_at >= now() - 7200)).all():
        if trip.id in (chk.targets or []) and not s.exec(select(CheckResponse).where(
                CheckResponse.check_id == chk.id, CheckResponse.trip_id == trip.id)).first():
            msgs = templates(trip.language)["check"]
            out.append({"check_id": chk.id, "message": msgs.get(chk.message_key, msgs["check_generic"])})
    return out


# ------------------------------------------------------------------------------------------ family + stats

def family_status(s: Session, trip: Trip) -> dict:
    status, ack = "on_trip", None
    if trip.status == "planned":
        status = "not_started"
    elif trip.status == "ended":
        status = "trip_ended"
    elif trip.status == "safe":
        status = "safe"
    elif trip.status == "sos":
        status = "help_requested"
        for r in trip_sos_status(s, trip):
            if r["incident_status"] in ("accepted", "en_route"):
                status, ack = "help_acknowledged", r["accepted_at"]
                break
            if r["incident_status"] == "resolved":
                status = "safe"
                break
    return {"first_name": trip.name.split(" ")[0], "route_name": route_facts(trip.route_id)["route_name"],
            "status": status, "last_check_in_ago_s": round(now() - trip.last_ping_at) if trip.last_ping_at else None,
            "acknowledged_at": ack}


def _feature_of(job_key: str) -> str:
    for p, f in (("pack_", "pack"), ("adv_", "advisory"), ("inc_", "report"), ("clu_", "cluster"), ("cop_", "copilot"),
                 ("sms_", "sms_parse")):
        if job_key.startswith(p):
            return f
    return "other"


def ai_stats(s: Session, route_id: str | None = None) -> dict:
    q = select(LlmCall).where(LlmCall.benchmark_run_id == None)  # noqa: E711
    if route_id:
        q = q.where(LlmCall.route_id == route_id)
    calls = s.exec(q).all()
    ok = [c for c in calls if c.status in ("ok", "retried")]
    known = [c for c in ok if c.cost_with_prune_usd is not None]
    by = {}
    for c in ok:
        f = _feature_of(c.job_key)
        b = by.setdefault(f, {"calls": 0, "cost_usd": 0.0, "cost_known": 0, "cache_hits": 0, "routed": 0})
        b["calls"] += 1
        b["cache_hits"] += 1 if c.cache_hit else 0
        b["routed"] += 1 if c.route_applied else 0
        if c.cost_with_prune_usd is not None:
            b["cost_usd"] += c.cost_with_prune_usd
            b["cost_known"] += 1
    jobs = s.exec(select(AiJob).where(AiJob.benchmark_run_id == None)).all()  # noqa: E711
    trips_started = len(s.exec(select(Trip).where(Trip.start_at != None, Trip.kind != "sim")).all())  # noqa: E711
    incidents = len([i for i in s.exec(select(Incident)).all() if not any(str(f).startswith("merged") for f in (i.flags or []))])
    total = sum(c.cost_with_prune_usd for c in known) if known else None
    without = [c.cost_without_prune_usd for c in ok if c.cost_without_prune_usd is not None]
    trip_cost = sum(by.get(f, {}).get("cost_usd", 0) for f in ("pack", "advisory"))
    emerg_cost = sum(by.get(f, {}).get("cost_usd", 0) for f in ("report", "cluster", "copilot", "sms_parse"))
    return {
        "calls": len(calls), "ok_calls": len(ok), "errors": len(calls) - len(ok),
        "cost_usd": total, "cost_inr": total * settings.usd_inr if total is not None else None,
        "cost_known_calls": len(known), "prune_estimate_without_usd": sum(without) if without else None,
        "cache_hits": sum(1 for c in ok if c.cache_hit), "routed": sum(1 for c in ok if c.route_applied),
        "escalations": sum(1 for c in ok if c.escalated),
        "template_fallbacks": sum(1 for j in jobs if j.source == "template"),
        "validator_rejections": sum(j.validator_rejections for j in jobs),
        "trips_started": trips_started, "incidents": incidents,
        "cost_per_trip_usd": (trip_cost / trips_started) if (known and trips_started) else None,
        "cost_per_emergency_usd": (emerg_cost / incidents) if (known and incidents) else None,
        "by_feature": by, "ai_configured": bool(settings.prune_api_key and settings.model_small and settings.model_large),
        "usd_inr": settings.usd_inr,
    }
