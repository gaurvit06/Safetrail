"""scripts/prune_check.py: the report must reflect exactly what Prune returned, and probe() must never raise."""
import importlib.util
import pathlib

import httpx
import openai

from app.ai import prune_client

_spec = importlib.util.spec_from_file_location("prune_check", pathlib.Path(__file__).resolve().parents[2] / "scripts" / "prune_check.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


def _err(status: int, code: str):
    resp = httpx.Response(status, request=httpx.Request("POST", "https://api.withprune.com/v1/chat/completions"),
                          headers={"x-prune-shield-code": code}, json={"error": {"code": code}})
    return openai.APIStatusError(f"{status} {code}", response=resp, body={"error": {"code": code}})


class _RawOK:
    status_code = 200
    headers = {"x-prune-cache-hit": "false", "content-type": "application/json"}
    text = '{"choices": [], "prune_metadata": {"cost_with_prune_usd": 0.00002, "receipt_signature": "abc"}}'


class _Client:
    def __init__(self, outcome):
        self.outcome, self.chat, self.completions, self.with_raw_response = outcome, self, self, self

    def with_options(self, **_):
        return self

    def create(self, **_):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def test_probe_returns_raw_body_and_errors_without_raising(monkeypatch):
    monkeypatch.setattr(prune_client, "_client", lambda key: _Client(_RawOK()))
    r = prune_client.probe(model="m", messages=[{"role": "user", "content": "hi"}], headers={})
    assert r["ok"] and r["status"] == 200 and r["body"]["prune_metadata"]["receipt_signature"] == "abc"
    monkeypatch.setattr(prune_client, "_client", lambda key: _Client(_err(429, "run_budget")))
    r = prune_client.probe(model="m", messages=[{"role": "user", "content": "hi"}], headers={})
    assert not r["ok"] and r["status"] == 429 and r["error_code"] == "run_budget"


def test_field_report_finds_used_and_unknown_fields():
    meta = {"cost_with_prune_usd": 0.0001, "receipt_signature": "sig", "brand_new": {"thing": 1}}
    hdrs = {"x-prune-cache-hit": "true", "x-prune-something-new": "x", "content-type": "application/json"}
    rep = pc.field_report(meta, hdrs)
    assert rep["extracted"]["cache_hit"] is True and rep["extracted"]["receipt_signature"] == "sig"
    used = {m["path"]: m["used"] for m in rep["meta"]}
    assert used == {"cost_with_prune_usd": True, "receipt_signature": True, "brand_new.thing": False}
    hused = {h["name"]: h["used"] for h in rep["headers"]}
    assert hused == {"x-prune-cache-hit": True, "x-prune-something-new": False}  # non-Prune headers are not listed


def _ok(meta=None, headers=None, status=200):
    return {"ok": True, "status": status, "headers": headers or {}, "body": {"prune_metadata": meta or {}}, "error_code": None}


def _fail(status, code):
    return {"ok": False, "status": status, "headers": {"x-prune-shield-code": code}, "body": {"error": {"code": code}}, "error_code": code}


def test_verdicts_and_markdown_come_only_from_results():
    results = {
        "basic": _ok({"cost_with_prune_usd": 0.00003, "receipt_signature": "sig"}, {"x-prune-cache-hit": "false"}),
        "cache": _ok({"receipt_signature": "sig"}, {"x-prune-cache-hit": "true"}),
        "run_budget": _fail(429, "run_budget"),
        "injection": _ok({}, {"x-prune-shield-code": "prompt_injection_signal"}),
        "policy_off": _fail(400, "invalid_header"),
        "large": _fail(403, "model_blocked"),
    }
    v = {x["check"]: x["level"] for x in pc.verdicts(results)}
    assert v == {"basic": "ok", "cache": "ok", "run_budget": "ok", "injection": "ok", "policy_off": "warn", "large": "fail"}
    md = pc.fields_markdown(results, "2026-01-01 00:00 UTC")
    assert "| `receipt_signature` | sig |" in md
    assert "| `cost_without_prune_usd` | **missing** |" in md  # never filled in with a guess
    assert "x-prune-shield-code" not in md.split("## Every Prune header seen")[1].split("##")[0]  # basic call had none


def test_an_empty_reply_through_the_app_fails_the_check():
    assert pc.verdicts({"app_path": {"ok": True, "row": {}, "reply_chars": 0}})[0]["level"] == "fail"
    assert pc.verdicts({"app_path": {"ok": True, "row": {}, "reply_chars": 9}})[0]["level"] == "ok"


def test_only_the_cache_checks_use_prunes_cache():
    calls = {c["name"]: c["headers"]["X-Prune-Cache"] for c in pc.plan("abc")}
    for name in ("basic", "cache", "cache_new_run", "cache_safety"):
        assert calls.pop(name) == "exact"
    assert set(calls.values()) == {"off"}


def test_a_cached_answer_for_a_different_request_fails_the_check():
    assert pc.verdicts({"cache_safety": _ok({}, {"x-prune-cache-hit": "true"})})[0]["level"] == "fail"
    assert pc.verdicts({"cache_safety": _ok({}, {"x-prune-cache-hit": "false"})})[0]["level"] == "ok"


def test_no_signal_and_missing_receipt_are_warnings():
    results = {"basic": _ok({"cost_with_prune_usd": 0.1}), "cache": _ok({}, {"x-prune-cache-hit": "false"}),
               "injection": _ok({}, {})}
    v = {x["check"]: x["level"] for x in pc.verdicts(results)}
    assert v == {"basic": "warn", "cache": "warn", "injection": "warn"}
