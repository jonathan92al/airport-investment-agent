"""Assemble one airport's data from all sources into a profile dict, with caveats attached."""
from functools import lru_cache

import pandas as pd

from . import metrics
from ..data import airports, ontime, t100


@lru_cache(maxsize=1)
def _ontime_all() -> pd.DataFrame:
    return ontime.load()


def build_profile(iata: str, ontime_df: pd.DataFrame | None = None) -> dict:
    iata = iata.upper()
    df = airports.load()
    row = df[df["iata"] == iata]
    if row.empty:
        raise KeyError(f"{iata} is not a US commercial-service airport in the reference data")
    info = row.iloc[0]
    od = _ontime_all() if ontime_df is None else ontime_df

    traffic = metrics.traffic_metrics(t100.monthly(iata))
    otm_rows = od[od["iata"] == iata]
    otm = metrics.ontime_metrics(otm_rows, int(info["runways"]))

    caveats = ["Runway count is a simple count of open runways; it ignores layout (parallel vs "
               "intersecting), spacing and fleet mix."]
    if traffic is None:
        caveats.append("No T-100 traffic data found for this airport.")
    else:
        caveats.append(f"T-100 traffic (passengers = enplanements, all carriers incl. international) "
                       f"runs through {traffic['data_through']}.")
        if traffic["passenger_growth_yoy"] is None:
            caveats.append("Fewer than 24 months of T-100 data, so growth is not available.")
    if otm is None:
        caveats.append("No on-time data found (airport may not be served by reporting carriers).")
    else:
        caveats.append(f"Congestion metrics use BTS on-time data for {otm['period']}: domestic flights by "
                       "large reporting carriers only (no international, no small commuters).")
    return {
        "iata": iata, "name": info["name"], "city": info["city"], "state": info["state"],
        "runways": int(info["runways"]),
        "traffic": traffic, "ontime": otm,
        "long_haul": metrics.long_haul_share(otm_rows) if len(otm_rows) else None,
        "caveats": caveats,
    }
