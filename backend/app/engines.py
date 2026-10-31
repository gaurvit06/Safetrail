"""Background engines: crowd density (SPEC 5.5), quiet tourists (5.11), zone expiry, retention (5.17).
Plain code only. Each tick is wrapped so one bad row never stops the loop."""
import asyncio
import logging
import math
import time
import uuid
from collections import Counter, defaultdict, deque

from sqlmodel import Session, select

from . import events
from .config import settings
from .core import active_zones, publish_zone, remove_zone, zone_public
from .db import engine
from .geo import angle_diff, bearing_deg, centroid, haversine_m, point_in_polygon, rect_polygon
from .models import Ping, Route, SosEvent, Trip, Zone
from .seeddata import route_facts, templates

log = logging.getLogger("safetrail.engines")

_hist: dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
_clear_streak: dict[str, int] = {}
_warned: dict[tuple[str, str], float] = {}
latest_heat: dict[str, dict] = {}


def _components(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    comps, seen = [], set()
    for c in cells:
        if c in seen:
            continue
        stack, comp = [c], set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            comp.add(cur)
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    n = (cur[0] + di, cur[1] + dj)
                    if n in cells and n not in seen:
                        stack.append(n)
        comps.append(comp)
    return comps


def _heading(s: Session, trip_id: str) -> float | None:
    pts = s.exec(select(Ping).where(Ping.trip_id == trip_id).order_by(Ping.id.desc()).limit(6)).all()
    pts = [p for p in pts if not p.flags]
    if len(pts) < 2:
        return None
    a, b = pts[min(len(pts) - 1, 3)], pts[0]
    if haversine_m(a.lat, a.lon, b.lat, b.lon) < 3:
        return None
    return bearing_deg(a.lat, a.lon, b.lat, b.lon)


def crowd_tick() -> None:
    t = time.time()
    with Session(engine) as s:
        for sim in s.exec(select(Trip).where(Trip.kind == "sim", Trip.status == "active")).all():
            if sim.end_at and sim.end_at > t:
                sim.last_ping_at = t  # keep demo crowds alive until their end time
                s.add(sim)
        s.commit()
        trips = [tr for tr in s.exec(select(Trip).where(Trip.sharing == True, Trip.status != "ended")).all()  # noqa: E712
                 if tr.last_ping_at and tr.last_ping_at >= t - 120 and tr.last_lat is not None]
        by_route = defaultdict(list)
        for tr in trips:
            by_route[tr.route_id].append(tr)
        auto = s.exec(select(Zone).where(Zone.source == "auto_crowd", Zone.active == True)).all()  # noqa: E712
        for route_id in set(by_route) | {z.route_id for z in auto}:
            route = s.get(Route, route_id)
            if not route:
                continue
            facts = route_facts(route_id)
            cap = max(1, facts.get("segment_capacity", 40))
            lat0 = route.center[1]
            dlat = settings.crowd_cell_m / 111_320
            dlon = settings.crowd_cell_m / (111_320 * math.cos(math.radians(lat0)))
            counts: Counter = Counter()
            for tr in by_route.get(route_id, []):
                counts[(math.floor(tr.last_lat / dlat), math.floor(tr.last_lon / dlon))] += 1
            cells, red = [], set()
            for key, n in counts.items():
                hk = f"{route_id}:{key[0]}:{key[1]}"
                hist = _hist[hk]
                prev = next((c for ts, c in hist if t - ts >= 50), None)
                hist.append((t, n))
                density = n / cap
                rising = prev is not None and prev > 0 and (n - prev) / prev >= 0.3
                level = "red" if density >= 0.9 or (density >= 0.75 and rising) else ("amber" if density >= 0.6 else "green")
                cells.append({"id": hk, "count": n, "density": round(density, 2), "level": level,
                              "trend": "rising" if rising else "steady",
                              "polygon": rect_polygon(key[0] * dlat, key[1] * dlon, (key[0] + 1) * dlat, (key[1] + 1) * dlon)})
                if level == "red":
                    red.add(key)
            existing = [z for z in auto if z.route_id == route_id]
            matched = set()
            blat, blon = 10 / 111_320, 10 / (111_320 * math.cos(math.radians(lat0)))
            for comp in _components(red):
                i0, i1 = min(c[0] for c in comp), max(c[0] for c in comp)
                j0, j1 = min(c[1] for c in comp), max(c[1] for c in comp)
                poly = rect_polygon(i0 * dlat - blat, j0 * dlon - blon, (i1 + 1) * dlat + blat, (j1 + 1) * dlon + blon)
                people = sum(counts[c] for c in comp)
                clat, clon = centroid(poly)
                z = next((z for z in existing if point_in_polygon(clat, clon, z.polygon)
                          or point_in_polygon(*centroid(z.polygon), poly)), None)
                if z:
                    matched.add(z.id)
                    _clear_streak[z.id] = 0
                    if z.polygon != poly:
                        z.polygon = poly
                        s.add(z)
                        s.commit()
                        events.publish("zone.published", {"zone": zone_public(s, z)}, events.ALL, route_id=route_id)
                else:
                    z = Zone(id="Z-CROWD-" + uuid.uuid4().hex[:6], route_id=route_id, kind="crowd", severity="warn",
                             polygon=poly, source="auto_crowd", simulated=route_id == "hall", created_by="crowd_engine")
                    publish_zone(s, z, "crowd_engine")
                    matched.add(z.id)
                    events.publish("crowd.red", {"zone_id": z.id, "people": people, "density": round(people / cap, 2),
                                                 "trend": "rising"}, events.ALL, route_id=route_id)
                _warn_approaching(s, z, by_route.get(route_id, []), people, facts)
            for z in existing:
                if z.id not in matched:
                    _clear_streak[z.id] = _clear_streak.get(z.id, 0) + 1
                    if _clear_streak[z.id] >= 2:
                        remove_zone(s, z, "crowd_engine")
                        events.publish("crowd.cleared", {"zone_id": z.id}, events.ALL, route_id=route_id)
            heat = {"route_id": route_id, "cells": cells, "capacity": cap, "ts": t}
            latest_heat[route_id] = heat
            events.publish("crowd.heat", heat, events.OPS, route_id=route_id)


def _warn_approaching(s: Session, z: Zone, trips: list[Trip], people: int, facts: dict) -> None:
    clat, clon = centroid(z.polygon)
    alts = facts.get("alternates") or []
    alt = alts[0]["name"] if alts else ""
    for tr in trips:
        if tr.kind == "sim" or point_in_polygon(tr.last_lat, tr.last_lon, z.polygon):
            continue
        if haversine_m(tr.last_lat, tr.last_lon, clat, clon) > 300:
            continue
        hd = _heading(s, tr.id)
        if hd is None or angle_diff(hd, bearing_deg(tr.last_lat, tr.last_lon, clat, clon)) > 45:
            continue
        if time.time() - _warned.get((tr.id, z.id), 0) < 300:
            continue
        _warned[(tr.id, z.id)] = time.time()
        msg = templates(tr.language)["crowd_ahead"].replace("{wait}", str(facts.get("crowd_wait_min", 20))) \
            .replace("{alt}", alt or "another path")
        events.publish("crowd.warn", {"zone_id": z.id, "people": people, "wait_min": facts.get("crowd_wait_min", 20),
                                      "alt_name": alt, "message": {tr.language: msg}}, {f"trip:{tr.id}"}, trip_id=tr.id)


def quiet_tick() -> None:
    t = time.time()
    with Session(engine) as s:
        for z in s.exec(select(Zone).where(Zone.active == True, Zone.expires_at != None)).all():  # noqa: E712,E711
            if z.expires_at <= t:
                remove_zone(s, z, "expiry")
        for tr in s.exec(select(Trip).where(Trip.kind == "tourist", Trip.sharing == True,  # noqa: E712
                                            Trip.status.in_(["active", "quiet", "quiet_red"]))).all():
            if not tr.last_ping_at:
                continue
            mins = (t - tr.last_ping_at) / 60
            risky = any(sg.get("risky") and sg.get("name") == tr.last_segment
                        for sg in route_facts(tr.route_id).get("segments", []))
            thr = settings.quiet_min_risky if risky else settings.quiet_min
            new = "quiet_red" if mins >= max(45, thr * 1.5) else ("quiet" if mins >= thr else "active")
            if new != tr.status:
                tr.status = new
                s.add(tr)
                s.commit()
                if new != "active":
                    events.publish("trip.quiet", {"trip_label": tr.label, "minutes": int(mins), "level": new,
                                                  "lat": tr.last_lat, "lon": tr.last_lon}, events.OPS,
                                   route_id=tr.route_id)


def retention_tick() -> None:
    cutoff = time.time() - settings.ping_retention_days * 86400
    with Session(engine) as s:
        old_trips = s.exec(select(Trip).where(Trip.status == "ended", Trip.end_at != None, Trip.end_at < cutoff)).all()  # noqa: E711
        for tr in old_trips:
            for p in s.exec(select(Ping).where(Ping.trip_id == tr.id)).all():
                s.delete(p)
        for r in s.exec(select(SosEvent).where(SosEvent.received_at_server < time.time() - 30 * 86400,
                                                SosEvent.note_text != None)).all():  # noqa: E711
            r.note_text = None
            s.add(r)
        from .models import SmsInbound
        for m in s.exec(select(SmsInbound).where(SmsInbound.received_at < time.time() - 30 * 86400,
                                                 SmsInbound.text != None)).all():  # noqa: E711
            m.text = None
            s.add(m)
        s.commit()


def weather_tick() -> None:
    """Refresh live weather for routes with travellers and push changes to every screen."""
    from . import weather

    with Session(engine) as s:
        routes = {tr.route_id for tr in s.exec(select(Trip).where(Trip.status != "ended")).all()} | {"kedarnath"}
    for rid in routes:
        before = (weather.cached(rid) or {}).get("fetched_at")
        w = weather.get(rid)
        if w.get("available") and w.get("fetched_at") != before:
            events.publish("weather.updated", {"route_id": rid, "weather": w}, events.ALL, route_id=rid)


async def _loop(fn, every_s: float) -> None:
    while True:
        await asyncio.sleep(every_s)
        try:
            await asyncio.to_thread(fn)
        except Exception:  # keep safety loops alive no matter what
            log.exception("%s failed", fn.__name__)


def start_engines() -> list[asyncio.Task]:
    return [asyncio.create_task(_loop(crowd_tick, settings.crowd_tick_s)),
            asyncio.create_task(_loop(quiet_tick, 30)),
            asyncio.create_task(_loop(retention_tick, 3600)),
            asyncio.create_task(asyncio.to_thread(weather_tick)),  # warm the weather cache at startup
            asyncio.create_task(_loop(weather_tick, 900))]
