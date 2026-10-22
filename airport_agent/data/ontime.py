"""BTS On-Time Performance (domestic flights by large reporting carriers).

Raw monthly files are ~30 MB zipped / ~600k flights. We aggregate each month to one row per
airport and cache only that, as sums and counts, so months can be combined correctly
(a mean of monthly means would be wrong).

Scope caveat: only domestic flights by carriers with >=0.5% of domestic passenger revenue
are reported. International flights and small commuter carriers are missing.
"""
import re
import zipfile

import numpy as np
import pandas as pd

from .. import config, http

_USECOLS = ["Origin", "Dest", "Distance", "Cancelled", "CancellationCode", "Diverted",
            "DepDelay", "DepDel15", "ArrDelay", "ArrDel15", "TaxiOut", "TaxiIn",
            "CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay"]

_BAND_EDGES = [0] + config.DISTANCE_EDGES + [np.inf]


def band_columns() -> list[str]:
    cols = []
    for lo, hi in zip(_BAND_EDGES[:-1], _BAND_EDGES[1:]):
        cols.append(f"band_{lo}_plus" if np.isinf(hi) else f"band_{lo}_{hi}")
    return cols


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """One raw month of flights -> one row per airport (departure side and arrival side)."""
    operated = df[df["Cancelled"] == 0]

    dep = df.groupby("Origin").agg(
        scheduled_deps=("Origin", "size"),
        cancelled=("Cancelled", "sum"),
        cancelled_weather=("CancellationCode", lambda s: (s == "B").sum()),
        cancelled_nas=("CancellationCode", lambda s: (s == "C").sum()),
    )
    op = operated.groupby("Origin").agg(
        operated_deps=("Origin", "size"),
        dep_del15=("DepDel15", "sum"),
        dep_delay_min=("DepDelay", "sum"),
        taxi_out_min=("TaxiOut", "sum"),
        taxi_out_n=("TaxiOut", "count"),
        distance_sum=("Distance", "sum"),
    )
    bands = pd.cut(operated["Distance"], _BAND_EDGES, right=False, labels=band_columns())
    band_counts = (pd.crosstab(operated["Origin"], bands)
                   .reindex(columns=band_columns(), fill_value=0))
    dep = dep.join(op).join(band_counts)

    arr = df[df["Cancelled"] == 0].groupby("Dest").agg(
        arrivals=("Dest", "size"),
        diverted=("Diverted", "sum"),
        arr_del15=("ArrDel15", "sum"),
        arr_delay_min=("ArrDelay", "sum"),
        taxi_in_min=("TaxiIn", "sum"),
        taxi_in_n=("TaxiIn", "count"),
        carrier_delay_min=("CarrierDelay", "sum"),
        weather_delay_min=("WeatherDelay", "sum"),
        nas_delay_min=("NASDelay", "sum"),
        security_delay_min=("SecurityDelay", "sum"),
        late_aircraft_delay_min=("LateAircraftDelay", "sum"),
    )
    out = dep.join(arr, how="outer").fillna(0)
    out.index.name = "iata"
    return out.reset_index()


def _month_cache(year: int, month: int):
    return config.CACHE_DIR / "ontime" / f"agg_{year}_{month:02d}.parquet"


def load_month(year: int, month: int) -> pd.DataFrame:
    path = _month_cache(year, month)
    if path.exists():
        return pd.read_parquet(path)

    zip_path = config.CACHE_DIR / "ontime" / "raw" / f"{year}_{month}.zip"
    http.download(config.ONTIME_ZIP_URL.format(year=year, month=month), zip_path)
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(name) as f:
            raw = pd.read_csv(f, usecols=_USECOLS, low_memory=False)
    agg = aggregate(raw)
    agg.insert(0, "month", pd.Timestamp(year=year, month=month, day=1))
    agg.to_parquet(path)
    zip_path.unlink()  # raw file is large and fully captured by the aggregate
    return agg


def available_months() -> list[tuple[int, int]]:
    html = http.get(config.ONTIME_INDEX_URL).text
    found = re.findall(r"On_Time_Reporting_Carrier_On_Time_Performance_1987_present_(\d{4})_(\d{1,2})\.zip", html)
    return sorted({(int(y), int(m)) for y, m in found})


def load(n_months: int = config.ONTIME_MONTHS) -> pd.DataFrame:
    """Airport-month rows for the most recent n published months (downloads what is missing)."""
    months = available_months()[-n_months:]
    return pd.concat([load_month(y, m) for y, m in months], ignore_index=True)
