import { Check, Lightbulb, Loader2, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { EXPLAIN } from "../explain";
import { vibrate } from "../lib/signals";

/* ---------------------------------------------------------------- toasts */
type Toast = { id: number; text: string; tone: "info" | "ok" | "warn" | "danger" };
const ToastCtx = createContext<(text: string, tone?: Toast["tone"]) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x.slice(-2), { id, text, tone }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), 3800);
  }, []);
  const color = { info: "bg-ink", ok: "bg-safe", warn: "bg-caution", danger: "bg-danger" };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 top-3 z-[100] flex flex-col items-center gap-2 px-3">
        {items.map((t) => (
          <div key={t.id} className={`animate-slideup rounded-xl px-4 py-3 text-sm font-semibold text-white shadow-float ${color[t.tone]}`}>{t.text}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* ---------------------------------------------------------------- explain mode */
const ExplainCtx = createContext<{ on: boolean; toggle: () => void }>({ on: false, toggle: () => {} });
export function ExplainProvider({ children }: { children: ReactNode }) {
  const [on, setOn] = useState(false);
  return <ExplainCtx.Provider value={{ on, toggle: () => setOn((v) => !v) }}>{children}</ExplainCtx.Provider>;
}
export const useExplain = () => useContext(ExplainCtx);
export function Explain({ id, dark }: { id: keyof typeof EXPLAIN | string; dark?: boolean }) {
  const { on } = useExplain();
  if (!on) return null;
  return <p className={`mt-1 rounded-lg px-2 py-1 text-xs ${dark ? "bg-white/10 text-night-text" : "bg-info/10 text-info"}`}><Lightbulb size={12} className="-mt-0.5 mr-1 inline" />{EXPLAIN[id]}</p>;
}
export function ExplainToggle({ dark }: { dark?: boolean }) {
  const { on, toggle } = useExplain();
  return (
    <button onClick={toggle} title="Explain mode" className={`grid h-9 w-9 place-items-center rounded-full border text-sm font-bold ${on ? "bg-info text-white border-info" : dark ? "border-night-line text-night-text" : "border-line bg-white"}`}>
      ?
    </button>
  );
}

/* ---------------------------------------------------------------- overlays */
export function Overlay({ children, onClose, tone = "light" }: { children: ReactNode; onClose?: () => void; tone?: "light" | "dark" | "none" }) {
  return (
    <div className={`fixed inset-0 z-50 flex items-end justify-center sm:items-center ${tone === "none" ? "" : "bg-black/40"}`} onClick={onClose}>
      <div className="animate-slideup max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-sheet bg-white shadow-float sm:rounded-sheet" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

export function SheetHeader({ title, onClose, sub }: { title: string; onClose?: () => void; sub?: string }) {
  return (
    <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-line bg-white px-5 pb-3 pt-4">
      <div>
        <h2 className="text-3xl leading-none">{title}</h2>
        {sub && <p className="text-sm text-muted">{sub}</p>}
      </div>
      {onClose && (
        <button onClick={onClose} className="grid h-10 w-10 place-items-center rounded-full bg-black/5" aria-label="Close">
          <X size={20} />
        </button>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- bottom sheet with drag */
export function BottomSheet({ children, peek = 132, collapse }: { children: ReactNode; peek?: number; collapse?: number }) {
  const [state, setState] = useState<0 | 1 | 2>(0);
  useEffect(() => setState(0), [collapse]);
  const drag = useRef<{ y: number; start: number } | null>(null);
  const [dy, setDy] = useState(0);
  const heights = [peek, Math.round(window.innerHeight * 0.48), Math.round(window.innerHeight * 0.86)];
  const h = heights[state];
  return (
    <div
      className="absolute inset-x-0 bottom-0 z-20 mx-auto max-w-lg rounded-t-sheet bg-white shadow-float transition-[height] duration-200"
      style={{ height: Math.max(peek, h - dy) }}
    >
      <div
        className="flex cursor-grab touch-none justify-center pb-2 pt-3"
        onPointerDown={(e) => {
          drag.current = { y: e.clientY, start: state };
          (e.target as HTMLElement).setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => drag.current && setDy(e.clientY - drag.current.y)}
        onPointerUp={() => {
          if (!drag.current) return;
          const moved = dy;
          let next = drag.current.start;
          if (Math.abs(moved) < 8) next = ((drag.current.start + 1) % 3) as 0 | 1 | 2;
          else if (moved < -40) next = Math.min(2, drag.current.start + 1) as 0 | 1 | 2;
          else if (moved > 40) next = Math.max(0, drag.current.start - 1) as 0 | 1 | 2;
          setState(next as 0 | 1 | 2);
          setDy(0);
          drag.current = null;
        }}
      >
        <div className="h-1.5 w-12 rounded-full bg-black/20" />
      </div>
      <div className="h-[calc(100%-28px)] overflow-y-auto px-4 pb-6">{children}</div>
    </div>
  );
}

/* ---------------------------------------------------------------- hold-to-activate button */
export function HoldButton({ onDone, ms = 1500, className, children, ringColor = "#fff", label }: { onDone: () => void; ms?: number; className?: string; children: ReactNode; ringColor?: string; label: string }) {
  const [p, setP] = useState(0);
  const t0 = useRef<number | null>(null);
  const raf = useRef<number>();
  const timer = useRef<number>();
  const stop = () => {
    t0.current = null;
    if (raf.current) cancelAnimationFrame(raf.current);
    clearTimeout(timer.current);
    setP(0);
  };
  // The ring is drawn with animation frames; completion uses a timer so it fires even if frames are throttled.
  const tick = () => {
    if (t0.current === null) return;
    setP(Math.min(1, (performance.now() - t0.current) / ms));
    raf.current = requestAnimationFrame(tick);
  };
  const start = () => {
    t0.current = performance.now();
    raf.current = requestAnimationFrame(tick);
    timer.current = window.setTimeout(() => {
      vibrate(200);
      stop();
      onDone();
    }, ms);
  };
  useEffect(() => stop, []);
  const r = 44;
  const c = 2 * Math.PI * r;
  return (
    <button
      aria-label={label}
      className={`relative select-none ${className}`}
      onPointerDown={(e) => {
        e.preventDefault();
        vibrate(30);
        start();
      }}
      onPointerUp={stop}
      onPointerLeave={stop}
      onPointerCancel={stop}
      onContextMenu={(e) => e.preventDefault()}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onDone()}
    >
      <svg className="pointer-events-none absolute inset-0 h-full w-full -rotate-90" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke={ringColor} strokeOpacity={0.25} strokeWidth="6" />
        <circle cx="50" cy="50" r={r} fill="none" stroke={ringColor} strokeWidth="6" strokeDasharray={c} strokeDashoffset={c * (1 - p)} strokeLinecap="round" />
      </svg>
      {children}
    </button>
  );
}

/* ---------------------------------------------------------------- misc */
export function Spinner({ size = 16 }: { size?: number }) {
  return <Loader2 size={size} className="animate-spin" />;
}

export function Step({ done, active, label, sub, last }: { done: boolean; active?: boolean; label: string; sub?: string; last?: boolean }) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div className={`grid h-8 w-8 place-items-center rounded-full border-2 ${done ? "border-safe bg-safe text-white" : active ? "border-info text-info" : "border-line text-muted"}`}>
          {done ? <Check size={18} /> : active ? <Spinner /> : <span className="h-2 w-2 rounded-full bg-line" />}
        </div>
        {!last && <div className={`w-0.5 flex-1 ${done ? "bg-safe" : "bg-line"}`} style={{ minHeight: 20 }} />}
      </div>
      <div className="pb-4">
        <p className={`font-semibold ${done ? "" : active ? "text-info" : "text-muted"}`}>{label}</p>
        {sub && <p className="text-sm text-muted">{sub}</p>}
      </div>
    </div>
  );
}

export function SourceTag({ source, cost, model, dark }: { source?: string | null; cost?: number | null; model?: string | null; dark?: boolean }) {
  if (!source) return null;
  const base = dark ? "text-night-text/60" : "text-muted";
  if (source === "template") return <span className={`text-xs ${base}`}>Standard text</span>;
  return (
    <span className={`text-xs ${base}`}>
      AI{model ? ` · ${model} model` : ""}
      {cost != null ? ` · $${cost.toFixed(5)}` : ""} · receipt ✓
    </span>
  );
}
