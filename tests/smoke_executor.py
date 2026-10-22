"""Executor on real data with hand-written plans (no LLM). Run: python tests/smoke_executor.py"""
import json

from airport_agent.agent import core, executor
from airport_agent.agent.plan import Plan

PLANS = [
    Plan(intent="rank_region", region="New England"),
    Plan(intent="compare", airports=["LA", "Santa Ana"]),
    Plan(intent="long_haul_share", airports=["Anchorage"]),
    Plan(intent="unmet_demand", airports=["SFO"]),
]
for p in PLANS:
    r = executor.run(p)
    text = json.dumps(core.compact(r), indent=1)
    print(f"=== {p.intent} | {len(text)} chars (~{len(text) // 4} tokens)")
    print("assumptions:", r["assumptions"], "| clarification:", r.get("clarification"), "| unresolved:", r.get("unresolved"))
