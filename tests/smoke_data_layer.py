"""Live smoke check of the data layer (hits the network). Run: python tests/smoke_data_layer.py"""
from airport_agent import config
from airport_agent.data import airports, ontime, t100

ne = airports.in_states(config.NEW_ENGLAND)
print("New England commercial airports:", len(ne), sorted(ne["iata"]))
for q in ["LAX", "Santa Ana", "Anchorage", "SFO"]:
    print(q, "->", airports.resolve(q)[["iata", "name", "state", "runways"]].to_dict("records"))

df = t100.monthly("ANC")
print("ANC T-100 rows:", len(df), "latest month:", df["month"].max().date(),
      "| load factor latest:", df.iloc[-1]["total_load_factor"])

m = ontime.available_months()[-1]
agg = ontime.load_month(*m)
print("on-time latest month:", m, "airports:", len(agg))
print(agg[agg["iata"].isin(["SFO", "ANC", "LAX", "SNA"])][
          ["iata", "scheduled_deps", "cancelled", "dep_del15", "operated_deps", "arrivals"]])
