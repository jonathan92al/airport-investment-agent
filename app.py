"""Chat UI. Run: streamlit run app.py"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from airport_agent.agent.core import Agent, compact
from airport_agent.agent.llm import LLM
from airport_agent.voice import Voice

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
.block-container { max-width: 1100px; padding-top: 4rem; }
.hero { position: relative; display: flex; align-items: center; gap: 1.1rem; margin: 0 0 1.5rem; padding: 1.4rem 1.5rem;
  text-align: left; border: 1px solid var(--card-border); border-radius: 1rem; overflow: hidden;
  background: linear-gradient(120deg, rgba(37,99,235,.14), rgba(14,165,233,.06) 55%, transparent); }
@media (prefers-color-scheme: dark) { .hero { background: linear-gradient(120deg, rgba(96,165,250,.18), rgba(56,189,248,.07) 55%, transparent); } }
.hero::after { content: ""; position: absolute; right: -2.5rem; top: -2.5rem; width: 11rem; height: 11rem; border-radius: 50%;
  background: radial-gradient(circle, rgba(96,165,250,.28), transparent 70%); pointer-events: none; }
.hero-badge { flex: none; display: grid; place-items: center; width: 3.4rem; height: 3.4rem; border-radius: .9rem;
  color: #fff; font-size: 1.5rem; background: linear-gradient(135deg, #2563eb, #0ea5e9); box-shadow: 0 6px 18px rgba(37,99,235,.35); }
.hero-badge i { transform: rotate(-20deg); }
.hero h1 { margin: 0; padding: 0; font-size: 2.1rem; font-weight: 750; letter-spacing: -.025em; line-height: 1.15;
  background: linear-gradient(90deg, var(--accent), #0ea5e9); -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent; }
.hero p { margin: .3rem 0 .7rem; font-size: 1rem; opacity: .75; }
.hero-chips { display: flex; flex-wrap: wrap; gap: .45rem; }
.hero-chips span { font-size: .75rem; font-weight: 500; padding: .2rem .65rem; border-radius: 999px;
  border: 1px solid var(--card-border); background: rgba(100,116,139,.08); }
.hero-chips i { color: var(--accent); margin-right: .35rem; }
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


@st.cache_resource
def _voice() -> Voice | None:
    return Voice() if Voice.available() else None


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


def _render(msg: dict, autoplay: bool = False):
    with st.chat_message(msg["role"]):
        if msg.get("grounded") is False:
            st.warning("The model's wording used numbers that are not in the computed results, so the plain "
                       "computed facts are shown instead.")
        st.markdown(msg["text"])
        if msg.get("audio_error"):
            st.caption(f":material/volume_off: Could not read the answer aloud. {msg['audio_error']}")
        if msg.get("audio"):
            st.audio(msg["audio"], format=msg.get("audio_mime", "audio/mpeg"), autoplay=autoplay)
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
    voice = _voice()
    speak_back = False
    if voice:
        st.divider()
        speak_back = st.toggle("Speak replies to voice questions", value=True)
    st.divider()
    st.caption("Numbers come from public BTS data and deterministic scoring code. The LLM only interprets "
               "your question and explains the results. Scores are 0-100 relative to US peers.")

_voice_chip = '<span><i class="fa-solid fa-microphone"></i>Voice enabled</span>' if voice else ""
st.markdown(f"""
<div class="hero">
  <div class="hero-badge"><i class="fa-solid fa-plane"></i></div>
  <div>
    <h1>Airport Investment Agent</h1>
    <p>Where should the next terminal dollar go? Ask in plain language, by text or voice.</p>
    <div class="hero-chips">
      <span><i class="fa-solid fa-database"></i>Public BTS data</span>
      <span><i class="fa-solid fa-calculator"></i>Deterministic scoring</span>
      <span><i class="fa-solid fa-shield-halved"></i>Numbers checked before narration</span>
      {_voice_chip}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
autoplay_last = st.session_state.pop("autoplay_last", False)
for i, m in enumerate(st.session_state.messages):
    _render(m, autoplay=autoplay_last and i == len(st.session_state.messages) - 1)

typed = st.chat_input("Ask about US airports…" + (" (or press the mic to talk)" if voice else ""),
                      accept_audio=bool(voice))
spoken = None
if voice:
    # The iframe only hosts a loader: the script is injected into the parent page so it can see the chat input.
    js = (Path(__file__).parent / "airport_agent" / "hold_to_talk.js").read_text(encoding="utf-8")
    components.html("<script>const d = window.parent.document, s = d.createElement('script');"
                    f"s.textContent = {json.dumps(js)}; d.head.appendChild(s);</script>", height=0)
    if typed and typed.audio:
        with st.spinner("Transcribing…"):
            try:
                spoken = voice.transcribe(typed.audio)
            except Exception as e:
                st.error(f"Could not transcribe: `{type(e).__name__}`")
        if spoken is not None and not spoken:
            st.warning("I didn't catch that. Try again.")
question = spoken or st.session_state.pop("pending", None) or (typed.text if voice and typed else typed)
if question:
    by_voice = bool(spoken) and speak_back
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
    if by_voice and "grounded" in msg:
        try:
            msg["audio"], msg["audio_mime"] = voice.speak(msg["text"]), voice.mime
            st.session_state.autoplay_last = True
        except Exception as e:  # the written answer is already complete; speech is optional
            msg["audio_error"] = f"{type(e).__name__}: {getattr(e, 'message', e)}"
    st.session_state.messages.append(msg)
    st.rerun()
