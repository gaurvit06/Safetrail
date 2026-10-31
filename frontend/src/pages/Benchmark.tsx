import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { Explain, ExplainToggle, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { inr, usd } from "../lib/format";

type Metrics = {
  trips: number; incidents: number; calls: number; ok_calls: number; errors: number;
  cost_usd: number | null; cost_known_calls: number; cost_per_trip_usd: number | null; cost_per_emergency_usd: number | null;
  prune_estimate_without_usd: number | null; pct_routed: number | null; pct_cache: number | null; escalations: number;
  p50_ms: number | null; p95_ms: number | null; jobs: number; template_fallbacks: number; template_rate_pct: number | null;
  invented_fact_rate_pct: number | null; count_accuracy_pct: number | null; injection_notes: number;
  injection_caught_scanner: number; injection_caught_prune: number; injection_recall_pct: number | null; clean_notes_flagged: number;
};
type Run = { key: string; label: string; about: string; config: string; run_id: number; nonce: string; completed_at: number; models: { small: string; large: string }; metrics: Metrics };
type Step = { step: string; usd: number; kind: "total" | "saving" };
type Results = { status: "ok" | "not_run"; generated?: string; no_ai?: boolean; usd_inr?: number; scenario?: { about: string }; runs: Record<string, Run>; waterfall: Step[] | null };

const ORDER = ["R1", "R2", "R3", "R4"];
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : `${v}%`);
const ms = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : `${v} ms`);

/** Benchmark page (SPEC 9.6): the same simulated scenario through R1-R4. Every figure comes from scripts/benchmark.py. */
export default function Benchmark() {
  const [res, setRes] = useState<Results | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api<Results>("/benchmark").then(setRes).catch((e) => setErr(e.message));
  }, []);
  const rate = res?.usd_inr ?? 88;
  const runs = ORDER.filter((k) => res?.runs[k]).map((k) => res!.runs[k]);
  const rows: [string, (m: Metrics) => string][] = [
    ["Cost per monitored trip", (m) => `${usd(m.cost_per_trip_usd, 7)} · ${inr(m.cost_per_trip_usd, rate)}`],
    ["Cost per emergency", (m) => `${usd(m.cost_per_emergency_usd, 7)} · ${inr(m.cost_per_emergency_usd, rate)}`],
    ["Total AI cost", (m) => `${usd(m.cost_usd, 6)} · ${inr(m.cost_usd, rate)}`],
    ["AI calls", (m) => `${m.ok_calls}${m.errors ? ` (+${m.errors} errors)` : ""}`],
    ["Routed to a cheaper model", (m) => pct(m.pct_routed)],
    ["Served from Prune's cache", (m) => pct(m.pct_cache)],
    ["Latency p50 / p95", (m) => `${ms(m.p50_ms)} / ${ms(m.p95_ms)}`],
    ["Standard-text fallbacks", (m) => `${pct(m.template_rate_pct)} (${m.template_fallbacks}/${m.jobs})`],
    ["Invented-fact rate", (m) => pct(m.invented_fact_rate_pct)],
    ["Count accuracy", (m) => pct(m.count_accuracy_pct)],
    ["Injection notes flagged", (m) => `${m.injection_caught_scanner} scanner · ${m.injection_caught_prune} Prune · ${pct(m.injection_recall_pct)} of ${m.injection_notes}`],
  ];
  const wfMax = Math.max(...(res?.waterfall ?? []).map((w) => Math.abs(w.usd)), 1e-12);
  const r3 = res?.runs.R3?.metrics;

  return (
    <div className="min-h-full bg-bg">
      <header className="flex flex-wrap items-center gap-3 border-b border-line bg-white px-4 py-3">
        <a href="/r" className="grid h-9 w-9 place-items-center rounded-full border border-line" aria-label="Back to responder"><ArrowLeft size={16} /></a>
        <div>
          <h1 className="text-lg font-bold">Benchmark: what each design choice saves</h1>
          <p className="text-xs text-muted">{res?.generated ? `Generated ${res.generated} · ${res.scenario?.about ?? ""}` : "SPEC 10.3 · four runs on one simulated scenario"}</p>
        </div>
        <div className="ml-auto"><ExplainToggle /></div>
      </header>

      <main className="mx-auto max-w-6xl space-y-5 p-4">
        {!res && !err && <div className="grid place-items-center p-10"><Spinner size={24} /></div>}
        {err && <p className="card p-4 text-danger">Couldn't load the benchmark: {err}</p>}
        {res?.status === "not_run" && (
          <div className="card space-y-2 p-5">
            <p className="text-lg font-bold">No benchmark results yet</p>
            <p className="text-muted">Nothing is shown until a real run produces it. Put the Prune keys and model names in <code>.env</code>, run <code>scripts/prune_check.py</code> once, then:</p>
            <pre className="overflow-x-auto rounded-lg bg-black/5 p-3 text-sm">backend/.venv/bin/python scripts/benchmark.py --trips 100</pre>
            <p className="text-sm text-muted">On Windows use <code>backend\.venv\Scripts\python</code>. R1 (naive) is the expensive run: raise the ops key's daily cap for the benchmark only.</p>
          </div>
        )}
        {res?.no_ai && <p className="rounded-xl border border-caution/40 bg-caution/10 p-3 text-sm"><b>Plumbing test with no AI.</b> Every feature used standard text; these are not benchmark results.</p>}

        {res?.status === "ok" && (
          <>
            <section className="grid gap-4 lg:grid-cols-[1fr_300px]">
              <div className="card p-4">
                <p className="font-semibold">Where the savings come from</p>
                {res.waterfall ? (
                  <div className="mt-3 space-y-2">
                    {res.waterfall.map((w) => (
                      <div key={w.step} className="grid grid-cols-[minmax(0,240px)_1fr_auto] items-center gap-3 text-sm">
                        <span className={w.kind === "total" ? "font-semibold" : "text-muted"}>{w.step}</span>
                        <div className="h-4 rounded-full bg-black/5">
                          <div className={`h-4 rounded-full ${w.kind === "total" ? "bg-ink" : "bg-safe"}`} style={{ width: `${Math.max(1, (100 * Math.abs(w.usd)) / wfMax)}%` }} />
                        </div>
                        <span className="font-mono tabular-nums">{w.kind === "saving" ? (w.usd < 0 ? "+" : "−") : ""}{usd(Math.abs(w.usd), 6)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-muted">Shown once all four runs (R1–R4) have measured costs. Partial or estimated charts are never drawn.</p>
                )}
                <Explain id="waterfall" />
              </div>
              <div className="card p-4">
                <p className="text-sm font-semibold">Prune estimate, list price</p>
                <p className="mt-1 font-mono text-2xl font-bold tabular-nums">{usd(r3?.prune_estimate_without_usd, 6)}</p>
                <p className="mt-1 text-xs text-muted">Prune's own figure for R3 without its optimisations. It's an estimate, not something we paid.</p>
                {r3 && <p className="mt-3 text-xs text-muted">Actually paid in R3: <b className="text-ink">{usd(r3.cost_usd, 6)}</b></p>}
              </div>
            </section>

            <section className="card overflow-x-auto p-0">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="border-b border-line bg-black/[.03] text-left">
                    <th className="p-3">Metric</th>
                    {runs.map((r) => <th key={r.key} className="p-3"><p>{r.label}</p><p className="text-xs font-normal text-muted">#{r.run_id} · {new Date(r.completed_at * 1000).toLocaleString()}</p></th>)}
                  </tr>
                </thead>
                <tbody>
                  {rows.map(([name, fn]) => (
                    <tr key={name} className="border-b border-line/60">
                      <td className="p-3 font-semibold">{name}</td>
                      {runs.map((r) => <td key={r.key} className="p-3 font-mono tabular-nums">{fn(r.metrics)}</td>)}
                    </tr>
                  ))}
                  <tr>
                    <td className="p-3 font-semibold">What it does</td>
                    {runs.map((r) => <td key={r.key} className="p-3 text-xs text-muted">{r.about} · {r.metrics.trips} trips · {r.models.small} / {r.models.large}</td>)}
                  </tr>
                </tbody>
              </table>
            </section>
            <Explain id="benchmark" />
            <p className="text-xs text-muted">Counts are computed by plain code, so count accuracy must be 100%. Every cost is Prune's own figure from stored responses; missing values show n/a. Full write-up: docs/BENCHMARK.md.</p>
          </>
        )}
      </main>
    </div>
  );
}
