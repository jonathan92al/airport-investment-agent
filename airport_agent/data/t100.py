"""BTS T-100 monthly traffic per origin airport (Socrata API on data.bts.gov).

Gives departures, passengers, seats and load factor, including international, for all
carriers. Does NOT give a distance distribution (only the average), so it is not used
for the long-haul share.
"""
import time

import pandas as pd

from .. import config, http

_NUM_COLS = ["total_departures", "total_passengers", "total_seats", "total_load_factor",
             "total_distance_flight_sm", "domestic_departures", "domestic_passengers",
             "domestic_seats"]
_TTL_SECONDS = 7 * 24 * 3600  # T-100 updates monthly


def monthly(iata: str, since_year: int = 2015) -> pd.DataFrame:
    """Monthly rows for one airport, sorted by date. Cached on disk for a week."""
    iata = iata.upper()
    path = config.CACHE_DIR / "t100" / f"{iata}.parquet"
    if path.exists() and (config.SNAPSHOT or time.time() - path.stat().st_mtime < _TTL_SECONDS):
        return pd.read_parquet(path)
    if config.SNAPSHOT:  # airport not in the snapshot (no scheduled service / not fetched when it was built)
        return pd.DataFrame()

    params = {
        "$select": "reporting_month," + ",".join(_NUM_COLS),
        "$where": f"origin_airport_code='{iata}' AND year >= '{since_year}'",
        "$order": "reporting_month",
        "$limit": 5000,
    }
    rows = http.get(config.SOCRATA_T100_BY_ORIGIN, params=params).json()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["month"] = pd.to_datetime(df.pop("reporting_month")).dt.to_period("M").dt.to_timestamp()
    for c in _NUM_COLS:
        df[c] = pd.to_numeric(df.get(c), errors="coerce")
    df = df.sort_values("month").reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    return df
