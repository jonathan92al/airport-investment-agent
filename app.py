"""Chat UI. Run: streamlit run app.py"""
import json

import pandas as pd
import streamlit as st

from airport_agent.agent.core import Agent, compact
from airport_agent.agent.llm import LLM

EXAMPLES = [
    "Which airports in New England are strong candidates for terminal expansion?",
    "Compare LA and Santa Ana airport congestion levels.",
    "What is the percentage of long haul flights out of Anchorage airport?",
    "What is the unmet flight demand in SFO airport and why?",
]

st.set_page_config(page_title="Airport Investment Agent", page_icon="✈️", layout="wide")


@st.cache_resource
def _llm() -> LLM:
    return LLM()


def _agent() -> Agent:
    if "agent" not in st.session_state:
        st.session_state.agent = Agent(_llm())
        st.session_state.messages = []
    return st.session_state.agent


def _pct(x):
    return None if x is None else f"{x:.1%}"


def _table(result: dict) -> pd.DataFrame | None:
    """A deterministic table of the numbers behind the answer, independent of the LLM's wording."""
    if result.get("ranked"):
        return pd.DataFrame([{
            "Rank": r["rank"], "Airport": r["iata"], "Score": r["score"],
            "Congestion": r["sub_scores"].get("congestion"), "Demand": r["sub_scores"].get("demand_pressure"),
            "Growth": r["sub_scores"].get("growth"), "Rank range*": "-".join(map(str, r["rank_range_across_weightings"])),
            "Load factor": _pct(r["load_factor"]), "Pax growth": _pct(r["passenger_growth_yoy"]),
        } for r in result["ranked"]])
    if result.get("airports") and result["intent"] == "compare":
        return pd.DataFrame([{
            "Airport": a["iata"], "Congestion score": a["congestion_score"], "Delayed >15m": _pct(a["dep_delay15_rate"]),
            "Taxi-out (min)": a["avg_taxi_out_min"] and round(a["avg_taxi_out_min"], 1),
            "Cancelled": _pct(a["cancel_rate"]),
            "Deps/runway/day": a["deps_per_runway_day"] and round(a["deps_per_runway_day"]),
            "Runways": a["runways"], "Load factor": _pct(a["load_factor"]),
        } for a in result["airports"]])
    return None


def _details(plan, result: dict | None):
    if not result:
        return
    table = _table(result)
    if table is not None:
        st.dataframe(table, hide_index=True, use_container_width=True)
        if result.get("ranked"):
            st.caption("*Rank range = best and worst rank across five alternative weightings. "
                       "A narrow range means the ranking is robust to the weights.")
    with st.expander("How this was computed"):
        st.caption("Plan chosen by the LLM router")
        st.json(plan.model_dump(exclude_none=True, exclude_defaults=True))
        st.caption("Results computed by code. The LLM only saw the plain-language `facts` list.")
        st.code(json.dumps(compact(result), indent=1), language="json")


def _render(msg: dict):
    with st.chat_message(msg["role"]):
        if msg.get("grounded") is False:
            st.warning("The model's wording used numbers that are not in the computed results, so the plain "
                       "computed facts are shown instead.")
        st.markdown(msg["text"])
        if msg["role"] == "assistant":
            _details(msg.get("plan"), msg.get("result"))


agent = _agent()

with st.sidebar:
    st.header("Airport Investment Agent")
    st.caption(f"Model: `{_llm().model}` (local)")
    st.markdown("**Try:**")
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True):
            st.session_state.pending = ex
    if st.button("Reset conversation"):
        st.session_state.pop("agent", None)
        st.rerun()
    st.divider()
    st.caption("Numbers come from public BTS data and deterministic scoring code. The LLM only interprets "
               "your question and explains the results. Scores are 0-100 relative to US peers.")

st.title("✈️ Airport Investment Agent")
for m in st.session_state.messages:
    _render(m)

question = st.session_state.pop("pending", None) or st.chat_input("Ask about US airports…")
if question:
    user = {"role": "user", "text": question}
    st.session_state.messages.append(user)
    _render(user)
    with st.chat_message("assistant"):
        with st.spinner("Fetching data and thinking (a local model can take a minute)…"):
            try:
                reply = agent.ask(question)
                msg = {"role": "assistant", "text": reply.text, "plan": reply.plan, "result": reply.result,
                       "grounded": reply.grounded}
            except Exception as e:  # shown to the user rather than a stack trace
                msg = {"role": "assistant", "text": f"Sorry, something went wrong: `{type(e).__name__}: {e}`\n\n"
                                                    "If this is a connection error, check that Ollama is running."}
    st.session_state.messages.append(msg)
    st.rerun()
