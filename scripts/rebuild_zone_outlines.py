"""Redraw the corridor zones of a route as true buffers, without internet.

    python scripts/rebuild_zone_outlines.py            (default: kedarnath)

The first fetch_osm.py drew each zone as a plain left/right offset of its line. On switchbacks that
outline folds over itself, and the even-odd point-in-polygon test then reads the folds as holes: 3% of
the trail inside the landslide zone tested as outside it. This rebuilds each zone that has a line with
fetch_osm.corridor (one simple polygon). Zones from the old format get their line back from the old
outline (the midpoints of its left and right offsets) and keep it as "centerline", so running this
again is harmless.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_osm import SEED, corridor  # noqa: E402


def recover_centerline(ring: list) -> list:
    n = (len(ring) - 1) // 2
    left, right = ring[:n], ring[n:2 * n][::-1]
    return [[round((a[0] + b[0]) / 2, 7), round((a[1] + b[1]) / 2, 7)] for a, b in zip(left, right)]


def main(route_id: str = "kedarnath") -> None:
    path = SEED / "routes" / f"{route_id}.json"
    route = json.loads(path.read_text(encoding="utf-8"))
    widths = {"Z-KED-L1": 70, "Z-KED-C1": 25}  # what fetch_osm.py used for the first outlines
    for z in route.get("zones", []):
        if "centerline" not in z:
            if z["id"] not in widths:
                continue
            z["centerline"], z["half_width_m"] = recover_centerline(z["polygon"]["coordinates"][0]), widths[z["id"]]
        before = len(z["polygon"]["coordinates"][0])
        z["polygon"] = corridor([(lat, lon) for lon, lat in z["centerline"]], z["half_width_m"])
        print(f"{z['id']}: {before} -> {len(z['polygon']['coordinates'][0])} outline points ({z['half_width_m']} m each side)")
    path.write_text(json.dumps(route, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(SEED.parents[1])}")


if __name__ == "__main__":
    main(*sys.argv[1:])
