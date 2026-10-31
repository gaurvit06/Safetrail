import type { Polygon } from "./types";

const R = 6371000;
const rad = (d: number) => (d * Math.PI) / 180;

export function haversine(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dp = rad(lat2 - lat1);
  const dl = rad(lon2 - lon1);
  const a = Math.sin(dp / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

export function bearing(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const y = Math.sin(rad(lon2 - lon1)) * Math.cos(rad(lat2));
  const x = Math.cos(rad(lat1)) * Math.sin(rad(lat2)) - Math.sin(rad(lat1)) * Math.cos(rad(lat2)) * Math.cos(rad(lon2 - lon1));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

export function cardinal(deg: number): string {
  return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round(deg / 45) % 8];
}

function ringContains(ring: number[][], lon: number, lat: number): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi || 1e-12) + xi) inside = !inside;
  }
  return inside;
}

export function pointInPolygon(lat: number, lon: number, poly: Polygon): boolean {
  const [outer, ...holes] = poly.coordinates;
  if (!ringContains(outer, lon, lat)) return false;
  return !holes.some((h) => ringContains(h, lon, lat));
}

const k = (Math.PI / 180) * R;
const toXY = (lat: number, lon: number, lat0: number) => [lon * k * Math.cos(rad(lat0)), lat * k];
const fromXY = (x: number, y: number, lat0: number) => [y / k, x / (k * Math.cos(rad(lat0)))];

/** Nearest point on the polygon's outer ring: { d (metres), lat, lon }. */
export function nearestBoundary(lat: number, lon: number, poly: Polygon): { d: number; lat: number; lon: number } {
  const ring = poly.coordinates[0];
  const [px, py] = toXY(lat, lon, lat);
  let best = { d: Infinity, lat, lon };
  for (let i = 0; i < ring.length - 1; i++) {
    const [ax, ay] = toXY(ring[i][1], ring[i][0], lat);
    const [bx, by] = toXY(ring[i + 1][1], ring[i + 1][0], lat);
    const dx = bx - ax;
    const dy = by - ay;
    const t = dx === 0 && dy === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)));
    const cx = ax + t * dx;
    const cy = ay + t * dy;
    const d = Math.hypot(px - cx, py - cy);
    if (d < best.d) {
      const [clat, clon] = fromXY(cx, cy, lat);
      best = { d, lat: clat, lon: clon };
    }
  }
  return best;
}

export function distanceToPolygon(lat: number, lon: number, poly: Polygon): number {
  return pointInPolygon(lat, lon, poly) ? 0 : nearestBoundary(lat, lon, poly).d;
}

export function centroid(poly: Polygon): [number, number] {
  const ring = poly.coordinates[0].slice(0, -1);
  const lat = ring.reduce((s, p) => s + p[1], 0) / ring.length;
  const lon = ring.reduce((s, p) => s + p[0], 0) / ring.length;
  return [lat, lon];
}

export function offset(lat: number, lon: number, northM: number, eastM: number): [number, number] {
  return [lat + northM / 111320, lon + eastM / (111320 * Math.cos(rad(lat)))];
}

/** A short path out of (or away from) a zone: from me to just beyond the nearest edge. */
export function safeWayOut(lat: number, lon: number, poly: Polygon): { path: number[][]; distance: number; dir: string } {
  const nb = nearestBoundary(lat, lon, poly);
  const inside = pointInPolygon(lat, lon, poly);
  let [clat, clon] = centroid(poly);
  // direction: away from the zone centre through the nearest edge point
  let vx = nb.lon - clon;
  let vy = nb.lat - clat;
  if (!inside) {
    vx = lon - clon;
    vy = lat - clat;
  }
  const len = Math.hypot(vx, vy) || 1;
  const stepLat = (vy / len) * (20 / 111320);
  const stepLon = (vx / len) * (20 / (111320 * Math.cos(rad(lat))));
  const target = inside ? [nb.lat + stepLat, nb.lon + stepLon] : [lat + stepLat * 2, lon + stepLon * 2];
  const distance = haversine(lat, lon, target[0], target[1]);
  return { path: [[lon, lat], [target[1], target[0]]], distance, dir: cardinal(bearing(lat, lon, target[0], target[1])) };
}

export function nearest<T extends { lat: number; lon: number }>(lat: number, lon: number, items: T[]): { item: T; d: number } | null {
  let best: { item: T; d: number } | null = null;
  for (const it of items) {
    const d = haversine(lat, lon, it.lat, it.lon);
    if (!best || d < best.d) best = { item: it, d };
  }
  return best;
}

export function nearestSegmentName(lat: number, lon: number, segments: { name: string; coords: number[][] }[]): string {
  let best = { d: Infinity, name: "" };
  for (const s of segments) {
    for (let i = 0; i < s.coords.length - 1; i++) {
      const poly: Polygon = { type: "Polygon", coordinates: [[s.coords[i], s.coords[i + 1], s.coords[i]]] };
      const d = nearestBoundary(lat, lon, poly).d;
      if (d < best.d) best = { d, name: s.name };
    }
  }
  return best.name;
}

export function fmtDistance(m: number): string {
  if (!isFinite(m)) return "–";
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m / 5) * 5} m`;
}
