"""Build the Kedarnath route from real OpenStreetMap data (© OpenStreetMap contributors, ODbL).

    python scripts/fetch_osm.py

Fetches the "Gaurikund Kedarnath Trek" path, the closed old trek road, and real hospitals and shelters
from the Overpass API, then writes backend/seed/routes/kedarnath.json and updates the route facts.
Run it once with internet; the result is committed so the app works offline. Medical posts and
checkpoints that OSM doesn't have stay marked as simulated, snapped onto the real trail.
"""
import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "backend" / "seed"
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
UA = "SafeTrail-hackathon/1.0 (https://github.com/gaurvit06/Safetrail)"
BBOX = "30.64,79.01,30.745,79.085"
TREK_NAMES = {"Gaurikund Kedarnath Trek", "Kedarnath Temple Road"}
OLD_NAMES = {"Old Kedarnath Trek Road", "Old Kedarnath Trek Route"}
# Approximate locations of named stops, used only to split the real line into sections.
WAYPOINTS = {"Jungle Chatti": (30.6705, 79.0383), "Bhimbali": (30.6856, 79.0469), "Linchauli": (30.7080, 79.0660),
             "Base Camp": (30.7265, 79.0695)}
SEGMENTS = [("S1", "Gaurikund to Jungle Chatti", None, "Jungle Chatti"),
            ("S2", "Jungle Chatti to Bhimbali", "Jungle Chatti", "Bhimbali"),
            ("S3", "Bhimbali to Linchauli", "Bhimbali", "Linchauli"),
            ("S4", "Linchauli to Base Camp", "Linchauli", "Base Camp"),
            ("S5", "Base Camp to Temple", "Base Camp", None)]


def overpass(query: str) -> dict:
    last = None
    for ep in ENDPOINTS:
        for _ in range(2):
            try:
                req = urllib.request.Request(ep, data=urllib.parse.urlencode({"data": query}).encode(),
                                             headers={"User-Agent": UA, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=90) as r:
                    return json.loads(r.read())
            except Exception as e:  # busy servers return 429/502/504; try again, then the next mirror
                last = e
                time.sleep(3)
    raise SystemExit(f"Overpass unavailable: {last}")


def hav(a, b) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def stitch(ways: list[list[tuple]]) -> list[tuple]:
    """Greedy chain from the southernmost end, always taking the nearest unused way within 40 m."""
    ways = [w for w in ways if len(w) >= 2]
    start = min(ways, key=lambda w: min(w[0][0], w[-1][0]))
    line = start if start[0][0] <= start[-1][0] else start[::-1]
    unused = [w for w in ways if w is not start]
    while unused:
        end = line[-1]
        best, best_d, rev = None, 40.0, False
        for w in unused:
            for cand, r in ((w[0], False), (w[-1], True)):
                d = hav(end, cand)
                if d < best_d:
                    best, best_d, rev = w, d, r
        if best is None:
            break
        unused.remove(best)
        line += (best[::-1] if rev else best)[1:]
    return line


def simplify(pts: list[tuple], tol: float) -> list[tuple]:
    if len(pts) < 3:
        return pts
    lat0 = pts[0][0]
    xy = [(p[1] * 111320 * math.cos(math.radians(lat0)), p[0] * 111320) for p in pts]

    def rec(i, j):
        ax, ay = xy[i]
        bx, by = xy[j]
        dx, dy = bx - ax, by - ay
        best, idx = 0.0, None
        for k in range(i + 1, j):
            px, py = xy[k]
            t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
            d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if d > best:
                best, idx = d, k
        if idx is None or best <= tol:
            return [i, j]
        left = rec(i, idx)
        return left[:-1] + rec(idx, j)
    return [pts[i] for i in rec(0, len(pts) - 1)]


def nearest_idx(line, pt) -> int:
    return min(range(len(line)), key=lambda i: hav(line[i], pt))


def corridor(pts: list[tuple], half_m: float) -> dict:
    """A polygon around a polyline (simple offset corridor)."""
    lat0 = pts[0][0]
    kx, ky = 111320 * math.cos(math.radians(lat0)), 111320
    left, right = [], []
    for i, p in enumerate(pts):
        a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        dx, dy = (b[1] - a[1]) * kx, (b[0] - a[0]) * ky
        n = math.hypot(dx, dy) or 1
        ox, oy = -dy / n * half_m, dx / n * half_m
        left.append([round(p[1] + ox / kx, 7), round(p[0] + oy / ky, 7)])
        right.append([round(p[1] - ox / kx, 7), round(p[0] - oy / ky, 7)])
    ring = left + right[::-1] + [left[0]]
    return {"type": "Polygon", "coordinates": [ring]}


def lonlat(pts) -> list[list[float]]:
    return [[round(p[1], 7), round(p[0], 7)] for p in pts]


def main():
    ways = overpass(f'[out:json][timeout:40];way["highway"]["name"~"Kedar|Gaurikund",i]({BBOX});out tags geom;')["elements"]
    pois = overpass(f'[out:json][timeout:25];(nwr["amenity"~"hospital|clinic|doctors|police|shelter|first_aid"]({BBOX});'
                    f'nwr["tourism"~"alpine_hut|wilderness_hut"]({BBOX}););out center tags;')["elements"]
    geom = lambda w: [(g["lat"], g["lon"]) for g in w.get("geometry", [])]
    trek = stitch([geom(w) for w in ways if w.get("tags", {}).get("name") in TREK_NAMES])
    old = stitch([geom(w) for w in ways if w.get("tags", {}).get("name") in OLD_NAMES])
    line = simplify(trek, 6)
    total = sum(hav(a, b) for a, b in zip(trek, trek[1:]))
    print(f"trek: {len(trek)} points -> {len(line)} after simplify, {total / 1000:.1f} km; old road: {len(old)} points")

    cuts = [0] + [nearest_idx(line, WAYPOINTS[name]) for name in ("Jungle Chatti", "Bhimbali", "Linchauli", "Base Camp")] + [len(line) - 1]
    segs, seg_len = [], {}
    for (sid, name, _, _), a, b in zip(SEGMENTS, cuts, cuts[1:]):
        part = line[a:b + 1]
        segs.append({"id": sid, "name": name, "coords": lonlat(part)})
        seg_len[sid] = round(sum(hav(x, y) for x, y in zip(part, part[1:])) / 1000, 1)

    help_points, osm_ids = [], {}
    for p in pois:
        t = p.get("tags", {})
        lat, lon = p.get("lat") or p["center"]["lat"], p.get("lon") or p["center"]["lon"]
        kind = {"hospital": "medical", "clinic": "medical", "doctors": "medical", "first_aid": "medical",
                "police": "police", "shelter": "shelter"}.get(t.get("amenity"), "shelter")
        hid = f"OSM-{p['type'][0].upper()}{p['id']}"
        help_points.append({"id": hid, "kind": kind, "name": t.get("name") or ("Rain shelter" if kind == "shelter" else kind.title()),
                            "lat": lat, "lon": lon, "simulated": False, "source": "osm"})
        osm_ids[hid] = kind
    snap = lambda name: line[nearest_idx(line, WAYPOINTS[name])]
    sim = [("PO-GK", "police", "Gaurikund police post", line[0]),
           ("MP-JC", "medical", "Jungle Chatti medical post", snap("Jungle Chatti")),
           ("MP-BB", "medical", "Bhimbali medical post", snap("Bhimbali")),
           ("MP-LC", "medical", "Linchauli medical post", snap("Linchauli"))]
    for hid, kind, name, (lat, lon) in sim:
        help_points.append({"id": hid, "kind": kind, "name": name, "lat": round(lat, 7), "lon": round(lon, 7),
                            "simulated": True, "source": "seed"})
    hospital = next((h for h in help_points if h["source"] == "osm" and h["kind"] == "medical"), None)

    i0, i1 = nearest_idx(line, (30.6940, 79.0566)), nearest_idx(line, (30.6984, 79.0616))
    zones = [{"id": "Z-KED-L1", "kind": "landslide", "severity": "danger", "segment_name": "Bhimbali to Linchauli",
              "polygon": corridor(line[min(i0, i1):max(i0, i1) + 1], 70)}]
    if len(old) > 2:
        zones.append({"id": "Z-KED-C1", "kind": "closed_trail", "severity": "warn", "segment_name": "Old Kedarnath trek road",
                      "polygon": corridor(simplify(old, 12), 25)})

    route = {
        "id": "kedarnath", "name": "Gaurikund to Kedarnath", "region": "Rudraprayag, Uttarakhand", "local_lang": "hi",
        "simulated": True,
        "_note": "Trail geometry, hospital and shelters: © OpenStreetMap contributors (ODbL), built by scripts/fetch_osm.py. "
                 "Medical posts, checkpoints and zones are simulated for the demo.",
        "line": lonlat(line), "segments": segs, "help_points": help_points,
        "checkpoints": [{"id": "CP-GK", "name": "Gaurikund registration", "lat": round(line[0][0], 7), "lon": round(line[0][1], 7)},
                        {"id": "CP-LC", "name": "Linchauli checkpoint", "lat": round(snap("Linchauli")[0], 7), "lon": round(snap("Linchauli")[1], 7)}],
        "zones": zones,
    }
    (SEED / "routes" / "kedarnath.json").write_text(json.dumps(route, ensure_ascii=False, indent=1), encoding="utf-8")

    facts_path = SEED / "route_facts" / "kedarnath.json"
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    facts["version"] = facts.get("version", 1) + 1
    facts["distance_km"] = round(total / 1000, 1)
    facts["data_sources"] = "Trail, hospital and shelters: OpenStreetMap contributors (ODbL). Medical posts: simulated."
    for sg in facts["segments"]:
        sg["length_km"] = seg_len.get(sg["id"], sg.get("length_km"))
        if hospital and sg["id"] in ("S4", "S5"):
            sg["nearest_help_id"] = hospital["id"]
    facts["help_points"] = [{"id": h["id"], "kind": h["kind"], "name": h["name"]} for h in help_points]
    facts_path.write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote routes/kedarnath.json ({len(help_points)} help points, {len(zones)} zones) and route facts v{facts['version']}")


if __name__ == "__main__":
    main()
