"""Deterministic KPI calculations. Pure functions over DataFrames; no network, no LLM."""
import pandas as pd

from .. import config
from ..data import ontime

_CAUSES = ["carrier", "weather", "nas", "security", "late_aircraft"]


def _div(a, b):
    return float(a) / float(b) if b else None


def long_haul_share(rows: pd.DataFrame, threshold_miles: int = config.LONG_HAUL_MILES) -> dict:
    """Share of operated departures with distance >= threshold (domestic, large carriers only)."""
    if threshold_miles not in config.DISTANCE_EDGES:
        raise ValueError(f"threshold must be one of {config.DISTANCE_EDGES}")
    cols = ontime.band_columns()
    # band i is [edge_{i-1}, edge_i); long-haul bands start at the threshold.
    first = ([0] + config.DISTANCE_EDGES).index(threshold_miles)
    long_cols = cols[first:]
    total = rows[cols].sum().sum()
    long = rows[long_cols].sum().sum()
    return {"threshold_miles": threshold_miles, "long_haul_flights": int(long),
            "total_flights": int(total), "share": _div(long, total),
            "bands": {c: int(rows[c].sum()) for c in cols}}


def ontime_metrics(rows: pd.DataFrame, runways: int) -> dict | None:
    """Congestion-related metrics for one airport from its airport-month rows."""
    if rows.empty:
        return None
    s = rows.sum(numeric_only=True)
    days = int(sum(m.days_in_month for m in rows["month"]))
    cause_min = {c: float(s[f"{c}_delay_min"]) for c in _CAUSES}
    cause_total = sum(cause_min.values())
    cancel_causes = {"weather": float(s["cancelled_weather"]), "nas": float(s["cancelled_nas"])}
    return {
        "period": f"{rows['month'].min():%Y-%m} to {rows['month'].max():%Y-%m}",
        "months": int(len(rows)),
        "scheduled_departures": int(s["scheduled_deps"]),
        "operated_departures": int(s["operated_deps"]),
        "cancel_rate": _div(s["cancelled"], s["scheduled_deps"]),
        "dep_delay15_rate": _div(s["dep_del15"], s["operated_deps"]),
        "avg_dep_delay_min": _div(s["dep_delay_min"], s["operated_deps"]),
        "arr_delay15_rate": _div(s["arr_del15"], s["arrivals"]),
        "avg_taxi_out_min": _div(s["taxi_out_min"], s["taxi_out_n"]),
        "avg_taxi_in_min": _div(s["taxi_in_min"], s["taxi_in_n"]),
        "deps_per_runway_day": _div(s["operated_deps"], days * runways),
        "nas_delay_min_per_arrival": _div(s["nas_delay_min"], s["arrivals"]),
        "delay_cause_share": {c: _div(v, cause_total) for c, v in cause_min.items()},
        "cancel_cause_share": {c: _div(v, sum(cancel_causes.values())) for c, v in cancel_causes.items()},
    }


def traffic_metrics(t100: pd.DataFrame) -> dict | None:
    """Last-12-month passengers (enplanements), seats, load factor, and year-over-year growth."""
    if t100 is None or t100.empty:
        return None
    end = t100["month"].max()
    last = t100[t100["month"] > end - pd.DateOffset(months=12)]
    prior = t100[(t100["month"] <= end - pd.DateOffset(months=12))
                 & (t100["month"] > end - pd.DateOffset(months=24))]
    pax, seats = last["total_passengers"].sum(), last["total_seats"].sum()
    growth = None
    if len(last) == 12 and len(prior) == 12 and prior["total_passengers"].sum() > 0:
        growth = pax / prior["total_passengers"].sum() - 1
    dep_growth = None
    if len(last) == 12 and len(prior) == 12 and prior["total_departures"].sum() > 0:
        dep_growth = last["total_departures"].sum() / prior["total_departures"].sum() - 1
    return {
        "data_through": f"{end:%Y-%m}",
        "months_in_window": int(len(last)),
        "annual_enplanements": int(pax),
        "annual_seats": int(seats),
        "annual_departures": int(last["total_departures"].sum()),
        "load_factor": _div(pax, seats),
        "passenger_growth_yoy": growth,
        "departure_growth_yoy": dep_growth,
        "avg_flight_distance_mi": _div((last["total_distance_flight_sm"] * last["total_departures"]).sum(),
                                       last["total_departures"].sum()),
    }
