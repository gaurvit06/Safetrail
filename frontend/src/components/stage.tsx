import { useEffect, useRef, useState } from "react";
import { inr } from "../lib/format";
import type { RoundSummary } from "../lib/types";

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/* ---------------------------------------------------------------- confetti (projector only) */
type Piece = { x: number; y: number; vx: number; vy: number; r: number; vr: number; w: number; h: number; c: string };
const COLORS = ["#0F766E", "#1E8E3E", "#E8A317", "#FFFFFF", "#1A73E8", "#D93025"];

/** A burst of confetti over the projector each time `burst` changes. Draws nothing with reduced motion. */
export function Confetti({ burst }: { burst: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current;
    if (!burst || !cv || reducedMotion()) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    const W = (cv.width = cv.offsetWidth * devicePixelRatio);
    const H = (cv.height = cv.offsetHeight * devicePixelRatio);
    const pieces: Piece[] = Array.from({ length: 220 }, (_, i) => {
      const left = i % 2 === 0;
      return {
        x: left ? W * 0.05 : W * 0.95, y: H * 0.95,
        vx: (left ? 1 : -1) * (6 + Math.random() * 14) * devicePixelRatio, vy: -(16 + Math.random() * 18) * devicePixelRatio,
        r: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.4,
        w: (6 + Math.random() * 8) * devicePixelRatio, h: (10 + Math.random() * 10) * devicePixelRatio,
        c: COLORS[i % COLORS.length],
      };
    });
    const start = performance.now();
    let frame = 0;
    const draw = (now: number) => {
      const t = (now - start) / 1000;
      ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = Math.max(0, 1 - Math.max(0, t - 2.4) / 0.8);
      for (const p of pieces) {
        p.vy += 0.55 * devicePixelRatio;
        p.vx *= 0.99;
        p.x += p.vx;
        p.y += p.vy;
        p.r += p.vr;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.r);
        ctx.fillStyle = p.c;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h * Math.abs(Math.cos(p.r * 2)));
        ctx.restore();
      }
      if (t < 3.2) frame = requestAnimationFrame(draw);
      else ctx.clearRect(0, 0, W, H);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [burst]);
  return <canvas ref={ref} className="pointer-events-none absolute inset-0 z-30 h-full w-full" aria-hidden />;
}

/* ---------------------------------------------------------------- big numbers that pop when they change */
function Num({ v }: { v: string | number }) {
  return <span key={String(v)} className="inline-block animate-[pop_.5s_ease-out] font-display font-bold tabular-nums">{v}</span>;
}

export type Headline = { round: number; onTrail: number; simulated: number; sos: number; incidents: number; aiCostUsd: number | null; aiConfigured: boolean; usdInr: number };

/** The headline across the projector, readable from the back of the room. Every number comes from live data. */
export function HeadlineBar({ h }: { h: Headline }) {
  const cost = !h.aiConfigured ? "standard text (no key)" : h.aiCostUsd === null ? "n/a" : inr(h.aiCostUsd, h.usdInr);
  return (
    <div className="pointer-events-none absolute inset-x-0 top-24 z-20 flex justify-center px-4" aria-live="polite">
      <style>{`@keyframes pop { 0% { transform: scale(1.6); color: #FCD34D } 100% { transform: scale(1) } }`}</style>
      <div className="flex flex-wrap items-baseline justify-center gap-x-6 gap-y-1 rounded-3xl bg-black/70 px-7 py-3 text-2xl text-white shadow-float backdrop-blur xl:text-3xl">
        <span className="rounded-full bg-white/15 px-3 py-0.5 text-lg font-bold xl:text-xl">Round {h.round}</span>
        <span><Num v={h.onTrail} /> on the trail{h.simulated > 0 && <span className="text-lg opacity-70"> +{h.simulated} simulated</span>}</span>
        <span className={h.sos ? "text-red-300" : ""}><Num v={h.sos} /> SOS → <Num v={h.incidents} /> incident{h.incidents === 1 ? "" : "s"}</span>
        <span>AI this round: <Num v={cost} /></span>
      </div>
    </div>
  );
}

/** Between rounds: what the last group of judges did, until the first new traveller joins. */
export function RoundRecap({ r, next, usdInr }: { r: RoundSummary; next: number; usdInr: number }) {
  const cost = r.ai_cost_usd === null ? (r.ai_calls ? "n/a" : "no AI calls") : inr(r.ai_cost_usd, usdInr);
  const items: [string, string][] = [
    ["Judges joined", String(r.judges)],
    ["SOS → incidents", `${r.sos} → ${r.incidents}`],
    ["Help accepted", String(r.accepted)],
    ["\"I'm safe\" answers", String(r.safe)],
    ["Tricks caught", `${r.tricks_caught}/${r.tricks}`],
    ["AI cost", `${cost}${r.ai_calls ? ` · ${r.ai_calls} calls` : ""}`],
  ];
  return (
    <div className="pointer-events-none absolute inset-0 z-20 grid place-items-center p-6">
      <div className="w-full max-w-2xl rounded-3xl bg-black/75 p-6 text-white shadow-float backdrop-blur">
        <p className="text-sm font-semibold uppercase tracking-wide opacity-70">Round {r.round} recap · {r.minutes} min</p>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {items.map(([k, v]) => (
            <div key={k} className="rounded-2xl bg-white/10 p-3">
              <p className="text-xs opacity-70">{k}</p>
              <p className="font-display text-4xl font-bold leading-none text-gold">{v}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-center font-display text-4xl font-bold">Round {next} · scan the QR to join</p>
      </div>
    </div>
  );
}

/** Full-width banner that shows briefly when a responder accepts an incident. */
export function AcceptBanner({ text }: { text: string | null }) {
  const [shown, setShown] = useState<string | null>(null);
  useEffect(() => {
    if (!text) return;
    setShown(text);
    const t = setTimeout(() => setShown(null), 3500);
    return () => clearTimeout(t);
  }, [text]);
  if (!shown) return null;
  return (
    <div className="pointer-events-none absolute inset-x-0 top-1/3 z-30 flex justify-center px-4">
      <div className="rounded-3xl bg-safe px-8 py-5 text-center font-display text-6xl font-bold text-white shadow-float">✓ {shown}</div>
    </div>
  );
}
