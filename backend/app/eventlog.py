"""Signed, hash-chained event log (SPEC 5.14).

hash = sha256(prev_hash | type | entity_id | payload_hash | ts_server), signature = Ed25519(hash).
Editing any row breaks its hash and every hash after it.
"""
import hashlib
import threading
import time

from sqlmodel import Session, select

from .db import engine
from .models import EventLog
from .security import canonical, log_signer

GENESIS = "0" * 64
_lock = threading.Lock()


def _hash(prev_hash: str, type_: str, entity_id: str, payload_hash: str, ts: float) -> str:
    return hashlib.sha256(f"{prev_hash}|{type_}|{entity_id}|{payload_hash}|{ts:.6f}".encode()).hexdigest()


def append(type_: str, entity_type: str, entity_id, payload: dict) -> EventLog:
    entity_id = str(entity_id)
    with _lock, Session(engine) as s:
        last = s.exec(select(EventLog).order_by(EventLog.seq.desc()).limit(1)).first()
        prev = last.hash if last else GENESIS
        ts = time.time()
        ph = hashlib.sha256(canonical(payload)).hexdigest()
        h = _hash(prev, type_, entity_id, ph, ts)
        signer = log_signer()
        row = EventLog(ts_server=ts, type=type_, entity_type=entity_type, entity_id=entity_id, payload=payload,
                       payload_hash=ph, prev_hash=prev, hash=h, signature=signer.sign(bytes.fromhex(h)).hex(),
                       key_id=signer.key_id)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def verify_rows(rows: list[EventLog]) -> dict:
    """Recompute payload hash, row hash and signature for each row. Rows need not be contiguous;
    each row is checked against its own stored prev_hash, and the full chain is checked separately."""
    signer = log_signer()
    for r in rows:
        ph = hashlib.sha256(canonical(r.payload)).hexdigest()
        if ph != r.payload_hash:
            return {"ok": False, "broken_seq": r.seq, "reason": "payload changed"}
        if _hash(r.prev_hash, r.type, r.entity_id, r.payload_hash, r.ts_server) != r.hash:
            return {"ok": False, "broken_seq": r.seq, "reason": "hash mismatch"}
        if not signer.verify(bytes.fromhex(r.hash), bytes.fromhex(r.signature)):
            return {"ok": False, "broken_seq": r.seq, "reason": "bad signature"}
    return {"ok": True}


def verify_chain(s: Session) -> dict:
    rows = s.exec(select(EventLog).order_by(EventLog.seq)).all()
    prev = GENESIS
    for r in rows:
        if r.prev_hash != prev:
            return {"ok": False, "broken_seq": r.seq, "reason": "chain link broken", "count": len(rows)}
        prev = r.hash
    res = verify_rows(rows)
    res["count"] = len(rows)
    return res


def entity_entries(s: Session, entity_type: str, entity_id) -> list[EventLog]:
    return s.exec(select(EventLog).where(EventLog.entity_type == entity_type, EventLog.entity_id == str(entity_id))
                  .order_by(EventLog.seq)).all()
