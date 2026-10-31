"""Small, dependency-free geometry helpers. Coordinates are (lon, lat) like GeoJSON."""
import math

EARTH_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_M * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def _ring_contains(ring, lon: float, lat: float) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def point_in_polygon(lat: float, lon: float, polygon: dict) -> bool:
    """polygon: GeoJSON Polygon geometry {type, coordinates:[outer, holes...]}."""
    rings = polygon["coordinates"]
    if not _ring_contains(rings[0], lon, lat):
        return False
    return not any(_ring_contains(h, lon, lat) for h in rings[1:])


def _to_xy(lat: float, lon: float, lat0: float):
    k = math.pi / 180 * EARTH_M
    return lon * k * math.cos(math.radians(lat0)), lat * k


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(px - ax, py - ay), (ax, ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy), (cx, cy)


def distance_to_polygon_m(lat: float, lon: float, polygon: dict) -> float:
    """0 if inside, otherwise distance to the nearest edge (equirectangular approximation)."""
    if point_in_polygon(lat, lon, polygon):
        return 0.0
    return nearest_boundary(lat, lon, polygon)[0]


def nearest_boundary(lat: float, lon: float, polygon: dict):
    """(distance_m, (lat, lon)) of the nearest point on the outer ring."""
    ring = polygon["coordinates"][0]
    px, py = _to_xy(lat, lon, lat)
    best = (float("inf"), None)
    for a, b in zip(ring, ring[1:]):
        ax, ay = _to_xy(a[1], a[0], lat)
        bx, by = _to_xy(b[1], b[0], lat)
        d, (cx, cy) = _seg_dist(px, py, ax, ay, bx, by)
        if d < best[0]:
            k = math.pi / 180 * EARTH_M
            best = (d, (cy / k, cx / (k * math.cos(math.radians(lat)))))
    return best


def centroid(polygon: dict):
    ring = polygon["coordinates"][0][:-1] or polygon["coordinates"][0]
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    return lat, lon


def circle_polygon(lat: float, lon: float, radius_m: float, steps: int = 32) -> dict:
    pts = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        dlat = (radius_m * math.cos(a)) / 111_320
        dlon = (radius_m * math.sin(a)) / (111_320 * math.cos(math.radians(lat)))
        pts.append([round(lon + dlon, 7), round(lat + dlat, 7)])
    pts.append(pts[0])
    return {"type": "Polygon", "coordinates": [pts]}


def rect_polygon(min_lat, min_lon, max_lat, max_lon) -> dict:
    ring = [[min_lon, min_lat], [max_lon, min_lat], [max_lon, max_lat], [min_lon, max_lat], [min_lon, min_lat]]
    return {"type": "Polygon", "coordinates": [ring]}


def polygon_area_m2(polygon: dict) -> float:
    ring = polygon["coordinates"][0]
    lat0 = ring[0][1]
    pts = [_to_xy(p[1], p[0], lat0) for p in ring]
    s = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:]))
    return abs(s) / 2


def offset_point(lat: float, lon: float, d_north_m: float, d_east_m: float):
    return lat + d_north_m / 111_320, lon + d_east_m / (111_320 * math.cos(math.radians(lat)))


def nearest_segment(lat: float, lon: float, segments: list[dict]):
    """segments: [{id, name, coords:[[lon,lat],...]}] -> (segment, distance_m)."""
    best, best_d = None, float("inf")
    px, py = _to_xy(lat, lon, lat)
    for seg in segments:
        pts = seg.get("coords") or []
        for a, b in zip(pts, pts[1:]):
            ax, ay = _to_xy(a[1], a[0], lat)
            bx, by = _to_xy(b[1], b[0], lat)
            d, _ = _seg_dist(px, py, ax, ay, bx, by)
            if d < best_d:
                best, best_d = seg, d
    return best, best_d
