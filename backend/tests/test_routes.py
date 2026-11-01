"""The extra demo routes (SPEC 10.1) load like the others, are fully labelled simulated, and are internally consistent."""
from sqlmodel import select

from app import weather
from app.ai.templates import pack_template, zone_text
from app.models import Route, Zone
from app.seeddata import route_facts, route_ids, route_seed, segment_for, templates


def test_all_four_routes_are_seeded(s):
    assert set(route_ids()) >= {"hall", "kedarnath", "sikkim", "park"}
    assert {r.id for r in s.exec(select(Route)).all()} >= {"hall", "kedarnath", "sikkim", "park"}
    kinds = {z.kind for z in s.exec(select(Zone).where(Zone.route_id.in_(["sikkim", "park"]))).all()}
    assert {"landslide", "restricted", "wildlife_core"} <= kinds  # SPEC 10.1


def test_extra_routes_are_consistent_and_simulated():
    for rid in ("sikkim", "park"):
        seed, facts = route_seed(rid), route_facts(rid)
        assert seed["simulated"] and facts["simulated"] and facts["emergency_number"] == "112"
        assert all(h["simulated"] for h in seed["help_points"]) and all("simulated" in h["name"] for h in seed["help_points"])
        help_ids = {h["id"] for h in seed["help_points"]}
        assert all(sg["nearest_help_id"] in help_ids for sg in facts["segments"])
        total = sum(sg["length_km"] for sg in facts["segments"])
        assert abs(total - facts["distance_km"]) < 0.3
        mid = seed["segments"][1]["coords"][len(seed["segments"][1]["coords"]) // 2]
        seg, d = segment_for(rid, mid[1], mid[0])
        assert seg["name"] == seed["segments"][1]["name"] and d < 5
        assert len(weather.section_points(rid)) == 3


def test_partial_translations_fall_back_to_english():
    ne, en = templates("ne"), templates("en")
    assert ne["phrases"]["thank_you"] == "धन्यवाद।" and ne["zone"] == en["zone"]
    assert zone_text("ne", "landslide", "Lachung to Bichu")["title"] == zone_text("en", "landslide", "x")["title"]
    pack = pack_template("sikkim", "en", "standard")
    help_line = next(p for p in pack["phrasebook"] if p["key"] == "help")
    assert help_line["local_text"] == ne["phrases"]["help"] and help_line["user_text"] == en["phrases"]["help"]


def _crossings(ring: list) -> int:
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    segs, n = list(zip(ring, ring[1:])), 0
    for i in range(len(segs)):
        for j in range(i + 2, len(segs)):
            if i == 0 and j == len(segs) - 1:
                continue
            (a, b), (c, d) = segs[i], segs[j]
            n += side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0
    return n


def test_seeded_zone_outlines_are_simple_and_cover_their_line():
    """A zone outline that crosses itself has holes for the even-odd test, so part of the trail
    inside a landslide zone would read as outside it (the first Kedarnath outlines did)."""
    from app.geo import point_in_polygon
    for rid in route_ids():
        for z in route_seed(rid).get("zones", []):
            ring = z["polygon"]["coordinates"][0]
            assert ring[0] == ring[-1], z["id"]
            assert _crossings(ring) == 0, f"{z['id']} outline crosses itself"
            line = z.get("centerline", [])
            for (lon1, lat1), (lon2, lat2) in zip(line, line[1:]):
                for k in range(5):
                    lat, lon = lat1 + (lat2 - lat1) * k / 5, lon1 + (lon2 - lon1) * k / 5
                    assert point_in_polygon(lat, lon, z["polygon"]), f"{z['id']}: its own line is outside at {lat},{lon}"
