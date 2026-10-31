"""AI job runner (SPEC 5.8 steps 1-6, 5.12 budget layers).

Every job: governor check -> Prune call -> parse + validate -> 1 repair call -> optional escalation
-> template fallback. Jobs are idempotent by job_key, so a restart never pays twice for finished work.
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable

from sqlmodel import Session, select

from .. import events
from ..config import JOB_CFG, model_for, settings
from ..db import engine
from ..models import AiJob
from .prune_client import STOP_CODES, AIUnavailable, _estimate, chat, configured
from .validators import parse_json

REUSE_STOPS = STOP_CODES | {"governor", "loop_guard", "max_steps"}
_sem: asyncio.Semaphore | None = None
_tasks: set = set()


@dataclass
class JobResult:
    output: dict
    source: str  # ai|template
    llm_call_ids: list[int] = field(default_factory=list)
    stopped_by: str | None = None
    shield_codes: list[str] = field(default_factory=list)
    escalated: bool = False


def spawn(coro) -> None:
    """Run a coroutine in the background from sync or async code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        t = loop.create_task(coro)
        _tasks.add(t)
        t.add_done_callback(_tasks.discard)
    elif events._loop is not None and events._loop.is_running():
        asyncio.run_coroutine_threadsafe(coro, events._loop)
    else:
        asyncio.run(coro)


def public_spent_usd() -> float:
    """Spend on the public (Break-it) key: Prune's actual cost where known, else the governor's estimate."""
    from ..models import LlmCall

    with Session(engine) as s:
        rows = s.exec(select(LlmCall).where(LlmCall.key_used == "public")).all()
    return sum((r.cost_with_prune_usd if r.cost_with_prune_usd is not None else (r.estimated_cost_usd or 0))
               for r in rows if r.status in ("ok", "retried"))


def _sema() -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(settings.max_concurrent_ai_jobs)
    return _sem


async def run_job(*, job_key: str, feature: str, route_id: str, run_id: str, messages: list[dict],
                  validate: Callable[[dict], tuple[dict, list[str]]], template: Callable[[], dict],
                  tier: str | None = None, budget_usd: float | None = None, max_steps: int | None = None,
                  max_tokens: int | None = None, key: str = "ops", escalate_upfront: bool = False,
                  allow_escalation: bool = False, governor: bool = True, policy: str | None = None,
                  cache: str | None = None, timeout: float = 20, benchmark_run_id: int | None = None,
                  run_budget_header: float | None = None) -> JobResult:
    cfg = JOB_CFG[feature]
    tier = tier or cfg["tier"]
    budget = cfg["budget_usd"] if budget_usd is None else budget_usd
    steps_cap = cfg["max_steps"] if max_steps is None else max_steps
    max_tokens = max_tokens or cfg["max_tokens"]

    with Session(engine) as s:
        job = s.exec(select(AiJob).where(AiJob.job_key == job_key)).first()
        if job and (job.status == "done" or (job.status == "template" and job.stopped_by in REUSE_STOPS)):
            return JobResult(job.output, job.source or "template", list(job.llm_call_ids or []), job.stopped_by)
        if not job:
            job = AiJob(job_key=job_key, feature=feature, budget_usd=budget, benchmark_run_id=benchmark_run_id)
        job.status, job.error = "running", None
        s.add(job)
        s.commit()

    result, source, stopped, ids, shields = None, "template", None, [], []
    spent, steps, rejections, escalated = 0.0, 0, 0, False
    tiers = ["large"] if escalate_upfront else [tier] + (["large"] if allow_escalation and tier == "small" else [])
    escalated = escalate_upfront

    async with _sema():
        if not configured(key):
            stopped = "ai_not_configured"
        elif key == "public" and public_spent_usd() >= settings.public_budget_usd:
            stopped = "public_budget"
            events.publish("ai.stopped", {"job_id": job_key, "feature": feature, "by": "public_budget",
                                          "spent_usd": public_spent_usd(), "budget_usd": settings.public_budget_usd},
                           events.OPS)
        else:
            for i, t in enumerate(tiers):
                if i > 0:
                    escalated = True
                est = _estimate(messages, max_tokens, t)
                if governor and spent + est > budget:
                    if t == "large" and spent + _estimate(messages, max_tokens, "small") <= budget:
                        t = "small"
                    else:
                        stopped = "governor"
                        events.publish("ai.budget_skip", {"job_id": job_key, "feature": feature, "by": "governor",
                                                          "spent_usd": spent, "budget_usd": budget}, events.OPS)
                        break
                try:
                    attempt_msgs = messages
                    for repair in (False, True):
                        steps += 1
                        if steps > steps_cap:
                            raise AIUnavailable("max_steps")
                        r = await chat(job_key=job_key, run_id=run_id, feature="repair" if repair else feature,
                                       route_id=route_id, model=model_for("small" if repair else t),
                                       tier="small" if repair else t, messages=attempt_msgs, max_tokens=max_tokens,
                                       budget_usd=run_budget_header if run_budget_header is not None else budget,
                                       max_steps=steps_cap, cache=cache, policy=policy, key=key, timeout=timeout,
                                       escalated=escalated, benchmark_run_id=benchmark_run_id)
                        ids.append(r.llm_call_id)
                        if r.shield_code:
                            shields.append(r.shield_code)
                        spent += r.cost_with_prune_usd if r.cost_with_prune_usd is not None else (r.estimated_cost_usd or 0)
                        try:
                            cleaned, errs = validate(parse_json(r.content))
                        except ValueError as e:
                            cleaned, errs = None, [str(e)]
                        if not errs:
                            result, source = cleaned, "ai"
                            break
                        rejections += 1
                        attempt_msgs = messages + [
                            {"role": "assistant", "content": (r.content or "")[:4000]},
                            {"role": "user", "content": "That JSON failed validation: " + "; ".join(errs[:6])
                             + ". Return the corrected JSON object only, using only facts from the input."}]
                    if result is not None:
                        break
                except AIUnavailable as e:
                    stopped = e.code
                    if e.is_budget_stop:
                        events.publish("ai.stopped", {"job_id": job_key, "feature": feature, "by": e.code,
                                                      "spent_usd": spent, "budget_usd": budget}, events.OPS)
                    break

    if result is None:
        result, source = template(), "template"
    with Session(engine) as s:
        job = s.exec(select(AiJob).where(AiJob.job_key == job_key)).first()
        job.status = "done" if source == "ai" else "template"
        job.source, job.output, job.llm_call_ids = source, result, ids
        job.spent_usd, job.steps_used, job.stopped_by = spent, steps, stopped
        job.validator_rejections, job.escalated, job.completed_at = rejections, escalated, time.time()
        s.add(job)
        s.commit()
    return JobResult(result, source, ids, stopped, shields, escalated)
