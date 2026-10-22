"""Central settings. Anything that changes a result lives here so it can be shown to the user."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".cache"

# Distance band edges (statute miles) used when aggregating on-time data. A "long-haul"
# threshold must be one of these edges, because only band counts are cached.
DISTANCE_EDGES = [500, 1000, 1500, 2000, 2500, 3000]
LONG_HAUL_MILES = 2500

# How many most-recent months of BTS on-time data to use for congestion metrics.
ONTIME_MONTHS = 12

# BTS endpoints.
ONTIME_ZIP_URL = ("https://transtats.bts.gov/PREZIP/"
                  "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip")
ONTIME_INDEX_URL = "https://transtats.bts.gov/PREZIP/"
SOCRATA_T100_BY_ORIGIN = "https://data.bts.gov/resource/r495-tyji.json"

OURAIRPORTS_BASE = "https://davidmegginson.github.io/ourairports-data/"

NEW_ENGLAND = ["CT", "ME", "MA", "NH", "RI", "VT"]
