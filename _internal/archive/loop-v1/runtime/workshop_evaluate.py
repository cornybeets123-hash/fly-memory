"""Audit ownership, observed outcomes, and paired movement on declared seeds."""

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

from .kernel import Kernel
from .simulation import compact, run
from .workshop_world import WorkshopWorld

# Evaluation labels never enter the controller, encoder, or retrieval request.
OUTCOMES = {(0, "west"): "returned", (0, "east"): "open", (0, "south"): "returned"}


def place(world, frame, view):
    x, y = frame["x"], frame["y"]
    cx, cy = world.junction_centers[0]
    if abs(x - cx) > 41 or abs(y - cy) > 41:
        raise ValueError("A query occurred outside its observed junction")
    angle = frame["heading"] + view["bearing"]
    dx, dy = math.cos(angle), math.sin(angle)
    crossed = [
        ((border - position) / velocity, label)
        for label, border, position, velocity in (
            ("west", cx - 40, x, dx),
            ("east", cx + 40, x, dx),
            ("north", cy - 40, y, dy),
            ("south", cy + 40, y, dy),
        )
        if abs(velocity) > 1e-9 and (border - position) / velocity > 1e-6
    ]
    identity = 0, min(crossed)[1]
    if identity not in OUTCOMES:
        raise ValueError("A view points toward the closed wall")
    return identity


def trials(kernel, world, seed, controls=True):
    common = {"seed": seed, "duration": 45, "trace": True}
    none = run(kernel, world, **common)
    personal = run(kernel, world, mode="personal", **common)
    history = personal["episodes"]
    shared = run(kernel, world, mode="shared", history=history, **common)
    private = run(kernel, world, mode="personal", owner="B", history=history, **common)
    results = {
        "none": none,
        "personal": personal,
        "shared": shared,
        "private_b": private,
    }
    if controls:
        for control in ("mute", "reverse"):
            results[control] = run(
                kernel, world, mode="shared", history=history, control=control, **common
            )
    return results


def audit(results, world):
    atlas, false_records = {}, []
    for name, result in results.items():
        frames = {f["ms"]: f for f in result["frames"]}
        decisions = {d["time"]: d for d in result["decisions"]}
        for episode in result["episodes"]:
            p = episode.point.payload
            event = next(
                e
                for e in result["events"]
                if e["kind"] == "observed"
                and e["observed_at_ms"] == p["observed_at_ms"]
            )
            capture = p["captured_at_ms"] - (p["observed_at_ms"] - event["time"])
            decision = decisions[capture]
            view = decision["views"][decision["choice"]]
            assert view["snapshot"] == p["snapshot"]
            identity = place(world, frames[capture], view)
            atlas[episode.point.id] = identity
            if p["outcome"] != OUTCOMES[identity]:
                false_records.append({"run": name, "place": identity, "payload": p})
    wrong_matches, false_exclusions = [], []
    for name, result in results.items():
        frames = {f["ms"]: f for f in result["frames"]}
        for decision in result["decisions"]:
            for view in decision["views"]:
                current = place(world, frames[decision["time"]], view)
                if view["applied"] and OUTCOMES[current] == "open":
                    false_exclusions.append({"run": name, "time": decision["time"]})
                for hit in view["hits"]:
                    if atlas.get(hit["id"]) != current:
                        wrong_matches.append(
                            {
                                "run": name,
                                "time": decision["time"],
                                "score": hit["score"],
                            }
                        )
    a, b = results["personal"], results["shared"]
    own = [
        (d, v["selected"]) for d in a["decisions"] for v in d["views"] if v["applied"]
    ]
    borrowed = [
        (d, v["selected"]) for d in b["decisions"] for v in d["views"] if v["applied"]
    ]
    own_ids = {h["id"] for _, h in own}
    observed = {e.point.id: e.point.payload for e in a["episodes"]}
    ownership = bool(own and borrowed)
    ownership &= all(
        h["id"] in observed
        and h["payload"]["source_fly"] == "A"
        and h["payload"]["observed_at_ms"] < d["time"] + 100
        for d, h in own
    )
    ownership &= all(
        h["id"] in own_ids and h["payload"]["source_fly"] == "A" for _, h in borrowed
    )
    ownership &= not any(v["hits"] for v in a["decisions"][0]["views"])
    first_b = borrowed[0][0]["time"] if borrowed else 0
    ownership &= not any(
        e["kind"] == "observed" and e["time"] <= first_b for e in b["events"]
    )
    private_hits = [
        v["selected"]
        for d in results["private_b"]["decisions"]
        for v in d["views"]
        if v["applied"]
    ]
    ownership &= bool(private_hits) and all(
        h["payload"]["source_fly"] == "B" for h in private_hits
    )
    return {
        "false_records": false_records,
        "wrong_matches": wrong_matches,
        "false_exclusions": false_exclusions,
        "ownership_passed": bool(ownership),
        "transferred_ids": sorted(own_ids & {h["id"] for _, h in borrowed}),
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


def evaluate(development=True, controls=True, scenery=True, swapped=False):
    seeds = list(range(300, 310) if development else range(32000, 32010))
    world = WorkshopWorld(scenery=scenery, swapped=swapped)
    report = {
        "seeds": seeds,
        "world": world.id,
        "protocol": world.protocol,
        "deadline_seconds": 45,
        "source": freeze(),
        "rows": [],
        "failures": [],
    }
    start = time.time()
    with Kernel() as kernel:
        for seed in seeds:
            results = trials(kernel, world, seed, controls and seed == seeds[0])
            truth = audit(results, world)
            errors = []
            for field in ("false_records", "wrong_matches", "false_exclusions"):
                if truth[field]:
                    errors.append(field)
            if not truth["ownership_passed"]:
                errors.append("Experience ownership or transfer failed")
            for name, returns, exit_expected in (
                ("none", 2, False),
                ("personal", 1, True),
                ("shared", 0, True),
                ("private_b", 1, True),
            ):
                summary = results[name]["summary"]
                if summary["exit"] != exit_expected or summary["returns"] < returns:
                    errors.append(f"{name}: exit or return failure")
                if summary["collisions"] or summary["longest_stall_s"] > 1:
                    errors.append(f"{name}: collision or stall")
            if (
                not results["shared"]["summary"]["time_ms"]
                < results["personal"]["summary"]["time_ms"]
                < 45000
            ):
                errors.append("Sharing did not save the exploration circuit")
            for name in ("mute", "reverse"):
                if name in results and results[name]["summary"]["exit"]:
                    errors.append(f"{name}: steering ablation failed")
            report["rows"].append(
                {
                    "seed": seed,
                    "runs": {n: compact(r) for n, r in results.items()},
                    "audit": truth,
                    "errors": errors,
                }
            )
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
