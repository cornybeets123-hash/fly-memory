"""Workshop setup, experiments, and live neural verification."""

import argparse
import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from pathlib import Path

from workshop.brain import ROOT, RecordedBrain
from workshop.simulation import Config, run


def setup_brain():
    bank = RecordedBrain()
    directory = ROOT / "brain"
    if not directory.exists():
        subprocess.run(
            [
                "git",
                "clone",
                "https://github.com/philshiu/Drosophila_brain_model",
                str(directory),
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(directory),
                "checkout",
                bank.data["provenance"]["upstream_sha"],
            ],
            check=True,
        )
    for item in bank.data["provenance"]["files"]:
        if item["path"].startswith("brain/"):
            path = ROOT / item["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                raise SystemExit(
                    f"Source checksum differs: {path}. Existing brain files were preserved."
                )
    print("Pinned brain source and connectome checksums verified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        choices=("evaluate", "setup-brain", "verify", "sessions"),
        default="evaluate",
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=[2000, 3000])
    parser.add_argument(
        "--modes", nargs="+", default=["none", "exact", "harm", "balanced", "shuffled"]
    )
    parser.add_argument("--top-k", type=int, default=1)
    parser.add_argument("--threshold", type=float, default=0.60)
    parser.add_argument(
        "--representation", choices=("raw", "centered"), default="centered"
    )
    parser.add_argument("--noise", type=float, default=0.015)
    parser.add_argument("--marker", type=float, default=0.30)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--memory-path", type=Path)
    parser.add_argument("--trial", default="p9-sugar-bitter-200-seed-100")
    args = parser.parse_args()
    args.output = args.output or Path("artifacts") / (
        "session-memory.json" if args.command == "sessions" else "evaluation.json"
    )
    if args.command == "sessions":
        from uuid import uuid4

        from workshop.sessions import session_probe

        path = args.memory_path or Path("state") / f"session-{uuid4().hex}"
        result = session_probe(path, student=os.getenv("WORKSHOP_EXERCISE") == "1")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return
    if args.command == "setup-brain":
        setup_brain()
        return
    if args.command == "verify":
        from workshop.brain import LiveBrain

        bank = RecordedBrain()
        trial = bank.trials[args.trial]
        result = LiveBrain(bank).response(
            int(trial["stimulation_hz"]["bitter"]), trial["seed"]
        )
        print(json.dumps(result, indent=2))
        if not result["matches_recording"]:
            raise SystemExit("Live response differs from its recording.")
        return
    results = []
    for seed in args.seeds:
        for mode in args.modes:
            cfg = Config(
                seed=seed,
                mode=mode,
                top_k=args.top_k,
                threshold=args.threshold,
                representation=args.representation,
                noise=args.noise,
                marker=args.marker,
            )
            result = run(
                cfg,
                record=False,
                baseline=False,
                student=os.getenv("WORKSHOP_EXERCISE") == "1",
            )
            results.append(
                {
                    "config": asdict(cfg),
                    "summary": result["summary"],
                    "wall_seconds": result["wall_seconds"],
                }
            )
            print(
                f"seed={seed} {mode:8} thriving={result['summary']['thriving']}/{cfg.flies} safe={result['summary']['safe_meals']} harmful={result['summary']['poison_meals']}",
                flush=True,
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "neural_source": "recorded",
                "engine": "Qdrant Edge 0.8.0",
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
