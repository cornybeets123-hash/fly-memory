"""Evaluate fixed policies on declared worlds, including failed controls."""

import json
from pathlib import Path

from .experiment import Config, compare


def evaluate(path, seeds=range(10000, 10020), controls=True):
    output = {
        "seeds": list(seeds),
        "results": [],
        "controls": [],
        "protocol": {
            "sensor_noise": "fresh per-contact noise keyed by seed, fly, object, and step",
            "stage_seed": 2000,
            "control_seeds": list(seeds)[:5],
            "comparison": "shared external schedule and matched neural seed per fly/object",
        },
    }
    for seed in output["seeds"]:
        for run in compare(Config(seed=seed), record=False):
            row = {
                "seed": seed,
                "mode": run["mode"],
                "summary": run["summary"],
                "world_hash": run["world_hash"],
                "wall_seconds": run["wall_seconds"],
            }
            output["results"].append(row)
            print(
                seed,
                run["mode"],
                run["summary"]["fed"],
                run["summary"]["harmful_meals"],
                flush=True,
            )
    if controls:
        for control in ("shuffled", "no_cue", "exact"):
            for seed in output["seeds"][:5]:
                for run in compare(Config(seed=seed), record=False, control=control):
                    output["controls"].append(
                        {
                            "seed": seed,
                            "mode": run["mode"],
                            "control": control,
                            "summary": run["summary"],
                        }
                    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n")
    return output


if __name__ == "__main__":
    evaluate("artifacts/evaluation.json")
