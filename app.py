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

st.set_page_config(page_title="Airport Investment Agent", page_icon=":material/flight:", layout="wide")



st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
<style>
:root { --accent: #2563eb; --card-border: rgba(100,116,139,.28); }
@media (prefers-color-scheme: dark) { :root { --accent: #60a5fa; --card-border: rgba(148,163,184,.25); } }
.block-container { max-width: 1100px; padding-top: 2.5rem; }
.app-title { display: flex; align-items: center; gap: .75rem; margin: 0 0 1.25rem; text-align: left; }
.app-title i { color: var(--accent); font-size: 1.6rem; transform: rotate(-20deg); }
.app-title h1 { margin: 0; padding: 0; font-size: 2rem; font-weight: 700; letter-spacing: -.02em; }
.app-title span { font-size: .9rem; opacity: .65; margin-left: .25rem; }
[data-testid="stSidebar"] i.fa-plane { color: var(--accent); margin-right: .5rem; }
[data-testid="stMarkdownContainer"], [data-testid="stMetric"], [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] button, [data-testid="stSidebar"] p { text-align: left !important; }
[data-testid="stSidebar"] button { justify-content: flex-start; }
[data-testid="stSidebar"] button p { text-align: left; }
[data-testid="stMetric"] { align-items: flex-start; }
[data-testid="stMetricValue"] { font-weight: 700; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--card-border); }
[data-testid="stChatMessage"] { background: transparent; border: 1px solid var(--card-border);
  border-radius: .75rem; padding: 1rem 1.1rem; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def _llm() -> LLM:
    return LLM()


def _agent() -> Agent:
    if "agent" not in st.session_state:
        st.session_state.agent = Agent(_llm())
        st.session_state.messages = []
    return st.session_state.agent


def _pct(x):
    return "n/a" if x is None else f"{x:.1%}"


def _num(x, nd=1):
    return "n/a" if x is None else f"{x:,.{nd}f}"


SCORE = st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f")


def _rank_view(r: dict):
    rows = r["ranked"]
    top = rows[0]
    tied = sum(1 for x in rows if top["score"] - x["score"] <= 1.0)
    excluded = len(r.get("excluded_below_scale_floor", [])) + len(r.get("excluded_insufficient_data", []))
    c1, c2, c3 = st.columns(3)
    c1.metric("Top candidate", top["iata"], f"score {top['score']:.1f}", delta_color="off")
    c2.metric("Effectively tied at the top", tied, help="Scores within 1 point of the leader.")
    c3.metric("Airports ranked", len(rows), f"{excluded} not ranked", delta_color="off",
              help="Below 500k enplanements or missing data.")
    df = pd.DataFrame([{
        "#": x["rank"], "Airport": x["iata"], "Score": x["score"],
        "Congestion": x["sub_scores"].get("congestion"), "Demand": x["sub_scores"].get("demand_pressure"),
        "Growth": x["sub_scores"].get("growth"),
        "Rank range": "-".join(map(str, x["rank_range_across_weightings"])),
        "Load factor": _pct(x["load_factor"]), "Pax growth": _pct(x["passenger_growth_yoy"]),
    } for x in rows])
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Score": SCORE, "Congestion": SCORE, "Demand": SCORE, "Growth": SCORE,
        "Rank range": st.column_config.TextColumn(help="Best and worst rank across five alternative weightings. "
                                                       "A narrow range means the ranking is robust.")})
    st.bar_chart(df.set_index("Airport")[["Congestion", "Demand", "Growth"]], height=220)
    st.caption("Sub-scores are 0-100 relative to US airports above 500k enplanements. "
               "Expansion score = 35% congestion + 35% demand pressure + 30% growth.")


def _compare_view(r: dict):
    rows = r["airports"]
    for col, a in zip(st.columns(len(rows)), rows):
        col.metric(f"{a['iata']} congestion", f"{a['congestion_score']:.1f}",
                   f"{a['congestion_score'] - rows[0]['congestion_score']:+.1f} vs {rows[0]['iata']}" if a is not rows[0] else None,
                   delta_color="off")
    table = pd.DataFrame({a["iata"]: {
        "Congestion score (0-100)": a["congestion_score"],
        "Departures delayed 15+ min": _pct(a["dep_delay15_rate"]),
        "Avg taxi-out (min)": _num(a["avg_taxi_out_min"]),
        "Cancelled": _pct(a["cancel_rate"]),
        "Departures / runway / day": _num(a["deps_per_runway_day"], 0),
        "Runways": a["runways"],
        "Load factor": _pct(a["load_factor"]),
        "Annual enplanements": _num(a["annual_enplanements"], 0),
    } for a in rows}).astype(str)
    st.dataframe(table, width="stretch")


def _long_haul_view(r: dict):
    lh = r["long_haul"]
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Flights of {lh['threshold_miles']:,}+ miles", _pct(lh["share"]))
    c2.metric("Long-haul departures", f"{lh['long_haul_flights']:,}")
    c3.metric("All departures", f"{lh['total_flights']:,}", r["airport"]["ontime_period"], delta_color="off")
    by = pd.DataFrame({"Share of departures": {f"{e:,}+ mi": v for e, v in r["share_by_threshold"].items()}})
    st.bar_chart(by, height=220)
    st.caption("Share of departures at or above each distance. Domestic flights by large carriers only.")


def _unmet_view(r: dict):
    c1, c2 = st.columns(2)
    c1.metric("Unmet-demand index (proxy)", f"{r['unmet_demand_index']:.1f} / 100",
              help="Built from load factor, air-traffic delay, cancellations and delay rate. "
                   "It is not a count of unserved passengers.")
    m = r["metrics"]
    c2.metric("Load factor", _pct(m.get("load_factor")), f"through {m.get('traffic_data_through')}", delta_color="off")
    drivers = pd.DataFrame([{"Driver": d["metric"].replace("_", " "), "Value": round(d["value"], 3),
                             "Score": d["score"], "Weight": d["weight"]} for d in r["drivers"]])
    st.dataframe(drivers, hide_index=True, width="stretch", column_config={"Score": SCORE})
    left, right = st.columns(2)
    for col, key, title in ((left, "delay_cause_share", "Delay minutes by cause"),
                            (right, "cancel_cause_share", "Cancellations by cause")):
        if r.get(key):
            col.caption(title)
            col.bar_chart(pd.Series(r[key], name="share"), height=200)


def _profile_view(r: dict):
    m = r["metrics"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Congestion score", r["congestion_score"])
    c2.metric("Expansion score", r["expansion_score"])
    c3.metric("Load factor", _pct(m.get("load_factor")))
    c4.metric("Passenger growth", _pct(m.get("passenger_growth_yoy")))


VIEWS = {"rank_region": ("ranked", _rank_view), "compare": ("airports", _compare_view),
         "long_haul_share": ("long_haul", _long_haul_view), "unmet_demand": ("unmet_demand_index", _unmet_view),
         "airport_profile": ("metrics", _profile_view)}


def _details(plan, result: dict | None):
    if not result:
        return
    key, view = VIEWS.get(result.get("intent"), (None, None))
    if view and result.get(key) is not None:
        with st.container(border=True):
            view(result)
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
    st.markdown('<h3 style="text-align:left"><i class="fa-solid fa-plane"></i>Airport Agent</h3>', unsafe_allow_html=True)
    st.caption(f"Model: `{_llm().model}`")
    st.markdown("**Try:**")
    for ex in EXAMPLES:
        if st.button(ex, width="stretch"):
            st.session_state.pending = ex
    if st.button("Reset conversation"):
        st.session_state.pop("agent", None)
        st.rerun()
    st.divider()
    st.caption("Numbers come from public BTS data and deterministic scoring code. The LLM only interprets "
               "your question and explains the results. Scores are 0-100 relative to US peers.")

st.markdown('<div class="app-title"><i class="fa-solid fa-plane"></i><h1>Airport Investment Agent</h1></div>', unsafe_allow_html=True)
for m in st.session_state.messages:
    _render(m)

question = st.session_state.pop("pending", None) or st.chat_input("Ask about US airports…")
if question:
    user = {"role": "user", "text": question}
    st.session_state.messages.append(user)
    _render(user)
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                reply = agent.ask(question)
                msg = {"role": "assistant", "text": reply.text, "plan": reply.plan, "result": reply.result,
                       "grounded": reply.grounded}
            except Exception as e:  # shown to the user rather than a stack trace
                msg = {"role": "assistant", "text": f"Sorry, something went wrong: `{type(e).__name__}: {e}`\n\n"
                                                    "If this is a connection error, check that Ollama is running."}
    st.session_state.messages.append(msg)
    st.rerun()
