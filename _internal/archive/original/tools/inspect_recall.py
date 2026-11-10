"""Compare retrieval policies in the same observed personal history."""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workshop.brain import RecordedBrain
from workshop.memory import ExperienceMemory
from workshop.simulation import Config, run

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--seed", type=int, default=3000)
parser.add_argument("--fly", type=int, default=2, help="One-based fly number")
parser.add_argument("--encounter", type=int, default=22, help="One-based encounter")
args = parser.parse_args()
student = os.getenv("WORKSHOP_EXERCISE") == "1"
cfg = Config(seed=args.seed)
if not 1 <= args.fly <= cfg.flies or not 1 <= args.encounter <= cfg.encounters:
    parser.error("Choose fly 1 through 16 and encounter 1 through 40.")
result = run(cfg, baseline=False, student=student)
history = result["histories"][args.fly - 1]
if len(history) < args.encounter:
    parser.error("This fly did not survive to that encounter.")
event = history[args.encounter - 1]
brain = RecordedBrain()
rows = {}
with ExperienceMemory(24, student=student) as memory:
    for point in result["memories"][args.fly - 1]:
        if point["tick"] < event["step"]:
            memory.restore(point)
    for policy in ("balanced", "harm"):
        recall = memory.recall(event["vector"], cfg.threshold, cfg.top_k, mode=policy)
        rows[policy] = {
            "recall": recall,
            "neural": brain.response(recall["bitter_hz"], event["neural"]["seed"]),
        }
print(
    json.dumps(
        {
            "seed": args.seed,
            "fly": args.fly,
            "encounter": args.encounter,
            "policies": rows,
        },
        indent=2,
    )
)
