"""Measure a small maze with neural choices and observed external memory."""

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

from .kernel import Kernel
from .simulation import compact, run
from .workshop_world import WorkshopWorld

# Evaluation labels remain outside perception, encoding, retrieval, and control.
OUTCOMES = {
    (0, "west"): "returned",
    (0, "south"): "returned",
    (0, "east"): "open",
    (1, "north"): "dead_end",
    (1, "south"): "open",
    (1, "west"): "open",
    (2, "west"): "dead_end",
    (2, "east"): "open",
    (2, "north"): "open",
}
DEADLINE = 65


def place(world, frame, view, outcomes=OUTCOMES):
    x, y = frame["x"], frame["y"]
    number, (cx, cy) = min(
        enumerate(world.junction_centers),
        key=lambda item: math.hypot(x - item[1][0], y - item[1][1]),
    )
    if abs(x - cx) > 41 or abs(y - cy) > 41:
        raise ValueError("A query occurred outside its observed fork")
    axis = view["camera_bearing"]
    if axis is None:
        return None
    direction = ("east", "south", "west", "north")[round(axis / (math.pi / 2)) % 4]
    key = number, direction
    if key not in outcomes:
        raise ValueError("A camera points toward a closed arm")
    return key


def capture_frame(result, decision):
    return next(
        f
        for f in result["frames"]
        if f["ms"] == decision.get("capture_time", decision["time"])
    )


def trials(kernel, world, seed, controls=False):
    settings = {"seed": seed, "duration": DEADLINE, "trace": True}
    none = run(kernel, world, **settings)
    personal = run(kernel, world, mode="personal", **settings)
    history = personal["episodes"]
    shared = run(kernel, world, mode="shared", history=history, **settings)
    private = run(
        kernel, world, mode="personal", owner="B", history=history, **settings
    )
    results = {
        "none": none,
        "personal": personal,
        "shared": shared,
        "private_b": private,
    }
    if controls:
        for control in ("mute_choice", "reverse_choice"):
            results[control] = run(
                kernel,
                world,
                mode="shared",
                history=history,
                control=control,
                **settings,
            )
    return results


def audit(results, world):
    atlas, false_records, gallery = {}, [], []
    for name, result in results.items():
        decisions = {d.get("capture_time", d["time"]): d for d in result["decisions"]}
        for d in result["decisions"]:
            frame = capture_frame(result, d)
            for v in d["views"]:
                if v["vector"] is not None:
                    gallery.append((place(world, frame, v), v["vector"]))
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
            assert view["snapshot"] == p["snapshot"]
            identity = place(world, capture_frame(result, d), view)
            atlas[episode.point.id] = identity
            if p["outcome"] != OUTCOMES[identity]:
                false_records.append({"run": name, "place": identity, "payload": p})
    wrong_matches, false_exclusions, repeated, ownership_errors = [], [], [], []
    matches, own_uses, borrowed_uses = 0, 0, 0
    for name, result in results.items():
        own_ids = {e.point.id for e in result["episodes"]}
        for d in result["decisions"]:
            frame = capture_frame(result, d)
            for index, v in enumerate(d["views"]):
                current = place(world, frame, v)
                if v["applied"] and OUTCOMES[current] == "open":
                    false_exclusions.append(
                        {"run": name, "time": d["time"], "place": current}
                    )
                if v["applied"] and index == d["choice"]:
                    repeated.append({"run": name, "time": d["time"]})
                for h in v["hits"]:
                    matches += 1
                    if atlas.get(h["id"]) != current:
                        wrong_matches.append(
                            {"run": name, "time": d["time"], "score": h["score"]}
                        )
                if not v["applied"]:
                    continue
                h = v["selected"]
                if name in {"personal", "private_b"}:
                    own_uses += 1
                    if (
                        h["id"] not in own_ids
                        or h["payload"]["source_fly"] != result["owner"]
                    ):
                        ownership_errors.append(name)
                    if h["payload"]["observed_at_ms"] >= d["capture_time"] + (
                        max(
                            (
                                e.point.payload["observed_at_ms"]
                                for e in results["personal"]["episodes"]
                            ),
                            default=0,
                        )
                        + 100
                        if name == "private_b"
                        else 100
                    ):
                        ownership_errors.append(name + ": future observation")
                elif name == "shared":
                    borrowed_uses += 1
                    if h["payload"]["source_fly"] != "A":
                        ownership_errors.append(name)
    same_scores, cross_scores = [], []
    for i, (identity, vector) in enumerate(gallery):
        for other, comparison in gallery[i + 1 :]:
            score = float(np.dot(vector, comparison))
            (same_scores if identity == other else cross_scores).append(score)
    return {
        "false_records": false_records,
        "wrong_matches": wrong_matches,
        "false_exclusions": false_exclusions,
        "repeated_with_evidence": repeated,
        "ownership_errors": ownership_errors,
        "returned_matches": matches,
        "own_uses": own_uses,
        "borrowed_uses": borrowed_uses,
        "same_entrance_score_min": min(same_scores, default=None),
        "cross_entrance_score_max": max(cross_scores, default=None),
    }


def freeze():
    root = Path(__file__).resolve().parents[2]
    files = [
        *sorted((root / "_internal/maze").glob("*.py")),
        root / "_internal/maze/neural.ts",
        root / "fly_brain.py",
        root / "memory.py",
        root / "pipeline.py",
        root / "uv.lock",
        *sorted((root / "_internal/brain").glob("*.ts")),
        *sorted((root / "_internal/brain/data").glob("*.gz")),
    ]
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }


def evaluate(development=True, controls=True):
    seeds = list(range(300, 310) if development else range(40000, 40020))
    world = WorkshopWorld()
    report = {
        "seeds": seeds,
        "world": world.id,
        "protocol": world.protocol,
        "deadline_seconds": DEADLINE,
        "source": freeze(),
        "rows": [],
        "failures": [],
    }
    start = time.time()
    with Kernel() as kernel:
        for seed in seeds:
            results = trials(kernel, world, seed, controls and seed == seeds[0])
            truth = audit(results, world)
            errors = [
                field
                for field in (
                    "false_records",
                    "wrong_matches",
                    "false_exclusions",
                    "ownership_errors",
                )
                if truth[field]
            ]
            if any(
                r["run"] not in {"reverse_choice"}
                for r in truth["repeated_with_evidence"]
            ):
                errors.append("Repeated adverse entry despite applied evidence")
            for name in ("none", "personal", "shared", "private_b"):
                summary = results[name]["summary"]
                if (
                    summary["collisions"]
                    or summary["longest_stall_s"] > 1
                    or summary["no_decision"]
                ):
                    errors.append(f"{name}: collision, stall, or no decision")
            if (
                "mute_choice" in results
                and not results["mute_choice"]["summary"]["no_decision"]
            ):
                errors.append("Muted decision failed to abstain")
            row = {
                "seed": seed,
                "runs": {n: compact(r) for n, r in results.items()},
                "audit": truth,
                "errors": errors,
            }
            report["rows"].append(row)
            report["failures"].extend(f"{seed}: {e}" for e in errors)
            print(
                json.dumps(
                    {
                        "seed": seed,
                        "errors": errors,
                        "metrics": {n: r["summary"] for n, r in results.items()},
                    }
                ),
                flush=True,
            )
    report["passed"] = not report["failures"]
    report["wall_seconds"] = time.time() - start
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--held-out", action="store_true")
    parser.add_argument("--no-controls", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(development=not args.held_out, controls=not args.no_controls)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k not in {"rows", "source"}}))
    raise SystemExit(0 if result["passed"] else 1)
