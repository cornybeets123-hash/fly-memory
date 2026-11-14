"""Declared webinar trials and an evaluation-only outcome atlas."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams

from . import cohort, memory
from .cohort_evaluate import audit
from .kernel import Kernel
from .webinar_world import WebinarWorld
from .workshop_evaluate import freeze

# Evaluation only. These labels never enter perception, vectors, or movement.
OUTCOMES = {
    (0, "west"): "returned",
    (0, "south"): "returned",
    (0, "east"): "open",
    (1, "west"): "open",
    (1, "north"): "dead_end",
    (1, "south"): "open",
    (2, "west"): "dead_end",
    (2, "east"): "open",
    (2, "north"): "open",
    (3, "west"): "open",
    (3, "north"): "open",
    (3, "south"): "dead_end",
    (4, "west"): "dead_end",
    (4, "east"): "open",
    (4, "south"): "open",
    (5, "west"): "open",
    (5, "north"): "open",
    (5, "east"): "dead_end",
    (6, "west"): "open",
    (6, "east"): "dead_end",
    (6, "south"): "open",
    (7, "east"): "open",
    (7, "north"): "open",
    (7, "south"): "dead_end",
}


def summaries(stages, world):
    """Measure exclusions against the separate evaluation atlas after movement ends."""
    from .workshop_evaluate import capture_frame, place

    atlas = {}
    for results in stages.values():
        for result in results:
            decisions = {
                d.get("capture_time", d["time"]): d for d in result["decisions"]
            }
            for episode in result["episodes"]:
                p = episode.point.payload
                event = next(
                    e
                    for e in result["events"]
                    if e["kind"] == "observed"
                    and e["observed_at_ms"] == p["observed_at_ms"]
                )
                capture = p["captured_at_ms"] - (p["observed_at_ms"] - event["time"])
                d = decisions[capture]
                atlas[episode.point.id] = place(
                    world, capture_frame(result, d), d["views"][d["choice"]], OUTCOMES
                )
    measured = {}
    for mode, results in stages.items():
        checked = audit({mode: results}, world, OUTCOMES, atlas)
        measured[mode] = {
            **cohort.totals(results),
            "false_exclusions": checked["false_exclusions"],
            "audit_errors": checked["errors"],
        }
    return measured


def evaluate(count=8, seed=300):
    from .presentation import pack, record, scene

    started = perf_counter()
    world = WebinarWorld()
    seeds = list(range(seed, seed + count))
    with Kernel() as kernel, TemporaryDirectory() as directory:
        path = Path(directory) / "edge"
        path.mkdir()
        shard = EdgeShard.create(
            str(path),
            EdgeConfig(
                vectors={"view": EdgeVectorParams(size=192, distance=Distance.Cosine)}
            ),
        )
        try:
            stages = {}
            history = []
            for mode in ("none", "personal", "shared"):
                stages[mode] = cohort.simulate(
                    kernel, world, mode, seeds, memory, shard, history=history
                )
                if mode == "personal":
                    history = [e for r in stages[mode] for e in r["episodes"]]
                print(
                    json.dumps(
                        {
                            "mode": mode,
                            "summary": cohort.totals(stages[mode]),
                            "wall_s": round(perf_counter() - started, 2),
                        }
                    ),
                    flush=True,
                )
            checked = audit(stages, world, OUTCOMES)
            print(json.dumps({"errors": checked["errors"]}), flush=True)
            bundles = {}
            for mode, results in stages.items():
                previous = (
                    "none"
                    if mode == "personal"
                    else "personal"
                    if mode == "shared"
                    else None
                )
                bundles[mode] = {
                    "mode": mode,
                    "flies": [pack(r, world) for r in results],
                    "comparisons": [cohort.movement(r) for r in stages[previous]]
                    if previous
                    else [],
                    "initial_memories": [record(e) for e in history]
                    if mode == "shared"
                    else [],
                    "world": scene(world),
                    "brain": kernel.info,
                    "cohort": {
                        "seeds": seeds,
                        "deadline_ms": world.deadline * 1000,
                        "summary": cohort.totals(results),
                    },
                    "source": "Recorded computation",
                    "code": "Completed code",
                }
            return {
                "world": world.id,
                "protocol": world.protocol,
                "seeds": seeds,
                "deadline_seconds": world.deadline,
                "source": freeze(),
                "wall_seconds": round(perf_counter() - started, 2),
                "summary": {m: cohort.totals(r) for m, r in stages.items()},
                "audit": checked,
                "passed": not checked["errors"],
                "runs": bundles,
            }
        finally:
            shard.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--seed", type=int, default=300)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.count, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(",", ":")))
    raise SystemExit(0 if result["passed"] else 1)
