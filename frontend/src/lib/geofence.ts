import { distanceToPolygon, pointInPolygon } from "./geo";
import type { Zone } from "./types";

export type Fix = { lat: number; lon: number; accuracy: number; ts: number; source?: "gps" | "checkpoint" | "sim" };

export type GeofenceEvent =
  | { type: "enter"; zone: Zone; fullScreen: boolean }
  | { type: "exit"; zone: Zone }
  | { type: "approach"; zone: Zone; distance: number }
  | { type: "approach_clear"; zone: Zone };

type ZoneState = { inside: boolean; inN: number; outN: number; approaching: boolean; apN: number; lastAlert: number };

/** On-phone geofencing with hysteresis (SPEC 5.3). Works with no network. */
export class Geofence {
  private st = new Map<string, ZoneState>();
  constructor(
    private opts = { approachM: 80, enterN: 2, exitN: 3, approachN: 2, cooldownMs: 5 * 60 * 1000, maxAccuracy: 60 },
  ) {}

  insideZones(): string[] {
    return [...this.st.entries()].filter(([, s]) => s.inside).map(([id]) => id);
  }

  update(fix: Fix, zones: Zone[], now = Date.now()): GeofenceEvent[] {
    const out: GeofenceEvent[] = [];
    if (fix.accuracy > this.opts.maxAccuracy) return out; // too rough to trust
    const ids = new Set(zones.map((z) => z.id));
    for (const id of [...this.st.keys()]) if (!ids.has(id)) this.st.delete(id);
    for (const z of zones) {
      const s = this.st.get(z.id) ?? { inside: false, inN: 0, outN: 0, approaching: false, apN: 0, lastAlert: 0 };
      const inside = pointInPolygon(fix.lat, fix.lon, z.polygon);
      const red = z.kind === "red_zone"; // alerts on the first fix inside, and again on any new entry
      const needIn = fix.source === "checkpoint" || red ? 1 : this.opts.enterN;
      if (inside) {
        s.inN += 1;
        s.outN = 0;
        if (!s.inside && s.inN >= needIn) {
          s.inside = true;
          s.approaching = false;
          const fullScreen = s.lastAlert === 0 || now - s.lastAlert > (red ? 20000 : this.opts.cooldownMs);
          if (fullScreen) s.lastAlert = now;
          out.push({ type: "enter", zone: z, fullScreen });
        }
      } else {
        s.outN += 1;
        s.inN = 0;
        if (s.inside && s.outN >= this.opts.exitN) {
          s.inside = false;
          out.push({ type: "exit", zone: z });
        }
        if (!s.inside) {
          const d = distanceToPolygon(fix.lat, fix.lon, z.polygon);
          if (d <= this.opts.approachM) {
            s.apN += 1;
            if (!s.approaching && s.apN >= this.opts.approachN) {
              s.approaching = true;
              out.push({ type: "approach", zone: z, distance: d });
            }
          } else {
            s.apN = 0;
            if (s.approaching) {
              s.approaching = false;
              out.push({ type: "approach_clear", zone: z });
            }
          }
        }
      }
      this.st.set(z.id, s);
    }
    return out;
  }
}
