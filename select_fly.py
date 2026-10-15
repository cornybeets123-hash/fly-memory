"""Which fly should the hero replay follow? Score every fly, report base rates, pick one.

A fly qualifies when, in the shared run, it
  - backs off a hazard because the fleet warned it (ask -> danger, never stung by it)
  - eats at least twice
  - meets the Venus flytrap after it appears and backs off without being caught
  - survives
and its twin in the naive run (same world, same start) dies.
"""
import json

from sim import Config, run

cfg = Config(seed=0)
ALL = range(cfg.flies)
shared = run(cfg, "shared", trace=ALL)["trace"]
naive = run(cfg, "naive", trace=ALL)["trace"]
NOVEL = cfg.food_types + cfg.hazard_types
is_hazard = lambda t: t >= cfg.food_types


def beats(tr, f):
    evs = [e for e in tr["events"] if e["f"] == f]
    warned = [e for e in evs if e["k"] == "ask" and e["answer"] == "danger" and is_hazard(e["t"]) and e["t"] != NOVEL]
    novel_avoid = [e for e in evs if e["k"] in ("ask", "local") and e.get("t") == NOVEL and
                   (e.get("answer") == "danger" or e.get("danger"))]
    stung = [e for e in evs if e["k"] == "sting"]
    eats = [e for e in evs if e["k"] == "eat"]
    return dict(warned=warned, novel_avoid=novel_avoid, stung=stung, eats=eats,
                alive=tr["alive"][-1][tr["flies"].index(f)] == 1)


rows = []
for f in ALL:
    s, n = beats(shared, f), beats(naive, f)
    ok = dict(warned=len(s["warned"]) > 0, eats2=len(s["eats"]) >= 2, novel=len(s["novel_avoid"]) > 0,
              survives=s["alive"], unstung=len(s["stung"]) == 0, twin_dies=not n["alive"])
    first_warn = s["warned"][0]["s"] if s["warned"] else 999
    rows.append((f, ok, first_warn, len(s["warned"]), len(n["stung"])))

base = {k: sum(r[1][k] for r in rows) / len(rows) for k in rows[0][1]}
good = [r for r in rows if all(r[1].values())]
good.sort(key=lambda r: (r[2], -r[3]))  # earliest warning first, then most warnings
pick = good[0][0]
out = {"base_rates": base, "qualifying": len(good), "pick": pick, "pick_first_warning_step": good[0][2],
       "top5": [(r[0], r[2], r[3]) for r in good[:5]]}
print(json.dumps(out, indent=1))
json.dump(out, open("viz/featured_fly.json", "w"), indent=1)
