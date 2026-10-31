"""Judging rounds on the stage: one tap recaps the round from real rows, resets the demo and starts the next round."""
import time

from sqlmodel import select

from app import core, stage
from app.models import DemoState, LlmCall, SosEvent, Trip


def test_next_round_recaps_resets_and_counts_ai_cost_honestly(s):
    first = stage.round_state(s)
    t, _ = core.create_trip(s, {"name": "Judge", "route_id": "hall", "consent": True})
    core.start_trip(s, t)
    core.receive_sos(s, t, {"client_id": "11111111-aaaa-4bbb-8ccc-000000000001", "kind": "injured", "people_bucket": "1",
                            "lat": 30.35, "lon": 76.37, "created_at_device": time.time()})
    s.add(LlmCall(job_key="inc_1_1", feature="report", status="ok", cost_with_prune_usd=0.00004))
    s.add(LlmCall(job_key="inc_1_1", feature="report", status="ok", cost_with_prune_usd=None))  # unknown cost stays unknown
    s.commit()
    r = stage.next_round(s)
    last = r["last"]
    assert r["round"] == first["round"] + 1 and last["round"] == first["round"]
    assert (last["judges"], last["sos"], last["incidents"]) == (1, 1, 1)
    assert last["ai_calls"] == 2 and abs(last["ai_cost_usd"] - 0.00004) < 1e-12
    assert s.exec(select(SosEvent)).all() == []  # the demo was reset
    assert s.get(Trip, t.id).status == "ended"
    assert s.get(DemoState, "round").value["round"] == r["round"]
    # the next round starts from zero, and with no Prune figures its cost is n/a, never $0
    nxt = stage.round_summary(s, r["round"], r["started_at"])
    assert nxt["judges"] == 0 and nxt["ai_cost_usd"] is None


def test_ai_stats_can_count_from_a_moment(s):
    s.add(LlmCall(job_key="pack_x", feature="pack", status="ok", cost_with_prune_usd=0.001, created_at=time.time() - 3600))
    s.add(LlmCall(job_key="pack_y", feature="pack", status="ok", cost_with_prune_usd=0.002))
    s.commit()
    assert abs(core.ai_stats(s)["cost_usd"] - 0.003) < 1e-12
    assert abs(core.ai_stats(s, since=time.time() - 60)["cost_usd"] - 0.002) < 1e-12
