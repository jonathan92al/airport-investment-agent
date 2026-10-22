"""Airport reference data (OurAirports): identity, location, state, runway count."""
import re
from functools import lru_cache

import pandas as pd

from .. import config, http


def _csv(name: str) -> pd.DataFrame:
    path = config.CACHE_DIR / "ourairports" / name
    if not path.exists():
        http.download(config.OURAIRPORTS_BASE + name, path)
    return pd.read_csv(path, low_memory=False)


@lru_cache(maxsize=1)
def load() -> pd.DataFrame:
    """US airports with scheduled commercial service and an IATA code.

    Columns: iata, ident, name, city, state, lat, lon, size, runways, longest_runway_ft.
    """
    df = _csv("airports.csv")
    df = df[(df["iso_country"] == "US")
            & (df["scheduled_service"] == "yes")
            & df["iata_code"].notna()
            & df["type"].isin(["large_airport", "medium_airport"])].copy()

    rw = _csv("runways.csv")
    rw = rw[rw["closed"] == 0]
    rw = rw.groupby("airport_ident").agg(runways=("id", "count"),
                                         longest_runway_ft=("length_ft", "max"))

    out = df.rename(columns={"iata_code": "iata", "municipality": "city",
                             "latitude_deg": "lat", "longitude_deg": "lon"})
    out["state"] = out["iso_region"].str.split("-").str[1]
    out["size"] = out["type"].str.replace("_airport", "", regex=False)
    out = out.merge(rw, left_on="ident", right_index=True, how="left")
    out["runways"] = out["runways"].fillna(1).astype(int)
    cols = ["iata", "ident", "name", "city", "state", "lat", "lon", "size", "runways", "longest_runway_ft"]
    return out[cols].reset_index(drop=True)


def in_states(states: list[str]) -> pd.DataFrame:
    df = load()
    return df[df["state"].isin(states)].reset_index(drop=True)


# Common metro nicknames that are neither an IATA code nor a city name.
ALIASES = {
    "la": ["LAX"], "l.a.": ["LAX"], "nyc": ["JFK", "LGA", "EWR"], "new york city": ["JFK", "LGA", "EWR"],
    "dc": ["DCA", "IAD"], "washington dc": ["DCA", "IAD"], "sf": ["SFO"], "bay area": ["SFO", "OAK", "SJC"],
    "dallas": ["DFW", "DAL"], "houston": ["IAH", "HOU"], "chicago": ["ORD", "MDW"],
}


def resolve(query: str) -> pd.DataFrame:
    """Find airports for a code, city or name. Returns all plausible matches, best first.

    Callers must handle more than one match (e.g. "Washington", "New York") rather than guess.
    Fallback matching is on whole words, so "LA" cannot match "Atlanta".
    """
    q = query.strip().lower()
    df = load()
    exact_code = df[df["iata"].str.lower() == q]
    if len(exact_code):
        return exact_code
    if q in ALIASES:
        return df[df["iata"].isin(ALIASES[q])]
    city = df[df["city"].str.lower() == q]
    if len(city):
        return city
    pattern = rf"\b{re.escape(q)}\b"
    return df[df["city"].str.lower().str.contains(pattern, regex=True, na=False)
              | df["name"].str.lower().str.contains(pattern, regex=True, na=False)]
