import pandas as pd
import pytest

from airport_agent.analytics import metrics, scoring
from airport_agent.data import ontime


TEST_ANCHORS = {
    "dep_delay15_rate": (0.10, 0.30), "avg_taxi_out_min": (12.0, 30.0), "cancel_rate": (0.005, 0.04),
    "deps_per_runway_day": (40.0, 200.0), "load_factor": (0.70, 0.90),
    "passenger_growth_yoy": (-0.05, 0.10), "nas_delay_min_per_arrival": (1.0, 6.0),
}


@pytest.fixture(autouse=True)
def fixed_anchors(monkeypatch):
    """Pin anchors so tests do not depend on the calibrated anchors.json."""
    monkeypatch.setattr(scoring, "ANCHORS", TEST_ANCHORS)


def test_scale_clips_and_interpolates():
    assert scoring.scale(0.20, 0.10, 0.30) == pytest.approx(50.0)
    assert scoring.scale(0.0, 0.10, 0.30) == 0.0
    assert scoring.scale(9.9, 0.10, 0.30) == 100.0
    assert scoring.scale(None, 0, 1) is None


def test_combine_renormalises_over_missing_components():
    parts = [scoring.Component("a", 1, 100.0, 0.5), scoring.Component("b", None, None, 0.5)]
    score, missing = scoring.combine(parts)
    assert score == 100.0 and missing == ["b"]


def _profile(iata, delay, taxi, cancel, dpr, lf, growth, enpl=5_000_000):
    return {"iata": iata, "name": iata,
            "ontime": {"dep_delay15_rate": delay, "avg_taxi_out_min": taxi, "cancel_rate": cancel,
                       "deps_per_runway_day": dpr},
            "traffic": {"load_factor": lf, "passenger_growth_yoy": growth, "annual_enplanements": enpl}}


def test_rank_orders_by_score_and_excludes_small_airports():
    busy = _profile("BUSY", 0.30, 30, 0.04, 200, 0.90, 0.10)
    calm = _profile("CALM", 0.10, 12, 0.005, 40, 0.70, -0.05)
    tiny = _profile("TINY", 0.30, 30, 0.04, 200, 0.90, 0.10, enpl=10_000)
    out = scoring.rank([calm, busy, tiny])
    assert [r["iata"] for r in out["ranked"]] == ["BUSY", "CALM"]
    assert out["ranked"][0]["score"] == 100.0 and out["ranked"][1]["score"] == 0.0
    assert out["excluded"][0]["iata"] == "TINY"


def test_missing_ontime_scores_but_is_flagged_and_not_ranked():
    p = _profile("X", 0, 0, 0, 0, 0.90, 0.10)
    p["ontime"] = None
    s = scoring.expansion_score(p)
    assert s["score"] == 100.0  # single-airport scoring renormalises, but says what is missing
    assert "congestion" in s["missing"]

    ok = _profile("OK", 0.20, 20, 0.02, 100, 0.80, 0.0)
    out = scoring.rank([p, ok])
    assert [r["iata"] for r in out["ranked"]] == ["OK"]
    assert out["excluded"][0]["iata"] == "X"
    assert "insufficient data" in out["excluded"][0]["reason"]


def test_partially_missing_subcomponent_also_blocks_ranking():
    p = _profile("P", 0.20, 20, 0.02, 100, 0.80, 0.0)
    p["ontime"]["avg_taxi_out_min"] = None
    out = scoring.rank([p])
    assert out["ranked"] == []
    assert "congestion.avg_taxi_out_min" in out["excluded"][0]["reason"]


def test_missing_anchors_fail_loudly(monkeypatch):
    monkeypatch.setattr(scoring, "ANCHORS", {})
    with pytest.raises(RuntimeError, match="calibrate"):
        scoring.congestion_index({"dep_delay15_rate": 0.2})


def test_sensitivity_reports_rank_range():
    a = _profile("A", 0.30, 30, 0.04, 200, 0.70, -0.05)  # congested but low demand/growth
    b = _profile("B", 0.10, 12, 0.005, 40, 0.90, 0.10)   # calm but high demand/growth
    sens = scoring.rank_sensitivity([a, b])
    assert sens["A"]["by_preset"]["congestion_heavy"] == 1
    assert sens["A"]["by_preset"]["demand_heavy"] == 2
    assert sens["A"]["best"] == 1 and sens["A"]["worst"] == 2


def test_long_haul_share_and_threshold_validation():
    cols = ontime.band_columns()
    row = {c: 0 for c in cols}
    row["band_0_500"], row["band_2500_3000"], row["band_3000_plus"] = 6, 1, 1
    df = pd.DataFrame([row])
    res = metrics.long_haul_share(df, 2500)
    assert res["share"] == pytest.approx(0.25) and res["long_haul_flights"] == 2
    assert metrics.long_haul_share(df, 3000)["share"] == pytest.approx(0.125)
    with pytest.raises(ValueError):
        metrics.long_haul_share(df, 2400)


def test_traffic_growth_needs_two_full_years():
    months = pd.date_range("2024-01-01", periods=24, freq="MS")
    pax = [100] * 12 + [110] * 12
    df = pd.DataFrame({"month": months, "total_passengers": pax, "total_seats": [130] * 24,
                       "total_departures": [10] * 24, "total_distance_flight_sm": [500] * 24})
    t = metrics.traffic_metrics(df)
    assert t["passenger_growth_yoy"] == pytest.approx(0.10)
    assert t["load_factor"] == pytest.approx(110 / 130)
    assert t["data_through"] == "2025-12"
    short = metrics.traffic_metrics(df.tail(15))
    assert short["passenger_growth_yoy"] is None
