import { QRCodeSVG } from "qrcode.react";
import { Maximize2, Volume2, VolumeX } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { AcceptBanner, Confetti, HeadlineBar, RoundRecap } from "../components/stage";
import MapView from "../components/MapView";
import { LoginCard, RoutingRiver, TallyCard, useOpsFeed } from "../components/ops";
import { Explain, ExplainToggle } from "../components/ui";
import { api } from "../lib/api";
import { inr, usd } from "../lib/format";
import { anyStaffToken } from "../lib/session";
import { cheer, unlockAudio } from "../lib/signals";
import type { AiStats, RoundState } from "../lib/types";

const OUTCOME: Record<string, string> = { caught: "✓ Caught", flagged: "⚑ Flagged", not_flagged: "? Not flagged", slipped: "✗ Slipped" };

/** Projector view (SPEC 9.4.1): no names, trip labels and nicknames only. */
export default function Stage() {
  const [token, setToken] = useState<string | null>(anyStaffToken);
  const routeId = new URLSearchParams(window.location.search).get("route") || "hall";
  const feed = useOpsFeed(routeId, token);
  const [qr, setQr] = useState<"join" | "break" | "responder" | null>("join");
  const [stats, setStats] = useState<AiStats | null>(null);
  const [round, setRound] = useState<RoundState | null>(null);
  const [sound, setSound] = useState(() => localStorage.getItem("st_stage_sound") === "1");
  const [burst, setBurst] = useState(0);
  const [accepted, setAccepted] = useState<string | null>(null);
  const loadRound = () => token && api<RoundState>("/stage/round", { token }).then(setRound).catch(() => {});
  useEffect(() => {
    loadRound();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  useEffect(() => {
    if (!token || !round) return;
    api<AiStats>(`/ai/stats?since=${round.started_at}`, { token }).then(setStats).catch(() => {});
  }, [token, feed.aiTick, round]);
  // live moments: a new round, and help being accepted (confetti + cheer)
  useEffect(() => {
    const e = feed.lastEvt;
    if (!e) return;
    if (e.type === "stage.round") {
      setRound(e.data as RoundState);
      setQr("join");
    } else if (e.type === "stage.reset") loadRound();
    else if (e.type === "incident.status" && e.data.status === "accepted") {
      setBurst((n) => n + 1);
      setAccepted(`Help accepted · incident #${e.data.incident_id}${e.data.team ? ` · ${e.data.team}` : ""}`);
      if (sound) cheer();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feed.lastEvt]);
  useEffect(() => {
    if (!sound) return; // sound was left on: the first tap anywhere on the projector unlocks audio again
    const f = () => unlockAudio();
    window.addEventListener("pointerdown", f, { once: true });
    return () => window.removeEventListener("pointerdown", f);
  }, [sound]);
  const toggleSound = () => {
    unlockAudio(); // the click is the gesture browsers need before playing sound
    setSound((v) => {
      localStorage.setItem("st_stage_sound", v ? "0" : "1");
      return !v;
    });
  };
  const base = (feed.config?.public_url || window.location.origin).replace(/\/$/, "");
  const urls = { join: `${base}/j`, break: `${base}/break`, responder: `${base}/jr` };
  const pins = useMemo(() => feed.incidents.filter((i) => !["resolved", "cancelled"].includes(i.status)).map((i) => ({ id: i.id, lat: i.center_lat, lon: i.center_lon, count: i.trip_count, priority: i.priority, status: i.status })), [feed.incidents]);
  const onTrail = feed.dots.filter((d) => d.kind === "tourist" && d.status !== "ended").length;
  const simulated = feed.dots.filter((d) => d.kind === "sim").length;
  const liveIncidents = feed.incidents.filter((i) => i.status !== "cancelled");
  const sos = feed.incidents.filter((i) => i.status !== "cancelled").reduce((n, i) => n + i.member_count, 0);
  const lanes = feed.river.reduce((acc, d) => ({ ...acc, [d.lane]: (acc[d.lane] ?? 0) + 1 }), {} as Record<string, number>);

  if (!token) return <div className="flow-root min-h-full bg-night-bg px-4"><LoginCard dark onDone={(t) => setToken(t)} /></div>;

  return (
    <div className="flex h-full bg-night-bg text-night-text">
      <div className="relative flex-1">
        {feed.route && <MapView dark bbox={feed.route.bbox} route={feed.route.line} zones={feed.zones} dots={feed.dots} crowd={feed.crowd} helpPoints={feed.route.help_points} incidents={pins} />}
        {round && <HeadlineBar h={{ round: round.round, onTrail, simulated, sos, incidents: liveIncidents.length, aiCostUsd: stats?.cost_usd ?? null, aiConfigured: stats?.ai_configured ?? false, usdInr: stats?.usd_inr ?? 88 }} />}
        {round?.last && onTrail === 0 && liveIncidents.length === 0 && <RoundRecap r={round.last} next={round.round} usdInr={stats?.usd_inr ?? 88} />}
        <Confetti burst={burst} />
        <AcceptBanner key={burst} text={accepted} />
        <div className="absolute left-4 top-4 z-10 flex items-center gap-3 rounded-2xl bg-black/60 px-4 py-2 backdrop-blur">
          <img src="/icon.svg" className="h-9 w-9" alt="" />
          <div><p className="font-display text-3xl font-bold leading-none">SafeTrail · Live</p><p className="text-xs opacity-70">{feed.route?.name ?? "…"} · zones, dispatches and demo travellers are simulated</p></div>
          <span className={`ml-2 h-3 w-3 rounded-full ${feed.connected ? "bg-safe" : "bg-offline"}`} />
        </div>
        <div className="absolute inset-x-4 bottom-4 z-10 rounded-2xl bg-black/65 p-3 backdrop-blur">
          {feed.ticker.slice(0, 4).map((t, i) => <p key={i} className={`truncate text-lg ${i ? "opacity-60" : "font-semibold"} ${t.tone === "danger" ? "text-red-300" : t.tone === "warn" ? "text-amber-300" : t.tone === "ok" ? "text-green-300" : ""}`}>{t.text}</p>)}
          {!feed.ticker.length && <p className="text-lg opacity-60">Waiting for the first traveller…</p>}
        </div>
      </div>
      <aside className="flex w-[34%] min-w-[340px] flex-col gap-3 overflow-y-auto border-l border-night-line p-4">
        <div className="flex items-center justify-between">
          <div className="flex gap-1 rounded-full bg-night-surface p-1 text-sm font-semibold">
            {(["join", "break", "responder"] as const).map((k) => <button key={k} onClick={() => setQr(qr === k ? null : k)} className={`rounded-full px-3 py-1 capitalize ${qr === k ? "bg-white text-ink" : ""}`}>{k === "join" ? "Join" : k === "break" ? "Break it" : "Responder"}</button>)}
          </div>
          <div className="flex gap-2"><button className="btn-dark min-h-[36px] px-2" title={sound ? "Sound on" : "Sound off: tap to allow the cheer"} onClick={toggleSound}>{sound ? <Volume2 size={16} /> : <VolumeX size={16} />}</button><ExplainToggle dark /><button className="btn-dark min-h-[36px] px-2" onClick={() => document.documentElement.requestFullscreen?.()}><Maximize2 size={16} /></button></div>
        </div>
        {qr && (
          <div className="rounded-2xl bg-white p-4 text-center text-ink">
            <QRCodeSVG value={urls[qr]} size={220} className="mx-auto" />
            <p className="mt-2 text-xl font-bold">{qr === "join" ? "Scan to join the trail" : qr === "break" ? "Try to break SafeTrail" : "Be the responder (PIN)"}</p>
            <p className="font-mono text-sm text-muted">{urls[qr].replace(/^https?:\/\//, "")}</p>
          </div>
        )}
        <div className="grid grid-cols-2 gap-2">
          <Big label="On the trail" value={onTrail} />
          <Big label="SOS received" value={sos} tone={sos ? "text-red-300" : ""} />
          <Big label="Safe answers" value={feed.tally ? `${feed.tally.safe}/${feed.tally.asked}` : "–"} />
          <Big label="AI cost this round" value={stats ? usd(stats.cost_usd) : "–"} sub={stats ? inr(stats.cost_usd, stats.usd_inr) : undefined} />
        </div>
        {feed.tally && <TallyCard t={feed.tally} dark />}
        <div>
          <p className="mb-1 font-display text-xl font-bold text-gold">Every AI call, through Prune</p>
          <RoutingRiver dots={feed.river} dark totals={lanes as any} />
          {stats && !stats.ai_configured && <p className="mt-1 text-xs text-amber-300">AI keys not set: standard text is used and safety still works.</p>}
        </div>
        <div>
          <p className="mb-1 font-display text-xl font-bold text-gold">Break it board</p>
          <Explain id="breakit" dark />
          <div className="space-y-1">
            {feed.board.slice(0, 6).map((b) => (
              <div key={b.attempt_id} className="flex items-center justify-between rounded-lg bg-night-surface px-3 py-2 text-sm">
                <span className="truncate"><b>{b.nickname}</b> · {b.trick.replace("_", " ")}</span>
                <span className={b.outcome === "slipped" ? "text-red-300" : b.outcome === "not_flagged" ? "text-amber-300" : "text-green-300"}>{OUTCOME[b.outcome] ?? b.outcome}</span>
              </div>
            ))}
            {!feed.board.length && <p className="text-sm opacity-60">No attempts yet.</p>}
          </div>
        </div>
      </aside>
    </div>
  );
}

function Big({ label, value, sub, tone }: { label: string; value: string | number; sub?: string; tone?: string }) {
  return (
    <div className="rounded-2xl bg-night-surface p-3">
      <p className="text-xs opacity-70">{label}</p>
      <p className={`font-display text-5xl font-bold leading-none text-gold ${tone ?? ""}`}>{value}</p>
      {sub && <p className="text-xs opacity-70">{sub}</p>}
    </div>
  );
}
