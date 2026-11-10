"""All-opening recognition checks. Evaluation labels stay outside every query vector."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams, Point

from . import memory
from .kernel import Kernel
from .simulation import run
from .workshop_evaluate import OUTCOMES, place
from .workshop_world import WorkshopWorld


def views(result, world):
    frames = {f["ms"]: f for f in result["frames"]}
    return [
        {
            "place": place(world, frames[d["time"]], v),
            "vector": v["vector"],
            "snapshot": v["snapshot"],
            "time": d["time"],
        }
        for d in result["decisions"]
        for v in d["views"]
    ]


def calibrate():
    world = WorkshopWorld()
    report = {
        "world": world.id,
        "protocol": world.protocol,
        "threshold": memory.MIN_SCORE,
        "margin": memory.MARGIN,
        "source_seed": 2000,
        "development_seeds": list(range(300, 310)),
        "scenery_seed": world.scenery_seed,
        "rows": [],
    }
    with Kernel() as kernel, TemporaryDirectory() as directory:
        source = run(kernel, world, seed=2000, duration=65, trace=True)
        source_personal = run(
            kernel,
            world,
            seed=2000,
            mode="personal",
            history=source["episodes"][:1],
            duration=65,
            pose_variant=1,
            trace=True,
        )
        references = [*views(source, world), *views(source_personal, world)]
        report["reference_scope"] = (
            "Both source approaches: the opening attempt and the personal-memory attempt, seed2000 only."
        )
        queries = []
        for seed in report["development_seeds"]:
            donor = run(kernel, world, seed=seed, duration=25, trace=True)
            baseline = run(
                kernel, world, seed=seed, duration=65, pose_variant=1, trace=True
            )
            personal = run(
                kernel,
                world,
                seed=seed,
                mode="personal",
                history=donor["episodes"],
                duration=65,
                pose_variant=1,
                trace=True,
            )
            queries.extend(
                {**v, "seed": seed, "run": name}
                for name, r in (("baseline", baseline), ("personal", personal))
                for v in views(r, world)
            )

        def bank(name, records):
            location = Path(directory) / name
            location.mkdir()
            shard = EdgeShard.create(
                str(location),
                EdgeConfig(
                    vectors={
                        "view": EdgeVectorParams(size=192, distance=Distance.Cosine)
                    }
                ),
            )
            for i, item in records:
                point = Point(
                    i,
                    {"view": item["vector"]},
                    {
                        "world": world.id,
                        "protocol": world.protocol,
                        "source_fly": "Calibration only",
                        "snapshot": item["snapshot"],
                        "outcome": OUTCOMES[item["place"]],
                    },
                )
                memory.remember(shard, point)
            return shard

        known_accepted = known_wrong = unknown_false = unknown_total = 0
        shards = []
        try:
            complete = bank("complete", list(enumerate(references)))
            shards.append(complete)
            for query in queries:
                hits = memory.recall(
                    complete, query["vector"], world.id, protocol=world.protocol
                )
                correct = (
                    bool(hits) and references[hits[0].id]["place"] == query["place"]
                )
                known_accepted += correct
                wrong = [h for h in hits if references[h.id]["place"] != query["place"]]
                known_wrong += len(wrong)
                report["rows"].append(
                    {
                        "seed": query["seed"],
                        "run": query["run"],
                        "time": query["time"],
                        "place": query["place"],
                        "accepted": correct,
                        "scores": [
                            {"place": references[h.id]["place"], "score": h.score}
                            for h in hits
                        ],
                    }
                )
            # Each absent-true-place query sees only one wrong-place record.
            # These are correlated query pairs over six places, not independent places.
            for i, reference in enumerate(references):
                sparse = bank(f"sparse-{i}", [(i, reference)])
                shards.append(sparse)
                for query in queries:
                    if query["place"] == reference["place"]:
                        continue
                    unknown_total += 1
                    hits = memory.recall(
                        sparse, query["vector"], world.id, protocol=world.protocol
                    )
                    unknown_false += bool(hits)
                sparse.close()
                shards.remove(sparse)
        finally:
            for shard in shards:
                shard.close()
    report["summary"] = {
        "known_queries": len(queries),
        "known_accepted": known_accepted,
        "wrong_returned_matches": known_wrong,
        "sparse_unknown_query_pairs": unknown_total,
        "sparse_unknown_false_accepts": unknown_false,
        "places": len({r["place"] for r in references}),
        "reference_views": len(references),
        "negative_scope": "Correlated one-record queries over six entrances; every true-place prototype is absent.",
    }
    return report


if __name__ == "__main__":
    import sys

    result = calibrate()
    Path(sys.argv[1]).write_text(json.dumps(result, indent=2))
    print(json.dumps(result["summary"]))
