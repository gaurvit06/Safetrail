import { describe, expect, it } from "vitest";
import { Geofence } from "./geofence";
import type { Zone } from "./types";

const zone: Zone = {
  id: "Z1", route_id: "hall", kind: "landslide", severity: "danger", source: "drawn", segment_name: "", simulated: true,
  active: true, created_at: 0, advisories: {},
  polygon: { type: "Polygon", coordinates: [[[76.0, 30.0], [76.001, 30.0], [76.001, 30.001], [76.0, 30.001], [76.0, 30.0]]] },
};
const inside = { lat: 30.0005, lon: 76.0005, accuracy: 10, ts: 0 };
const outside = { lat: 30.01, lon: 76.01, accuracy: 10, ts: 0 };
const near = { lat: 30.0015, lon: 76.0005, accuracy: 10, ts: 0 }; // ~55 m north of the edge

describe("Geofence", () => {
  it("needs 2 inside fixes to enter and 3 outside fixes to exit", () => {
    const g = new Geofence();
    expect(g.update(inside, [zone])).toEqual([]);
    expect(g.update(inside, [zone])[0].type).toBe("enter");
    expect(g.update(outside, [zone])).toEqual([]);
    expect(g.update(outside, [zone])).toEqual([]);
    expect(g.update(outside, [zone])[0].type).toBe("exit");
  });

  it("alerts for a red zone on the first fix inside, and again on a new entry", () => {
    const red = { ...zone, id: "R1", kind: "red_zone" };
    const g = new Geofence();
    const first = g.update(inside, [red], 1000)[0];
    expect(first.type === "enter" && first.fullScreen).toBe(true);
    for (let i = 0; i < 3; i++) g.update(outside, [red], 2000);
    const again = g.update(inside, [red], 30000)[0];
    expect(again.type === "enter" && again.fullScreen).toBe(true);
  });

  it("does not flicker on one noisy fix", () => {
    const g = new Geofence();
    g.update(inside, [zone]);
    g.update(inside, [zone]);
    expect(g.update(outside, [zone])).toEqual([]);
    expect(g.update(inside, [zone])).toEqual([]);
  });

  it("ignores rough fixes", () => {
    const g = new Geofence();
    expect(g.update({ ...inside, accuracy: 200 }, [zone])).toEqual([]);
    expect(g.update({ ...inside, accuracy: 200 }, [zone])).toEqual([]);
  });

  it("warns when approaching", () => {
    const g = new Geofence();
    g.update(near, [zone]);
    const ev = g.update(near, [zone]);
    expect(ev[0].type).toBe("approach");
  });

  it("enters on a single checkpoint scan", () => {
    const g = new Geofence();
    expect(g.update({ ...inside, source: "checkpoint" }, [zone])[0].type).toBe("enter");
  });

  it("limits full-screen alerts to one per zone per cooldown", () => {
    const g = new Geofence();
    g.update(inside, [zone], 0);
    const first = g.update(inside, [zone], 1000)[0] as any;
    expect(first.fullScreen).toBe(true);
    for (let i = 0; i < 3; i++) g.update(outside, [zone], 2000);
    g.update(inside, [zone], 3000);
    const again = g.update(inside, [zone], 4000)[0] as any;
    expect(again.type).toBe("enter");
    expect(again.fullScreen).toBe(false);
  });
});
