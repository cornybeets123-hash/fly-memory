"""Record a real run for the replay page: same seed, same worlds, naive vs shared.

Flies 0-3 are shown (not picked for drama: they are simply the first four).
The counters on the page are the whole fleet of 1,000.
Writes viz/trace.js.
"""
import json
from pathlib import Path

import numpy as np

from sim import Config, run

SHOW = [0, 1, 2, 3]
cfg = Config(seed=0)
runs = {c: run(cfg, c, trace=SHOW) for c in ("naive", "shared")}

# the shared memory, flattened to 2-D so people can watch it fill up
log = runs["shared"]["fleet_log"]
ups = runs["shared"]["trace"]["uploads"]
X = np.array([v for _, _, v in log])
X = X - X.mean(0)
_, _, vt = np.linalg.svd(X, full_matrices=False)
xy = X @ vt[:2].T
xy = (xy - xy.min(0)) / (xy.max(0) - xy.min(0))
memory = [{"s": s, "f": f, "t": t, "x": round(float(a), 3), "y": round(float(b), 3)}
          for (s, f, t, _), (a, b) in zip(ups, xy)]

out = {
    "config": cfg.__dict__,
    "food_types": cfg.food_types,
    "novel_type": cfg.food_types + cfg.hazard_types,
    "memory": memory,
}
for c, r in runs.items():
    ps = r["per_step"]
    out[c] = {
        "trace": {k: v for k, v in r["trace"].items() if k != "uploads"},
        "alive": ps["alive"],
        "stings": np.cumsum(ps["stings"]).tolist(),
        "food": np.cumsum(ps["food"]).tolist(),
        "writes": np.cumsum(ps["writes"]).tolist(),
        "queries": np.cumsum(ps["queries"]).tolist(),
        "summary": {k: r[k] for k in ("stings_per_fly", "food_per_fly", "survival", "first_meeting_right_call",
                                      "fleet_writes", "fleet_queries", "total_upstream_bytes", "firehose_bytes")},
    }

Path("viz").mkdir(exist_ok=True)
Path("viz/trace.js").write_text("window.TRACE = " + json.dumps(out, separators=(",", ":")) + ";\n")
print("wrote viz/trace.js", round(Path("viz/trace.js").stat().st_size / 1024), "KB")
for c in runs:
    t = runs[c]["trace"]
    kinds = {}
    for e in t["events"]:
        kinds[e["k"]] = kinds.get(e["k"], 0) + 1
    print(c, "alive at end:", t["alive"][-1], kinds)
