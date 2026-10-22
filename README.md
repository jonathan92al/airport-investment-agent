# Airport Investment Intelligence Agent

A chat agent that helps analysts find US airports where modernisation is likely to pay off. It answers
questions about expansion candidates, congestion, long-haul share and unmet demand using public BTS data
and deterministic scoring. See [DESIGN.md](DESIGN.md) for the methodology, tradeoffs and limitations.

## Setup (Windows, Python 3.12)

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Install [Ollama](https://ollama.com) and pull the default model (about 4.7 GB):

```powershell
ollama pull qwen2.5:7b-instruct
```

No account or API key is needed. To use another OpenAI-compatible provider, set `LLM_BASE_URL`,
`LLM_MODEL` and `LLM_API_KEY` in a `.env` file.

If HTTPS requests fail behind a corporate proxy, the code already uses the Windows certificate store
(`truststore`); no extra configuration is needed.

## Run

```powershell
.venv\Scripts\python.exe -m streamlit run app.py     # chat UI
.venv\Scripts\python.exe -m airport_agent.cli        # terminal chat
```

On first use the app downloads 12 months of BTS on-time data (about 350 MB, aggregated to a few MB and
cached in `.cache/`) and per-airport T-100 data on demand. The first question can take several minutes;
later ones are faster. On a 15 GB CPU-only laptop the 7B model took 26-42 s per answer once the data was cached.

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
Live checks that hit the real data sources and the real model:
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
