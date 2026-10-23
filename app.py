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
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>
:root { --p-page: #f5f5f3; --p-bg: #fdfdfb; --p-fg: #17181c; --p-mute: #4a4b52; --p-dim: #74757c;
  --p-line: rgba(23,24,28,.35); --p-stub: #f1f1ee; --p-shadow: rgba(23,24,28,.3); --p-border: rgba(23,24,28,.18); --p-side: #ebebe8; }
:root[data-p-theme="dark"] { --p-page: #1e1f24; --p-bg: #2b2c33; --p-fg: #ecece8; --p-mute: #bdbdc4; --p-dim: #8e8f98;
  --p-line: rgba(236,236,232,.3); --p-stub: rgba(236,236,232,.05); --p-shadow: rgba(14,14,18,.55); --p-border: rgba(236,236,232,.14); --p-side: #25262b; }
html, body, .stApp, [data-testid="stSidebar"], [data-testid="stChatInput"] textarea, button, input {
  font-family: 'IBM Plex Sans', system-ui, sans-serif; }
[data-testid="stIconMaterial"], .material-symbols-rounded { font-family: 'Material Symbols Rounded' !important; }
.block-container { max-width: 1100px; padding-top: 4rem; }
.pass { position: relative; display: flex; margin: 0 0 1.75rem; text-align: left; color: var(--p-fg); border-radius: 1.1rem;
  background: var(--p-bg);
  box-shadow: 0 18px 40px -22px var(--p-shadow); border: 1.5px solid var(--p-fg); overflow: hidden; }
.pass::before, .pass::after { content: ""; position: absolute; right: 13.2rem; width: 1.4rem; height: 1.4rem; border-radius: 50%;
  background: var(--p-page); z-index: 2; }
.pass::before { top: -.7rem; } .pass::after { bottom: -.7rem; }
.pass-main { flex: 1; padding: 1.6rem 1.8rem 1.2rem; position: relative; }
.pass-eyebrow { font: 600 .68rem/1 'IBM Plex Mono', ui-monospace, monospace; letter-spacing: .28em; text-transform: uppercase;
  color: var(--p-dim); display: flex; align-items: center; gap: .6rem; }
.pass h1 { margin: .85rem 0 .35rem; padding: 0; font: 500 2.4rem/1.1 'IBM Plex Sans', system-ui, sans-serif;
  letter-spacing: -.025em; color: var(--p-fg); }
.pass h1 em { font-style: normal; color: var(--p-fg); }
.pass p { margin: 0 0 1.1rem; max-width: 34rem; font-size: 1rem; line-height: 1.5; color: var(--p-mute); }
.pass-route { display: flex; align-items: center; gap: .7rem; font: 500 .78rem 'IBM Plex Mono', ui-monospace, monospace; color: var(--p-fg); }
.pass-route b { font-weight: 500; font-size: 1.1rem; letter-spacing: .08em; color: var(--p-fg); }
.pass-route .line { flex: 1; max-width: 11rem; height: 0; border-top: 2px dashed var(--p-line); position: relative; }
.pass-route .line i { position: absolute; right: -.2rem; top: -.62rem; color: var(--p-fg); font-size: .9rem; }
.pass-stub { width: 13.5rem; padding: 1.6rem 1.3rem; border-left: 2px dashed var(--p-line); display: flex;
  flex-direction: column; justify-content: center; gap: .85rem; background: var(--p-stub); }
.pass-stub div { font: 500 .78rem/1.25 'IBM Plex Mono', ui-monospace, monospace; color: var(--p-fg); }
.pass-stub small { display: block; font-size: .58rem; letter-spacing: .22em; text-transform: uppercase; color: var(--p-dim); margin-bottom: .2rem; }
.pass-stub .ok { color: var(--p-fg); font-weight: 700; }
@media (max-width: 760px) { .pass-stub { display: none; } .pass::before, .pass::after { display: none; } .pass h1 { font-size: 1.9rem; } }
[data-testid="stSidebar"] { background: var(--p-side); border-right: 1px solid var(--p-border); }
[data-testid="stSidebar"] .block-container, [data-testid="stSidebarUserContent"] { padding-top: 1.2rem; }
.sb-brand { display: flex; align-items: center; gap: .65rem; margin: 0 0 .4rem; }
.sb-name { font: 700 1.05rem/1.1 'IBM Plex Sans', system-ui, sans-serif; letter-spacing: -.01em; }
.sb-label { font: 600 .62rem/1 'IBM Plex Mono', ui-monospace, monospace; letter-spacing: .22em; text-transform: uppercase;
  color: var(--p-dim); margin: 1.4rem 0 .6rem; }
.sb-note { font-size: .78rem; line-height: 1.5; color: var(--p-mute); }
.sb-note b { color: var(--p-fg); font-weight: 600; }
[data-testid="stSidebar"] [data-testid="stButton"] button { background: transparent; border: 1px solid var(--p-border);
  border-radius: .6rem; padding: .5rem .7rem; min-height: 0; justify-content: flex-start; text-align: left;
  transition: border-color .12s, background .12s; }
[data-testid="stSidebar"] [data-testid="stButton"] button p { font-size: .82rem; line-height: 1.4; }
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="secondary"]:hover { border-color: var(--p-fg); background: var(--p-bg); }
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="tertiary"] { border-color: transparent; padding-left: 0; color: var(--p-mute); }
[data-testid="stSidebar"] [data-testid="stButton"] button[kind="tertiary"]:hover { color: var(--p-fg); background: transparent; }
[data-testid="stSidebar"] [data-testid="stCheckbox"] label > div:nth-child(2) { background: transparent !important;
  border: 1.5px solid var(--p-fg) !important; }
[data-testid="stSidebar"] [data-testid="stCheckbox"] label > div:nth-child(2) > div { background: var(--p-fg) !important; }
[data-testid="stSidebar"] [data-testid="stCheckbox"] label[data-selected="true"] > div:nth-child(2) { background: var(--p-fg) !important; }
[data-testid="stSidebar"] [data-testid="stCheckbox"] label[data-selected="true"] > div:nth-child(2) > div { background: var(--p-bg) !important; }
[data-testid="stMarkdownContainer"], [data-testid="stMetric"], [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] button, [data-testid="stSidebar"] p { text-align: left !important; }
[data-testid="stSidebar"] button { justify-content: flex-start; }
[data-testid="stSidebar"] button p { text-align: left; }
[data-testid="stMetric"] { align-items: flex-start; }
[data-testid="stMetricValue"] { font-weight: 700; }
[data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--p-border); }
[data-testid="stChatMessage"] { background: transparent; border: 1px solid var(--p-border);
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
    st.markdown('<div class="sb-brand"><div class="sb-name">Airport Agent</div></div>', unsafe_allow_html=True)
    if st.button("Reset conversation", type="tertiary", icon=":material/restart_alt:"):
        st.session_state.pop("agent", None)
        st.rerun()
    st.markdown('<div class="sb-label">Try asking</div>', unsafe_allow_html=True)
    for ex in EXAMPLES:
        if st.button(ex, width="stretch"):
            st.session_state.pending = ex
    voice = _voice()
    speak_back = False
    if voice:
        st.markdown('<div class="sb-label">Voice</div>', unsafe_allow_html=True)
        speak_back = st.toggle("Speak replies to voice questions", value=True)
    st.markdown(f'<div class="sb-label">About</div><div class="sb-note">Numbers come from public BTS data and '
                f'deterministic scoring code; the LLM only interprets your question and explains the results.<br>'
                f'Model: <b>{_llm().model}</b></div>', unsafe_allow_html=True)

_voice_field = '<div><small>Input</small>Text <span class="ok">+ Voice</span></div>' if voice else '<div><small>Input</small>Text</div>'
st.markdown(f"""
<div class="pass">
  <div class="pass-main">
    <div class="pass-eyebrow">Investment briefing &middot; Boarding pass</div>
    <h1>Airport Investment <em>Agent</em></h1>
    <p>Where should the next terminal dollar go? Ask in plain language and get a ranked, evidence-backed answer.</p>
    <div class="pass-route"><b>QUESTION</b><span class="line"><i class="fa-solid fa-plane"></i></span><b>DECISION</b></div>
  </div>
  <div class="pass-stub">
    <div><small>Data</small>BTS on-time + T-100</div>
    <div><small>Scoring</small>Deterministic code</div>
    <div><small>Numbers</small><span class="ok">Verified</span> before narration</div>
    {_voice_field}
  </div>
</div>
""", unsafe_allow_html=True)
autoplay_last = st.session_state.pop("autoplay_last", False)
for i, m in enumerate(st.session_state.messages):
    _render(m, autoplay=autoplay_last and i == len(st.session_state.messages) - 1)

typed = st.chat_input("Ask about US airports…" + (" (or press the mic to talk)" if voice else ""),
                      accept_audio=bool(voice))
spoken = None


def _inject(*names: str):
    """Load scripts into the parent page (the component iframe only hosts this loader)."""
    code = "\n".join((Path(__file__).parent / "airport_agent" / n).read_text(encoding="utf-8") for n in names)
    components.html("<script>const d = window.parent.document, s = d.createElement('script');"
                    f"s.textContent = {json.dumps(code)}; d.head.appendChild(s);</script>", height=0)


_inject("theme_sync.js", *(["hold_to_talk.js"] if voice else []))
if voice:
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
