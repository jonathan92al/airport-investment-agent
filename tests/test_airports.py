"""Airport lookup. Uses the cached OurAirports files (downloaded on first use)."""
from airport_agent.data import airports


def codes(q):
    return set(airports.resolve(q)["iata"])


def test_la_means_los_angeles_not_every_name_containing_la():
    assert codes("LA") == {"LAX"}
    assert "ATL" not in codes("LA")


def test_codes_cities_and_names():
    assert codes("SFO") == {"SFO"}
    assert codes("sfo") == {"SFO"}
    assert codes("Santa Ana") == {"SNA"}
    assert codes("Anchorage") >= {"ANC"}
    assert codes("Kennedy") == {"JFK"}


def test_unknown_and_short_garbage_match_nothing():
    assert codes("Narnia") == set()
    assert codes("zz") == set()


def test_trailing_airport_word_is_ignored():
    assert list(airports.resolve("Santa Ana airport")["iata"]) == list(airports.resolve("Santa Ana")["iata"]) == ["SNA"]
