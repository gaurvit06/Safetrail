"""Phase 2: Digital Tourist ID linked to the permit a traveller already holds (SPEC 17). SIMULATED.

- A mock registry (seed/mock_registry.json) stands in for the e-Visa, e-ILP and yatra systems, which have no open API.
- The ID number is normalised, looked up and hashed at once. Only the hash and the last 4 characters are stored,
  and the number never reaches the AI, a log or the event chain.
- Upgrading re-signs the trip pass with the permit type, dates and the restricted zones it allows, so phones and
  checkpoints can apply it offline. Upgrades and revocations go into the signed hash chain (SPEC 17.4).
- Aadhaar is optional only: the last 4 digits, self-declared, never a permit.
"""
import datetime as dt
import hashlib
import hmac
import re
import time
from functools import lru_cache

from sqlmodel import Session, select

from . import eventlog, events
from .config import SEED_DIR, settings
from .models import Pass, PassRevocation, PermitRecord, Trip, Zone
from .security import b64u, canonical, pass_signer
from .seeddata import _read

ID_TYPES = {"visa", "evisa", "passport", "eilp", "yatra", "digilocker", "voter", "aadhaar_masked"}
SELF_DECLARED = "Self-declared (Aadhaar last 4 digits only)"
LOOKUPS_PER_HOUR = 10
_lookups: dict[str, list[float]] = {}


@lru_cache
def registry() -> dict:
    return _read(SEED_DIR / "mock_registry.json")


def normalise(number: str) -> str:
    return re.sub(r"[\s\-./]", "", number or "").upper()


def id_hash(id_type: str, number: str) -> str:
    return hmac.new(settings.token_secret.encode(), f"{id_type}:{normalise(number)}".encode(), hashlib.sha256).hexdigest()


def _day(s: str, end: bool = False) -> float:
    d = dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))
    return (d + dt.timedelta(days=1, seconds=-1)).timestamp() if end else d.timestamp()


def _rate_ok(trip_id: str) -> bool:
    now = time.time()
    xs = [t for t in _lookups.get(trip_id, []) if now - t < 3600]
    _lookups[trip_id] = xs + [now]
    return len(xs) < LOOKUPS_PER_HOUR


def public(rec: PermitRecord, s: Session, trip: Trip) -> dict:
    names = {z.id: (z.segment_name or z.id) for z in s.exec(select(Zone).where(Zone.id.in_(rec.permitted_zone_ids or []))).all()}
    now = time.time()
    return {"record_id": rec.id, "id_type": rec.id_type, "id_last4": rec.id_last4, "permit_type": rec.permit_type,
            "issuing_state": rec.issuing_state, "valid_from": rec.valid_from, "valid_to": rec.valid_to,
            "permitted_zone_ids": rec.permitted_zone_ids or [], "permitted_zones": [names.get(z, z) for z in rec.permitted_zone_ids or []],
            "covers_route": trip.route_id in (rec.routes or []), "expired": now > rec.valid_to,
            "verified_via": rec.verified_via, "simulated": True}


def lookup(s: Session, trip: Trip, id_type: str, number: str) -> dict:
    if id_type not in ID_TYPES:
        return {"found": False, "reason": "unknown_id_type"}
    if not _rate_ok(trip.id):
        return {"found": False, "reason": "too_many_lookups"}
    norm = normalise(number)
    if len(norm) < 4:
        return {"found": False, "reason": "too_short"}
    h, last4 = id_hash(id_type, norm), norm[-4:]
    if id_type == "aadhaar_masked":  # never looked up anywhere; only the last 4 digits are kept, by the user's choice
        rec = PermitRecord(trip_id=trip.id, id_type=id_type, id_last4=last4, id_hash=h, permit_type=SELF_DECLARED,
                           issuing_state="", valid_from=time.time(), valid_to=trip.end_at or time.time() + 2 * 86400,
                           permitted_zone_ids=[], routes=[trip.route_id], verified_via="manual")
    else:
        hit = next((r for r in registry()["records"] if r["id_type"] == id_type and normalise(r["number"]) == norm), None)
        if not hit:
            return {"found": False, "reason": "not_found"}
        rec = PermitRecord(trip_id=trip.id, id_type=id_type, id_last4=last4, id_hash=h, permit_type=hit["permit_type"],
                           issuing_state=hit["issuing_state"], valid_from=_day(hit["valid_from"]),
                           valid_to=_day(hit["valid_to"], end=True), permitted_zone_ids=hit["permitted_zone_ids"],
                           routes=hit["routes"], verified_via="mock_registry")
    s.add(rec)
    s.commit()
    s.refresh(rec)
    return {"found": True, "permit": public(rec, s, trip)}


def upgrade(s: Session, trip: Trip, ps: Pass, record_id: int) -> dict:
    rec = s.get(PermitRecord, record_id)
    if not rec or rec.trip_id != trip.id:
        return {"ok": False, "reason": "unknown_record"}
    if time.time() > rec.valid_to:
        return {"ok": False, "reason": "permit_expired"}
    if s.exec(select(PassRevocation).where(PassRevocation.pass_id == ps.id)).first():
        return {"ok": False, "reason": "pass_revoked"}
    level = "self_declared" if rec.id_type == "aadhaar_masked" else "verified"
    payload = {**ps.payload, "valid_to": int(min(ps.valid_to, rec.valid_to)), "kyc_level": level, "id_type": rec.id_type,
               "id_last4": rec.id_last4, "permit_type": rec.permit_type, "permit_valid_to": int(rec.valid_to),
               "permitted_zone_ids": sorted(rec.permitted_zone_ids or [])}
    body = canonical(payload)
    ps.payload, ps.qr = payload, b64u(body) + "." + b64u(pass_signer().sign(body))
    ps.valid_to, ps.kyc_level = payload["valid_to"], level
    s.add(ps)
    s.commit()
    eventlog.append("pass.upgraded", "pass", ps.id, {"id_type": rec.id_type, "permit_type": rec.permit_type,
                                                     "kyc_level": level, "valid_to": payload["valid_to"]})
    return {"ok": True, "pass": payload, "pass_qr": ps.qr, "permit": public(rec, s, trip)}


def revoke(s: Session, pass_id: str, reason: str, actor: str) -> dict:
    ps = s.get(Pass, pass_id)
    if not ps:
        return {"ok": False, "reason": "unknown_pass"}
    existing = s.exec(select(PassRevocation).where(PassRevocation.pass_id == pass_id)).first()
    if existing:
        return {"ok": True, "revoked_at": existing.revoked_at, "already": True}
    r = PassRevocation(pass_id=pass_id, reason=(reason or "")[:120], revoked_by=actor)
    s.add(r)
    s.commit()
    eventlog.append("pass.revoked", "pass", pass_id, {"reason": r.reason, "by": actor})
    events.publish("pass.revoked", {"pass_id": pass_id, "reason": r.reason, "revoked_at": r.revoked_at},
                   events.OPS | {f"trip:{ps.trip_id}"})
    return {"ok": True, "revoked_at": r.revoked_at}


def revocations(s: Session, since: float = 0) -> list[dict]:
    rows = s.exec(select(PassRevocation).where(PassRevocation.revoked_at > since).order_by(PassRevocation.revoked_at)).all()
    return [{"pass_id": r.pass_id, "reason": r.reason, "revoked_at": r.revoked_at} for r in rows]


def check(s: Session, result: dict, zone_id: str | None = None) -> dict:
    """Add the server-side checks to an offline-style signature check: revoked, and not permitted for a zone."""
    p = result.get("payload") or {}
    if p.get("pass_id") and s.exec(select(PassRevocation).where(PassRevocation.pass_id == p["pass_id"])).first():
        return {**result, "valid": False, "reason": "revoked"}
    if result.get("valid") and zone_id:
        z = s.get(Zone, zone_id)
        if z and z.kind == "restricted" and zone_id not in (p.get("permitted_zone_ids") or []):
            return {**result, "zone_ok": False, "zone_name": z.segment_name or z.id}
        return {**result, "zone_ok": True}
    return result


def explainer_input(trip: Trip, rec: PermitRecord) -> dict:
    text = registry()["permit_text"].get(rec.permit_type, "")
    return {"permit_type": rec.permit_type, "state": rec.issuing_state or "India", "official_text": text,
            "language": trip.language}
