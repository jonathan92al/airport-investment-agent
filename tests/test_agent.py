import pytest

from airport_agent.agent import core, guard, regions
from airport_agent.agent.plan import Plan


def test_region_resolution():
    assert regions.resolve("New England") == ["CT", "MA", "ME", "NH", "RI", "VT"]
    assert regions.resolve("the Northeast") == regions.resolve("northeast")
    assert regions.resolve("Texas") == ["TX"]
    assert regions.resolve("CA and Nevada") == ["CA", "NV"]
    assert regions.resolve("Narnia") is None
    assert regions.resolve(None) is None


FACTS = ["#1 BOS: expansion score 64.7. Load factor 81.7%, passenger growth -2.4%, 20,983,745 annual enplanements.",
         "BOS rank is 1 to 5 across alternative weightings (sensitive to the weights)."]


class FakeLLM:
    """Returns scripted plans/drafts and records what the narrator was shown."""

    def __init__(self, plans, drafts=None):
        self.plans, self.drafts = list(plans), list(drafts or [])
        self.router_prompts, self.narrator_prompts = [], []

    def plan(self, messages):
        self.router_prompts.append(messages[-1]["content"])
        return self.plans.pop(0)

    def narrate(self, messages, max_tokens=1200):
        self.narrator_prompts.append(messages[-1]["content"])
        return self.drafts.pop(0) if self.drafts else "BOS scores 64.7."


@pytest.fixture
def fake_executor(monkeypatch):
    def run(plan):
        if plan.airports == ["Nowhere"]:
            return {"intent": plan.intent, "clarification": "Which airport?"}
        return {"intent": plan.intent, "facts": list(FACTS), "assumptions": ["Used BOS."],
                "uncertainty": ["Weights are judgment calls."], "caveats": ["Domestic flights only."]}
    monkeypatch.setattr(core.executor, "run", run)


def test_follow_up_receives_previous_plan_as_context(fake_executor):
    llm = FakeLLM([Plan(intent="compare", airports=["LAX", "SFO"]),
                   Plan(intent="compare", airports=["LAX", "SNA"])])
    agent = core.Agent(llm)
    agent.ask("Compare LAX and SFO")
    agent.ask("What about SNA instead of SFO?")
    assert "PREVIOUS TURN: none" in llm.router_prompts[0]
    assert '"intent": "compare"' in llm.router_prompts[1] and "LAX" in llm.router_prompts[1]


def test_narrator_sees_only_facts_and_reply_ends_with_code_written_notes(fake_executor):
    llm = FakeLLM([Plan(intent="airport_profile", airports=["BOS"])])
    reply = core.Agent(llm).ask("Tell me about BOS")
    assert "FACTS:" in llm.narrator_prompts[0] and "RESULTS" not in llm.narrator_prompts[0]
    assert reply.grounded
    tail = reply.text.split("**Assumptions & uncertainty**")[1]
    for note in ("Used BOS.", "Weights are judgment calls.", "Domestic flights only."):
        assert note in tail


def test_invented_number_is_rejected_and_facts_shown_instead(fake_executor):
    llm = FakeLLM([Plan(intent="airport_profile", airports=["BOS"])], drafts=["BOS growth is -0.024% and 18.5 delay."])
    reply = core.Agent(llm).ask("Tell me about BOS")
    assert not reply.grounded and 18.5 in reply.unsupported
    assert "64.7" in reply.text and "-0.024" not in reply.text
    assert "Domestic flights only." in reply.text  # caveats still appended


def test_empty_or_truncated_draft_falls_back_to_facts(fake_executor):
    llm = FakeLLM([Plan(intent="airport_profile", airports=["BOS"])], drafts=[""])
    reply = core.Agent(llm).ask("Tell me about BOS")
    assert not reply.grounded and "64.7" in reply.text


def test_clarification_skips_narrator_and_keeps_previous_context(fake_executor):
    llm = FakeLLM([Plan(intent="airport_profile", airports=["BOS"]),
                   Plan(intent="airport_profile", airports=["Nowhere"]),
                   Plan(intent="explain_previous")])
    agent = core.Agent(llm)
    agent.ask("Tell me about BOS")
    reply = agent.ask("Tell me about Nowhere")
    assert reply.text == "Which airport?" and len(llm.narrator_prompts) == 1
    agent.ask("Why?")
    assert "BOS" in llm.narrator_prompts[-1]  # explained the last *successful* result


def test_explain_previous_without_history_and_out_of_scope(fake_executor):
    llm = FakeLLM([Plan(intent="explain_previous"), Plan(intent="out_of_scope")])
    agent = core.Agent(llm)
    assert "no earlier answer" in agent.ask("Why?").text
    assert "only help with US airport" in agent.ask("What's the weather on Mars?").text
    assert llm.narrator_prompts == []


def test_guard_accepts_copied_numbers_and_ignores_small_counts_and_list_markers():
    answer = "1. BOS scores 64.7 with 20,983,745 enplanements; passenger growth -2.4%. Two of 5 airports."
    assert guard.unsupported_numbers(answer, FACTS) == []


def test_guard_catches_the_unit_and_rounding_errors_seen_with_the_7b_model():
    assert guard.unsupported_numbers("Growth is -0.024%.", FACTS) == [0.024]
    assert guard.unsupported_numbers("About 21 million enplanements.", FACTS) == [21.0]
    assert guard.unsupported_numbers("The index is 86.3%.", ["Index 86.3 out of 100."]) == []  # % is not a unit check
