"""End-to-end with the real local model. Run: python tests/smoke_llm.py"""
import time

from airport_agent.agent.core import Agent

QUESTIONS = [
    "Which airports in New England are strong candidates for terminal expansion?",
    "Why is the top one ranked above the others?",
    "Compare LA and Santa Ana airport congestion levels.",
    "What about SFO instead of Santa Ana?",
    "What is the percentage of long haul flights out of Anchorage airport?",
    "What is the unmet flight demand in SFO airport and why?",
]

agent = Agent()
for q in QUESTIONS:
    t0 = time.time()
    r = agent.ask(q)
    print(f"\n##### {q}\n[{time.time() - t0:.0f}s] plan={r.plan.model_dump(exclude_none=True, exclude_defaults=True)}\n{r.text}", flush=True)
