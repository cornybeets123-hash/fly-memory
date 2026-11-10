"""Measure sparse-history retrieval on development views before the held-out gate."""

import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams

from . import memory
from .kernel import Kernel
from .simulation import run
from .vision import encode, snapshot
from .world import World


def calibrate():
    report = {
        "protocol": memory.PROTOCOL,
        "threshold": memory.MIN_SCORE,
        "margin": memory.MARGIN,
        "development_seeds": list(range(300, 310)),
        "known": [],
        "unknown": [],
        "scope": "One witnessed north dead end. Negatives are correlated local crops of two absent entrances, not independent places.",
    }
    with Kernel() as kernel, TemporaryDirectory() as directory:
        world = World()
        source = run(kernel, world, seed=2000, duration=25)
        record = next(
            e for e in source["episodes"] if e.point.payload["outcome"] == "dead_end"
        )
        reference = np.asarray(record.point.vector["view"])
        location = Path(directory) / "index"
        location.mkdir()
        shard = EdgeShard.create(
            str(location),
            EdgeConfig(
                vectors={"view": EdgeVectorParams(size=192, distance=Distance.Cosine)}
            ),
        )
        try:
            memory.remember(shard, record.point)
            for seed in report["development_seeds"]:
                for variant in (0, 1):
                    trial = run(
                        kernel,
                        world,
                        seed=seed,
                        pose_variant=variant,
                        duration=3.6,
                        trace=True,
                    )
                    decision = trial["decisions"][0]
                    known = decision["views"][0]["vector"]
                    hits = memory.recall(shard, known, world.id)
                    report["known"].append(
                        {
                            "seed": seed,
                            "variant": variant,
                            "cosine": float(reference @ known),
                            "accepted": bool(hits) and hits[0].id == record.point.id,
                        }
                    )
                    if variant:
                        continue
                    approach = [
                        f for f in trial["frames"] if f["ms"] <= decision["time"]
                    ][-15:]
                    for frame in approach:
                        x, y, h = frame["x"], frame["y"], frame["heading"]
                        candidates = [
                            h + o.bearing
                            for o in world.openings(x, y, h)
                            if math.sin(h + o.bearing) > 0
                        ]
                        south = candidates[0] if candidates else math.pi / 2
                        for kind, bearing in (
                            ("absent_south", south),
                            ("absent_west", math.pi),
                        ):
                            vector = encode(snapshot(world, x, y, bearing))
                            hits = memory.recall(shard, vector, world.id)
                            report["unknown"].append(
                                {
                                    "seed": seed,
                                    "time": frame["ms"],
                                    "kind": kind,
                                    "cosine": float(reference @ vector),
                                    "accepted": bool(hits),
                                }
                            )
        finally:
            shard.close()
    report["summary"] = {
        "known": len(report["known"]),
        "known_accepted": sum(r["accepted"] for r in report["known"]),
        "minimum_known_cosine": min(r["cosine"] for r in report["known"]),
        "unknown": len(report["unknown"]),
        "unknown_false_accepted": sum(r["accepted"] for r in report["unknown"]),
        "maximum_unknown_cosine": max(r["cosine"] for r in report["unknown"]),
    }
    return report


if __name__ == "__main__":
    import sys

    result = calibrate()
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2))
    print(json.dumps(result["summary"]))
