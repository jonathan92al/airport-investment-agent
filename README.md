# airport-investment-agent

Airport Investment Intelligence Agent: a chat agent that ranks and compares US airports for modernization investment.

A chat agent that helps analysts find US airports where modernisation is likely to pay off. It answers
questions about expansion candidates, congestion, long-haul share and unmet demand using public BTS data
and deterministic scoring. See [DESIGN.md](DESIGN.md) for the methodology, tradeoffs and limitations.

## Setup (Windows, Python 3.12)

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The chat model runs on [Groq](https://console.groq.com/keys) through its OpenAI-compatible API, so you need a
free Groq API key. Create a `.env` file in the project root:

```
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
LLM_API_KEY=gsk_your_key_here
```

Any other OpenAI-compatible provider works the same way by changing these three values. The same Groq key
also enables voice (see below). When deployed on Streamlit Cloud, put the same values in the app's secrets
(see `.streamlit/secrets.toml.example`) instead of a `.env` file.

### Voice (optional)

Press the mic in the chat bar (hold to talk, release to send); a short tap keeps recording until you press
Submit. The question is transcribed, answered as usual, and the bottom line is read back aloud (toggle in
the sidebar). Voice appears automatically when a key is available: `VOICE_API_KEY`, or `LLM_API_KEY` when
`LLM_BASE_URL` is OpenAI or Groq, or `OPENAI_API_KEY`.

| Provider | Speech to text | Text to speech |
|---|---|---|
| OpenAI (default) | `gpt-4o-mini-transcribe` | `gpt-4o-mini-tts` |
| Groq | `whisper-large-v3-turbo` | `canopylabs/orpheus-v1-english` |

Groq's Orpheus voice needs its terms accepted once by an org admin in the
[Groq playground](https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english).
Override with `VOICE_BASE_URL`, `VOICE_STT_MODEL`, `VOICE_TTS_MODEL`, `VOICE_TTS_VOICE`.

**Mobile:** browsers allow the microphone only on HTTPS or `localhost`. Hosted deployments (Streamlit Cloud)
are HTTPS and work; opening `http://<your-pc-ip>:8501` on a phone does not, and the mic button is hidden
by the browser. On narrow screens the ticket's side panel is hidden and a "Voice on" note appears instead.

The UI follows the Streamlit light/dark setting (Settings menu) with a boarding-pass header and IBM Plex fonts.

If HTTPS requests fail behind a corporate proxy, the code already uses the Windows certificate store
(`truststore`); no extra configuration is needed.

## Run locally

1. Complete the setup above (virtual environment, dependencies, `.env` with your Groq key).
2. Start the chat UI:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py     # chat UI at http://localhost:8501
.venv\Scripts\python.exe -m airport_agent.cli        # or: terminal chat
```

By default the app runs in live mode: on first use it downloads 12 months of BTS on-time data (about 350 MB,
aggregated to a few MB and cached in `.cache/`) and per-airport T-100 data on demand. The first question can
take several minutes; later ones are faster.

To skip the downloads and use the committed data snapshot in `data/` (what the hosted app does), set
`DATA_MODE=snapshot` before starting:

```powershell
$env:DATA_MODE="snapshot"; .venv\Scripts\python.exe -m streamlit run app.py
```

## Example questions
- Which airports in New England are strong candidates for terminal expansion?
- Compare LA and Santa Ana airport congestion levels.
- What is the percentage of long haul flights out of Anchorage airport?
- What is the unmet flight demand in SFO airport and why?
- Follow-ups: "Why is the top one ranked above the others?", "What about SFO instead?", "And for flights over 3000 miles?"

## Tests

```powershell
$env:PYTHONPATH="."; .venv\Scripts\python.exe -m pytest tests -q
```

Unit tests need no network except `test_airports.py`, which downloads the small OurAirports files once.
Live checks that hit the real data sources and the configured LLM:
`tests/smoke_data_layer.py`, `smoke_analytics.py`, `smoke_executor.py`, `smoke_llm.py`
(run each with `$env:PYTHONPATH="."`).

## Recalibrating the scores

Score anchors come from the national distribution of each metric and are stored in
`airport_agent/analytics/anchors.json`. After refreshing the data, regenerate them with:

```powershell
.venv\Scripts\python.exe -m airport_agent.analytics.calibrate
```

## Layout

```
app.py                      Streamlit chat UI
airport_agent/
  data/                     airports (OurAirports), t100 (BTS Socrata API), ontime (BTS monthly files)
  analytics/                metrics, scoring, profile assembly, calibration
  agent/                    plan schema, regions, executor, prompts, LLM client, conversation loop
tests/                      unit tests and live smoke scripts
```
