"""Copy the live cache into ./data so the app can run hosted with no network access to BTS.

Run: python -m airport_agent.data.snapshot   (after the app has been used locally, or after calibrate)
"""
import json
import shutil
from datetime import date

import pandas as pd

from .. import config
from . import airports, ontime, t100

SRC = config.ROOT / ".cache"
DST = config.ROOT / "data"


def build():
    if config.SNAPSHOT:
        raise SystemExit("Run this without DATA_MODE=snapshot so it reads the live cache.")
    ontime.load()                                    # make sure the latest 12 months are cached
    codes = sorted(airports.load()["iata"])
    for code in codes:                               # T-100 for every airport the app can resolve
        t100.monthly(code)

    if DST.exists():
        shutil.rmtree(DST)
    (DST / "ontime").mkdir(parents=True)
    (DST / "t100").mkdir()
    (DST / "ourairports").mkdir()

    months = ontime.available_months()[-config.ONTIME_MONTHS:]
    for y, m in months:
        shutil.copy(ontime._month_cache(y, m), DST / "ontime")
    n_t100 = 0
    for code in codes:
        f = SRC / "t100" / f"{code}.parquet"
        if f.exists():
            shutil.copy(f, DST / "t100")
            n_t100 += 1

    # Keep only the US rows the app reads (the full OurAirports files are ~17 MB).
    ap = pd.read_csv(SRC / "ourairports" / "airports.csv", low_memory=False)
    ap = ap[ap["iso_country"] == "US"]
    ap.to_csv(DST / "ourairports" / "airports.csv", index=False)
    rw = pd.read_csv(SRC / "ourairports" / "runways.csv", low_memory=False)
    rw[rw["airport_ident"].isin(ap["ident"])].to_csv(DST / "ourairports" / "runways.csv", index=False)

    t = pd.concat([pd.read_parquet(f) for f in (DST / "t100").glob("*.parquet")])
    manifest = {
        "built": date.today().isoformat(),
        "ontime_months": [f"{y}-{m:02d}" for y, m in months],
        "t100_through": str(t["month"].max().date()),
        "t100_airports": n_t100,
    }
    (DST / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(manifest)


if __name__ == "__main__":
    build()
