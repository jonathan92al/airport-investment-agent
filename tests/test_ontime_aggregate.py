import numpy as np
import pandas as pd

from airport_agent.data import ontime


def _flights():
    rows = [
        # Origin, Dest, Distance, Cancelled, Code, Diverted, DepDelay, DepDel15, ArrDelay, ArrDel15, TaxiOut, TaxiIn
        ("AAA", "BBB", 300, 0, None, 0, 20, 1, 25, 1, 10, 5),
        ("AAA", "BBB", 2600, 0, None, 0, 0, 0, -5, 0, 20, 7),
        ("AAA", "CCC", 1200, 1, "B", 0, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan),
        ("BBB", "AAA", 300, 0, None, 0, 5, 0, 0, 0, 12, 6),
    ]
    cols = ["Origin", "Dest", "Distance", "Cancelled", "CancellationCode", "Diverted", "DepDelay",
            "DepDel15", "ArrDelay", "ArrDel15", "TaxiOut", "TaxiIn"]
    df = pd.DataFrame(rows, columns=cols)
    for c in ["CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay"]:
        df[c] = 0.0
    df.loc[0, "NASDelay"] = 15.0
    return df


def test_departure_counts_and_cancellations():
    agg = ontime.aggregate(_flights()).set_index("iata")
    a = agg.loc["AAA"]
    assert a.scheduled_deps == 3
    assert a.operated_deps == 2
    assert a.cancelled == 1 and a.cancelled_weather == 1 and a.cancelled_nas == 0
    assert a.dep_del15 == 1
    assert a.dep_delay_min == 20  # cancelled flight excluded


def test_distance_bands_use_operated_flights_only():
    a = ontime.aggregate(_flights()).set_index("iata").loc["AAA"]
    assert a["band_0_500"] == 1
    assert a["band_2500_3000"] == 1
    assert a["band_1000_1500"] == 0  # the 1200-mile flight was cancelled
    assert sum(a[c] for c in ontime.band_columns()) == a.operated_deps


def test_arrival_side_and_delay_causes():
    b = ontime.aggregate(_flights()).set_index("iata").loc["BBB"]
    assert b.arrivals == 2
    assert b.arr_del15 == 1
    assert b.nas_delay_min == 15
    assert b.taxi_in_min == 12 and b.taxi_in_n == 2
