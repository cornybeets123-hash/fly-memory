"""Export the hero replay data for the B and C visuals: viz/story.js

One featured fly (picked by select_fly.py, criteria and base rates included), followed in
both runs (same world, same start): alone vs sharing one memory. Everything else on screen
(fleet counters, the memory map, match scores) comes from the same real runs.
"""
import json
from pathlib import Path

import numpy as np

from sim import Config, run

pick = json.load(open("viz/featured_fly.json"))
FLY = pick["pick"]
cfg = Config(seed=0)
runs = {c: run(cfg, c, trace=[FLY]) for c in ("naive", "shared")}

NAMES = ["apple", "banana", "honey", "wine", "apple-bait trap", "spider", "frog", "gecko", "Venus flytrap"]
UPLOAD_BYTES = cfg.dim * 4 + 24
QUERY_BYTES = cfg.dim * 4

# memory map: PCA of every uploaded smell; the featured fly's questions are projected into the same space
log = runs["shared"]["fleet_log"]
ups = runs["shared"]["trace"]["uploads"]
X = np.array([v for _, _, v in log])
mu = X.mean(0)
_, _, vt = np.linalg.svd(X - mu, full_matrices=False)
basis = vt[:2].T
xy = (X - mu) @ basis
lo, hi = xy.min(0), xy.max(0)
norm = lambda p: ((p - lo) / (hi - lo)).round(4).tolist()
memory = [{"id": i, "s": s, "f": f, "t": t, "danger": d, "xy": norm(p)}
          for i, ((s, f, t, d), p) in enumerate(zip(ups, xy))]


def fly_view(r):
    tr = r["trace"]
    evs = []
    for e in tr["events"]:
        e = dict(e)
        if e.get("vec") is not None:
            e["qxy"] = norm((np.array(e.pop("vec")) - mu) @ basis)
        else:
            e.pop("vec", None)
        if "hits" in e:
            e["hits"] = [dict(t=h[0], score=h[1], danger=h[2], fly=h[3], step=h[4], id=h[5]) for h in e["hits"]]
        evs.append(e)
    return {"pos": [p[0] for p in tr["pos"]], "alive": [a[0] for a in tr["alive"]],
            "obj_pos": tr["obj_pos"][0], "obj_type": tr["obj_type"][0], "events": evs}


def fleet(r):
    ps = r["per_step"]
    w, q = np.cumsum(ps["writes"]), np.cumsum(ps["queries"])
    return {"alive": ps["alive"], "stings": np.cumsum(ps["stings"]).tolist(), "food": np.cumsum(ps["food"]).tolist(),
            "writes": w.tolist(), "queries": q.tolist(), "local_hits": np.cumsum(ps["local_hits"]).tolist(),
            "upstream_bytes": (w * UPLOAD_BYTES + q * QUERY_BYTES).tolist()}


story = {
    "about": "Replay of a real run of sim.py (seed 0, 1,000 flies, 400 steps). Not scripted.",
    "config": cfg.__dict__,
    "names": NAMES,
    "food_types": cfg.food_types,
    "novel_type": cfg.food_types + cfg.hazard_types,
    "featured": {"fly": FLY, "why": "earliest fleet warning among flies that hit every story beat",
                 "qualifying_flies": pick["qualifying"], "base_rates": pick["base_rates"]},
    "bytes": {"upload": UPLOAD_BYTES, "query": QUERY_BYTES, "firehose_total": runs["shared"]["firehose_bytes"]},
    "naive": {"fly": fly_view(runs["naive"]), "fleet": fleet(runs["naive"]),
              "summary": {k: runs["naive"][k] for k in ("stings_per_fly", "food_per_fly", "survival", "first_meeting_right_call")}},
    "shared": {"fly": fly_view(runs["shared"]), "fleet": fleet(runs["shared"]),
               "summary": {k: runs["shared"][k] for k in ("stings_per_fly", "food_per_fly", "survival",
                                                          "first_meeting_right_call", "total_upstream_bytes")}},
    "memory": memory,
}
Path("viz/story.js").write_text("window.STORY = " + json.dumps(story, separators=(",", ":")) + ";\n")
print("wrote viz/story.js", round(Path("viz/story.js").stat().st_size / 1024), "KB, featured fly", FLY)
for c in ("naive", "shared"):
    evs = story[c]["fly"]["events"]
    kinds = {}
    for e in evs:
        kinds[e["k"]] = kinds.get(e["k"], 0) + 1
    print(c, "alive at end:", story[c]["fly"]["alive"][-1], kinds)
print("warnings:", [(e["s"], NAMES[e["t"]], e["score"], [(NAMES[h["t"]], h["score"], h["fly"]) for h in e["hits"][:3]])
                    for e in story["shared"]["fly"]["events"] if e["k"] == "ask" and e["answer"] == "danger"])
