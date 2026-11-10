"""The pre-UI integrated junction gate. Run development before the held-out seeds."""

import argparse
import hashlib
import json
import math
import time
from functools import partial
from pathlib import Path

from . import memory
from .kernel import Kernel
from .simulation import compact, run
from .world import World


def observed(result):
    return [e for e in result["events"] if e["kind"] == "observed"]


def check_association(result):
    decisions = result["decisions"]
    for event in observed(result):
        assert event["captured_at_ms"] < event["observed_at_ms"]
        matching = [
            d
            for d in decisions
            if d["views"][d["choice"]]["snapshot"] == event["snapshot"]
        ]
        assert matching, "A completed record lost its selected entrance snapshot"


def entrance(frame, view):
    """Evaluation truth only. These branch labels never reach runtime inputs."""
    x, y, heading = frame["x"], frame["y"], frame["heading"] + view["bearing"]
    dx, dy = math.cos(heading), math.sin(heading)
    crossings = []
    for label, border, position, velocity in (
        ("west", 220, x, dx),
        ("east_wall", 300, x, dx),
        ("north", -40, y, dy),
        ("south", 40, y, dy),
    ):
        if abs(velocity) > 1e-9 and (border - position) / velocity > 1e-6:
            crossings.append(((border - position) / velocity, label))
    assert crossings, "Cannot resolve evaluated entrance"
    label = min(crossings)[1]
    assert label != "east_wall", "A chosen view points into the closed wall"
    return label


def audit_records(results):
    atlas = {}
    frames_by_run = {}
    for name, result in results.items():
        frames = {f["ms"]: f for f in result["frames"]}
        frames_by_run[name] = frames
        for decision in result["decisions"]:
            for view in decision["views"]:
                atlas[view["snapshot"]] = entrance(frames[decision["time"]], view)
    false_records, wrong_matches, matches = [], [], 0
    for name, result in results.items():
        for record in observed(result):
            label = atlas[record["snapshot"]]
            expected = "open" if label == "south" else "dead_end"
            if record["outcome"] != expected:
                false_records.append(
                    {"run": name, "record": record, "expected": expected}
                )
        for decision in result["decisions"]:
            for view in decision["views"]:
                for hit in view["hits"]:
                    matches += 1
                    source = atlas[hit["payload"]["snapshot"]]
                    current = entrance(frames_by_run[name][decision["time"]], view)
                    if source != current:
                        wrong_matches.append(
                            {
                                "run": name,
                                "time": decision["time"],
                                "source": source,
                                "current": current,
                            }
                        )
    return {
        "false_records": false_records,
        "wrong_matches": wrong_matches,
        "returned_matches": matches,
    }


def evaluate(development=False):
    seeds = list(range(300, 310) if development else range(10000, 10010))
    started = time.time()
    report = {
        "stage": "development" if development else "held_out",
        "seeds": seeds,
        "protocol": memory.PROTOCOL,
        "threshold": memory.MIN_SCORE,
        "margin": memory.MARGIN,
        "rows": [],
        "failures": [],
    }
    with Kernel() as kernel:
        report["brain"] = kernel.info
        trial = partial(run, trace=True)
        for seed in seeds:
            donor = trial(kernel, World(), seed=seed, duration=25)
            history = donor["episodes"]
            personal = trial(
                kernel,
                World(),
                seed=seed,
                mode="personal",
                history=history,
                pose_variant=1,
            )
            recipient = trial(
                kernel,
                World(),
                seed=seed,
                mode="shared",
                history=[*history, *personal["episodes"]],
                pose_variant=1,
            )
            ghost = trial(
                kernel,
                World(),
                seed=seed,
                mode="personal",
                history=history,
                pose_variant=1,
                control="no_memory",
            )
            muted = trial(
                kernel,
                World(),
                seed=seed,
                mode="personal",
                history=history,
                pose_variant=1,
                control="mute",
                duration=8,
            )
            reversed_readout = trial(
                kernel,
                World(),
                seed=seed,
                mode="personal",
                history=history,
                pose_variant=1,
                control="reverse",
                duration=15,
            )
            results = {
                "donor": donor,
                "personal": personal,
                "recipient": recipient,
                "ghost": ghost,
                "muted": muted,
                "reversed": reversed_readout,
            }
            row = {
                "seed": seed,
                "runs": {name: compact(r) for name, r in results.items()},
            }
            report["rows"].append(row)
            errors = []
            row["truth_audit"] = audit_records(results)
            if row["truth_audit"]["false_records"]:
                errors.append("False stored outcome in the geometry audit")
            if row["truth_audit"]["wrong_matches"]:
                errors.append("Wrong accepted match in the geometry audit")
            for name, result in results.items():
                try:
                    check_association(result)
                except AssertionError as error:
                    errors.append(f"{name}: {error}")
            for name in ("donor", "personal", "recipient", "ghost"):
                summary = results[name]["summary"]
                if (
                    summary["collisions"]
                    or summary["longest_stall_s"] > 1
                    or summary["minimum_wall_clearance"] <= 5
                ):
                    errors.append(f"{name}: controller clearance or stall failure")
            if len([e for e in observed(donor) if e["outcome"] == "dead_end"]) != 1:
                errors.append("Donor did not publish exactly one witnessed dead end")
            for name, result in (("personal", personal), ("recipient", recipient)):
                summary = result["summary"]
                if not summary["exit"] or summary["detours"] != 0:
                    errors.append(f"{name}: exit or detour failure")
                if summary["collisions"] or summary["longest_stall_s"] > 3:
                    errors.append(f"{name}: collision or stall failure")
                if not result["decisions"]:
                    errors.append(f"{name}: no entry query")
                    continue
                first = result["decisions"][0]
                harmful = [v for v in first["views"] if v["selected"]]
                # The evaluated first junction has two visible openings: north is the witnessed trap.
                if len(harmful) != 1 or harmful[0]["bearing"] >= 0:
                    errors.append(f"{name}: wrong accepted match or false exclusion")
                if first["views"][first["choice"]]["applied"]:
                    errors.append(f"{name}: selected an excluded opening")
                if not observed(result) or observed(result)[-1]["outcome"] != "open":
                    errors.append(f"{name}: exit did not complete open evidence")
            if ghost["summary"]["detours"] < 1:
                errors.append("Matched no-memory ghost did not enter the known trap")
            if ghost["summary"]["path"] <= personal["summary"]["path"]:
                errors.append("Memory did not reduce traveled distance")
            if not any(
                v["selected"] and not v["applied"]
                for d in ghost["decisions"]
                for v in d["views"]
            ):
                errors.append(
                    "Ghost did not preserve selected evidence with the consumer disabled"
                )
            if muted["summary"]["exit"] or muted["summary"]["motor_spikes"] <= 0:
                errors.append(
                    "Disconnected readout did not preserve spikes and break the route"
                )
            if any(f["applied_yaw"] != 0 for f in muted["frames"]):
                errors.append("Disconnected readout still changed heading")
            row["errors"] = errors
            report["failures"].extend(f"{seed}: {error}" for error in errors)
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
    report["wall_seconds"] = time.time() - started
    report["runtime_hashes"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in Path(__file__).parent.glob("*.py")
    }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.development)
    args.output.write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"rows", "brain", "runtime_hashes"}
            }
        )
    )
    raise SystemExit(0 if result["passed"] else 1)
