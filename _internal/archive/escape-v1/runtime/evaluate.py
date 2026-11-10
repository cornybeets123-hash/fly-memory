"""Evaluate the declared schedule, held-out seeds, and causal controls."""

import json
from dataclasses import asdict
from statistics import mean

from .package import computation_hash
from .scene import ROOT, Config, simulate


def aggregate(rows):
    return {
        key: round(mean(row["summary"][key] for row in rows), 3)
        for key in rows[0]["summary"]
    }


def evaluate():
    source_hash = computation_hash()
    protocol = json.loads((ROOT / "_maintainer/evaluation-protocol.json").read_text())
    results = {mode: [] for mode in protocol["modes"]}
    controls = {control: [] for control in protocol["controls"]}
    rows, matched, clear = [], True, True
    for seed in protocol["seeds"]:
        paired = {
            mode: simulate(Config(seed=seed), mode, True, trace=False)
            for mode in protocol["modes"]
        }
        reference = {
            (e["cycle"], e["fly"]): e["neural"]["natural_input_hash"]
            for e in paired["none"]["events"]
        }
        for mode, result in paired.items():
            results[mode].append(result)
            matched &= all(
                reference[e["cycle"], e["fly"]] == e["neural"]["natural_input_hash"]
                for e in result["events"]
            )
            clear &= all(
                e["escaped"] for e in paired["none"]["events"] if e["cycle"] == 3
            )
            rows.append(
                {
                    "seed": seed,
                    "mode": mode,
                    "world_hash": result["world_hash"],
                    "summary": result["summary"],
                }
            )
        print(f"Evaluated seed {seed}", flush=True)
    for seed in protocol["control_seeds"]:
        for control in protocol["controls"]:
            controls[control].append(
                simulate(Config(seed=seed), "shared", True, control, trace=False)
            )
        print(f"Checked controls for seed {seed}", flush=True)
    sensitivity = []
    for clearance in protocol["clearance_sensitivity_ms"]:
        for mode in protocol["modes"]:
            cfg = Config(seed=10000, clearance_ms=clearance)
            result = simulate(cfg, mode, True, trace=False)
            sensitivity.append(
                {"config": asdict(cfg), "mode": mode, "summary": result["summary"]}
            )
    means = {mode: aggregate(values) for mode, values in results.items()}
    checks = {
        "shared_harm_below_personal_below_none": means["shared"]["hits"]
        < means["personal"]["hits"]
        < means["none"]["hits"],
        "safe_feeding_retained_pct_min": means["shared"]["safe_feeding_retained_pct"]
        >= 95,
        "shared_false_jump_rate_max": means["shared"]["false_jumps"] / 18 <= 0.05,
        "natural_input_hashes_match": matched,
        "baseline_clear_view_escapes": clear,
        "removing_safe_evidence_causes_false_escapes": aggregate(
            controls["remove_safe"]
        )["false_jumps"]
        > 0,
        "always_escape_loses_safe_feeding": aggregate(controls["always_escape"])[
            "safe_feeding_retained_pct"
        ]
        < means["shared"]["safe_feeding_retained_pct"],
        "muted_replay_removes_early_action": all(
            e["action_ms"] is None or e["action_ms"] > 100
            for r in controls["no_replay"]
            for e in r["events"]
        ),
        "muted_motor_prevents_all_escape": all(
            e["action_ms"] is None for r in controls["no_motor"] for e in r["events"]
        ),
    }
    output = {
        "computation_hash": source_hash,
        "protocol": protocol,
        "means": means,
        "controls": {k: aggregate(v) for k, v in controls.items()},
        "checks": checks,
        "rows": rows,
        "sensitivity": sensitivity,
        "scope": "Measured model/task results. The cue encoder, visibility, and refuge movement are engineered. The v783 Float32 runtime has not been established as Brian2-identical.",
    }
    if computation_hash() != source_hash:
        raise RuntimeError(
            "The implementation changed during evaluation. Run the final evaluation again."
        )
    path = ROOT / "_internal/escape/data/evaluation.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    target = ROOT / "artifacts/escape-evaluation.json"
    target.write_text(path.read_text())
    print(
        json.dumps(
            {"means": means, "controls": output["controls"], "checks": checks}, indent=2
        )
    )
    if not all(checks.values()):
        raise RuntimeError(
            "A declared evaluation gate failed. Inspect the saved evaluation."
        )
    return output
