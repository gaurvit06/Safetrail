import { BrowserQRCodeReader, type IScannerControls } from "@zxing/browser";
import { Check, ChevronDown, ChevronRight, ExternalLink, KeyRound, Link2, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, connectEvents } from "../lib/api";
import { ago, clock, duration, hm, inr, KIND_LABEL, RISK_SHORT, riskText, SOS_ICON, usd, weatherIcon } from "../lib/format";
import { setRoleToken } from "../lib/session";
import type { AiStats, Config, Dot, Evt, HeatCell, IncidentDetail, IncidentSummary, LlmCallBrief, RouteDetail, Tally, Weather, WeatherSection, Zone } from "../lib/types";
import { verifyEntries, verifyPassOffline, type EntryCheck, type LogEntry } from "../lib/verify";
import { Explain, SourceTag, Spinner, useToast } from "./ui";

/* ================================================================ live feed for responders + stage */
export type TickerItem = { ts: number; text: string; tone: "info" | "ok" | "warn" | "danger" };
export type RiverDot = { id: number; feature: string; lane: "SMALL" | "LARGE" | "ROUTED" | "CACHE" | "STOPPED"; ts: number; cost: number | null };

function laneOf(d: any): RiverDot["lane"] {
  if (d.status === "error" || d.error_code) return "STOPPED";
  if (d.cache_hit) return "CACHE";
  if (d.route_applied) return "ROUTED";
  return d.tier === "large" ? "LARGE" : "SMALL";
}

export function useOpsFeed(routeId: string, token: string | null) {
  const [route, setRoute] = useState<RouteDetail | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [dots, setDots] = useState<Record<string, Dot>>({});
  const [incidents, setIncidents] = useState<Record<number, IncidentSummary>>({});
  const [heat, setHeat] = useState<HeatCell[]>([]);
  const [tally, setTally] = useState<Tally | null>(null);
  const [river, setRiver] = useState<RiverDot[]>([]);
  const [ticker, setTicker] = useState<TickerItem[]>([]);
  const [board, setBoard] = useState<any[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastEvt, setLastEvt] = useState<Evt | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [aiTick, setAiTick] = useState(0);
  const [weather, setWeather] = useState<Weather | null>(null); // null = still loading
  const tick = (text: string, tone: TickerItem["tone"] = "info") => setTicker((x) => [{ ts: Date.now() / 1000, text, tone }, ...x].slice(0, 40));

  // Weather loads on its own so a slow forecast never delays the map, incidents or SOS.
  useEffect(() => {
    let live = true;
    setWeather(null);
    api<Weather>(`/weather?route_id=${routeId}`)
      .then((w) => live && setWeather(w))
      .catch(() => live && setWeather({ route_id: routeId, available: false, sections: [], level: "none", attribution: "" }));
    return () => {
      live = false;
    };
  }, [routeId]);

  const load = useCallback(async () => {
    if (!token) return;
    const [r, incs, st, h, cfg] = await Promise.all([
      api<RouteDetail>(`/routes/${routeId}`),
      api<IncidentSummary[]>(`/incidents?route_id=${routeId}`, { token }),
      api<any>(`/stage/state?route_id=${routeId}`, { token }),
      api<any>(`/crowd/heat?route_id=${routeId}`, { token }),
      api<Config>("/config"),
    ]);
    setRoute(r);
    setZones(r.zones);
    setIncidents(Object.fromEntries(incs.map((i) => [i.id, i])));
    setDots(Object.fromEntries((st.positions as Dot[]).map((d) => [d.trip_label, d])));
    setBoard(st.board);
    setTally(st.check);
    setHeat(h.cells ?? []);
    setConfig(cfg);
  }, [routeId, token]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  useEffect(() => {
    if (!token) return;
    const onEvt = (e: Evt) => {
      if (e.route_id && e.route_id !== routeId && !["ai.call", "ai.stopped", "ai.budget_skip", "system.degraded", "breakit.result", "stage.reset"].includes(e.type)) return;
      const d = e.data;
      setLastEvt(e);
      switch (e.type) {
        case "trip.started":
          tick(`${d.trip_label} joined the trail`);
          break;
        case "trip.position":
          setDots((x) => ({ ...x, [d.trip_label]: { ...x[d.trip_label], ...d } }));
          if (d.flags?.includes("impossible_travel")) tick(`${d.trip_label}: impossible jump flagged (position not updated)`, "warn");
          break;
        case "trip.ended":
          setDots((x) => {
            const n = { ...x };
            delete n[d.trip_label];
            return n;
          });
          break;
        case "trip.quiet":
          setDots((x) => (x[d.trip_label] ? { ...x, [d.trip_label]: { ...x[d.trip_label], status: d.level } } : x));
          tick(`${d.trip_label} has been quiet for ${d.minutes} min`, "warn");
          break;
        case "zone.published":
          setZones((zs) => [...zs.filter((z) => z.id !== d.zone.id), d.zone]);
          if (d.zone.source !== "auto_crowd") tick(`Zone published: ${KIND_LABEL[d.zone.kind] ?? d.zone.kind}${d.zone.segment_name ? ` · ${d.zone.segment_name}` : ""}`, "danger");
          break;
        case "zone.advisory_ready":
          setZones((zs) => zs.map((z) => (z.id === d.zone_id ? { ...z, advisories: { ...z.advisories, ...d.advisories } } : z)));
          tick(`Warnings ready in ${Object.keys(d.advisories).length} languages (${d.source === "ai" ? "AI" : d.source === "template" ? "standard text" : "mixed"})`, "ok");
          break;
        case "zone.removed":
          setZones((zs) => zs.filter((z) => z.id !== d.zone_id));
          break;
        case "zone.entered":
          tick(`${d.trip_label} entered a ${KIND_LABEL[d.kind] ?? d.kind} zone`, "danger");
          break;
        case "zone.approach":
          tick(`${d.trip_label} is approaching a ${KIND_LABEL[d.kind] ?? d.kind} zone`, "warn");
          break;
        case "crowd.heat":
          setHeat(d.cells);
          break;
        case "crowd.red":
          tick(`Crowd building: ${d.people} people in one spot`, "warn");
          break;
        case "sos.received":
          setDots((x) => (x[d.trip_label] ? { ...x, [d.trip_label]: { ...x[d.trip_label], status: "sos" } } : x));
          tick(`SOS from ${d.trip_label}: ${d.kind}${d.delay_s > 10 ? ` · arrived ${duration(d.delay_s)} after it was pressed` : ""}`, "danger");
          break;
        case "incident.updated":
          setIncidents((x) => ({ ...x, [d.id]: d }));
          break;
        case "incident.status":
          setIncidents((x) => (x[d.incident_id] ? { ...x, [d.incident_id]: { ...x[d.incident_id], status: d.status, team: d.team } } : x));
          tick(`Incident #${d.incident_id}: ${d.status.replace("_", " ")}`, "ok");
          break;
        case "incident.summary_ready":
        case "incident.report_ready":
          setIncidents((x) => {
            const i = x[d.incident_id];
            if (!i) return x;
            const headline = e.type === "incident.summary_ready" ? d.content?.summary : i.type === "single" ? d.content?.headline : i.headline;
            return { ...x, [d.incident_id]: { ...i, headline: headline ?? i.headline, headline_source: d.source } };
          });
          break;
        case "check.tally":
          setTally(d);
          break;
        case "ai.call": {
          const rd: RiverDot = { id: d.call_id, feature: d.feature, lane: laneOf(d), ts: Date.now(), cost: d.cost_with_usd };
          setRiver((x) => [...x.filter((r) => Date.now() - r.ts < 4000), rd].slice(-40));
          setAiTick((n) => n + 1);
          break;
        }
        case "ai.stopped":
        case "ai.budget_skip":
          setRiver((x) => [...x, { id: Date.now(), feature: d.feature, lane: "STOPPED" as const, ts: Date.now(), cost: null }].slice(-40));
          tick(`${d.by === "governor" ? "Budget governor" : `Prune (${d.by})`} stopped ${d.feature} → standard text. Alerts unaffected.`, "warn");
          setAiTick((n) => n + 1);
          break;
        case "system.degraded":
          tick(`AI paused: ${d.reason}. Safety features keep working.`, "warn");
          break;
        case "weather.updated": {
          if (!d.weather?.available) break;
          setWeather(d.weather);
          const bad = (d.weather.sections as WeatherSection[]).map((s) => ({ s, r: s.risks.find((x) => x.level === "danger") })).filter((x) => x.r);
          if (bad.length) tick(`Weather: ${bad.map(({ s, r }) => `${riskText(RISK_SHORT, r!.key, r!.value)} · ${s.name}`).join("; ")}`, "danger");
          break;
        }
        case "breakit.result":
          setBoard((b) => [d, ...b].slice(0, 30));
          tick(`Break it: ${d.nickname} tried ${d.trick.replace("_", " ")} → ${d.outcome.replace("_", " ")}`, d.outcome === "slipped" ? "danger" : "ok");
          break;
        case "stage.reset":
          load();
          setTicker([]);
          setRiver([]);
          break;
      }
    };
    return connectEvents(token, onEvt, setConnected);
  }, [token, routeId, load]);

  return { route, zones, dots: Object.values(dots), incidents: Object.values(incidents).sort((a, b) => b.id - a.id), heat, tally, river, ticker, board, connected, lastEvt, config, aiTick, weather, reload: load };
}

/* ================================================================ weather along the route (responder) */
const WX_CHIP: Record<WeatherSection["level"], string> = {
  danger: "border-danger bg-danger text-white",
  warn: "border-caution/40 bg-caution/10 text-caution",
  none: "border-line",
};

export function WeatherPanel({ weather, onLocate, onDrawZone }: { weather: Weather | null; onLocate?: (s: WeatherSection) => void; onDrawZone?: (s: WeatherSection) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!weather) return <div className="flex items-center gap-2 rounded-2xl border border-line p-3 text-sm text-muted"><Spinner /> Loading weather…</div>;
  if (!weather.available) return <p className="rounded-2xl border border-line p-3 text-sm text-muted">Weather isn't available right now. Zone alerts and SOS don't depend on it.</p>;
  const sel = weather.sections.find((s) => s.segment_id === open) ?? null;
  const warned = weather.sections.filter((s) => s.level !== "none").length;
  const top = (s: WeatherSection) => s.risks.find((r) => r.level === "danger") ?? s.risks[0];
  const n = (v: number | null | undefined) => (v === null || v === undefined ? "–" : Math.round(v));
  return (
    <div className="rounded-2xl border border-line p-3">
      <div className="flex items-baseline justify-between gap-2">
        <p className="shrink-0 text-sm font-semibold">Weather · next {weather.hours_ahead ?? 12} h</p>
        <p className={`text-right text-xs ${weather.stale ? "font-semibold text-caution" : "text-muted"}`}>{weather.stale ? "Last forecast" : "Updated"} {ago(weather.fetched_at)} · {weather.source}</p>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {weather.sections.map((s) => {
          const r = top(s);
          return (
            <button
              key={s.segment_id}
              title={s.risks.map((x) => riskText(RISK_SHORT, x.key, x.value)).join(", ") || "No warnings"}
              onClick={() => {
                setOpen(open === s.segment_id ? null : s.segment_id);
                onLocate?.(s);
              }}
              className={`chip border px-2.5 py-1 text-xs ${WX_CHIP[s.level]} ${open === s.segment_id ? "ring-2 ring-ink/30" : ""}`}
            >
              {weatherIcon(s.now.code)} {s.name} · {n(s.now.temp_c)}°{r ? ` · ${riskText(RISK_SHORT, r.key, r.value)}` : ""}
            </button>
          );
        })}
      </div>
      {sel ? (
        <div className="mt-2 rounded-xl bg-black/[.03] p-2.5 text-sm">
          <p className="font-semibold">{weatherIcon(sel.now.code)} {sel.name} · {n(sel.now.temp_c)}° · {sel.now.desc}{sel.elevation_m ? ` · ${Math.round(sel.elevation_m)} m` : ""}</p>
          <p className="text-xs text-muted">
            Next {weather.hours_ahead ?? 12} h: {n(sel.next12h.temp_min)}° to {n(sel.next12h.temp_max)}° · rain {sel.next12h.rain_12h} mm ({sel.next12h.rain_prob_max}% max chance) · snow {sel.next12h.snow_12h} cm · gusts {sel.next12h.gust_max} km/h
          </p>
          {sel.risks.length === 0 && <p className="mt-1 text-xs text-safe">No warnings for this section.</p>}
          {sel.risks.map((r) => <p key={r.key} className={`mt-1 text-xs font-semibold ${r.level === "danger" ? "text-danger" : "text-caution"}`}>⚠ {riskText(RISK_SHORT, r.key, r.value)}</p>)}
          {sel.level !== "none" && onDrawZone && (
            <button className="btn-ghost mt-2 min-h-[36px] text-sm" onClick={() => onDrawZone(sel)}>Draw a zone here</button>
          )}
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted">{warned ? `${warned} of ${weather.sections.length} sections have warnings. Tap one for details.` : "No weather warnings on this route."}</p>
      )}
      <Explain id="weather" />
      <p className="mt-1 text-[10px] text-muted">{weather.attribution}</p>
    </div>
  );
}

/* ================================================================ login */
export function LoginCard({ roles = ["responder", "presenter"], onDone, dark }: { roles?: ("responder" | "presenter")[]; onDone: (token: string, role: string) => void; dark?: boolean }) {
  const [role, setRole] = useState<"responder" | "presenter">(roles[0]);
  const [pin, setPin] = useState("");
  const [err, setErr] = useState("");
  const submit = async () => {
    try {
      const r = await api<{ token: string; role: "responder" | "presenter" }>("/auth/login", { body: { role, pin } });
      setRoleToken(r.role, r.token);
      onDone(r.token, r.role);
    } catch (e: any) {
      setErr(e.message);
    }
  };
  return (
    <div className={`mx-auto mt-16 w-full max-w-sm rounded-sheet p-6 ${dark ? "bg-night-surface text-night-text" : "card"}`}>
      <div className="flex items-center gap-2 text-lg font-bold"><KeyRound size={20} /> Staff login</div>
      {roles.length > 1 && (
        <div className="mt-4 flex gap-2">
          {roles.map((r) => <button key={r} onClick={() => setRole(r)} className={`chip border px-3 py-2 text-sm capitalize ${role === r ? "border-brand bg-brand text-white" : dark ? "border-night-line" : "border-line"}`}>{r}</button>)}
        </div>
      )}
      <input className="input mt-4 text-center font-mono text-2xl tracking-[0.4em] text-ink" inputMode="numeric" placeholder="PIN" value={pin} onChange={(e) => setPin(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
      {err && <p className="mt-2 text-sm text-danger">{err}</p>}
      <button className="btn-primary mt-4 w-full" onClick={submit}>Log in</button>
      <p className="mt-3 text-center text-xs opacity-60">Demo PINs are set in .env (RESPONDER_PIN, PRESENTER_PIN)</p>
    </div>
  );
}

/* ================================================================ routing river */
const LANES: { key: RiverDot["lane"]; label: string; color: string }[] = [
  { key: "SMALL", label: "SMALL", color: "#1A73E8" },
  { key: "LARGE", label: "LARGE", color: "#7C3AED" },
  { key: "ROUTED", label: "ROUTED", color: "#0EA5E9" },
  { key: "CACHE", label: "CACHE", color: "#EAB308" },
  { key: "STOPPED", label: "STOPPED", color: "#D93025" },
];

export function RoutingRiver({ dots, dark, totals }: { dots: RiverDot[]; dark?: boolean; totals?: Partial<Record<RiverDot["lane"], number>> }) {
  return (
    <div className={`rounded-2xl p-3 ${dark ? "bg-night-surface" : "bg-black/[.03]"}`}>
      <style>{`@keyframes river { from { left: 0% } to { left: calc(100% - 12px) } }`}</style>
      {LANES.map((l) => (
        <div key={l.key} className="flex items-center gap-2 py-1">
          <span className="w-16 text-[11px] font-bold" style={{ color: l.color }}>{l.label}</span>
          <div className={`relative h-3 flex-1 rounded-full ${dark ? "bg-white/10" : "bg-black/5"}`}>
            {dots.filter((d) => d.lane === l.key).map((d) => (
              <span key={d.id + d.lane} title={d.feature} className="absolute top-0 h-3 w-3 rounded-full shadow" style={{ background: l.color, animation: "river 1.6s ease-out forwards", boxShadow: l.key === "CACHE" ? "0 0 10px #EAB308" : undefined }} />
            ))}
          </div>
          {totals && <span className={`w-8 text-right font-mono text-xs ${dark ? "text-night-text/70" : "text-muted"}`}>{totals[l.key] ?? 0}</span>}
        </div>
      ))}
      <Explain id="routingRiver" dark={dark} />
    </div>
  );
}

/* ================================================================ AI & cost */
export function CostPanel({ token, aiTick, dark }: { token: string; aiTick: number; dark?: boolean }) {
  const [s, setS] = useState<AiStats | null>(null);
  const [calls, setCalls] = useState<(LlmCallBrief & any)[]>([]);
  const [open, setOpen] = useState<number | null>(null);
  useEffect(() => {
    const load = () => {
      api<AiStats>("/ai/stats", { token }).then(setS).catch(() => {});
      api<any[]>("/ai/calls?limit=60", { token }).then(setCalls).catch(() => {});
    };
    load();
    const i = setInterval(load, 10000);
    return () => clearInterval(i);
  }, [token, aiTick]);
  if (!s) return <div className="p-6"><Spinner /></div>;
  const max = Math.max(s.prune_estimate_without_usd ?? 0, s.cost_usd ?? 0, 1e-9);
  const pct = (n: number, d: number) => (d ? `${Math.round((100 * n) / d)}%` : "–");
  const muted = dark ? "text-night-text/60" : "text-muted";
  return (
    <div className="space-y-4">
      {!s.ai_configured && (
        <div className="rounded-xl border border-caution/40 bg-caution/10 p-3 text-sm">
          <b>AI is off:</b> add the Prune keys and model names to <code>.env</code>. Until then every AI feature uses standard text, and every safety feature still works. That's the design.
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Stat label="AI cost today" value={usd(s.cost_usd)} sub={inr(s.cost_usd, s.usd_inr)} dark={dark} />
        <Stat label="AI calls" value={String(s.ok_calls)} sub={`${s.errors} errors`} dark={dark} />
        <Stat label="Cost per monitored trip" value={usd(s.cost_per_trip_usd, 6)} sub={`${s.trips_started} trips`} dark={dark} />
        <Stat label="Cost per emergency" value={usd(s.cost_per_emergency_usd, 6)} sub={`${s.incidents} incidents`} dark={dark} />
        <Stat label="Served from Prune cache" value={pct(s.cache_hits, s.ok_calls)} sub={`${s.cache_hits} calls`} dark={dark} />
        <Stat label="Routed to a cheaper model" value={pct(s.routed, s.ok_calls)} sub={`${s.escalations} escalations`} dark={dark} />
        <Stat label="Standard-text fallbacks" value={String(s.template_fallbacks)} sub="AI never blocks safety" dark={dark} />
        <Stat label="Invented facts rejected" value={String(s.validator_rejections)} sub="by our validators" dark={dark} />
      </div>
      <div>
        <p className="text-sm font-semibold">Cost meters</p>
        <Meter label="Prune estimate without optimisations (list price)" v={s.prune_estimate_without_usd} max={max} color="#D93025" dark={dark} />
        <Meter label="Actual with Prune" v={s.cost_usd} max={max} color="#1E8E3E" dark={dark} />
        <Explain id="costMeters" dark={dark} />
      </div>
      <div>
        <p className="text-sm font-semibold">By feature</p>
        <table className="mt-1 w-full text-sm">
          <thead className={muted}><tr><th className="text-left font-medium">Feature</th><th className="text-right font-medium">Calls</th><th className="text-right font-medium">Cache</th><th className="text-right font-medium">Cost</th></tr></thead>
          <tbody>
            {Object.entries(s.by_feature).map(([f, b]) => (
              <tr key={f} className="border-t border-black/5"><td className="py-1 capitalize">{f}</td><td className="text-right font-mono">{b.calls}</td><td className="text-right font-mono">{b.cache_hits}</td><td className="text-right font-mono">{b.cost_known ? usd(b.cost_usd) : "n/a"}</td></tr>
            ))}
            {!Object.keys(s.by_feature).length && <tr><td colSpan={4} className={`py-2 ${muted}`}>No AI calls yet.</td></tr>}
          </tbody>
        </table>
      </div>
      <div>
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold">Receipts</p>
          <a className="flex items-center gap-1 text-sm font-semibold text-brand" href="https://withprune.com/verify" target="_blank" rel="noreferrer">Verify on Prune <ExternalLink size={14} /></a>
        </div>
        <Explain id="receipts" dark={dark} />
        <div className="mt-2 space-y-1">
          {calls.map((c) => (
            <div key={c.id} className={`rounded-lg ${dark ? "bg-white/5" : "bg-black/[.03]"}`}>
              <button className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm" onClick={() => setOpen(open === c.id ? null : c.id)}>
                {open === c.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <span className="w-14 font-mono text-xs">{hm(c.created_at)}</span>
                <span className="flex-1 capitalize">{c.feature}{c.escalated ? " ↑" : ""}</span>
                <span className="chip bg-black/5 text-[10px]">{c.status === "ok" || c.status === "retried" ? (c.cache_hit ? "cache" : c.route_applied ? "routed" : c.tier || "ok") : c.error_code}</span>
                <span className="w-20 text-right font-mono text-xs">{usd(c.cost_with_prune_usd, 6)}</span>
              </button>
              {open === c.id && (
                <div className="space-y-1 px-3 pb-3 font-mono text-xs">
                  <p>requested: {c.requested_model} → routed: {c.routed_model ?? "n/a"} {c.route_reason ? `(${c.route_reason})` : ""}</p>
                  <p>tokens: {c.prompt_tokens ?? "n/a"} in / {c.completion_tokens ?? "n/a"} out · saved {c.tokens_saved ?? "n/a"} · {c.latency_ms ?? "–"} ms · key {c.key_used}</p>
                  <p>Prune estimate (list price): {usd(c.cost_without_prune_usd, 6)} · shield: {c.shield_code ?? "–"}</p>
                  <p className="break-all">signature: {c.receipt_signature ? `${String(c.receipt_signature).slice(0, 48)}…` : "n/a"} · key {c.receipt_signing_key_id ?? "n/a"}</p>
                  <p>run: {c.run_id}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, sub, dark }: { label: string; value: string; sub?: string; dark?: boolean }) {
  return (
    <div className={`rounded-xl p-3 ${dark ? "bg-white/5" : "bg-black/[.03]"}`}>
      <p className={`text-xs ${dark ? "text-night-text/60" : "text-muted"}`}>{label}</p>
      <p className="font-mono text-lg font-bold">{value}</p>
      {sub && <p className={`text-xs ${dark ? "text-night-text/60" : "text-muted"}`}>{sub}</p>}
    </div>
  );
}

function Meter({ label, v, max, color, dark }: { label: string; v: number | null; max: number; color: string; dark?: boolean }) {
  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs"><span>{label}</span><span className="font-mono">{usd(v)}</span></div>
      <div className={`mt-1 h-3 rounded-full ${dark ? "bg-white/10" : "bg-black/5"}`}><div className="h-3 rounded-full transition-all duration-700" style={{ width: `${v ? Math.max(2, (100 * v) / max) : 0}%`, background: color }} /></div>
    </div>
  );
}

/* ================================================================ incidents */
const PRI = { P1: "bg-danger text-white", P2: "bg-caution text-white", P3: "bg-info text-white" } as const;
const FLAG_LABEL: Record<string, string> = { suspicious_text: "Suspicious text", prune_injection_signal: "Prune injection signal", flood: "SOS flood", duplicate_seen: "Duplicate resent", impossible_travel: "Impossible travel", breakit: "Break-it test" };

export function IncidentRow({ i, selected, onClick }: { i: IncidentSummary; selected?: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`card w-full p-3 text-left transition ${selected ? "border-2 border-brand" : ""} ${i.status === "resolved" ? "opacity-60" : ""}`}>
      <div className="flex items-center gap-2">
        <span className={`chip ${PRI[i.priority]}`}>{i.priority}</span>
        <span className="font-semibold">#{i.id} · {i.type === "cluster" ? `${i.trip_count} groups` : "single"}</span>
        <span className="ml-auto text-xs text-muted">{ago(i.first_sos_at)}</span>
      </div>
      <p className="mt-1 line-clamp-2 text-sm">{i.headline ?? "…"}</p>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
        <span className="chip bg-black/5">👥 {i.people_total}</span>
        {i.injured_total > 0 && <span className="chip bg-danger/10 text-danger">🩹 {i.injured_total}</span>}
        <span className="chip bg-black/5 capitalize">{i.status.replace("_", " ")}</span>
        {i.flags.filter((f) => FLAG_LABEL[f]).map((f) => <span key={f} className="chip bg-[#7C3AED]/10 text-[#7C3AED]">{FLAG_LABEL[f]}</span>)}
      </div>
    </button>
  );
}

export function IncidentPanel({ id, token, lastEvt, onClose, compact }: { id: number; token: string; lastEvt: Evt | null; onClose: () => void; compact?: boolean }) {
  const toast = useToast();
  const [d, setD] = useState<IncidentDetail | null>(null);
  const [tab, setTab] = useState<"details" | "timeline">("details");
  const [busy, setBusy] = useState(false);
  const [briefing, setBriefing] = useState(false);
  const [showOrig, setShowOrig] = useState(false);
  const load = useCallback(() => api<IncidentDetail>(`/incidents/${id}`, { token }).then(setD).catch(() => {}), [id, token]);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    const e = lastEvt;
    if (!e) return;
    const iid = e.data?.incident_id ?? (e.type === "incident.updated" ? e.data?.id : undefined);
    if (iid === id) {
      load();
      if (e.type === "incident.brief_ready") setBriefing(false);
    }
  }, [lastEvt, id, load]);

  const setStatus = async (status: string) => {
    setBusy(true);
    try {
      await api(`/incidents/${id}/status`, { token, body: { status } });
      toast(status === "accepted" ? "Accepted. The tourists' phones now show 'Help acknowledged'." : `Marked ${status.replace("_", " ")}`, "ok");
      load();
    } catch (e: any) {
      toast(e.message, "danger");
    } finally {
      setBusy(false);
    }
  };
  const brief = async () => {
    setBriefing(true);
    await api(`/incidents/${id}/brief`, { token, body: {} }).catch(() => setBriefing(false));
    setTimeout(() => {
      load();
      setBriefing(false);
    }, 12000);
  };

  if (!d) return <div className="p-6"><Spinner /></div>;
  const summary = d.type === "cluster" ? d.cluster_summary : d.report;
  const src = d.type === "cluster" ? d.summary_source : d.report_source;
  const call = d.llm_calls.find((c) => c.status === "ok" || c.status === "retried");
  const next = { new: "accepted", accepted: "en_route", en_route: "resolved" }[d.status as "new" | "accepted" | "en_route"];
  const nextLabel = { accepted: "Accept", en_route: "Team en route", resolved: "Resolved" }[next as "accepted" | "en_route" | "resolved"];

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start gap-2 border-b border-line p-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2"><span className={`chip ${PRI[d.priority]}`}>{d.priority}</span><span className="text-sm text-muted">#{d.id} · first SOS {ago(d.first_sos_at)}</span></div>
          <p className="mt-1 text-lg font-bold leading-snug">{d.headline}</p>
          <p className="text-sm text-muted">{d.segment_name || "Unknown section"} · radius {Math.round(d.radius_m)} m</p>
        </div>
        <button onClick={onClose} className="grid h-9 w-9 place-items-center rounded-full bg-black/5"><X size={16} /></button>
      </div>
      {!compact && (
        <div className="flex gap-1 border-b border-line px-3 py-2">
          {(["details", "timeline"] as const).map((x) => <button key={x} onClick={() => setTab(x)} className={`rounded-full px-4 py-1.5 text-sm font-semibold capitalize ${tab === x ? "bg-ink text-white" : "text-muted"}`}>{x}</button>)}
        </div>
      )}
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {tab === "details" ? (
          <>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-black/[.03] p-2"><p className="font-mono text-2xl font-bold">{d.people_total}</p><p className="text-xs text-muted">people</p></div>
              <div className="rounded-xl bg-danger/5 p-2"><p className="font-mono text-2xl font-bold text-danger">{d.injured_total}</p><p className="text-xs text-muted">injury reports</p></div>
              <div className="rounded-xl bg-black/[.03] p-2"><p className="font-mono text-2xl font-bold">{d.member_count}</p><p className="text-xs text-muted">SOS ({d.trip_count} groups)</p></div>
            </div>
            <Explain id="counts" />
            {d.flags.filter((f) => FLAG_LABEL[f]).length > 0 && <div className="flex flex-wrap gap-1.5">{d.flags.filter((f) => FLAG_LABEL[f]).map((f) => <span key={f} className="chip bg-[#7C3AED]/10 text-[#7C3AED]"><ShieldAlert size={12} />{FLAG_LABEL[f]}</span>)}</div>}
            {summary && (
              <div className="card p-3">
                <p className="text-sm font-semibold">{d.type === "cluster" ? "Summary" : "Report"}</p>
                <p className="mt-1">{summary.summary ?? summary.headline}</p>
                {summary.what_we_know && <ul className="mt-2 list-disc pl-5 text-sm">{summary.what_we_know.map((x: string) => <li key={x}>{x}</li>)}</ul>}
                {summary.needs?.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{summary.needs.map((n: string) => <span key={n} className="chip bg-info/10 text-info">{n.replace("_", " ")}</span>)}</div>}
                {summary.budget_limit && <span className="chip mt-2 bg-caution/10 text-caution">Budget limit reached · counts still live</span>}
                <div className="mt-2"><SourceTag source={src} cost={call?.cost_with_prune_usd} model={call?.tier} /></div>
                {src === "template" && <Explain id="template" />}
              </div>
            )}
            {d.report?.suggested_questions?.length > 0 && (
              <div>
                <p className="text-sm font-semibold">Ask the tourist</p>
                <ul className="mt-1 space-y-1 text-sm">{d.report.suggested_questions.map((q: string) => <li key={q} className="rounded-lg bg-black/[.03] px-3 py-2">“{q}”</li>)}</ul>
              </div>
            )}
            <div>
              <div className="flex items-center justify-between"><p className="text-sm font-semibold">SOS reports</p><button className="text-xs font-semibold text-brand" onClick={() => setShowOrig((v) => !v)}>{showOrig ? "Show translation" : "Show original"}</button></div>
              <div className="mt-1 space-y-2">
                {d.sos.map((s) => (
                  <div key={s.client_id} className={`rounded-xl border border-line p-3 text-sm ${s.cancelled_at ? "opacity-50" : ""}`}>
                    <div className="flex items-center gap-2"><span className="text-lg">{SOS_ICON[s.kind]}</span><b>{s.trip_label}</b><span className="text-muted">{s.name}</span><span className="ml-auto chip bg-black/5">{s.people_bucket} ppl</span></div>
                    {s.note_text && <p className="mt-1">“{showOrig || d.type === "cluster" ? s.note_text : d.report?.translated_note || s.note_text}”</p>}
                    <p className="mt-1 text-xs text-muted">{clock(s.created_at_device)} pressed · received {clock(s.received_at_server)}{s.delay_s > 5 ? ` (delay ${duration(s.delay_s)})` : ""} · via {s.channel} · ±{Math.round(s.accuracy_m)} m{s.cancelled_at ? " · cancelled" : ""}</p>
                    {s.flags.filter((f) => FLAG_LABEL[f]).length > 0 && <div className="mt-1 flex flex-wrap gap-1">{s.flags.filter((f) => FLAG_LABEL[f]).map((f) => <span key={f} className="chip bg-[#7C3AED]/10 text-[#7C3AED]">{FLAG_LABEL[f]}</span>)}</div>}
                  </div>
                ))}
              </div>
            </div>
            {d.brief && (
              <div className="card p-3">
                <p className="text-sm font-semibold">Next steps (copilot)</p>
                <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm">{d.brief.steps.map((st: any) => <li key={st.sop_id + st.text}>{st.text} <span className="font-mono text-xs text-muted">[{st.sop_id}]</span></li>)}</ol>
                {d.brief.help_points?.length > 0 && <p className="mt-2 text-xs text-muted">Nearby: {d.brief.help_points.map((h: any) => h.name).join(" · ")}</p>}
                <div className="mt-2"><SourceTag source={d.brief_source} /></div>
              </div>
            )}
          </>
        ) : (
          <Timeline id={id} token={token} />
        )}
      </div>
      <div className="grid gap-2 border-t border-line p-3">
        {next && <button className={next === "accepted" ? "btn-danger text-lg" : "btn-primary"} disabled={busy} onClick={() => setStatus(next)}>{busy ? <Spinner /> : <Check size={18} />} {nextLabel}</button>}
        {!next && <p className="text-center font-semibold text-safe">Resolved {hm(d.resolved_at)}</p>}
        {!compact && <button className="btn-ghost" disabled={briefing} onClick={brief}>{briefing ? <Spinner /> : null} Brief me (SOP next steps)</button>}
      </div>
    </div>
  );
}

function Timeline({ id, token }: { id: number; token: string }) {
  const [data, setData] = useState<{ entries: LogEntry[]; pubkey: string; chain_check: any } | null>(null);
  const [checks, setChecks] = useState<EntryCheck[] | null>(null);
  const [verifying, setVerifying] = useState(false);
  useEffect(() => {
    api(`/incidents/${id}/timeline`, { token }).then(setData).catch(() => {});
  }, [id, token]);
  const verify = async () => {
    if (!data) return;
    setVerifying(true);
    setChecks([]);
    const res = await verifyEntries(data.entries, data.pubkey);
    for (let i = 0; i < res.length; i++) {
      await new Promise((r) => setTimeout(r, 120));
      setChecks(res.slice(0, i + 1));
    }
    setVerifying(false);
  };
  if (!data) return <Spinner />;
  const allOk = checks && checks.length === data.entries.length && checks.every((c) => c.hashOk && c.sigOk);
  return (
    <div>
      <button className="btn-primary w-full" onClick={verify} disabled={verifying}><Link2 size={18} /> Verify timeline</button>
      <Explain id="timeline" />
      {checks && !verifying && (
        <p className={`mt-2 rounded-xl p-3 text-sm font-semibold ${allOk && data.chain_check.ok ? "bg-safe/10 text-safe" : "bg-danger/10 text-danger"}`}>
          {allOk && data.chain_check.ok ? `✓ ${data.entries.length} events · hashes match · signatures valid · full chain intact (${data.chain_check.count} events)` : `✗ Broken: ${data.chain_check.reason ?? "an entry failed verification"}`}
        </p>
      )}
      <ol className="mt-3 space-y-2">
        {data.entries.map((e) => {
          const c = checks?.find((x) => x.seq === e.seq);
          return (
            <li key={e.seq} className="flex gap-3 text-sm">
              <span className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs ${c ? (c.hashOk && c.sigOk ? "bg-safe text-white" : "bg-danger text-white") : "bg-black/5"}`}>{c ? (c.hashOk && c.sigOk ? "✓" : "✗") : e.seq}</span>
              <div className="min-w-0">
                <p className="font-semibold">{e.type}</p>
                <p className="text-xs text-muted">{clock(e.ts_server)} · hash {e.hash.slice(0, 12)}… ← {e.prev_hash.slice(0, 8)}…</p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/* ================================================================ checks */
export function TallyCard({ t, onLocate, dark }: { t: Tally; onLocate?: (label: string) => void; dark?: boolean }) {
  const total = Math.max(1, t.asked);
  const seg = (n: number) => `${(100 * n) / total}%`;
  return (
    <div className={`rounded-2xl p-4 ${dark ? "bg-night-surface" : "card"}`}>
      <div className="flex items-center justify-between"><p className="font-bold">"Are you safe?" · {hm(t.sent_at)}</p><span className="text-sm">{t.asked} asked</span></div>
      <div className="mt-3 flex h-4 overflow-hidden rounded-full bg-black/10">
        <div className="bg-safe transition-all" style={{ width: seg(t.safe) }} />
        <div className="bg-danger transition-all" style={{ width: seg(t.need_help) }} />
      </div>
      <div className="mt-2 grid grid-cols-3 text-center">
        <div><p className="font-mono text-2xl font-bold text-safe">{t.safe}</p><p className="text-xs opacity-70">safe</p></div>
        <div><p className="font-mono text-2xl font-bold text-danger">{t.need_help}</p><p className="text-xs opacity-70">need help</p></div>
        <div><p className="font-mono text-2xl font-bold">{t.no_answer}</p><p className="text-xs opacity-70">no answer</p></div>
      </div>
      {t.no_answer_trip_labels.length > 0 && onLocate && (
        <div className="mt-2 flex flex-wrap gap-1">{t.no_answer_trip_labels.map((l) => <button key={l} onClick={() => onLocate(l)} className={`chip ${t.overdue ? "bg-caution/20 text-caution" : "bg-black/5"}`}>{l}</button>)}</div>
      )}
    </div>
  );
}

/* ================================================================ pass scanner (checkpoints) */
export function PassScanner({ pubkey, onClose }: { pubkey: string; onClose: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [res, setRes] = useState<{ valid: boolean; reason: string; payload?: any } | null>(null);
  const [manual, setManual] = useState("");
  const [camErr, setCamErr] = useState(false);
  useEffect(() => {
    let controls: IScannerControls | null = null;
    const reader = new BrowserQRCodeReader();
    reader
      .decodeFromVideoDevice(undefined, video.current!, async (r) => {
        if (r) {
          setRes(await verifyPassOffline(r.getText(), pubkey));
          controls?.stop();
        }
      })
      .then((c) => (controls = c))
      .catch(() => setCamErr(true));
    return () => controls?.stop();
  }, [pubkey]);
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 sm:items-center" onClick={onClose}>
      <div className="w-full max-w-md rounded-t-sheet bg-white p-5 sm:rounded-sheet" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between"><p className="text-lg font-bold">Verify a trip pass</p><button onClick={onClose}><X /></button></div>
        <p className="text-sm text-muted">Checked on this device with the server's public key. Works offline.</p>
        {!res && !camErr && <video ref={video} className="mt-3 aspect-square w-full rounded-2xl bg-black object-cover" muted playsInline />}
        {camErr && <p className="mt-3 text-sm text-caution">Camera unavailable. Paste the pass text instead.</p>}
        {!res && (
          <div className="mt-3 flex gap-2">
            <input className="input" placeholder="…or paste the pass text" value={manual} onChange={(e) => setManual(e.target.value)} />
            <button className="btn-primary" onClick={async () => setRes(await verifyPassOffline(manual, pubkey))}>Check</button>
          </div>
        )}
        {res && (
          <div className={`mt-4 rounded-2xl p-5 text-center ${res.valid ? "bg-safe/10 text-safe" : "bg-danger/10 text-danger"}`}>
            {res.valid ? <ShieldCheck className="mx-auto" size={48} /> : <ShieldAlert className="mx-auto" size={48} />}
            <p className="mt-2 text-2xl font-extrabold">{res.valid ? "Valid pass" : res.reason === "forged" ? "Forged pass" : res.reason === "expired" ? "Expired pass" : "Unreadable"}</p>
            {res.payload && <p className="mt-1 text-sm text-ink">{res.payload.trip_label} · route {res.payload.route_id} · valid until {new Date(res.payload.valid_to * 1000).toLocaleString()}</p>}
            <button className="btn-ghost mt-4" onClick={() => setRes(null)}>Scan another</button>
          </div>
        )}
      </div>
    </div>
  );
}

export { ago, clock };
