"""Plan -> deterministic results. No LLM here.

Besides the structured numbers, each result carries:
- facts: plain-language statements with units already formatted. The narrator may only rephrase these.
- uncertainty: limitations specific to this answer. Code appends them to the reply, so they are never skipped.
- assumptions: every guess made on the user's behalf.
"""
from . import regions
from .plan import Plan
from .. import config
from ..analytics import metrics, profile, scoring
from ..data import airports, t100

DEFAULT_TOP_N = 5
MAX_COMPARE = 4
TIE_POINTS = 1.0  # scores this close to the top are reported as a tie

CONGESTION_LABELS = {
    "dep_delay15_rate": ("departures delayed 15+ minutes", lambda x: pct(x)),
    "avg_taxi_out_min": ("average taxi-out time", lambda x: f"{x:.1f} min"),
    "cancel_rate": ("cancellation rate", lambda x: pct(x)),
    "deps_per_runway_day": ("departures per runway per day", lambda x: f"{x:.0f}"),
}


def pct(x, digits: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{digits}f}%"


def _new_result(plan: Plan) -> dict:
    return {"intent": plan.intent, "assumptions": [], "facts": [], "uncertainty": [], "caveats": [
        "Congestion metrics use BTS on-time data: domestic flights by large reporting carriers only.",
        "Passenger and load-factor figures come from BTS T-100, which lags the on-time data by months."]}


def _pick(query: str, assumptions: list[str]) -> str | None:
    """One IATA code for a user-named airport. If several match, take the busiest and say so."""
    found = airports.resolve(query)
    if found.empty:
        return None
    if len(found) == 1:
        return found.iloc[0]["iata"]

    def enplanements(iata):
        t = metrics.traffic_metrics(t100.monthly(iata))
        return t["annual_enplanements"] if t else 0

    ranked = sorted(found["iata"], key=enplanements, reverse=True)
    others = ", ".join(ranked[1:6]) + (", ..." if len(ranked) > 6 else "")
    assumptions.append(f"'{query}' matched {len(ranked)} airports; used {ranked[0]}, the busiest by "
                       f"enplanements (others: {others}).")
    return ranked[0]


def _resolve_all(names: list[str], assumptions: list[str]):
    codes, missing = [], []
    for n in names:
        code = _pick(n, assumptions)
        (codes if code else missing).append(code or n)
    return list(dict.fromkeys(codes)), missing


def _key_metrics(p: dict) -> dict:
    t, o = p.get("traffic") or {}, p.get("ontime") or {}
    return {
        "annual_enplanements": t.get("annual_enplanements"), "load_factor": t.get("load_factor"),
        "passenger_growth_yoy": t.get("passenger_growth_yoy"), "traffic_data_through": t.get("data_through"),
        "dep_delay15_rate": o.get("dep_delay15_rate"), "avg_taxi_out_min": o.get("avg_taxi_out_min"),
        "cancel_rate": o.get("cancel_rate"), "deps_per_runway_day": o.get("deps_per_runway_day"),
        "runways": p["runways"], "ontime_period": o.get("period"),
    }


def _rank_region(plan: Plan, out: dict):
    states = regions.resolve(plan.region)
    if not states:
        out["clarification"] = (f"I don't recognise the region '{plan.region}'. "
                                "Try a US state, a region like New England, or 'US'.")
        return
    profs = [profile.build_profile(i) for i in airports.in_states(states)["iata"]]
    res, sens = scoring.rank(profs), scoring.rank_sensitivity(profs)
    by_iata = {p["iata"]: p for p in profs}
    top_n = max(1, min(plan.top_n or DEFAULT_TOP_N, 10))
    out["region"] = {"input": plan.region, "states": states, "airports_considered": len(profs)}
    out["weights"] = res["weights"]
    out["ranked"] = [{
        "rank": r["rank"], "iata": r["iata"], "name": r["name"], "score": r["score"],
        "sub_scores": {k: v["score"] for k, v in r["sub_scores"].items()},
        "rank_range_across_weightings": [sens[r["iata"]]["best"], sens[r["iata"]]["worst"]],
        **_key_metrics(by_iata[r["iata"]]),
    } for r in res["ranked"][:top_n]]
    floor = [e["iata"] for e in res["excluded"] if e["reason"].startswith("below scale floor")]
    out["excluded_below_scale_floor"] = floor
    out["excluded_insufficient_data"] = [e for e in res["excluded"] if e["iata"] not in floor]

    rows, facts, unc = out["ranked"], out["facts"], out["uncertainty"]
    if not rows:
        out["clarification"] = f"No airport in {plan.region} had enough data to be ranked."
        return
    facts.append(f"{len(res['ranked'])} of {len(profs)} airports in {plan.region} could be ranked. Scores are "
                 "0-100 relative to US airports above 500,000 annual enplanements; higher means a stronger "
                 "expansion case.")
    tied = [r["iata"] for r in rows if rows[0]["score"] - r["score"] <= TIE_POINTS]
    if len(tied) > 1:
        facts.append(f"{', '.join(tied)} are within {TIE_POINTS:g} point of each other at the top, so they "
                     "are effectively tied.")
        unc.append(f"The top scores ({', '.join(str(r['score']) for r in rows if r['iata'] in tied)}) are too "
                   "close to separate with confidence.")
    for r in rows:
        lo, hi = r["rank_range_across_weightings"]
        stable = "stable" if hi - lo <= 1 else "sensitive to the weights"
        s = r["sub_scores"]
        facts.append(
            f"#{r['rank']} {r['iata']} ({r['name']}): expansion score {r['score']}. Congestion {s['congestion']:.0f}, "
            f"demand pressure {s['demand_pressure']:.0f}, growth {s['growth']:.0f}. Load factor {pct(r['load_factor'])}, "
            f"passenger growth {pct(r['passenger_growth_yoy'])}, {r['annual_enplanements']:,} annual enplanements. "
            f"Rank is {lo} to {hi} across alternative weightings ({stable}).")
        if hi - lo > 1:
            unc.append(f"{r['iata']}'s rank ranges from {lo} to {hi} depending on the weights.")
    if floor:
        facts.append(f"{len(floor)} smaller airports were not ranked because they are below 500,000 annual "
                     f"enplanements: {', '.join(floor)}.")
    for e in out["excluded_insufficient_data"]:
        facts.append(f"{e['iata']} was not ranked: {e['reason']}.")
    unc.append("Weights (congestion 0.35, demand 0.35, growth 0.30) are judgment calls, not fitted to investment returns.")
    unc.append("Demand pressure is the load factor; growth is year-over-year passenger growth.")


def _compare(plan: Plan, out: dict):
    codes, missing = _resolve_all(plan.airports, out["assumptions"])
    if missing:
        out["unresolved"] = missing
        out["facts"].append(f"Could not find: {', '.join(missing)}.")
    if len(codes) < 2:
        out["clarification"] = "Please name at least two US commercial airports to compare."
        return
    rows, comps = [], {}
    for iata in codes[:MAX_COMPARE]:
        p = profile.build_profile(iata)
        ci = scoring.congestion_index(p["ontime"])
        comps[iata] = {c["name"]: c for c in ci["components"]}
        rows.append({"iata": iata, "name": p["name"], "congestion_score": ci["score"],
                     "expansion_score": scoring.expansion_score(p)["score"], **_key_metrics(p)})
    out["airports"] = rows
    facts, unc = out["facts"], out["uncertainty"]
    for r in rows:
        if r["congestion_score"] is None:
            facts.append(f"{r['iata']} ({r['name']}): no on-time data, so congestion cannot be scored.")
            continue
        facts.append(f"{r['iata']} ({r['name']}): congestion score {r['congestion_score']}. "
                     f"Departures delayed 15+ minutes {pct(r['dep_delay15_rate'])}, average taxi-out "
                     f"{r['avg_taxi_out_min']:.1f} min, cancellations {pct(r['cancel_rate'])}, "
                     f"{r['deps_per_runway_day']:.0f} departures per runway per day ({r['runways']} runways).")
    scored = sorted((r for r in rows if r["congestion_score"] is not None),
                    key=lambda r: r["congestion_score"], reverse=True)
    if len(scored) >= 2:
        hi, lo = scored[0], scored[-1]
        out["most_congested"] = hi["iata"]
        facts.append(f"{hi['iata']} is the most congested ({hi['congestion_score']} vs {lo['congestion_score']} "
                     f"for {lo['iata']}). Congestion scores are 0-100 relative to US airports.")
        diffs = {n: (comps[hi["iata"]][n]["score"] - comps[lo["iata"]][n]["score"]) * comps[hi["iata"]][n]["weight"]
                 for n in CONGESTION_LABELS
                 if comps[hi["iata"]][n]["score"] is not None and comps[lo["iata"]][n]["score"] is not None}
        if diffs:
            main = max(diffs, key=diffs.get)
            label, fmt = CONGESTION_LABELS[main]
            facts.append(f"The biggest contributor to the gap is {label}: {fmt(comps[hi['iata']][main]['raw'])} "
                         f"for {hi['iata']} vs {fmt(comps[lo['iata']][main]['raw'])} for {lo['iata']}.")
            negligible = [CONGESTION_LABELS[n][0] for n, d in diffs.items() if abs(d) < 2]
            if negligible:
                facts.append(f"Little difference in: {', '.join(negligible)}.")
    unc.append("Runway count is a simple count of open runways; layout, spacing and weather limits are ignored.")
    unc.append("Constraints not in the data (noise rules, curfews, gates) are not reflected in the scores.")


def _single(plan: Plan, out: dict) -> dict | None:
    codes, missing = _resolve_all(plan.airports[:1], out["assumptions"])
    if not codes:
        out["clarification"] = (f"I couldn't find a US commercial airport matching "
                                f"'{' '.join(missing) or 'your request'}'. Which airport do you mean?")
        return None
    return profile.build_profile(codes[0])


def _long_haul(plan: Plan, out: dict):
    p = _single(plan, out)
    if p is None:
        return
    threshold = plan.threshold_miles or config.LONG_HAUL_MILES
    if threshold not in config.DISTANCE_EDGES:
        nearest = min(config.DISTANCE_EDGES, key=lambda e: abs(e - threshold))
        out["assumptions"].append(f"Thresholds are limited to {config.DISTANCE_EDGES}; used {nearest} "
                                  f"instead of {threshold} miles.")
        threshold = nearest
    if p["long_haul"] is None:
        out["clarification"] = f"{p['iata']} has no BTS on-time data, so a long-haul share can't be computed."
        return
    rows = profile._ontime_all()
    rows = rows[rows["iata"] == p["iata"]]
    lh = metrics.long_haul_share(rows, threshold)
    out["airport"] = {"iata": p["iata"], "name": p["name"], "ontime_period": p["ontime"]["period"]}
    out["long_haul"] = {k: lh[k] for k in ("threshold_miles", "long_haul_flights", "total_flights", "share")}
    by_thr = {e: metrics.long_haul_share(rows, e)["share"] for e in config.DISTANCE_EDGES}
    out["share_by_threshold"] = by_thr
    out["assumptions"].append(f"'Long-haul' defined as {threshold}+ statute miles.")
    out["facts"] += [
        f"{pct(lh['share'])} of {p['iata']}'s departures ({lh['long_haul_flights']:,} of {lh['total_flights']:,}) "
        f"are {threshold:,} miles or longer, over {p['ontime']['period']}.",
        "Share of departures at or above other distances: " + "; ".join(
            f"{e:,} miles {pct(s)}" for e, s in by_thr.items()) + ".",
    ]
    out["uncertainty"].append(f"Only domestic flights by large reporting carriers are counted. International and "
                              f"cargo flights from {p['iata']} are not in this data, so the true share of "
                              "long-haul flights may differ.")
    out["uncertainty"].append("There is no single definition of long-haul; the share depends on the threshold chosen.")


def _unmet(plan: Plan, out: dict):
    p = _single(plan, out)
    if p is None:
        return
    u = scoring.unmet_demand(p)
    o = p.get("ontime") or {}
    t = p.get("traffic") or {}
    out["airport"] = {"iata": p["iata"], "name": p["name"]}
    out["unmet_demand_index"] = u["score"]
    out["drivers"] = [{"metric": d["name"], "value": d["raw"], "score": round(d["score"], 1), "weight": d["weight"]}
                      for d in u["drivers"]]
    out["missing"] = u["missing"]
    out["delay_cause_share"] = o.get("delay_cause_share")
    out["cancel_cause_share"] = o.get("cancel_cause_share")
    out["metrics"] = _key_metrics(p)
    facts = out["facts"]
    facts.append(f"Unmet-demand index for {p['iata']}: {u['score']} out of 100. This is a proxy built from "
                 "load factor, air-traffic-system delay, cancellations and delay rate; it is not a measured "
                 "number of unserved passengers.")
    if t.get("load_factor") is not None:
        facts.append(f"Load factor {pct(t['load_factor'])} (seats filled), through {t['data_through']}.")
    if o:
        facts.append(f"{pct(o['dep_delay15_rate'])} of departures are delayed 15+ minutes; average "
                     f"air-traffic-system (NAS) delay is {o['nas_delay_min_per_arrival']:.1f} minutes per arrival; "
                     f"{pct(o['cancel_rate'])} of flights are cancelled.")
        cs = o["delay_cause_share"]
        facts.append("Share of delay minutes by cause: " + ", ".join(
            f"{k.replace('_', ' ')} {pct(v)}" for k, v in sorted(cs.items(), key=lambda kv: -kv[1]) if v) + ".")
        cc = o["cancel_cause_share"]
        if any(cc.values()):
            facts.append("Share of cancellations with a recorded cause: " + ", ".join(
                f"{k} {pct(v)}" for k, v in cc.items()) + ".")
    top = [d["name"].replace("_", " ") for d in u["drivers"][:2]]
    if top:
        facts.append(f"The strongest signals in the index are {top[0]} and {top[1] if len(top) > 1 else top[0]}.")
    out["uncertainty"] += [
        "Unmet demand is not directly observable. High load factors and system delays are consistent with "
        "constrained capacity but can also come from airline scheduling or weather.",
        "The reasons given come only from the delay and cancellation causes recorded in the data.",
    ]


def _profile(plan: Plan, out: dict):
    p = _single(plan, out)
    if p is None:
        return
    m = _key_metrics(p)
    out["airport"] = {"iata": p["iata"], "name": p["name"], "state": p["state"]}
    out["metrics"] = m
    out["congestion_score"] = scoring.congestion_index(p["ontime"])["score"]
    out["expansion_score"] = scoring.expansion_score(p)["score"]
    out["airport_caveats"] = p["caveats"]
    out["facts"] += [
        f"{p['iata']} ({p['name']}), {p['state']}: {p['runways']} runways, "
        f"{(m['annual_enplanements'] or 0):,} annual enplanements, load factor {pct(m['load_factor'])}, "
        f"passenger growth {pct(m['passenger_growth_yoy'])}.",
        f"Congestion score {out['congestion_score']}; expansion score {out['expansion_score']} "
        "(0-100, relative to US airports).",
    ]
    out["uncertainty"] += p["caveats"]


_HANDLERS = {"rank_region": _rank_region, "compare": _compare, "long_haul_share": _long_haul,
             "unmet_demand": _unmet, "airport_profile": _profile}


def run(plan: Plan) -> dict:
    out = _new_result(plan)
    handler = _HANDLERS.get(plan.intent)
    if handler:
        handler(plan, out)
    return out
