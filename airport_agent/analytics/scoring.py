"""Deterministic scoring. All weights and anchors are judgment calls, listed here in one place.

Each metric is mapped to 0-100 against fixed anchors (not against peers), so an airport's score
does not change when the comparison set changes. A component whose data is missing is dropped
and the remaining weights are renormalised; the result is flagged so the caller can say so.
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path

ANCHOR_FILE = Path(__file__).with_name("anchors.json")

# metric -> (value scoring 0, value scoring 100). The 10th and 90th percentile of that metric across
# US airports above the scale floor, written by `python -m airport_agent.analytics.calibrate`.
# Empty until calibrated; _component() then fails with a clear message.
ANCHORS: dict[str, tuple[float, float]] = (
    {k: tuple(v) for k, v in json.loads(ANCHOR_FILE.read_text())["anchors"].items()}
    if ANCHOR_FILE.exists() else {})

CONGESTION_WEIGHTS = {"dep_delay15_rate": 0.35, "avg_taxi_out_min": 0.20,
                      "cancel_rate": 0.15, "deps_per_runway_day": 0.30}
EXPANSION_WEIGHTS = {"congestion": 0.35, "demand_pressure": 0.35, "growth": 0.30}
UNMET_WEIGHTS = {"load_factor": 0.40, "nas_delay_min_per_arrival": 0.30,
                 "cancel_rate": 0.15, "dep_delay15_rate": 0.15}

MIN_ANNUAL_ENPLANEMENTS = 500_000  # below this the airport is too small to be a terminal-expansion target

# Alternative weightings used to test whether a ranking is robust.
SENSITIVITY_PRESETS = {
    "default": EXPANSION_WEIGHTS,
    "equal": {"congestion": 1 / 3, "demand_pressure": 1 / 3, "growth": 1 / 3},
    "congestion_heavy": {"congestion": 0.6, "demand_pressure": 0.2, "growth": 0.2},
    "demand_heavy": {"congestion": 0.2, "demand_pressure": 0.6, "growth": 0.2},
    "growth_heavy": {"congestion": 0.2, "demand_pressure": 0.2, "growth": 0.6},
}


@dataclass
class Component:
    name: str
    raw: float | None
    score: float | None  # 0-100, None if raw is missing
    weight: float
    anchors: tuple | None = None


def scale(value, lo, hi) -> float | None:
    if value is None:
        return None
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0))


def _component(name, raw, weight) -> Component:
    if name not in ANCHORS:
        raise RuntimeError(f"No anchors for '{name}'. Run: python -m airport_agent.analytics.calibrate")
    lo, hi = ANCHORS[name]
    return Component(name, raw, scale(raw, lo, hi), weight, (lo, hi))


def combine(parts: list[Component]) -> tuple[float | None, list[str]]:
    """Weighted mean over available components. Returns (score, names of missing components)."""
    avail = [p for p in parts if p.score is not None]
    missing = [p.name for p in parts if p.score is None]
    if not avail:
        return None, missing
    w = sum(p.weight for p in avail)
    return sum(p.score * p.weight for p in avail) / w, missing


def _result(score, parts, missing):
    return {"score": None if score is None else round(score, 1),
            "components": [asdict(p) for p in parts],
            "missing": missing}


def congestion_index(ontime: dict | None) -> dict:
    ontime = ontime or {}
    parts = [_component(k, ontime.get(k), w) for k, w in CONGESTION_WEIGHTS.items()]
    return _finish(parts)


def _finish(parts):
    score, missing = combine(parts)
    return _result(score, parts, missing)


def demand_pressure(traffic: dict | None) -> dict:
    parts = [_component("load_factor", (traffic or {}).get("load_factor"), 1.0)]
    return _finish(parts)


def growth_score(traffic: dict | None) -> dict:
    parts = [_component("passenger_growth_yoy", (traffic or {}).get("passenger_growth_yoy"), 1.0)]
    return _finish(parts)


def expansion_score(profile: dict, weights: dict | None = None) -> dict:
    """Terminal-expansion attractiveness (0-100): congestion + demand pressure + growth."""
    weights = weights or EXPANSION_WEIGHTS
    sub = {"congestion": congestion_index(profile.get("ontime")),
           "demand_pressure": demand_pressure(profile.get("traffic")),
           "growth": growth_score(profile.get("traffic"))}
    parts = [Component(k, sub[k]["score"], sub[k]["score"], weights[k]) for k in weights]
    score, missing = combine(parts)
    out = _result(score, parts, missing)
    out["sub_scores"] = sub
    return out


def unmet_demand(profile: dict) -> dict:
    """Proxy for demand the airport cannot currently serve. NOT a measured quantity.

    High load factors (spill), NAS/system delay and capacity-driven cancellations are consistent
    with unmet demand, but they can also reflect airline scheduling or weather.
    """
    t, o = profile.get("traffic") or {}, profile.get("ontime") or {}
    raw = {"load_factor": t.get("load_factor"),
           "nas_delay_min_per_arrival": o.get("nas_delay_min_per_arrival"),
           "cancel_rate": o.get("cancel_rate"),
           "dep_delay15_rate": o.get("dep_delay15_rate")}
    parts = [_component(k, raw[k], w) for k, w in UNMET_WEIGHTS.items()]
    score, missing = combine(parts)
    res = _result(score, parts, missing)
    res["drivers"] = sorted((p for p in res["components"] if p["score"] is not None),
                            key=lambda p: p["score"] * p["weight"], reverse=True)
    return res


def eligibility(profile: dict) -> str | None:
    """Reason an airport is excluded from expansion ranking, or None if eligible."""
    t = profile.get("traffic")
    if not t:
        return "no T-100 traffic data"
    if t["annual_enplanements"] < MIN_ANNUAL_ENPLANEMENTS:
        return f"below scale floor ({t['annual_enplanements']:,} < {MIN_ANNUAL_ENPLANEMENTS:,} enplanements)"
    return None


def _missing_data(score: dict) -> list[str]:
    """Components missing at any level. Ranking on partial data would reward the gap."""
    missing = list(score["missing"])
    for name, sub in score["sub_scores"].items():
        missing += [f"{name}.{m}" for m in sub["missing"]]
    return missing


def rank(profiles: list[dict], weights: dict | None = None) -> dict:
    """Rank eligible airports. Excluded ones are listed with a reason: below the scale floor,
    or missing data for any component (never scored on a subset)."""
    ranked, excluded = [], []
    for p in profiles:
        reason = eligibility(p)
        if reason:
            excluded.append({"iata": p["iata"], "reason": reason})
            continue
        s = expansion_score(p, weights)
        missing = _missing_data(s)
        if missing:
            excluded.append({"iata": p["iata"], "reason": "insufficient data: missing " + ", ".join(missing)})
            continue
        ranked.append({"iata": p["iata"], "name": p.get("name"), **s})
    ranked.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return {"weights": weights or EXPANSION_WEIGHTS, "ranked": ranked, "excluded": excluded}


def rank_sensitivity(profiles: list[dict]) -> dict:
    """Rank of each airport under every preset weighting. Narrow range => robust ranking."""
    ranks: dict[str, dict[str, int]] = {}
    for name, w in SENSITIVITY_PRESETS.items():
        for r in rank(profiles, w)["ranked"]:
            ranks.setdefault(r["iata"], {})[name] = r["rank"]
    return {iata: {"by_preset": by, "best": min(by.values()), "worst": max(by.values())}
            for iata, by in ranks.items()}
