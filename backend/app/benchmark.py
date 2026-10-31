"""Benchmark runs R1-R4 (SPEC 10.2, 10.3): one simulated scenario through four configurations, all through Prune.

Run it with scripts/benchmark.py, which points DB_PATH at backend/benchmark.db first, so benchmark trips, SOS and
incidents never appear on the live demo screens. Every number in the results comes from stored Prune data
(LlmCall rows) or from plain counting; a value Prune didn't return stays None and shows as n/a.

How each run maps to the app:
- packs: SafeTrail builds one pack per (route, language, profile bucket); naive builds one personalised pack per trip.
- zone warnings: one advisory job per zone (every language in ADVISORY_LANGS), as when an officer publishes a zone.
- SOS: replayed in scenario-time order through the real grouping code (core.attach_to_incident). A new single
  incident gets a report. A cluster gets a summary under the app's refresh limits (no more than one per
  CLUSTER_SUMMARY_MIN_INTERVAL_S of scenario time, at most 3), or after every SOS in the naive run.
- copilot: one brief per incident at the end (an officer opening each incident once).
"""
import asyncio
import time
import uuid
from collections import Counter

from sqlmodel import Session, select

from . import core
from .ai import features
from .ai.jobs import BENCH
from .config import SEED_DIR, settings
from .db import engine
from .geo import haversine_m
from .models import AiJob, BenchmarkRun, Incident, LlmCall, Pass, SafetyPack, SosEvent, Trip, Zone, ZoneAdvisory
from .seeddata import _read

RUNS = {
    "R1": {"label": "R1 Naive", "config": "naive", "policy": "off", "cache": "off", "tier": "large", "naive": True,
           "about": "MODEL_LARGE for everything, one personalised pack per trip, a cluster summary after every SOS, no budgets"},
    "R2": {"label": "R2 SafeTrail, no Prune optimisations", "config": "lean_no_prune", "policy": "off", "cache": "off",
           "about": "Full SafeTrail design (buckets, templates, refresh limits, budgets); Prune routing and cache off"},
    "R3": {"label": "R3 SafeTrail + Prune (cold)", "config": "prune_cold", "policy": "balanced", "cache": "exact",
           "about": "Full design with Prune routing and exact cache, fresh nonce so nothing is cached yet"},
    "R4": {"label": "R4 SafeTrail + Prune (warm)", "config": "prune_warm", "policy": "balanced", "cache": "exact",
           "about": "R3 again with the same nonce: a second day of tourists on the same routes"},
}
ORDER = ["R3", "R4", "R2", "R1"]
TRIP_FEATURES = ("pack", "advisory")
EMERGENCY_FEATURES = ("report", "cluster", "copilot", "sms_parse")


def load_scenario() -> tuple[dict, dict]:
    d = SEED_DIR / "scenario"
    return _read(d / "benchmark_scenario.json"), _read(d / "labels.json")


def _reset(s: Session) -> None:
    """Clear the previous run's scenario rows. LlmCall and BenchmarkRun rows stay: they are the results."""
    for m in (SosEvent, Incident, Pass, Trip, ZoneAdvisory, AiJob, SafetyPack):
        for row in s.exec(select(m)).all():
            s.delete(row)
    for z in s.exec(select(Zone).where(Zone.id.startswith("BZ"))).all():
        s.delete(z)
    s.commit()


def _feature(job_key: str) -> str:
    return core._feature_of(job_key)


def _pct(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 1) if d else None


def _quantile(xs: list[int], q: float) -> int | None:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(round(q * (len(xs) - 1)))))]


def metrics(s: Session, run_id: int, trips_n: int, labels: dict, sos_ids: dict[int, int]) -> dict:
    calls = s.exec(select(LlmCall).where(LlmCall.benchmark_run_id == run_id)).all()
    ok = [c for c in calls if c.status in ("ok", "retried")]
    known = [c for c in ok if c.cost_with_prune_usd is not None]
    by: dict[str, dict] = {}
    for c in ok:
        b = by.setdefault(_feature(c.job_key), {"calls": 0, "cost_usd": 0.0, "cost_known": 0})
        b["calls"] += 1
        if c.cost_with_prune_usd is not None:
            b["cost_usd"] += c.cost_with_prune_usd
            b["cost_known"] += 1
    cost = round(sum(c.cost_with_prune_usd for c in known), 8) if known else None
    without = [c.cost_without_prune_usd for c in ok if c.cost_without_prune_usd is not None]
    jobs = s.exec(select(AiJob).where(AiJob.benchmark_run_id == run_id)).all()
    called = [j for j in jobs if j.llm_call_ids]
    incs = [i for i in s.exec(select(Incident)).all() if i.status != "cancelled"]

    # computed counts vs the ground truth (must be 100%: counts never come from the AI)
    matched, checks = 0, []
    for gid, g in labels["groups"].items():
        inc = min(incs, key=lambda i: haversine_m(i.center_lat, i.center_lon, g["center"][0], g["center"][1]), default=None)
        ok_ = bool(inc) and inc.member_count == g["sos_count"] and inc.people_total == g["people_total"] \
            and (inc.count_by_kind or {}) == g["count_by_kind"] and inc.segment_name == g["segment"] \
            and inc.type == g["type"]
        matched += ok_
        checks.append({"group": gid, "ok": ok_, "incident_id": inc.id if inc else None})

    # injection notes: caught by our scanner (no AI) and/or flagged from Prune's injection signal
    inc_flags = {i.id: set(i.flags or []) for i in incs}
    inj = [n for n in labels["notes"] if n["is_injection"]]
    clean = [n for n in labels["notes"] if not n["is_injection"]]
    rows = {r.id: r for r in s.exec(select(SosEvent)).all()}

    def flagged(n, by_prune: bool) -> bool:
        r = rows.get(sos_ids.get(n["sos"]))
        if not r:
            return False
        return "prune_injection_signal" in inc_flags.get(r.incident_id, set()) if by_prune else "suspicious_text" in (r.flags or [])

    scanner = sum(flagged(n, False) for n in inj)
    prune = sum(flagged(n, True) for n in inj)
    either = sum(flagged(n, False) or flagged(n, True) for n in inj)
    lat = [c.latency_ms for c in ok if c.latency_ms is not None]
    trip_cost = sum(by.get(f, {}).get("cost_usd", 0) for f in TRIP_FEATURES)
    emerg_cost = sum(by.get(f, {}).get("cost_usd", 0) for f in EMERGENCY_FEATURES)
    return {
        "trips": trips_n, "incidents": len(incs), "calls": len(calls), "ok_calls": len(ok), "errors": len(calls) - len(ok),
        "cost_usd": cost, "cost_known_calls": len(known),
        "cost_per_trip_usd": round(trip_cost / trips_n, 8) if known and trips_n else None,
        "cost_per_emergency_usd": round(emerg_cost / len(incs), 8) if known and incs else None,
        "prune_estimate_without_usd": round(sum(without), 8) if without else None,
        "by_feature": by,
        "pct_routed": _pct(sum(1 for c in ok if c.route_applied), len(ok)),
        "pct_cache": _pct(sum(1 for c in ok if c.cache_hit), len(ok)),
        "escalations": sum(1 for c in ok if c.escalated),
        "p50_ms": _quantile(lat, 0.5), "p95_ms": _quantile(lat, 0.95),
        "jobs": len(jobs), "template_fallbacks": sum(1 for j in jobs if j.source == "template"),
        "template_rate_pct": _pct(sum(1 for j in jobs if j.source == "template"), len(jobs)),
        "invented_fact_rate_pct": _pct(sum(1 for j in called if j.validator_rejections), len(called)),
        "validator_rejections": sum(j.validator_rejections for j in jobs),
        "count_accuracy_pct": _pct(matched, len(labels["groups"])), "count_checks": checks,
        "injection_notes": len(inj), "injection_caught_scanner": scanner, "injection_caught_prune": prune,
        "injection_recall_pct": _pct(either, len(inj)),
        "clean_notes_flagged": sum(flagged(n, False) for n in clean),
    }


async def run(key: str, *, trips_n: int, nonce: str) -> dict:
    """Run one configuration on the scenario and return its result entry."""
    spec = RUNS[key]
    scenario, labels = load_scenario()
    trips = scenario["trips"][:trips_n]
    with Session(engine) as s:
        _reset(s)
        br = BenchmarkRun(config=spec["config"], nonce=nonce, status="running")
        s.add(br)
        s.commit()
        s.refresh(br)
        rid = br.id
    started = time.time()
    token = BENCH.set({"run_id": rid, "tag": f"b{rid}", "nonce": nonce, "policy": spec["policy"], "cache": spec["cache"],
                       "tier": spec.get("tier"), "naive": spec.get("naive", False)})
    try:
        # 1. safety packs
        if spec.get("naive"):
            jobs = [features.build_pack(t["route_id"], t["language"], t["profile_bucket"], suffix=f"_t{t['i']}",
                                        extra_profile=t["naive_profile"], benchmark_run_id=rid) for t in trips]
        else:
            keys = sorted({(t["route_id"], t["language"], t["profile_bucket"]) for t in trips})
            jobs = [features.build_pack(r, lang, b, benchmark_run_id=rid) for r, lang, b in keys]
        await asyncio.gather(*jobs)

        # 2. zone warnings
        with Session(engine) as s:
            for z in scenario["zones"]:
                s.add(Zone(id=f"BZ{rid}-{z['id']}", route_id=z["route_id"], kind=z["kind"], severity=z["severity"],
                           polygon=z["polygon"], source="drawn" if z["note"] else "seeded", note=z["note"],
                           segment_name=z["segment_name"], created_by="benchmark", active=False))
            s.commit()
        await asyncio.gather(*[features.build_advisories(f"BZ{rid}-{z['id']}", scanner=core.scan_injection,
                                                         benchmark_run_id=rid) for z in scenario["zones"]])

        # 3. SOS, in scenario time order, through the app's own grouping code
        sos_ids: dict[int, int] = {}
        last_summary: dict[int, float] = {}
        refreshes: Counter = Counter()
        interval_min = settings.cluster_summary_min_interval_s / 60
        with Session(engine) as s:
            sender = {}
            for x in scenario["sos"]:
                t = scenario["trips"][x["trip"]]
                trip, _ = core.create_trip(s, {"name": t["label"], "route_id": t["route_id"], "language": t["language"],
                                               "profile_bucket": t["profile_bucket"], "consent_version": "benchmark"},
                                           kind="sim")
                trip.status, trip.sharing, trip.start_at, trip.last_ping_at = "active", True, time.time(), time.time() - 300
                s.add(trip)
                sender[x["n"]] = trip.id
            s.commit()
        for x in scenario["sos"]:
            with Session(engine) as s:
                trip = s.get(Trip, sender[x["n"]])
                note = x["note"]
                row = SosEvent(client_id=f"bench{rid}-{x['n']}-{uuid.uuid4().hex[:6]}", trip_id=trip.id, kind=x["kind"],
                               people_bucket=x["people_bucket"], note_text=note, lat=x["lat"], lon=x["lon"],
                               created_at_device=time.time(), flags=["suspicious_text"] if core.scan_injection(note) else [])
                s.add(row)
                s.commit()
                s.refresh(row)
                sos_ids[x["n"]] = row.id
                inc, _ = core.attach_to_incident(s, row, trip)
                inc_id, inc_type = inc.id, inc.type
            if inc_type == "single":
                await features.build_report(inc_id)
            elif spec.get("naive"):
                await features.build_cluster_summary(inc_id, force=True, governor=False)
            elif refreshes[inc_id] < 3 and (inc_id not in last_summary or x["t_min"] - last_summary[inc_id] >= interval_min):
                await features.build_cluster_summary(inc_id, force=True)
                last_summary[inc_id], refreshes[inc_id] = x["t_min"], refreshes[inc_id] + 1

        # 4. one copilot brief per incident
        with Session(engine) as s:
            open_ids = [i.id for i in s.exec(select(Incident)).all() if i.status != "cancelled"]
        for i in open_ids:
            await features.build_brief(i)
    finally:
        BENCH.reset(token)

    with Session(engine) as s:
        m = metrics(s, rid, len(trips), labels, sos_ids)
        br = s.get(BenchmarkRun, rid)
        br.status, br.metrics, br.completed_at = "done", m, time.time()
        s.add(br)
        s.commit()
    return {"key": key, "label": spec["label"], "about": spec["about"], "config": spec["config"], "run_id": rid,
            "nonce": nonce, "policy": spec["policy"], "cache": spec["cache"], "started_at": started,
            "completed_at": time.time(), "models": {"small": settings.model_small, "large": settings.model_large},
            "ai_configured": bool(settings.prune_api_key and settings.model_small and settings.model_large),
            "metrics": m}


def waterfall(runs: dict) -> list[dict] | None:
    """Naive -> saved by design -> saved by Prune routing -> saved by Prune cache -> final (SPEC 9.6).
    Only when all four runs have measured costs; otherwise None (never a partial or guessed chart)."""
    c = {k: (runs.get(k) or {}).get("metrics", {}).get("cost_usd") for k in ("R1", "R2", "R3", "R4")}
    if any(v is None for v in c.values()):
        return None
    return [{"step": "Naive (R1)", "usd": c["R1"], "kind": "total"},
            {"step": "Saved by SafeTrail's design (R1 → R2)", "usd": c["R1"] - c["R2"], "kind": "saving"},
            {"step": "Saved by Prune routing (R2 → R3)", "usd": c["R2"] - c["R3"], "kind": "saving"},
            {"step": "Saved by Prune's exact cache (R3 → R4)", "usd": c["R3"] - c["R4"], "kind": "saving"},
            {"step": "SafeTrail + Prune, warm (R4)", "usd": c["R4"], "kind": "total"}]


async def run_many(keys: list[str], *, trips_n: int, nonces: dict[str, str]) -> list[dict]:
    """All requested runs in ONE event loop (the job semaphore binds to the loop that first uses it)."""
    out = []
    for k in keys:
        out.append(await run(k, trips_n=trips_n, nonce=nonces[k]))
    return out
