"""The CSED block demo: one-tap red zone and a simulated crowd around one area only."""
import asyncio
import time

from sqlmodel import select

from app import engines, stage
from app.core import active_zones, create_trip
from app.geo import point_in_polygon
from app.models import Trip, Zone
from app.seeddata import route_seed


def _clear_zones(s):
    for z in s.exec(select(Zone).where(Zone.route_id == "hall", Zone.active == True)).all():  # noqa: E712
        z.active = False
        s.add(z)
    s.commit()


def test_flag_csed_covers_the_whole_block_with_a_margin(s):
    _clear_zones(s)
    r = stage.flag_csed(s)
    assert r["zone"]["kind"] == "red_zone" and r["zone"]["severity"] == "danger" and r["zone"]["simulated"]
    assert r["zone"]["segment_name"] == "CSED block"
    poly = r["zone"]["polygon"]
    for lon, lat in route_seed("hall")["line"]:
        assert point_in_polygon(lat, lon, poly)
    assert not point_in_polygon(30.3535, 76.3702, poly)  # the path down by the library stays outside


def test_flag_csed_twice_keeps_one_zone(s):
    _clear_zones(s)
    first = stage.flag_csed(s)
    second = stage.flag_csed(s)
    assert first["zone"]["id"] == second["zone"]["id"]
    assert sum(1 for z in active_zones(s, "hall") if z.kind == "red_zone") == 1


def test_csed_is_red_again_after_a_reset(s):
    _clear_zones(s)
    stage.reset_demo(s)
    assert stage.csed_red_zone(s) is not None


def test_clear_csed_removes_the_zone(s):
    _clear_zones(s)
    stage.flag_csed(s)
    assert stage.clear_csed(s)["ok"]
    assert stage.csed_red_zone(s) is None
    assert not stage.clear_csed(s)["ok"]


def test_red_zone_warning_has_its_own_text():
    from app.ai.templates import zone_text
    assert zone_text("en", "red_zone", "CSED block")["title"] == "Red zone: do not enter"
    assert "CSED block" in zone_text("hi", "red_zone", "CSED block")["body"]


def _person(s, lat, lon, kind="tourist"):
    tr, _ = create_trip(s, {"name": "P", "route_id": "hall", "consent_version": "v1"}, kind=kind)
    tr.status, tr.sharing, tr.last_lat, tr.last_lon, tr.last_ping_at = "active", True, lat, lon, time.time()
    s.add(tr)
    s.commit()
    return tr


def test_heat_points_add_up_and_tourists_never_see_one_person_alone(s):
    engines.latest_heat.clear()
    lat, lon = 30.3552, 76.3696
    for _ in range(4):
        _person(s, lat, lon)
    _person(s, lat + 0.004, lon + 0.004)  # alone, far from the others
    engines.crowd_tick()
    heat = engines.latest_heat["hall"]
    assert heat["people"] == 5 and sum(p["n"] for p in heat["points"]) == 5
    public = engines.latest_public_heat["hall"]
    assert public["people"] == 4
    assert all(abs(p["lat"] - lat) < 0.001 for p in public["points"])


def test_heat_clears_when_everyone_has_left(s):
    engines.latest_heat.clear()
    tr = _person(s, 30.3552, 76.3696)
    engines.crowd_tick()
    assert engines.latest_heat["hall"]["people"] == 1
    tr.status = "ended"
    s.add(tr)
    s.commit()
    engines.crowd_tick()
    assert engines.latest_heat["hall"]["people"] == 0 and engines.latest_heat["hall"]["points"] == []


def test_clients_can_catch_up_on_events_by_number():
    from app import events
    start = events.since(-1, {"tourists"})
    assert start["events"] == []
    events.publish("for.tourists", {}, {"tourists"})
    events.publish("for.staff", {}, events.OPS)
    tourist = events.since(start["seq"], {"tourists"})
    assert [e["type"] for e in tourist["events"]] == ["for.tourists"]
    assert [e["type"] for e in events.since(start["seq"], {"responder"})["events"]] == ["for.staff"]
    assert events.since(tourist["seq"], {"tourists"})["events"] == []


def test_simulated_crowd_stays_around_csed_and_stops(s, monkeypatch):
    engines.latest_heat.clear()
    monkeypatch.setattr(stage.time, "monotonic", time.monotonic)
    asyncio.run(stage.csed_crowd(n=12, build_s=0.05, hold_s=0, drift_s=0))
    s.expire_all()
    people = s.exec(select(Trip).where(Trip.kind == "sim", Trip.route_id == "hall")).all()
    assert len(people) == 12 and all(tr.status == "ended" for tr in people)
    assert engines.latest_heat["hall"]["people"] == 0
    route = route_seed("hall")["line"]
    lat0, lon0 = route[0][1], route[0][0]
    for tr in people:
        assert abs(tr.last_lat - lat0) < 0.002 and abs(tr.last_lon - lon0) < 0.002  # within about 200 m
