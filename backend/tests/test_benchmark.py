"""Benchmark plumbing with AI off: same scenario, exact computed counts, honest n/a costs, nonce and run tags."""
import asyncio
import json

from fastapi.testclient import TestClient

from app import benchmark
from app.ai import jobs


def test_scenario_matches_spec_shape():
    sc, labels = benchmark.load_scenario()
    assert len(sc["trips"]) == 500 and len(sc["zones"]) == 6 and len(sc["sos"]) == 40
    assert sum(1 for g in labels["groups"].values() if g["type"] == "cluster") == 3
    assert sum(1 for g in labels["groups"].values() if g["type"] == "single") == 6
    assert sum(1 for n in labels["notes"] if n["is_injection"]) == 4
    assert {n["lang"] for n in labels["notes"]} == {"en", "hi", "as"}
    blob = json.dumps(sc, ensure_ascii=False)
    assert "@" not in blob and "+91" not in blob  # no contact details anywhere in the scenario


def test_design_run_counts_exactly_and_never_invents_costs():
    jobs._sem = None
    try:
        r = asyncio.run(benchmark.run_many(["R2"], trips_n=40, nonces={"R2": "testnonce"}))[0]
    finally:
        jobs._sem = None
    m = r["metrics"]
    assert m["count_accuracy_pct"] == 100.0 and m["incidents"] == 9
    assert m["calls"] == 0 and m["cost_usd"] is None and m["cost_per_trip_usd"] is None  # AI off: n/a, not $0
    assert m["template_fallbacks"] == m["jobs"] > 0
    assert m["injection_caught_scanner"] == 2 and m["clean_notes_flagged"] == 0  # English tricks only, no false alarms
    assert benchmark.waterfall({"R2": r}) is None  # never a partial or guessed chart


def test_bench_context_adds_nonce_and_forces_tier():
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "{}"}]
    assert jobs.with_nonce(msgs, "abc")[0]["content"] == "sys [run abc]"
    assert jobs.with_nonce(jobs.with_nonce(msgs, "abc"), "abc")[0]["content"] == "sys [run abc]"  # added once
    assert jobs.with_nonce(msgs, "") is msgs


def test_benchmark_endpoint_reports_not_run(monkeypatch, tmp_path):
    from app import config
    from app.main import app

    monkeypatch.setattr(config, "REPO_DIR", tmp_path)
    r = TestClient(app).get("/api/benchmark")
    assert r.status_code == 200 and r.json()["status"] == "not_run"
