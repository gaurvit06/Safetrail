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
