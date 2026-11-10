"""Independent checks on sim.py. Run from fly-memory/:  python audit/audit.py"""
import json
import sys
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

sys.path.insert(0, str(Path(__file__).parent.parent))
from sim import Config, run  # noqa: E402

out = {}

# 1. The location control relies on score_threshold meaning "max distance" for EUCLID. Prove it.
c = QdrantClient(":memory:")
c.create_collection("t", vectors_config=models.VectorParams(size=2, distance=models.Distance.EUCLID))
c.upsert("t", [models.PointStruct(id=i, vector=[float(i), 0.0]) for i in range(10)])
got = [p.id for p in c.query_points("t", query=[0.0, 0.0], limit=10, score_threshold=3.0).points]
out["euclid_threshold_returns"] = got
assert sorted(got) == [0, 1, 2, 3], f"EUCLID score_threshold is not a max distance: {got}"

# 2. Fresh seeds nobody has looked at. Same story or not?
fresh = {}
for cond in ["naive", "private", "shared", "shuffled", "location"]:
    rs = [run(Config(seed=s), cond) for s in range(100, 105)]
    fresh[cond] = {k: float(np.mean([r[k] for r in rs])) for k in
                   ("first_meeting_right_call", "food_per_fly", "survival", "stings_per_fly")}
    if cond == "shared":
        shared_runs = rs
    print("fresh", cond, {k: round(v, 3) for k, v in fresh[cond].items()}, flush=True)
out["fresh_seeds_100_104"] = fresh

# 3. Upstream traffic, counted honestly: a query sends a vector up too.
d = Config().dim
up = []
for r in shared_runs:
    sniffs = r["local_hits"] + r["fleet_queries"]          # every odor a fly had to decide about
    up.append({
        "uploads_bytes": r["bytes_up"],
        "query_bytes": r["fleet_queries"] * (d * 4),
        "total_upstream_bytes": r["bytes_up"] + r["fleet_queries"] * (d * 4),
        "every_sniff_to_cloud_bytes": sniffs * (d * 4),     # no local memory, cloud decides everything
        "firehose_bytes": r["firehose_bytes"],
        "sniffs": sniffs,
        "fleet_queries": r["fleet_queries"],
        "writes": r["fleet_writes"],
    })
out["traffic"] = {k: float(np.mean([u[k] for u in up])) for k in up[0]}
print("traffic", {k: round(v) for k, v in out["traffic"].items()}, flush=True)

# 4. The "new hazard learned in ~10 steps" claim: how many first meetings sit in each bin?
meets = [(st - Config().novel_step, a) for r in shared_runs for st, a in r["novel_first_meet"]]
bins = [(0, 5), (5, 10), (10, 20), (20, 50), (50, 200)]
out["novel_bins"] = [{"steps": f"{lo}-{hi}", "n": sum(lo <= s < hi for s, _ in meets),
                      "avoided": float(np.mean([a for s, a in meets if lo <= s < hi] or [np.nan]))}
                     for lo, hi in bins]
print("novel", out["novel_bins"], flush=True)

# 5. Robustness: messier smells, stricter/looser matching. Where does it break?
rob = []
for noise in (0.5, 0.8, 1.0, 1.3):
    for thr in (0.5, 0.6, 0.7):
        row = {"instance_noise": noise, "threshold": thr}
        for cond in ("private", "shared", "shuffled"):
            rs = [run(Config(seed=s, instance_noise=noise, match_threshold=thr), cond) for s in range(3)]
            row[cond] = float(np.mean([r["first_meeting_right_call"] for r in rs]))
            row[cond + "_food"] = float(np.mean([r["food_per_fly"] for r in rs]))
        rob.append(row)
        print("robust", {k: round(v, 3) for k, v in row.items()}, flush=True)
out["robustness"] = rob

(Path(__file__).parent / "audit_results.json").write_text(json.dumps(out, indent=1))
print("wrote audit/audit_results.json")
