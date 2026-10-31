"""Build the two extra demo routes from SPEC 10.1: `sikkim` (Lachung to Yumthang) and `park` (Corbett Tiger Reserve).

    backend/.venv/bin/python scripts/make_extra_routes.py

Writes backend/seed/routes/<id>.json and backend/seed/route_facts/<id>.json. EVERYTHING here is simulated:
the lines are drawn by hand through approximate landmark positions (OpenStreetMap was not reachable when they were
made), and every help point, checkpoint and zone is a demo stand-in. To use real geometry, redraw the waypoints on
geojson.io (or extend scripts/fetch_osm.py) and run this again. Never use these lines for navigation.
"""
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEED = REPO / "backend" / "seed"
sys.path.insert(0, str(REPO / "backend"))

from app.geo import haversine_m  # noqa: E402

NOTE = ("Route line drawn by hand through approximate landmark positions (simulated, not for navigation). "
        "Help points, checkpoints and zones are simulated for the demo. Rebuild with scripts/make_extra_routes.py.")

ROUTES = {
    "sikkim": {
        "name": "Lachung to Yumthang Valley", "region": "North Sikkim, Sikkim", "local_lang": "ne",
        # (lon, lat, label) along the Lachung Chu valley; the segment breaks are at the labelled points
        "waypoints": [(88.7441, 27.6886, "Lachung"), (88.7426, 27.6990, None), (88.7431, 27.7085, None),
                      (88.7398, 27.7230, "Bichu"), (88.7391, 27.7340, None), (88.7362, 27.7480, None),
                      (88.7300, 27.7700, "Shingba"), (88.7246, 27.7820, None), (88.7180, 27.7950, None),
                      (88.7085, 27.8080, None), (88.7040, 27.8150, None), (88.6962, 27.8264, "Yumthang")],
        "segments": [("Y1", "Lachung to Bichu", ["landslides and falling rocks after rain", "narrow road shared with vehicles"], "HP-LCH"),
                     ("Y2", "Bichu to Shingba", ["ice on the road early in the morning", "rhododendron sanctuary: stay on the road"], "HP-SHG"),
                     ("Y3", "Shingba to Yumthang", ["altitude above 3,500 m: go slowly", "cold wind, below zero at night"], "HP-YUM")],
        "help_points": [("HP-LCH", "medical", "Lachung health centre (simulated)", 88.7448, 27.6893),
                        ("HP-SHG", "police", "Shingba police check post (simulated)", 88.7305, 27.7695),
                        ("HP-YUM", "shelter", "Yumthang tourist shelter (simulated)", 88.6970, 27.8255),
                        ("HP-YFA", "medical", "Yumthang first-aid post (simulated)", 88.6955, 27.8270)],
        "checkpoints": [("CP-LCH", "Lachung permit check (simulated)", 88.7441, 27.6886),
                        ("CP-YUM", "Yumthang checkpoint (simulated)", 88.6962, 27.8264)],
        "zones": [{"id": "Z-SKM-L1", "kind": "landslide", "severity": "danger", "segment": "Lachung to Bichu",
                   "circle": (88.7431, 27.7085, 220)},
                  {"id": "Z-SKM-R1", "kind": "restricted", "severity": "warn",
                   "segment": "Beyond Yumthang (Yume Samdong road)",
                   "box": (88.680, 27.836, 88.725, 27.880)}],
        "facts": {"control_room_label": "North Sikkim district control room (simulated)", "segment_capacity": 30,
                  "crowd_wait_min": 15, "alternates": [{"id": "ALT-Y1", "name": "Wait at Lachung until the road is cleared"}],
                  "altitude_relevant": True, "altitude_m": {"start": 2700, "end": 3560},
                  "permit_note": "Foreign visitors need a Restricted Area Permit (RAP) and travel with a registered operator; "
                                 "the road beyond Yumthang is not open to them (simulated summary)."},
    },
    "park": {
        "name": "Dhangarhi gate to Dhikala (Corbett Tiger Reserve)", "region": "Nainital and Pauri, Uttarakhand",
        "local_lang": "hi",
        "waypoints": [(79.0600, 29.5150, "Dhangarhi gate"), (79.0420, 29.5230, None), (79.0230, 29.5330, None),
                      (79.0010, 29.5440, None), (78.9810, 29.5520, None), (78.9650, 29.5550, "Gairal"),
                      (78.9480, 29.5540, None), (78.9280, 29.5510, None), (78.9050, 29.5480, "Sarapduli"),
                      (78.8870, 29.5470, None), (78.8700, 29.5455, None), (78.8530, 29.5446, "Dhikala")],
        "segments": [("P1", "Dhangarhi gate to Gairal", ["wild elephants on the road: stop and keep 50 m away", "stay inside the vehicle"], "HP-GRL"),
                     ("P2", "Gairal to Sarapduli", ["tigers and leopards: never get out of the vehicle", "river crossings after rain"], "HP-SRP"),
                     ("P3", "Sarapduli to Dhikala", ["open grassland: no walking off the road", "dusk: be inside the fenced camp before dark"], "HP-DKL")],
        "help_points": [("HP-DHG", "ranger", "Dhangarhi gate forest post (simulated)", 79.0605, 29.5145),
                        ("HP-GRL", "shelter", "Gairal forest rest house (simulated)", 78.9655, 29.5560),
                        ("HP-SRP", "shelter", "Sarapduli forest rest house (simulated)", 78.9055, 29.5490),
                        ("HP-DKL", "medical", "Dhikala camp first aid (simulated)", 78.8525, 29.5452)],
        "checkpoints": [("CP-DHG", "Dhangarhi entry gate (simulated)", 79.0600, 29.5150),
                        ("CP-DKL", "Dhikala camp gate (simulated)", 78.8530, 29.5446)],
        "zones": [{"id": "Z-PRK-W1", "kind": "wildlife_core", "severity": "danger", "segment": "Dhikala grassland (off-road core)",
                   "box": (78.872, 29.528, 78.930, 29.541)},
                  {"id": "Z-PRK-F1", "kind": "flood", "severity": "warn", "segment": "Gairal to Sarapduli",
                   "circle": (78.9280, 29.5510, 180)}],
        "facts": {"control_room_label": "Corbett forest control room (simulated)", "segment_capacity": 25,
                  "crowd_wait_min": 10, "alternates": [{"id": "ALT-P1", "name": "Wait at Gairal rest house for a ranger escort"}],
                  "altitude_relevant": False,
                  "permit_note": "Entry only with a park entry permit booked for the zone and date, in a registered vehicle "
                                 "with a guide (simulated summary)."},
    },
}


def densify(points: list[tuple[float, float]], step_m: float = 50) -> list[list[float]]:
    out = [list(points[0])]
    for (lon1, lat1), (lon2, lat2) in zip(points, points[1:]):
        n = max(1, math.ceil(haversine_m(lat1, lon1, lat2, lon2) / step_m))
        out += [[round(lon1 + (lon2 - lon1) * i / n, 7), round(lat1 + (lat2 - lat1) * i / n, 7)] for i in range(1, n + 1)]
    return out


def length_km(coords: list[list[float]]) -> float:
    return sum(haversine_m(a[1], a[0], b[1], b[0]) for a, b in zip(coords, coords[1:])) / 1000


def circle(lon: float, lat: float, r: float) -> dict:
    pts = [[round(lon + r * math.sin(a) / (111320 * math.cos(math.radians(lat))), 7), round(lat + r * math.cos(a) / 111320, 7)]
           for a in (2 * math.pi * i / 24 for i in range(24))]
    return {"type": "Polygon", "coordinates": [pts + [pts[0]]]}


def box(w: float, s: float, e: float, n: float) -> dict:
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


def build(rid: str, r: dict) -> tuple[dict, dict]:
    wps = r["waypoints"]
    breaks = [i for i, w in enumerate(wps) if w[2]]  # indices of labelled waypoints
    seg_out, fact_segs, line = [], [], []
    for (sid, name, risks, help_id), a, b in zip(r["segments"], breaks, breaks[1:]):
        coords = densify([(w[0], w[1]) for w in wps[a:b + 1]])
        line += coords if not line else coords[1:]
        seg_out.append({"id": sid, "name": name, "coords": coords})
        fact_segs.append({"id": sid, "name": name, "length_km": round(length_km(coords), 1), "risky": True,
                          "nearest_help_id": help_id, "risks": risks})
    hps = [{"id": i, "kind": k, "name": n, "lat": la, "lon": lo, "simulated": True, "source": "seed"}
           for i, k, n, lo, la in r["help_points"]]
    zones = [{"id": z["id"], "kind": z["kind"], "severity": z["severity"], "segment_name": z["segment"],
              "polygon": circle(*z["circle"]) if "circle" in z else box(*z["box"])} for z in r["zones"]]
    seed = {"id": rid, "name": r["name"], "region": r["region"], "local_lang": r["local_lang"], "simulated": True,
            "_note": NOTE, "line": line, "segments": seg_out, "help_points": hps,
            "checkpoints": [{"id": i, "name": n, "lat": la, "lon": lo} for i, n, lo, la in r["checkpoints"]], "zones": zones}
    facts = {"version": 1, "route_name": r["name"], "simulated": True, "distance_km": round(length_km(line), 1),
             "emergency_number": "112", **r["facts"], "segments": fact_segs,
             "help_points": [{"id": h["id"], "kind": h["kind"], "name": h["name"]} for h in hps],
             "data_sources": "Route line drawn by hand through approximate landmark positions; help points, checkpoints "
                             "and zones simulated. Not for navigation."}
    return seed, facts


def main() -> None:
    for rid, r in ROUTES.items():
        seed, facts = build(rid, r)
        (SEED / "routes" / f"{rid}.json").write_text(json.dumps(seed, ensure_ascii=False, indent=1), encoding="utf-8")
        (SEED / "route_facts" / f"{rid}.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{rid}: {facts['distance_km']} km, {len(seed['segments'])} sections, {len(seed['help_points'])} help points, "
              f"{len(seed['zones'])} zones")


if __name__ == "__main__":
    main()
