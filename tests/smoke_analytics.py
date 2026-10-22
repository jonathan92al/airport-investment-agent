"""Run the four exam questions through the analytics layer on live data.
Run: python tests/smoke_analytics.py"""
from airport_agent import config
from airport_agent.analytics import profile, scoring
from airport_agent.data import airports


def pct(x):
    return "n/a" if x is None else f"{x:.1%}"


print("== Q1: New England expansion ranking ==")
profs = [profile.build_profile(i) for i in airports.in_states(config.NEW_ENGLAND)["iata"]]
res = scoring.rank(profs)
sens = scoring.rank_sensitivity(profs)
for r in res["ranked"]:
    s = sens[r["iata"]]
    print(f"{r['rank']:>2} {r['iata']} score={r['score']:5.1f} "
          f"cong={r['sub_scores']['congestion']['score']} dem={r['sub_scores']['demand_pressure']['score']} "
          f"grow={r['sub_scores']['growth']['score']} | rank range {s['best']}-{s['worst']} missing={r['missing']}")
print("excluded:", [(e['iata']) for e in res["excluded"]])

print("\n== Q2: LAX vs SNA congestion ==")
for i in ["LAX", "SNA"]:
    p = profile.build_profile(i)
    c = scoring.congestion_index(p["ontime"])
    o = p["ontime"]
    print(i, "congestion", c["score"], "| delay15", pct(o["dep_delay15_rate"]), "taxi-out", round(o["avg_taxi_out_min"], 1),
          "cancel", pct(o["cancel_rate"]), "deps/rwy/day", round(o["deps_per_runway_day"], 1))

print("\n== Q3: ANC long-haul share ==")
lh = profile.build_profile("ANC")["long_haul"]
print({k: v for k, v in lh.items() if k != "bands"}, lh["bands"])

print("\n== Q4: SFO unmet demand proxy ==")
p = profile.build_profile("SFO")
u = scoring.unmet_demand(p)
print("index", u["score"], "| load factor", pct(p["traffic"]["load_factor"]))
for d in u["drivers"]:
    print("  ", d["name"], d["raw"], "->", round(d["score"], 1))
print("delay causes:", {k: pct(v) for k, v in p["ontime"]["delay_cause_share"].items()})
print("cancel causes:", {k: pct(v) for k, v in p["ontime"]["cancel_cause_share"].items()})
