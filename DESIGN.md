# Airport Investment Intelligence Agent: Design

## Goal
Help analysts find US airports where modernisation is likely to pay off because flight and passenger
capacity is under pressure. The agent answers questions such as "which New England airports are strong
candidates for terminal expansion?", compares airports, reports long-haul share, and estimates unmet demand.

## Architecture

```
question ─► ROUTER (LLM) ─► plan (validated JSON) ─► EXECUTOR (Python) ─► facts ─► NARRATOR (LLM) ─► GUARD (Python) ─► answer + notes
                                                          │
                                         data layer (cached public APIs) + scoring (deterministic)
```

| Layer | Responsibility | Uses AI? |
|---|---|---|
| Router | Turns the question (and the previous turn, for follow-ups) into a small plan: intent, airports, region | Yes, structured JSON output, schema-validated |
| Executor | Resolves names and regions, fetches data, computes every number and score, records assumptions | No |
| Narrator | Rephrases pre-written plain-language facts. It never sees raw results and does not write caveats | Yes |
| Guard | Rejects a draft containing any number (above 10) not present in the facts and shows the facts instead. Code then appends assumptions, uncertainty and data caveats, so they cannot be dropped | No |
| UI | Streamlit chat; also shows the plan, a numeric table and the raw results | No |

The LLM never calculates, never picks data sources and never sees raw data. If it misroutes, the worst case
is a wrong plan, which is visible in the UI and checked by code (unknown airports or regions produce a
clarifying question instead of a guess).

### Data sources (all public, no keys)
| Source | Used for |
|---|---|
| BTS T-100 via `data.bts.gov` (Socrata API) | Monthly enplanements, seats, load factor, growth |
| BTS On-Time Performance (TranStats monthly files) | Delays, cancellations, taxi-out time, delay causes, flight-distance bands |
| OurAirports | Airport identity, state, runway count |

On-time files are large, so each month is aggregated once into per-airport sums and counts and cached;
months are combined from sums, never by averaging monthly averages.

## Scoring methodology
Every metric is mapped to 0 to 100 between two fixed **anchors**: the 10th percentile of US airports
(scores 0) and the 90th percentile (scores 100). The reference set is the 140 airports with at least
500,000 annual enplanements and data in both sources. Anchors are computed once
(`python -m airport_agent.analytics.calibrate`) and stored in `analytics/anchors.json`, so an airport's score
does not change with the comparison set or between runs.

| Index | Components (weight) |
|---|---|
| **Congestion** | departures delayed 15+ min (0.35), runway utilisation: departures per runway per day (0.30), taxi-out time (0.20), cancellation rate (0.15) |
| **Demand pressure** | load factor |
| **Growth** | year-over-year passenger growth |
| **Expansion score** | congestion (0.35) + demand pressure (0.35) + growth (0.30) |
| **Unmet-demand proxy** | load factor (0.40), air-traffic-system delay per arrival (0.30), cancellation rate (0.15), delay rate (0.15) |

Rules around the scores:
- Airports below 500,000 enplanements are not ranked (too small to be terminal-expansion targets). They are listed.
- An airport missing any component is not ranked. It is listed as "insufficient data". Ranking it on a subset would reward missing data.
- Every ranking is re-run under five alternative weightings; the best and worst rank is reported. A wide
  range means the order is sensitive to the weights and should not be over-read.
- The long-haul share is exact for the data it covers: operated departures at or above a threshold
  (default 2,500 miles) divided by all operated departures. Other thresholds are shown for comparison.

### Unmet demand
Unmet demand cannot be observed. The index is a **proxy**: high load factors, delays attributed to the air
traffic system, and cancellations are consistent with capacity limits, but can also come from airline
scheduling or weather. The agent is instructed to say this, to give reasons only from the delay and
cancellation causes in the data, and never to quote a number of unserved passengers.

## Key tradeoffs
| Decision | Why | Cost |
|---|---|---|
| Router, executor and narrator instead of a free tool-calling loop | A small local model is far more reliable filling in a short JSON plan than running multi-step tool use; all numbers stay testable | Less flexible: new question types need a new intent |
| Local open model (Ollama, `qwen2.5:7b-instruct`) | Free, private, no account | 26-42 s per answer on CPU (measured); weaker wording than a large hosted model. The guard checks numbers only, not wording, so a draft can still mis-describe a driver (seen once in testing); the facts and the computed table are shown alongside. The client is OpenAI-compatible, so Groq, Gemini or OpenRouter are a config change |
| Percentile anchors, hand-set weights | Transparent, stable, easy to explain | Weights are judgment, not fitted to investment outcomes. Anything above the 90th percentile scores 100, so extreme airports are not separated |
| Bulk BTS files, cached | Public, reproducible, no API keys | Not live; data lags by about 2 months (on-time) and about 6 months (T-100) |

## Known limitations (communicated to the user in every answer)
- On-time data covers **domestic flights by large reporting carriers only**: no international flights, no
  small commuter carriers. Long-haul share and congestion metrics inherit this. At airports with heavy
  international or cargo activity (for example Anchorage) they describe only part of the traffic.
- Traffic data (T-100) and congestion data cover **different periods**; the periods are stated in the answer.
- Runway count is a simple count of open runways. Layout, spacing and weather-related capacity are ignored.
- Constraints that are not in the data (noise curfews, gate availability, land) are not scored.
- "Long-haul" has no single definition; the threshold is configurable and always stated.
- Informal regions ("New England", "West Coast") use the fixed state lists in `agent/regions.py`.
- Ambiguous airport names resolve to the busiest match, and the answer says so.

## Testing
Unit tests cover the aggregation, scaling, scoring, ranking exclusions, sensitivity, long-haul share,
airport-name resolution, region parsing and the conversation logic (with a scripted fake LLM). Live smoke
scripts in `tests/` exercise the real data sources and the real model.
