"""Audit the actual group histories, ownership filters, and measured search calls."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams

from . import cohort, memory
from .kernel import Kernel
from .simulation import compact
from .workshop_evaluate import OUTCOMES, capture_frame, freeze, place
from .workshop_world import WorkshopWorld


def audit(stages, world, outcomes=OUTCOMES, source_atlas=None):
    atlas, errors = dict(source_atlas or {}), []
    for mode, results in stages.items():
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
                view = d["views"][d["choice"]]
                identity = place(world, capture_frame(result, d), view, outcomes)
                atlas[episode.point.id] = identity
                if (
                    p["outcome"] != outcomes[identity]
                    or p["snapshot"] != view["snapshot"]
                ):
                    errors.append(f"{result['owner']}: incorrect observed record")
    query_count, uses, other_sources = 0, 0, 0
    false_exclusions = 0
    queries = []
    for mode, results in stages.items():
        for result in results:
            if (
                result["summary"]["collisions"]
                or result["summary"]["longest_stall_s"] > 1
                or result["summary"]["no_decision"]
            ):
                errors.append(f"{mode}/{result['owner']}: movement failure")
            for d in result["decisions"]:
                frame = capture_frame(result, d)
                for index, v in enumerate(d["views"]):
                    identity = place(world, frame, v, outcomes)
                    if mode == "none":
                        if v["search_ms"] is not None or v["hits"]:
                            errors.append("No-memory fly performed retrieval")
                    elif v["vector"] is not None:
                        if v["search_ms"] is None or v["search_ms"] < 0:
                            errors.append("Missing measured search time")
                        query_count += 1
                    for h in v["hits"]:
                        if atlas.get(h["id"]) != identity:
                            errors.append(
                                f"{mode}/{result['owner']}: wrong-place match {h['score']}"
                            )
                        source = h["payload"]["source_fly"]
                        if mode == "personal" and source != result["owner"]:
                            errors.append(f"Personal fly borrowed {source}")
                        if result["mode"] == "hive":
                            observed = h["payload"]["observed_at_ms"] - 100
                            if observed > d["time"]:
                                errors.append("Hive fly read a future observation")
                        elif mode == "shared" and not source.startswith("A"):
                            errors.append(
                                "Shared fly read another B's current-group observation"
                            )
                    if v["applied"]:
                        uses += 1
                        if outcomes[identity] == "open":
                            false_exclusions += 1
                            errors.append("A progress entrance was excluded")
                        if d["choice"] == index:
                            errors.append(
                                "Applied evidence did not prevent a repeated adverse entry"
                            )
                        source = v["selected"]["payload"]["source_fly"]
                        other_sources += (
                            mode == "shared" and source[1:] != result["owner"][1:]
                        )
                    queries.append(
                        {
                            "mode": mode,
                            "fly": result["owner"],
                            "time": d["time"],
                            "entrance": identity,
                            "search_ms": v["search_ms"],
                            "returned": len(v["hits"]),
                            "applied": v["applied"],
                        }
                    )
            if mode == "personal" and any(
                v["hits"] for v in result["decisions"][0]["views"]
            ):
                errors.append("Personal fly started with eligible history")
    return {
        "errors": errors,
        "queries": queries,
        "query_count": query_count,
        "memory_uses": uses,
        "borrowed_from_other_pair": other_sources,
        "false_exclusions": false_exclusions,
    }


def evaluate(bases):
    report = {
        "bases": bases,
        "group_size": cohort.SIZE,
        "deadline_seconds": cohort.DEADLINE,
        "shared_pool": "Completed A group, unchanged while all B brains run",
        "source": freeze(),
        "groups": [],
        "failures": [],
    }
    with Kernel() as kernel:
        world = WorkshopWorld()
        for base in bases:
            seeds = list(range(base, base + cohort.SIZE))
            with TemporaryDirectory() as directory:
                location = Path(directory) / "memory"
                location.mkdir()
                shard = EdgeShard.create(
                    str(location),
                    EdgeConfig(
                        vectors={
                            "view": EdgeVectorParams(size=192, distance=Distance.Cosine)
                        }
                    ),
                )
                try:
                    none = cohort.simulate(kernel, world, "none", seeds, memory, None)
                    personal = cohort.simulate(
                        kernel, world, "personal", seeds, memory, shard
                    )
                    history = [e for result in personal for e in result["episodes"]]
                    shared = cohort.simulate(
                        kernel, world, "shared", seeds, memory, shard, history
                    )
                    stages = {"none": none, "personal": personal, "shared": shared}
                    checked = audit(stages, world)
                    row = {
                        "seeds": seeds,
                        "summary": {m: cohort.totals(r) for m, r in stages.items()},
                        "audit": checked,
                        "runs": {
                            m: [compact(r) for r in rows] for m, rows in stages.items()
                        },
                    }
                    report["groups"].append(row)
                    report["failures"].extend(checked["errors"])
                    print(
                        json.dumps(
                            {
                                "base": base,
                                "summary": row["summary"],
                                "errors": checked["errors"],
                            }
                        ),
                        flush=True,
                    )
                finally:
                    shard.close()
    report["passed"] = not report["failures"]
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bases", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.bases)
    args.output.write_text(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
