import { BellRing, Circle, LogOut, Megaphone, PenLine, ScanLine, Undo2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import MapView from "../components/MapView";
import { CostPanel, IncidentPanel, IncidentRow, LoginCard, PassScanner, RoutingRiver, TallyCard, useOpsFeed, WeatherPanel } from "../components/ops";
import { Explain, ExplainToggle, useToast } from "../components/ui";
import { api } from "../lib/api";
import { KIND_LABEL, RISK_SHORT, riskText } from "../lib/format";
import { ZoneIcon } from "../components/icons";
import { getRoleToken, setRoleToken } from "../lib/session";
import type { Dot, RouteSummary, WeatherSection } from "../lib/types";

const KINDS = ["landslide", "closed_trail", "restricted", "wildlife_core", "flood", "custom"];

function circle(lat: number, lon: number, r: number): number[][] {
  const pts = [];
  for (let i = 0; i < 32; i++) {
    const a = (i / 32) * 2 * Math.PI;
    pts.push([lon + (r * Math.sin(a)) / (111320 * Math.cos((lat * Math.PI) / 180)), lat + (r * Math.cos(a)) / 111320]);
  }
  return pts;
}

export default function Responder({ simple }: { simple?: boolean }) {
  const toast = useToast();
  const [token, setToken] = useState<string | null>(() => getRoleToken("responder") || getRoleToken("presenter"));
  const [routeId, setRouteId] = useState(simple ? "hall" : localStorage.getItem("st_r_route") || "hall");
  const feed = useOpsFeed(routeId, token);
  const [tab, setTab] = useState<"incidents" | "checks" | "ai">("incidents");
  const [sel, setSel] = useState<number | null>(null);
  const [draw, setDraw] = useState<null | { mode: "shape" | "circle"; pts: number[][]; center?: [number, number]; r: number }>(null);
  const [form, setForm] = useState(false);
  const [zk, setZk] = useState({ kind: "landslide", severity: "danger", note: "", expires: 0 });
  const [checkOpen, setCheckOpen] = useState(false);
  const [scan, setScan] = useState(false);
  const [fly, setFly] = useState<{ lat: number; lon: number; key: number } | null>(null);
  const [dotSel, setDotSel] = useState<Dot | null>(null);
  const [routes, setRoutes] = useState<RouteSummary[]>([]);
  useEffect(() => {
    api<RouteSummary[]>("/routes").then((r) => setRoutes([...r].sort((a, b) => (a.id === "hall" ? -1 : b.id === "hall" ? 1 : a.name.localeCompare(b.name))))).catch(() => {});
  }, []);

  const open = feed.incidents.filter((i) => i.status !== "cancelled");
  const pins = useMemo(() => open.filter((i) => i.status !== "resolved").map((i) => ({ id: i.id, lat: i.center_lat, lon: i.center_lon, count: i.trip_count, priority: i.priority, selected: i.id === sel, status: i.status })), [open, sel]);
  const counts = { trail: feed.dots.filter((d) => d.kind !== "sim").length, open: open.filter((i) => i.status !== "resolved").length, quiet: feed.dots.filter((d) => d.status.startsWith("quiet")).length, crowd: feed.zones.filter((z) => z.kind === "crowd").length };

  if (!token) return <div className="min-h-full bg-bg px-4"><LoginCard onDone={(t) => setToken(t)} /></div>;

  const draftPts = draw?.mode === "circle" && draw.center ? circle(draw.center[0], draw.center[1], draw.r) : draw?.pts ?? null;
  const publish = async () => {
    if (!draftPts || draftPts.length < 3) return;
    try {
      const r = await api<{ phones_notified: number }>("/zones", {
        token,
        body: { route_id: routeId, kind: zk.kind, severity: zk.severity, polygon: { type: "Polygon", coordinates: [[...draftPts, draftPts[0]]] }, note: zk.note || null, expires_in_min: zk.expires || null },
      });
      toast(`Zone published · sent to ${r.phones_notified} phones · translations on the way`, "ok");
      setDraw(null);
      setForm(false);
      setZk({ ...zk, note: "" });
    } catch (e: any) {
      if (e.status === 401) setToken(null);
      toast(e.message, "danger");
    }
  };
  const sendCheck = async (zoneId: string | null) => {
    try {
      await api("/safety-checks", { token, body: { route_id: routeId, zone_id: zoneId, message_key: zoneId ? "check_landslide" : "check_generic" } });
      toast('"Are you safe?" sent', "ok");
      setCheckOpen(false);
      setTab("checks");
    } catch (e: any) {
      toast(e.message, "danger");
    }
  };
  const locate = (label: string) => {
    const d = feed.dots.find((x) => x.trip_label === label);
    if (d) setFly({ lat: d.lat, lon: d.lon, key: Date.now() });
  };
  // Weather only suggests a zone: this pre-fills the drawing tool, and the officer adjusts it and decides whether to publish.
  const zoneFromWeather = (s: WeatherSection) => {
    setFly({ lat: s.lat, lon: s.lon, key: Date.now() });
    setDraw({ mode: "circle", pts: [], center: [s.lat, s.lon], r: 250 });
    setForm(false);
    const what = s.risks.map((r) => riskText(RISK_SHORT, r.key, r.value)).join(", ");
    setZk({ kind: "custom", severity: s.level === "danger" ? "danger" : "warn", note: `Weather warning, next 12 h: ${what}`.slice(0, 200), expires: 360 });
  };
  const logout = () => {
    setRoleToken("responder", null);
    setRoleToken("presenter", null);
    setToken(null);
  };

  if (simple) {
    return (
      <div className="flex h-full flex-col bg-bg">
        <div className="flex items-center justify-between border-b border-line bg-white p-4"><p className="text-lg font-bold">Responder · CSED block demo</p><span className={`chip ${feed.connected ? "bg-safe/10 text-safe" : "bg-black/5"}`}>{feed.connected ? "Live" : "…"}</span></div>
        {sel ? <div className="flex-1 overflow-hidden bg-white"><IncidentPanel id={sel} token={token} lastEvt={feed.lastEvt} onClose={() => setSel(null)} compact /></div> : (
          <div className="flex-1 space-y-2 overflow-y-auto p-3">
            {open.length === 0 && <p className="p-6 text-center text-muted">No SOS yet. When someone presses SOS, it appears here.</p>}
            {open.map((i) => <IncidentRow key={i.id} i={i} onClick={() => setSel(i.id)} />)}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-bg">
      <header className="z-10 flex flex-wrap items-center gap-2 border-b border-line bg-white px-3 py-2">
        <img src="/icon.svg" className="h-8 w-8" alt="" />
        <select className="rounded-lg border border-line bg-white px-2 py-1.5 font-semibold" value={routeId} onChange={(e) => { setRouteId(e.target.value); localStorage.setItem("st_r_route", e.target.value); setSel(null); }}>
          {routes.length === 0 && <option value={routeId}>{routeId}</option>}
          {routes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        <div className="flex flex-wrap gap-1.5 text-sm">
          <span className="chip bg-info/10 text-info">{counts.trail} on trail</span>
          <span className={`chip ${counts.open ? "bg-danger text-white" : "bg-black/5"}`}>{counts.open} open incidents</span>
          {counts.crowd > 0 && <span className="chip bg-caution/10 text-caution">{counts.crowd} crowd alert</span>}
          {counts.quiet > 0 && <span className="chip bg-caution/10 text-caution">{counts.quiet} quiet</span>}
          <span className={`chip ${feed.connected ? "bg-safe/10 text-safe" : "bg-black/5 text-muted"}`}>{feed.connected ? "● Live" : "Reconnecting…"}</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button className="btn-ghost min-h-[40px]" onClick={() => { setDraw({ mode: "shape", pts: [], r: 100 }); setForm(false); }}><PenLine size={16} /> Draw zone</button>
          <button className="btn-ghost min-h-[40px]" onClick={() => setCheckOpen(true)}><BellRing size={16} /> Safety check</button>
          <button className="btn-ghost min-h-[40px]" onClick={() => setScan(true)}><ScanLine size={16} /> Verify pass</button>
          <ExplainToggle />
          <button className="grid h-9 w-9 place-items-center rounded-full border border-line" title="Log out" onClick={logout}><LogOut size={16} /></button>
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1">
        <div className="relative flex-1">
          {feed.route && (
            <MapView
              bbox={feed.route.bbox}
              route={feed.route.line}
              zones={feed.zones}
              dots={feed.dots}
              heat={feed.heat}
              helpPoints={feed.route.help_points}
              incidents={pins}
              draft={draftPts}
              flyTo={fly}
              onIncidentClick={(id) => { setSel(id); setTab("incidents"); }}
              onDotClick={(d) => setDotSel(d)}
              onClick={draw ? (lat, lon) => setDraw((dr) => (dr ? (dr.mode === "circle" ? { ...dr, center: [lat, lon] } : { ...dr, pts: [...dr.pts, [lon, lat]] }) : dr)) : undefined}
            />
          )}
          <div className="pointer-events-none absolute bottom-3 left-3 max-w-xs"><Explain id="heat" /><Explain id="quiet" /></div>
          {dotSel && (
            <div className="absolute left-3 top-3 z-20 card w-64 p-3 shadow-float">
              <div className="flex justify-between"><b>{dotSel.trip_label}</b><button onClick={() => setDotSel(null)}><X size={16} /></button></div>
              <p className="text-sm">{dotSel.name} · <span className="capitalize">{dotSel.status.replace("_", " ")}</span></p>
              <p className="text-xs text-muted">±{Math.round(dotSel.accuracy_m ?? 0)} m · {dotSel.kind}</p>
              {dotSel.flags?.includes("impossible_travel") && <p className="mt-1 text-xs font-semibold text-[#7C3AED]">Impossible jump flagged</p>}
            </div>
          )}
          {draw && (
            <div className="absolute left-1/2 top-3 z-20 w-[min(560px,92%)] -translate-x-1/2 card p-3 shadow-float">
              {!form ? (
                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex rounded-full border border-line p-0.5 text-sm font-semibold">
                    <button className={`rounded-full px-3 py-1 ${draw.mode === "shape" ? "bg-ink text-white" : ""}`} onClick={() => setDraw({ ...draw, mode: "shape" })}><PenLine size={14} className="inline" /> Shape</button>
                    <button className={`rounded-full px-3 py-1 ${draw.mode === "circle" ? "bg-ink text-white" : ""}`} onClick={() => setDraw({ ...draw, mode: "circle" })}><Circle size={14} className="inline" /> Circle</button>
                  </div>
                  <p className="text-sm text-muted">{draw.mode === "shape" ? `Tap the map to add corners (${draw.pts.length})` : draw.center ? "Pick a radius" : "Tap the centre of the danger"}</p>
                  {draw.mode === "circle" && draw.center && [50, 100, 250, 500].map((r) => <button key={r} onClick={() => setDraw({ ...draw, r })} className={`chip border ${draw.r === r ? "border-danger bg-danger text-white" : "border-line"}`}>{r} m</button>)}
                  <div className="ml-auto flex gap-2">
                    {draw.mode === "shape" && <button className="btn-ghost min-h-[38px]" disabled={!draw.pts.length} onClick={() => setDraw({ ...draw, pts: draw.pts.slice(0, -1) })}><Undo2 size={16} /></button>}
                    <button className="btn-ghost min-h-[38px]" onClick={() => setDraw(null)}>Cancel</button>
                    <button className="btn-danger min-h-[38px]" disabled={!draftPts || draftPts.length < 3} onClick={() => setForm(true)}>Next</button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-1.5">{KINDS.map((k) => <button key={k} onClick={() => setZk({ ...zk, kind: k })} className={`chip border px-3 py-1.5 text-sm ${zk.kind === k ? "border-danger bg-danger text-white" : "border-line"}`}><ZoneIcon kind={k} size={14} className="-mt-0.5 mr-1 inline" />{KIND_LABEL[k]}</button>)}</div>
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-semibold">Severity</span>
                    {["danger", "warn"].map((s) => <button key={s} onClick={() => setZk({ ...zk, severity: s })} className={`chip border capitalize ${zk.severity === s ? "border-ink bg-ink text-white" : "border-line"}`}>{s === "warn" ? "Caution" : "Danger"}</button>)}
                    <span className="ml-3 font-semibold">Expires</span>
                    {[[60, "1 h"], [360, "6 h"], [1440, "24 h"], [0, "Never"]].map(([m, l]) => <button key={l} onClick={() => setZk({ ...zk, expires: m as number })} className={`chip border ${zk.expires === m ? "border-ink bg-ink text-white" : "border-line"}`}>{l}</button>)}
                  </div>
                  <input className="input" maxLength={200} placeholder="Note for tourists (optional, translated automatically)" value={zk.note} onChange={(e) => setZk({ ...zk, note: e.target.value })} />
                  <div className="flex justify-end gap-2"><button className="btn-ghost" onClick={() => setForm(false)}>Back</button><button className="btn-danger" onClick={publish}>Publish to all phones</button></div>
                </div>
              )}
            </div>
          )}
          {checkOpen && (
            <div className="absolute left-1/2 top-3 z-20 w-[min(460px,92%)] -translate-x-1/2 card p-4 shadow-float">
              <div className="flex justify-between"><p className="font-bold">Send "Are you safe?" to…</p><button onClick={() => setCheckOpen(false)}><X size={18} /></button></div>
              <div className="mt-3 space-y-2">
                {feed.zones.filter((z) => z.kind !== "crowd").map((z) => <button key={z.id} onClick={() => sendCheck(z.id)} className="btn-ghost w-full justify-start"><ZoneIcon kind={z.kind} size={16} className="mr-1 inline" />Everyone in or recently in: {KIND_LABEL[z.kind]} {z.segment_name ? `· ${z.segment_name}` : ""}</button>)}
                <button onClick={() => sendCheck(null)} className="btn-ghost w-full justify-start"><Megaphone size={16} className="mr-1 inline" />Everyone on this route</button>
              </div>
            </div>
          )}
        </div>

        <aside className="flex w-[420px] max-w-[48vw] flex-col border-l border-line bg-white">
          {sel ? (
            <IncidentPanel id={sel} token={token} lastEvt={feed.lastEvt} onClose={() => setSel(null)} />
          ) : (
            <>
              <div className="flex gap-1 border-b border-line p-2">
                {([["incidents", `Incidents (${counts.open})`], ["checks", "Checks"], ["ai", "AI & cost"]] as const).map(([k, l]) => <button key={k} onClick={() => setTab(k)} className={`rounded-full px-4 py-1.5 text-sm font-semibold ${tab === k ? "bg-ink text-white" : "text-muted"}`}>{l}</button>)}
              </div>
              <div className="flex-1 space-y-2 overflow-y-auto p-3">
                {tab === "incidents" && (
                  <>
                    <WeatherPanel weather={feed.weather} onLocate={(s) => setFly({ lat: s.lat, lon: s.lon, key: Date.now() })} onDrawZone={zoneFromWeather} />
                    {open.length === 0 && <p className="p-6 text-center text-muted">No incidents. SOS reports appear here, grouped by place, newest first.</p>}
                    {[...open].sort((a, b) => (a.status === "resolved" ? 1 : 0) - (b.status === "resolved" ? 1 : 0) || a.priority.localeCompare(b.priority) || b.last_sos_at - a.last_sos_at).map((i) => <IncidentRow key={i.id} i={i} onClick={() => setSel(i.id)} />)}
                    <div className="pt-3">
                      <p className="label">Live feed</p>
                      {feed.ticker.slice(0, 12).map((t, k) => <p key={k} className={`border-b border-black/5 py-1.5 text-sm ${t.tone === "danger" ? "text-danger" : t.tone === "warn" ? "text-caution" : t.tone === "ok" ? "text-safe" : ""}`}>{t.text}</p>)}
                    </div>
                  </>
                )}
                {tab === "checks" && (feed.tally ? <TallyCard t={feed.tally} onLocate={locate} /> : <p className="p-6 text-center text-muted">No safety check sent yet. Use "Safety check" above.</p>)}
                {tab === "ai" && (
                  <>
                    <RoutingRiver dots={feed.river} />
                    <CostPanel token={token} aiTick={feed.aiTick} />
                    <a href="/benchmark" className="btn-ghost w-full">Benchmark R1–R4: cost per trip vs naive →</a>
                  </>
                )}
              </div>
            </>
          )}
        </aside>
      </div>
      {scan && feed.config && <PassScanner pubkey={feed.config.pass_pubkey} token={token} zones={feed.zones} onClose={() => setScan(false)} />}
    </div>
  );
}
