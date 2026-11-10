"""An observed-experience loop with actual neural readouts and isolated Edge shards."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from time import perf_counter
from uuid import uuid4

import numpy as np

from workshop.brain import RecordedBrain
from workshop.memory import ExperienceMemory
from workshop.senses import OdorSpace


@dataclass(frozen=True)
class Config:
    seed: int = 2000
    mode: str = "balanced"
    flies: int = 16
    encounters: int = 40
    threshold: float = 0.60
    top_k: int = 1
    representation: str = "centered"
    noise: float = 0.015
    marker: float = 0.30
    margin: float = 0.0

    def __post_init__(self):
        if self.mode not in {"none", "exact", "harm", "balanced", "shuffled"}:
            raise ValueError("Unknown memory policy.")
        if self.representation not in {"raw", "centered"}:
            raise ValueError("Unknown vector representation.")
        if (
            not 0 <= self.seed <= 1_000_000
            or not 1 <= self.flies <= 16
            or not 12 <= self.encounters <= 80
        ):
            raise ValueError(
                "Seed, fly count, or encounter count is outside the workshop limits."
            )
        if (
            not 0 <= self.threshold <= 1
            or not 1 <= self.top_k <= 10
            or not 0 <= self.margin <= 1
        ):
            raise ValueError("Invalid retrieval settings.")
        if not 0 <= self.noise <= 0.2 or not 0 <= self.marker <= 0.5:
            raise ValueError("Invalid sensory settings.")


def world(cfg, space, fly):
    """Potential contacts are fixed before action, including independent observation noise."""
    rng = np.random.default_rng(cfg.seed + fly)
    positions = np.random.default_rng(np.random.SeedSequence([cfg.seed, fly, 91]))
    result = []
    for tick in range(cfg.encounters):
        family = str(rng.choice(list(space.recipes)))
        harmful = bool(rng.random() < 0.35)
        response = space.sample(
            family, harmful, rng, noise=cfg.noise, marker=cfg.marker
        )
        vector = space.encode(response, cfg.representation)
        result.append(
            {
                "step": tick,
                "family": family,
                "harmful": harmful,
                "response": response,
                "vector": vector,
                "map": space.project(vector),
                "position": positions.uniform(0.15, 0.85, 2).tolist(),
            }
        )
    return result


def simulate(cfg, brain, space, *, student=False, record=True):
    histories, memories, curves = [], [], []
    for fly in range(cfg.flies):
        history, own_points = [], []
        safe = poison = refused = seen_harm = 0
        with ExperienceMemory(space.dim, student=student) as memory:
            for contact in world(cfg, space, fly):
                tick = contact["step"]
                recall = memory.recall(
                    contact["vector"],
                    cfg.threshold,
                    cfg.top_k,
                    mode=cfg.mode,
                    margin=cfg.margin,
                )
                neural = brain.response(recall["bitter_hz"], brain.seed_for(fly, tick))
                feeding = neural["feeding"]
                # Only this post-action handler reads the hidden environmental outcome.
                harmful = contact["harmful"]
                seen_harm += harmful
                safe += feeding and not harmful
                poison += feeding and harmful
                refused += not feeding and not harmful
                observed = (-1 if harmful else 1) if feeding else None
                written = None
                if feeding and cfg.mode != "none" and (cfg.mode != "harm" or harmful):
                    point_id = tick + 1
                    # Label corruption is an explicit negative control, independent of truth.
                    reported = observed
                    if cfg.mode == "shuffled":
                        reported = int(
                            np.random.default_rng(
                                np.random.SeedSequence([cfg.seed, fly, tick, 88])
                            ).choice([-1, 1])
                        )
                    memory.remember(point_id, contact["vector"], reported, tick)
                    written = {
                        **memory.points[point_id],
                        "fly": fly,
                        "map": contact["map"],
                        "observed_outcome": observed,
                    }
                    own_points.append(written)
                # Sickness is survivable twice. The third harmful meal ends the life.
                # At least 12 safe meals also matter: freezing cannot win.
                alive = poison < 3
                event = {
                    **contact,
                    "fly": fly,
                    "recall": recall,
                    "neural": neural,
                    "observed_outcome": observed,
                    "write": written,
                    "safe_meals": int(safe),
                    "poison_meals": int(poison),
                    "safe_refusals": int(refused),
                    "hazards_seen": int(seen_harm),
                    "health": max(0, 100 - 34 * poison),
                    "alive": bool(alive),
                    "memory_count": len(memory.points),
                }
                history.append(event)
                if not alive:
                    break
        histories.append(history)
        memories.append(own_points)
    for tick in range(cfg.encounters):
        rows = [h[min(tick, len(h) - 1)] for h in histories]
        curves.append(
            {
                "step": tick,
                "alive": sum(e["alive"] for e in rows),
                "safe_meals": sum(e["safe_meals"] for e in rows),
                "poison_meals": sum(e["poison_meals"] for e in rows),
                "memories": sum(e["memory_count"] for e in rows),
                "recalls": sum(
                    bool(e["recall"]["hits"])
                    for h in histories
                    for e in h
                    if e["step"] <= tick
                ),
            }
        )
    last = [h[-1] for h in histories]
    required = int(np.ceil(cfg.encounters * 0.30))
    summary = {
        "stimulus_counts": {
            str(dose): sum(
                e["recall"]["bitter_hz"] == dose for h in histories for e in h
            )
            for dose in (0, 50, 100, 150, 200)
        },
        "recalled_but_fed": sum(
            e["recall"]["bitter_hz"] > 0 and e["neural"]["feeding"]
            for h in histories
            for e in h
        ),
        "total": cfg.flies,
        "alive": sum(e["alive"] for e in last),
        "thriving": sum(e["alive"] and e["safe_meals"] >= required for e in last),
        "minimum_safe_meals": required,
        "safe_meals": sum(e["safe_meals"] for e in last),
        "poison_meals": sum(e["poison_meals"] for e in last),
        "safe_refusals": sum(e["safe_refusals"] for e in last),
        "memories": sum(len(m) for m in memories),
        "early_poison_meals": sum(
            e["observed_outcome"] == -1
            for h in histories
            for e in h
            if e["step"] < cfg.encounters // 2
        ),
        "late_poison_meals": sum(
            e["observed_outcome"] == -1
            for h in histories
            for e in h
            if e["step"] >= cfg.encounters // 2
        ),
    }
    return {
        "config": asdict(cfg),
        "summary": summary,
        "curves": curves,
        "histories": histories if record else [],
        "memories": memories if record else [],
    }


def run(cfg, *, student=False, record=True, brain=None, space=None, baseline=True):
    start = perf_counter()
    brain, space = brain or RecordedBrain(), space or OdorSpace()
    result = simulate(cfg, brain, space, student=student, record=record)
    result["id"] = uuid4().hex
    result["wall_seconds"] = round(perf_counter() - start, 3)
    if baseline and cfg.mode != "none":
        control = simulate(replace(cfg, mode="none"), brain, space, record=False)
        result["baseline"] = {
            "summary": control["summary"],
            "curves": control["curves"],
        }
    else:
        result["baseline"] = None
    return result


def intervention(result, fly, tick, point_id, brain, *, live=None, student=False):
    """Delete and restore a real point in the exact pre-contact personal history."""
    cfg = Config(**result["config"])
    if not 0 <= fly < cfg.flies:
        raise ValueError("Unknown fly.")
    event = next((e for e in result["histories"][fly] if e["step"] == tick), None)
    if event is None:
        raise ValueError("This fly did not reach this encounter.")
    points = [p for p in result["memories"][fly] if p["tick"] < tick]
    with ExperienceMemory(len(event["vector"]), student=student) as memory:
        for point in points:
            memory.restore(point)

        def evaluate():
            recall = memory.recall(
                event["vector"],
                cfg.threshold,
                cfg.top_k,
                mode=cfg.mode,
                margin=cfg.margin,
            )
            neural = (live or brain).response(
                recall["bitter_hz"], event["neural"]["seed"]
            )
            if live and not neural.get("matches_recording", False):
                raise RuntimeError(
                    "Live spikes differ from the recording. Compare simulator versions with "
                    "brain-bank.json provenance. Use the recorded intervention while investigating."
                )
            return {"recall": recall, "neural": neural}

        before = evaluate()
        original = event["neural"]
        if (
            before["recall"] != event["recall"]
            or before["neural"]["trial_id"] != original["trial_id"]
            or before["neural"]["readouts_hz"] != original["readouts_hz"]
        ):
            raise ValueError(
                "Reconstructed encounter differs from the original. Run the experiment again."
            )
        removed = memory.delete(point_id)
        try:
            after = evaluate()
        finally:
            memory.restore(removed)
        restored = evaluate()
    return {
        "fly": fly,
        "step": tick,
        "point_id": point_id,
        "before": before,
        "after": after,
        "restored": restored,
        "changed_decision": before["neural"]["feeding"] != after["neural"]["feeding"],
        "restored_decision": before["neural"]["feeding"]
        == restored["neural"]["feeding"],
        "source": "live" if live else "recorded",
    }
