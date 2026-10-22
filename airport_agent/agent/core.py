"""The conversation loop: route (LLM) -> execute (Python) -> narrate (LLM, checked) -> append caveats (Python)."""
import json
from dataclasses import dataclass, field

from . import executor, guard, prompts
from .llm import LLM
from .plan import Plan


@dataclass
class Reply:
    text: str
    plan: Plan | None = None
    result: dict | None = None
    grounded: bool = True  # False if the LLM's wording was rejected and the plain facts were shown instead
    unsupported: list = field(default_factory=list)


def compact(obj, digits: int = 3):
    """Round floats and drop empty values (used to show raw results compactly)."""
    if isinstance(obj, float):
        return round(obj, digits)
    if isinstance(obj, dict):
        return {k: compact(v, digits) for k, v in obj.items()
                if v is not None and not (isinstance(v, (list, dict)) and not v)}
    if isinstance(obj, list):
        return [compact(v, digits) for v in obj]
    return obj


def notes(result: dict) -> list[str]:
    """Assumptions, answer-specific uncertainty and data caveats, de-duplicated, in that order."""
    return list(dict.fromkeys(result.get("assumptions", []) + result.get("uncertainty", [])
                              + result.get("caveats", [])))


def compose(body: str, result: dict) -> str:
    bullets = "\n".join(f"- {n}" for n in notes(result))
    return f"{body}\n\n**Assumptions & uncertainty**\n{bullets}"


class Agent:
    def __init__(self, llm: LLM | None = None):
        self.llm = llm or LLM()
        self.last_plan: Plan | None = None
        self.last_result: dict | None = None

    def _context(self) -> str | None:
        if not self.last_plan:
            return None
        return json.dumps(self.last_plan.model_dump(exclude_none=True, exclude_defaults=True))

    def ask(self, question: str) -> Reply:
        plan = self.llm.plan([{"role": "system", "content": prompts.ROUTER_SYSTEM},
                              {"role": "user", "content": prompts.router_user(question, self._context())}])

        if plan.intent == "out_of_scope":
            return Reply("I can only help with US airport questions: expansion candidates, congestion "
                         "comparisons, long-haul share, and unmet demand.", plan)

        if plan.intent == "explain_previous":
            if not self.last_result:
                return Reply("There is no earlier answer to explain yet. Ask me about an airport or region first.", plan)
            result = self.last_result
        else:
            result = executor.run(plan)
            if result.get("clarification"):
                return Reply(result["clarification"], plan, result)
            self.last_plan, self.last_result = plan, result

        facts = "\n".join(f"- {f}" for f in result["facts"])
        draft = self.llm.narrate([{"role": "system", "content": prompts.NARRATOR_SYSTEM},
                                  {"role": "user", "content": f"Question: {question}\n\nFACTS:\n{facts}"}])
        bad = guard.unsupported_numbers(draft, result["facts"] + [question])
        if bad or not draft:
            return Reply(compose("Here are the computed facts:\n" + facts, result), plan, result,
                         grounded=False, unsupported=bad)
        return Reply(compose(draft, result), plan, result)
