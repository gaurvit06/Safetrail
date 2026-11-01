"""Server-Sent Events broadcaster (SPEC Section 8).

Every event is published with a set of audiences:
  "responder", "stage", "tourists" (all tourists), "trip:<trip_id>" (one tourist).
A subscriber receives an event if any of its audiences matches.
"""
import asyncio
import itertools
import json
import time
from collections import deque
from dataclasses import dataclass, field

_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


@dataclass(eq=False)
class Subscriber:
    audiences: set[str]
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=1000))


_subs: set[Subscriber] = set()
_recent: list[dict] = []  # last events for the stage ticker
# Free Cloudflare tunnels hold back event streams, so clients also fetch recent events by number (see since()).
_log: deque = deque(maxlen=3000)
_numbers = itertools.count(1)


def subscribe(audiences: set[str]) -> Subscriber:
    s = Subscriber(audiences)
    _subs.add(s)
    return s


def unsubscribe(s: Subscriber) -> None:
    _subs.discard(s)


def _deliver(evt: dict, audiences: set[str]) -> None:
    for s in list(_subs):
        if s.audiences & audiences:
            try:
                s.queue.put_nowait(evt)
            except asyncio.QueueFull:
                pass  # slow client: drop rather than block safety work


def publish(type_: str, data: dict, audiences: set[str] | list[str], *, route_id: str | None = None,
            trip_id: str | None = None) -> dict:
    evt = {"seq": next(_numbers), "type": type_, "ts": time.time(), "route_id": route_id, "trip_id": trip_id, "data": data}
    aud = set(audiences)
    _log.append((aud, evt))
    if "stage" in aud or "responder" in aud:
        _recent.append(evt)
        del _recent[:-50]
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if _loop is not None and running is not _loop:
        _loop.call_soon_threadsafe(_deliver, evt, aud)
    else:
        _deliver(evt, aud)
    return evt


def since(after: int, audiences: set[str]) -> dict:
    """Events for these audiences after number `after`. With after < 0 it only returns the current number,
    so a client that just connected doesn't replay old events."""
    log = list(_log)
    latest = log[-1][1]["seq"] if log else 0
    if after < 0:
        return {"seq": latest, "events": []}
    return {"seq": latest, "events": [e for aud, e in log if e["seq"] > after and aud & audiences]}


def recent(n: int = 20) -> list[dict]:
    return _recent[-n:]


def encode(evt: dict) -> str:
    return json.dumps(evt, ensure_ascii=False, default=str)


OPS = {"responder", "stage"}
ALL = {"responder", "stage", "tourists"}
