"""Derive scoring anchors from the national distribution of each metric.

Reference set: US commercial airports above the scale floor that have both T-100 and on-time data.
Anchors are the 10th percentile (scores 0) and 90th percentile (scores 100) of that set.

Run: python -m airport_agent.analytics.calibrate   (rewrites anchors.json; commit the result)
"""
import json

import pandas as pd

from . import profile, scoring
from ..data import airports

PERCENTILES = (0.10, 0.90)


def collect() -> pd.DataFrame:
    od = profile._ontime_all()
    have_ontime = set(od["iata"])
    rows = []
    for iata in airports.load()["iata"]:
        if iata not in have_ontime:
            continue
        p = profile.build_profile(iata, od)
        t, o = p["traffic"], p["ontime"]
        if not t or not o or t["annual_enplanements"] < scoring.MIN_ANNUAL_ENPLANEMENTS:
            continue
        rows.append({"iata": iata, **{k: o[k] for k in ("dep_delay15_rate", "avg_taxi_out_min", "cancel_rate",
                                                         "deps_per_runway_day", "nas_delay_min_per_arrival")},
                     "load_factor": t["load_factor"], "passenger_growth_yoy": t["passenger_growth_yoy"]})
    return pd.DataFrame(rows).set_index("iata")


def main():
    df = collect()
    lo_q, hi_q = PERCENTILES
    anchors = {c: [float(df[c].quantile(lo_q)), float(df[c].quantile(hi_q))] for c in df.columns}
    out = {"method": f"p{int(lo_q * 100)} scores 0, p{int(hi_q * 100)} scores 100, across reference airports",
           "reference_airports": int(len(df)),
           "n_per_metric": {c: int(df[c].notna().sum()) for c in df.columns},
           "anchors": anchors}
    scoring.ANCHOR_FILE.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
