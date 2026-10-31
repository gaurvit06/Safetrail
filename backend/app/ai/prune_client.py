"""The ONLY module that imports the OpenAI SDK (SPEC 1.1, 5.13). Every LLM call goes through Prune.

chat() sends the standard Prune headers, captures prune_metadata and response headers, logs every
attempt to LlmCall, publishes `ai.call` events, and applies the retry table in SPEC 5.13.
"""
import asyncio
import hashlib
import json
import random
import time
from collections import Counter, deque
from dataclasses import dataclass, field

import openai
from openai import OpenAI
from sqlmodel import Session

from .. import events
from ..config import settings
from ..db import engine
from ..models import LlmCall
from .pii import scrub

FAIL_CLOSED = {"shield_unavailable", "check_failed"}
PAUSE_CODES = {"rate_limit", "anomaly_spike", "loop_detected"}
STOP_CODES = {"run_budget", "agent_step_budget", "spend_cap", "customer_budget"}
PLAN_CODES = {"plan_limit", "free_trial_ended"}


class AIUnavailable(Exception):
    """The AI can't be used for this job: the caller must fall back to the template."""

    def __init__(self, code: str, http_status: int | None = None):
        super().__init__(code)
        self.code = code
        self.http_status = http_status

    @property
    def is_budget_stop(self) -> bool:
        return self.code in STOP_CODES or self.code in {"governor", "loop_guard", "max_steps"}


@dataclass
class ChatResult:
    content: str
    llm_call_id: int
    cache_hit: bool | None
    cost_with_prune_usd: float | None
    estimated_cost_usd: float | None
    model_used: str | None
    shield_code: str | None
    metadata: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)


_clients: dict[str, OpenAI] = {}
_call_times: deque = deque()
_paused_until = 0.0
_plan_blocked = False
_payload_counts: dict[str, Counter] = {}


def configured(key: str = "ops") -> bool:
    k = settings.prune_api_key if key == "ops" else settings.prune_public_api_key
    return bool(k and settings.model_small and settings.model_large) and not _plan_blocked


def _client(key: str) -> OpenAI:
    api_key = settings.prune_api_key if key == "ops" else settings.prune_public_api_key
    if not api_key:
        raise AIUnavailable("ai_not_configured")
    if key not in _clients:
        _clients[key] = OpenAI(base_url=settings.prune_base_url, api_key=api_key, max_retries=0)
    return _clients[key]


async def _rate_gate() -> None:
    while True:
        now = time.time()
        if now < _paused_until:
            await asyncio.sleep(min(1.0, _paused_until - now))
            continue
        while _call_times and now - _call_times[0] > 60:
            _call_times.popleft()
        if len(_call_times) < settings.max_calls_per_min:
            _call_times.append(now)
            return
        await asyncio.sleep(0.5)


def prune_headers(run_id: str, budget_usd: float | None, max_steps: int | None, feature: str, route_id: str,
                  cache: str, policy: str) -> dict:
    h = {
        "X-Prune-Run-Id": run_id,
        "X-Prune-Feature-Id": feature,
        "X-Prune-Customer-Id": f"route_{route_id}",
        "X-Prune-Cache": cache,
        "X-Prune-Model-Policy": policy,
        "X-Prune-Injection": settings.prune_injection_mode,
    }
    if budget_usd is not None:
        h["X-Prune-Run-Budget-Usd"] = f"{budget_usd:.6f}"
    if max_steps is not None:
        h["X-Prune-Max-Steps"] = str(max_steps)
    return h


def _first(d: dict, *paths):
    for p in paths:
        cur = d
        for part in p.split("."):
            if not isinstance(cur, dict) or part not in cur:
                cur = None
                break
            cur = cur[part]
        if cur is not None:
            return cur
    return None


def _num(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _bool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    return str(v).lower() in {"true", "1", "yes", "hit"}


def _extract(meta: dict, headers: dict) -> dict:
    """Map Prune metadata + headers to LlmCall fields. Exact names are CONFIRMed in docs/PRUNE_FIELDS.md;
    unknown values stay None and the UI shows n/a (never a guess)."""
    hd = {k.lower(): v for k, v in (headers or {}).items()}
    meta = meta or {}
    return {
        "route_applied": _bool(hd.get("x-prune-route-applied")),
        "original_model": hd.get("x-prune-original-model"),
        "routed_model": hd.get("x-prune-routed-model"),
        "route_reason": hd.get("x-prune-route-reason"),
        "route_fallback": hd.get("x-prune-route-fallback"),
        "provider": hd.get("x-prune-provider"),
        "shield_code": hd.get("x-prune-shield-code") or _first(meta, "shield_code", "shield.code"),
        "cache_hit": _bool(hd.get("x-prune-cache-hit")) if "x-prune-cache-hit" in hd else _bool(_first(meta, "cache_hit", "cache.hit")),
        "cost_with_prune_usd": _num(_first(meta, "cost_with_prune_usd", "cost.with_prune_usd", "cost_usd")),
        "cost_without_prune_usd": _num(_first(meta, "cost_without_prune_usd", "cost.without_prune_usd")),
        "cost_saved_usd": _num(_first(meta, "cost_saved_usd", "cost_saved", "cost.saved_usd")) or _num(hd.get("x-prune-cost-saved")),
        "tokens_saved": _first(meta, "tokens_saved", "optimizations.tokens_saved"),
        "optimizations_applied": _first(meta, "optimizations_applied", "optimizations"),
        "pii_shield": _first(meta, "pii_shield", "shield.pii"),
        "receipt_signature": _first(meta, "receipt_signature", "receipt.signature"),
        "receipt_signing_key_id": _first(meta, "receipt_signing_key_id", "receipt.key_id", "signing_key_id"),
    }


def _err_code(e: Exception) -> str:
    headers = getattr(getattr(e, "response", None), "headers", {}) or {}
    code = headers.get("x-prune-shield-code") if hasattr(headers, "get") else None
    body = getattr(e, "body", None)
    if not code and isinstance(body, dict):
        code = _first(body, "error.code", "code", "error.type", "shield_code")
    if not code:
        status = getattr(e, "status_code", None)
        code = {402: "plan_limit", 429: "rate_limit", 403: "forbidden"}.get(status, f"http_{status}")
    return str(code)


def _estimate(messages: list[dict], max_tokens: int, tier: str) -> float:
    from ..config import PRICE_TABLE

    chars = sum(len(m.get("content", "")) for m in messages)
    p = PRICE_TABLE.get(tier, PRICE_TABLE["small"])
    return (chars / 4) / 1e6 * p["in"] + max_tokens / 1e6 * p["out"]


def _log(fields: dict) -> int:
    with Session(engine) as s:
        row = LlmCall(**fields)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id


def _publish_call(call_id: int, feature: str, fields: dict) -> None:
    events.publish("ai.call", {
        "call_id": call_id, "feature": feature, "tier": fields.get("tier"), "requested_model": fields.get("requested_model"),
        "routed_model": fields.get("routed_model"), "route_applied": fields.get("route_applied"),
        "route_reason": fields.get("route_reason"), "cache_hit": fields.get("cache_hit"),
        "cost_with_usd": fields.get("cost_with_prune_usd"), "cost_without_usd": fields.get("cost_without_prune_usd"),
        "latency_ms": fields.get("latency_ms"), "escalated": fields.get("escalated", False),
        "shield_code": fields.get("shield_code"), "status": fields.get("status"), "error_code": fields.get("error_code"),
    }, events.OPS, route_id=fields.get("route_id"))


async def chat(*, job_key: str, run_id: str, feature: str, route_id: str, model: str, tier: str,
               messages: list[dict], max_tokens: int, budget_usd: float | None, max_steps: int | None,
               cache: str | None = None, policy: str | None = None, key: str = "ops", timeout: float = 20,
               escalated: bool = False, benchmark_run_id: int | None = None) -> ChatResult:
    global _paused_until, _plan_blocked
    if _plan_blocked:
        raise AIUnavailable("plan_limit")
    if not model:
        raise AIUnavailable("ai_not_configured")
    client = _client(key)
    cache = cache or settings.prune_cache_mode
    policy = policy or settings.prune_model_policy
    headers = prune_headers(run_id, budget_usd, max_steps, feature, route_id, cache, policy)
    payload_hash = hashlib.sha256(json.dumps([model, messages, max_tokens], sort_keys=True).encode()).hexdigest()
    counts = _payload_counts.setdefault(run_id, Counter())
    est = _estimate(messages, max_tokens, tier)
    preview = scrub(json.dumps(messages[-1:], ensure_ascii=False))[:1500]
    base = {"job_key": job_key, "run_id": run_id, "feature": feature, "route_id": route_id, "tier": tier,
            "requested_model": model,
            "cache_mode": cache, "model_policy": policy, "estimated_cost_usd": est, "prompt_preview": preview,
            "escalated": escalated, "key_used": key, "benchmark_run_id": benchmark_run_id}

    for attempt in range(2):
        if counts[payload_hash] >= 2:  # Prune flags agent_loop at 3 identical steps
            raise AIUnavailable("loop_guard")
        counts[payload_hash] += 1
        await _rate_gate()
        t0 = time.time()
        try:
            raw = await asyncio.to_thread(
                lambda: client.with_options(timeout=timeout).chat.completions.with_raw_response.create(
                    model=model, messages=messages, max_tokens=max_tokens, temperature=0, stream=False,
                    extra_headers=headers))
            resp_headers = dict(raw.headers)
            parsed = raw.parse()
            body = parsed.model_dump()
            meta = body.get("prune_metadata") or {}
            content = (parsed.choices[0].message.content or "") if parsed.choices else ""
            usage = body.get("usage") or {}
            fields = {**base, **_extract(meta, resp_headers), "http_status": raw.status_code,
                      "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                      "latency_ms": int((time.time() - t0) * 1000), "raw_metadata": meta, "raw_headers": resp_headers,
                      "status": "ok" if attempt == 0 else "retried"}
            cid = _log(fields)
            _publish_call(cid, feature, fields)
            return ChatResult(content=content, llm_call_id=cid, cache_hit=fields["cache_hit"],
                              cost_with_prune_usd=fields["cost_with_prune_usd"], estimated_cost_usd=est,
                              model_used=fields.get("routed_model") or body.get("model") or model,
                              shield_code=fields["shield_code"], metadata=meta, headers=resp_headers)
        except openai.APIStatusError as e:
            status, code = e.status_code, _err_code(e)
            resp_headers = dict(getattr(e.response, "headers", {}) or {})
            fields = {**base, **_extract({}, resp_headers), "http_status": status, "status": "error",
                      "error_code": code, "latency_ms": int((time.time() - t0) * 1000), "raw_headers": resp_headers}
            fields["shield_code"] = fields.get("shield_code") or code
            cid = _log(fields)
            _publish_call(cid, feature, fields)
            if status == 503 and (code in FAIL_CLOSED or code.startswith("shield_preflight")) and attempt == 0:
                await asyncio.sleep(min(float(resp_headers.get("retry-after", 2) or 2), 10))
                continue
            if status == 429 and code in PAUSE_CODES and attempt == 0:
                _paused_until = time.time() + 20
                events.publish("system.degraded", {"reason": code, "resume_in_s": 20}, events.OPS)
                await asyncio.sleep(20)
                continue
            if status == 402 or code in PLAN_CODES:
                _plan_blocked = True
                events.publish("system.degraded", {"reason": code, "resume_in_s": None}, events.OPS)
                raise AIUnavailable(code, status)
            if status >= 500 and attempt == 0:
                await asyncio.sleep(1 + random.random())
                continue
            raise AIUnavailable(code, status)
        except (openai.APITimeoutError, openai.APIConnectionError) as e:
            code = "timeout" if isinstance(e, openai.APITimeoutError) else "connection"
            fields = {**base, "status": "error", "error_code": code, "latency_ms": int((time.time() - t0) * 1000)}
            cid = _log(fields)
            _publish_call(cid, feature, fields)
            if attempt == 0:
                await asyncio.sleep(1 + random.random())
                continue
            raise AIUnavailable(code)
    raise AIUnavailable("retries_exhausted")


def _json_or_text(text: str):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return text


def probe(*, model: str, messages: list[dict], headers: dict, max_tokens: int = 60, key: str = "ops",
          timeout: float = 30) -> dict:
    """Diagnostics for scripts/prune_check.py: ONE raw call, no retry, no logging, no events.

    Returns the HTTP status, response headers and JSON body exactly as Prune sent them (or the error), so the real
    field names can be written into docs/PRUNE_FIELDS.md. Lives here because this is the only module allowed to use
    the OpenAI SDK.
    """
    client = _client(key)
    t0 = time.time()
    try:
        raw = client.with_options(timeout=timeout).chat.completions.with_raw_response.create(
            model=model, messages=messages, max_tokens=max_tokens, temperature=0, stream=False, extra_headers=headers)
        return {"ok": True, "status": raw.status_code, "headers": dict(raw.headers), "body": _json_or_text(raw.text),
                "error_code": None, "latency_ms": int((time.time() - t0) * 1000)}
    except openai.APIStatusError as e:
        return {"ok": False, "status": e.status_code, "headers": dict(getattr(e.response, "headers", {}) or {}),
                "body": e.body if e.body is not None else _json_or_text(getattr(e.response, "text", "")),
                "error_code": _err_code(e), "latency_ms": int((time.time() - t0) * 1000)}
    except (openai.APITimeoutError, openai.APIConnectionError) as e:
        return {"ok": False, "status": None, "headers": {}, "body": str(e),
                "error_code": "timeout" if isinstance(e, openai.APITimeoutError) else "connection",
                "latency_ms": int((time.time() - t0) * 1000)}


def reset_state() -> None:
    """Test helper."""
    global _paused_until, _plan_blocked
    _paused_until, _plan_blocked = 0.0, False
    _payload_counts.clear()
    _call_times.clear()
    _clients.clear()
