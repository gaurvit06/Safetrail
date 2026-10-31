import maplibregl, { type GeoJSONSource, type Map as MLMap, type Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { centroid } from "../lib/geo";
import { KIND_ICON } from "../lib/format";
import type { Checkpoint, Dot, HeatCell, HelpPoint, Zone } from "../lib/types";

export type IncidentPin = { id: number; lat: number; lon: number; count: number; priority: string; selected?: boolean; status: string };
export type Me = { lat: number; lon: number; accuracy: number; heading?: number | null; demo?: boolean };

type Props = {
  dark?: boolean;
  bbox?: number[] | null;
  route?: { type: "LineString"; coordinates: number[][] } | null;
  zones?: Zone[];
  highlightZoneId?: string | null;
  me?: Me | null;
  dots?: Dot[];
  heat?: HeatCell[];
  helpPoints?: HelpPoint[];
  checkpoints?: Checkpoint[];
  incidents?: IncidentPin[];
  path?: number[][] | null;
  draft?: number[][] | null;
  followMe?: boolean;
  flyTo?: { lat: number; lon: number; zoom?: number; key: number } | null;
  onClick?: (lat: number, lon: number) => void;
  onZoneClick?: (z: Zone) => void;
  onHelpClick?: (hp: HelpPoint) => void;
  onIncidentClick?: (id: number) => void;
  onDotClick?: (d: Dot) => void;
  className?: string;
};

const fc = (features: any[]) => ({ type: "FeatureCollection", features }) as any;
const STATUS_COLOR: Record<string, string> = { active: "#1A73E8", quiet: "#F59E0B", quiet_red: "#EA580C", sos: "#D93025", safe: "#1E8E3E", planned: "#80868B", ended: "#80868B" };
const HP_ICON: Record<string, string> = { medical: "✚", shelter: "⌂", police: "★", ranger: "✦", checkpoint: "◆" };

function circlePoly(lat: number, lon: number, r: number) {
  const pts = [];
  for (let i = 0; i <= 36; i++) {
    const a = (i / 36) * 2 * Math.PI;
    pts.push([lon + (r * Math.sin(a)) / (111320 * Math.cos((lat * Math.PI) / 180)), lat + (r * Math.cos(a)) / 111320]);
  }
  return { type: "Polygon", coordinates: [pts] };
}

/** OpenStreetMap raster tiles (no key; light use only, never bulk-prefetched). Offline, the route,
 *  zones and help points still draw as GeoJSON on the plain background. The projector gets a dimmed copy. */
function style(dark: boolean): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      base: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, maxzoom: 19, attribution: "© OpenStreetMap contributors" },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": dark ? "#1b1f24" : "#ece7dd" } },
      {
        id: "base",
        type: "raster",
        source: "base",
        paint: dark ? { "raster-saturation": -0.7, "raster-brightness-max": 0.42, "raster-contrast": 0.15 } : { "raster-saturation": -0.25 },
      },
    ],
  };
}

export default function MapView(p: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const loaded = useRef(false);
  const props = useRef(p);
  props.current = p;
  const markers = useRef<Record<string, Marker>>({});
  const followed = useRef(false);

  const set = (id: string, data: any) => {
    const src = map.current?.getSource(id) as GeoJSONSource | undefined;
    if (loaded.current && src) src.setData(data);
  };

  const syncAll = () => {
    const q = props.current;
    set("route", fc(q.route ? [{ type: "Feature", geometry: q.route, properties: {} }] : []));
    set("zones", fc((q.zones ?? []).map((z) => ({ type: "Feature", geometry: z.polygon, properties: { id: z.id, kind: z.kind, severity: z.severity, hl: z.id === q.highlightZoneId ? 1 : 0 } }))));
    set("heat", fc((q.heat ?? []).map((c) => ({ type: "Feature", geometry: c.polygon, properties: { level: c.level } }))));
    set("dots", fc((q.dots ?? []).filter((d) => d.lat != null).map((d) => ({ type: "Feature", geometry: { type: "Point", coordinates: [d.lon, d.lat] }, properties: { label: d.trip_label, color: STATUS_COLOR[d.status] ?? "#1A73E8", sim: d.kind === "sim" ? 1 : 0, flagged: d.flags?.length ? 1 : 0, kind: d.kind } }))));
    set("path", fc(q.path ? [{ type: "Feature", geometry: { type: "LineString", coordinates: q.path }, properties: {} }] : []));
    const dr = q.draft ?? [];
    set("draft", fc([
      ...(dr.length >= 3 ? [{ type: "Feature", geometry: { type: "Polygon", coordinates: [[...dr, dr[0]]] }, properties: {} }] : []),
      ...(dr.length >= 2 ? [{ type: "Feature", geometry: { type: "LineString", coordinates: dr }, properties: {} }] : []),
      ...dr.map((c) => ({ type: "Feature", geometry: { type: "Point", coordinates: c }, properties: {} })),
    ]));
    set("acc", fc(q.me ? [{ type: "Feature", geometry: circlePoly(q.me.lat, q.me.lon, Math.max(q.me.accuracy, 4)), properties: {} }] : []));
    syncMarkers();
  };

  const marker = (key: string, lngLat: [number, number], html: string, onClick?: () => void, cls = "") => {
    const m = map.current!;
    let mk = markers.current[key];
    if (!mk) {
      const div = document.createElement("div");
      div.className = cls;
      if (onClick) {
        div.style.cursor = "pointer";
        div.addEventListener("click", (e) => {
          e.stopPropagation();
          (div as any)._onClick?.();
        });
      }
      mk = new maplibregl.Marker({ element: div }).setLngLat(lngLat).addTo(m);
      markers.current[key] = mk;
    }
    const div = mk.getElement();
    if (div.innerHTML !== html) div.innerHTML = html;
    (div as any)._onClick = onClick;
    mk.setLngLat(lngLat);
    return key;
  };

  const syncMarkers = () => {
    if (!map.current || !loaded.current) return;
    const q = props.current;
    const keep = new Set<string>();
    if (q.me) {
      const hd = q.me.heading != null ? `<div class="st-heading" style="transform:rotate(${q.me.heading}deg)"></div>` : "";
      keep.add(marker("me", [q.me.lon, q.me.lat], `<div class="st-me ${q.me.demo ? "st-me-demo" : ""}"><div class="st-me-ring"></div>${hd}<div class="st-me-dot"></div></div>`));
    }
    for (const hp of q.helpPoints ?? [])
      keep.add(marker(`hp:${hp.id}`, [hp.lon, hp.lat], `<div class="st-pin st-pin-${hp.kind}" title="${hp.name}">${HP_ICON[hp.kind] ?? "•"}</div>`, () => props.current.onHelpClick?.(hp)));
    for (const cp of q.checkpoints ?? []) keep.add(marker(`cp:${cp.id}`, [cp.lon, cp.lat], `<div class="st-pin st-pin-checkpoint" title="${cp.name}">◆</div>`));
    for (const z of q.zones ?? []) {
      const [lat, lon] = centroid(z.polygon);
      keep.add(marker(`z:${z.id}`, [lon, lat], `<div class="st-zone-badge st-zone-${z.kind === "crowd" || z.severity === "warn" ? "warn" : "danger"}">${KIND_ICON[z.kind] ?? "⚠"}</div>`, () => props.current.onZoneClick?.(z)));
    }
    for (const inc of q.incidents ?? [])
      keep.add(marker(`i:${inc.id}`, [inc.lon, inc.lat], `<div class="st-inc st-inc-${inc.priority} ${inc.selected ? "st-inc-sel" : ""} ${inc.status !== "new" ? "st-inc-ack" : ""}"><span>${inc.count}</span></div>`, () => props.current.onIncidentClick?.(inc.id)));
    for (const [k, mk] of Object.entries(markers.current))
      if (!keep.has(k)) {
        mk.remove();
        delete markers.current[k];
      }
  };

  useEffect(() => {
    if (!el.current) return;
    const bb = p.bbox;
    const m = new maplibregl.Map({
      container: el.current,
      style: style(!!p.dark),
      center: bb ? [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2] : [76.37, 30.354],
      zoom: 15,
      attributionControl: { compact: true },
    });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: false }), "top-right");
    m.on("load", () => {
      const add = (id: string) => m.addSource(id, { type: "geojson", data: fc([]) });
      ["route", "zones", "heat", "dots", "path", "draft", "acc"].forEach(add);
      m.addLayer({ id: "heat", type: "fill", source: "heat", paint: { "fill-color": ["match", ["get", "level"], "red", "#D93025", "amber", "#F59E0B", "#22C55E"], "fill-opacity": 0.38 } });
      m.addLayer({ id: "route-casing", type: "line", source: "route", paint: { "line-color": "#ffffff", "line-width": 9, "line-opacity": 0.9 }, layout: { "line-cap": "round", "line-join": "round" } });
      m.addLayer({ id: "route", type: "line", source: "route", paint: { "line-color": "#1A73E8", "line-width": 5 }, layout: { "line-cap": "round", "line-join": "round" } });
      const zColor = ["case", ["any", ["==", ["get", "kind"], "crowd"], ["==", ["get", "severity"], "warn"]], "#D97706", "#D93025"] as any;
      m.addLayer({ id: "zones-fill", type: "fill", source: "zones", paint: { "fill-color": zColor, "fill-opacity": ["case", ["==", ["get", "hl"], 1], 0.34, 0.2] } });
      m.addLayer({ id: "zones-line-danger", type: "line", source: "zones", filter: ["all", ["!=", ["get", "kind"], "crowd"], ["==", ["get", "severity"], "danger"]], paint: { "line-color": "#D93025", "line-width": 2.5 } });
      m.addLayer({ id: "zones-line-warn", type: "line", source: "zones", filter: ["any", ["==", ["get", "kind"], "crowd"], ["==", ["get", "severity"], "warn"]], paint: { "line-color": "#D97706", "line-width": 2.5, "line-dasharray": [2, 1.5] } });
      m.addLayer({ id: "acc", type: "fill", source: "acc", paint: { "fill-color": "#1A73E8", "fill-opacity": 0.1 } });
      m.addLayer({ id: "path", type: "line", source: "path", paint: { "line-color": "#1E8E3E", "line-width": 5, "line-dasharray": [1.5, 1.2] }, layout: { "line-cap": "round" } });
      m.addLayer({ id: "draft-fill", type: "fill", source: "draft", filter: ["==", ["geometry-type"], "Polygon"], paint: { "fill-color": "#D93025", "fill-opacity": 0.18 } });
      m.addLayer({ id: "draft-line", type: "line", source: "draft", filter: ["==", ["geometry-type"], "LineString"], paint: { "line-color": "#D93025", "line-width": 2, "line-dasharray": [2, 1] } });
      m.addLayer({ id: "draft-pts", type: "circle", source: "draft", filter: ["==", ["geometry-type"], "Point"], paint: { "circle-radius": 5, "circle-color": "#fff", "circle-stroke-color": "#D93025", "circle-stroke-width": 2 } });
      m.addLayer({ id: "dots", type: "circle", source: "dots", paint: { "circle-radius": ["case", ["==", ["get", "sim"], 1], 4, 7], "circle-color": ["get", "color"], "circle-opacity": ["case", ["==", ["get", "sim"], 1], 0.6, 1], "circle-stroke-width": ["case", ["==", ["get", "flagged"], 1], 3, 2], "circle-stroke-color": ["case", ["==", ["get", "flagged"], 1], "#7C3AED", "#ffffff"] } });
      loaded.current = true;
      if (bb && bb.length === 4) m.fitBounds([[bb[0], bb[1]], [bb[2], bb[3]]], { padding: 60, maxZoom: 17, duration: 0 });
      syncAll();
    });
    m.on("click", (e) => {
      const q = props.current;
      const dot = q.onDotClick ? m.queryRenderedFeatures(e.point, { layers: ["dots"] })[0] : undefined;
      if (dot) {
        const d = (q.dots ?? []).find((x) => x.trip_label === dot.properties?.label);
        if (d) return q.onDotClick!(d);
      }
      if (q.onClick) return q.onClick(e.lngLat.lat, e.lngLat.lng);
      const zf = m.queryRenderedFeatures(e.point, { layers: ["zones-fill"] })[0];
      if (zf && q.onZoneClick) {
        const z = (q.zones ?? []).find((x) => x.id === zf.properties?.id);
        if (z) q.onZoneClick(z);
      }
    });
    return () => {
      Object.values(markers.current).forEach((mk) => mk.remove());
      markers.current = {};
      loaded.current = false;
      m.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.dark]);

  useEffect(() => {
    syncAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.route, p.zones, p.heat, p.dots, p.path, p.draft, p.me, p.helpPoints, p.checkpoints, p.incidents, p.highlightZoneId]);

  useEffect(() => {
    if (p.followMe && p.me && map.current && !followed.current) {
      followed.current = true;
      map.current.flyTo({ center: [p.me.lon, p.me.lat], zoom: Math.max(map.current.getZoom(), 16), duration: 800 });
    }
  }, [p.me, p.followMe]);

  useEffect(() => {
    if (p.flyTo && map.current) map.current.flyTo({ center: [p.flyTo.lon, p.flyTo.lat], zoom: p.flyTo.zoom ?? 17, duration: 700 });
  }, [p.flyTo?.key]);

  useEffect(() => {
    const bb = p.bbox;
    if (bb && bb.length === 4 && map.current && loaded.current) map.current.fitBounds([[bb[0], bb[1]], [bb[2], bb[3]]], { padding: 60, maxZoom: 17, duration: 500 });
  }, [p.bbox?.join(",")]);

  return <div ref={el} className={p.className ?? "absolute inset-0"} />;
}
