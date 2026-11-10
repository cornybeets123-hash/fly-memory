"""A spatial experiment with observed memories and fixed external events."""

from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from types import SimpleNamespace

import numpy as np
from qdrant_edge import (
    Distance,
    EdgeConfig,
    EdgeShard,
    EdgeVectorParams,
    Point,
    UpdateOperation,
)

from fly_brain import FlyBrain

from . import answers
from .neural_display import spikes
from .senses import OdorSpace
from .story import chapters

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Config:
    seed: int = 2000
    flies: int = 12
    steps: int = 600
    wave: int = 300
    epoch_steps: int = 100
    width: float = 64.0
    height: float = 38.0
    objects: int = 12
    speed: float = 0.48
    sense_radius: float = 18.0
    contact_radius: float = 1.65
    energy_start: float = 90.0
    energy_cost: float = 0.24
    safe_energy: float = 24.0
    harmful_energy: float = 18.0
    injuries_to_die: int = 3
    minimum_meals: int = 4
    sensor_noise: float = 0.018

    def __post_init__(self):
        if not 0 <= self.seed <= 1_000_000:
            raise ValueError("Choose a seed between zero and 1000000.")
        if not 1 <= self.flies <= 24 or not 100 <= self.steps <= 1200:
            raise ValueError(
                "This experiment supports one to 24 flies and 100 to 1200 steps."
            )


def load_code(reference=False):
    if reference:
        return answers, answers, "Completed code"

    def read(name):
        path = ROOT / f"{name}.py"
        module = SimpleNamespace(__name__=f"workshop_{name}", __file__=str(path))
        # Compile from source to avoid stale same-second bytecode during live coding.
        exec(compile(path.read_text(), str(path), "exec"), module.__dict__)  # noqa: S102
        return module

    return read("memory"), read("pipeline"), "Your code"


class World:
    """Precompute external events before any policy acts."""

    def __init__(self, cfg, control="normal"):
        self.cfg = cfg
        space = OdorSpace()
        self.space = space
        names = list(space.responses)
        library = np.stack(list(space.responses.values()))
        base = []
        for family in ("banana", "pear", "mixed"):
            weights = np.array([space.recipes[family].get(n, 0) for n in names])
            base.append(weights @ library)
        self.prototypes = base + [
            0.60 * base[0] + 0.40 * space.responses["acetophenone"],
            0.40 * base[1] + 0.60 * space.responses["ethanol"],
            0.35 * base[2] + 0.65 * space.responses["1-hexanol"],
        ]
        self.epochs = []
        epoch_count = (cfg.steps + cfg.epoch_steps - 1) // cfg.epoch_steps
        for epoch in range(epoch_count):
            rng = np.random.default_rng(np.random.SeedSequence([cfg.seed, 10, epoch]))
            phase = epoch * cfg.epoch_steps >= cfg.wave
            kinds = np.array([0, 1, 2, 0, 1, 2, 0, 1, 3, 4, 3, 5 if phase else 4])
            rng.shuffle(kinds)
            nodes = []
            for object_id, kind in enumerate(kinds):
                x = 8 + (object_id % 4) * 16 + rng.uniform(-3.0, 3.0)
                y = 7 + (object_id // 4) * 12 + rng.uniform(-2.0, 2.0)
                family = int(kind) % 3
                response = np.array(self.prototypes[int(kind)]).copy()
                if control == "no_cue":
                    response = np.array(base[family]).copy()
                response += rng.normal(0, 0.009, space.dim)
                nodes.append(
                    {
                        "id": epoch * cfg.objects + object_id,
                        "x": float(x),
                        "y": float(y),
                        "kind": int(kind),
                        "family": family,
                        "response": response.tolist(),
                    }
                )
            self.epochs.append(nodes)
        rng = np.random.default_rng(np.random.SeedSequence([cfg.seed, 11]))
        self.starts = rng.uniform(
            [4, 4], [cfg.width - 4, cfg.height - 4], (cfg.flies, 2)
        )
        self.headings = rng.uniform(-np.pi, np.pi, cfg.flies)
        self.wander = np.random.default_rng(
            np.random.SeedSequence([cfg.seed, 12])
        ).normal(0, 0.30, (cfg.steps, cfg.flies))
        self.labels = np.random.default_rng(
            np.random.SeedSequence([cfg.seed, 14])
        ).choice([-1, 1], (cfg.steps, cfg.flies))
        encoded = json.dumps(
            {"epochs": self.epochs, "starts": self.starts.tolist()}, sort_keys=True
        )
        self.fingerprint = hashlib.sha256(encoded.encode()).hexdigest()

    def scent(self, epoch, object_index, fly, tick):
        response = self.epochs[epoch][object_index]["response"]
        noise = np.random.default_rng(
            np.random.SeedSequence(
                [self.cfg.seed, 13, fly, self.epochs[epoch][object_index]["id"], tick]
            )
        ).normal(0, self.cfg.sensor_noise, self.space.dim)
        return self.space.encode(np.array(response) + noise)

    def neural_seed(self, fly, object_id, seeds):
        key = np.random.SeedSequence(
            [self.cfg.seed, 15, fly, object_id]
        ).generate_state(1)[0]
        return int(seeds[int(key) % len(seeds)])

    def public_nodes(self):
        # Spectator labels never enter scent(), retrieval, or the brain input.
        return [
            [
                {
                    **{k: n[k] for k in ("id", "x", "y", "family")},
                    "hazard": n["kind"] >= 3,
                    "variant": n["kind"],
                }
                for n in epoch
            ]
            for epoch in self.epochs
        ]


def _shard(stack, name, dim):
    directory = stack.enter_context(TemporaryDirectory(prefix=f"fly-{name}-"))
    shard = EdgeShard.create(
        directory,
        EdgeConfig(
            vectors={"odor": EdgeVectorParams(size=dim, distance=Distance.Cosine)},
            max_search_threads=1,
        ),
    )
    stack.callback(shard.close)
    return shard


def validate_hits(hits):
    for hit in hits:
        if not hasattr(hit, "score") or not isinstance(
            getattr(hit, "payload", None), dict
        ):
            raise ValueError("memory.recall: return Edge hits with with_payload=True.")
        if not {"outcome", "step", "source_fly"}.issubset(hit.payload):
            raise ValueError(
                "memory.recall: each payload needs outcome, step, and source_fly."
            )


def simulate(cfg, mode, *, reference=True, control="normal", record=True, world=None):
    if mode not in {"none", "personal", "shared"}:
        raise ValueError("Choose no memory, personal memory, or shared memory.")
    if control not in {"normal", "shuffled", "no_cue", "exact"}:
        raise ValueError("Unknown experiment control.")
    started = perf_counter()
    world = world or World(cfg, control)
    memory, pipeline, code_label = (
        (answers, answers, "Completed code" if reference else "Your code")
        if mode == "none"
        else load_code(reference)
    )
    brain = FlyBrain()
    f = cfg.flies
    positions = world.starts.copy()
    heading = world.headings.copy()
    energy = np.full(f, cfg.energy_start)
    alive = np.ones(f, dtype=bool)
    injury = np.zeros(f, dtype=int)
    safe = np.zeros(f, dtype=int)
    refusals = np.zeros(f, dtype=int)
    starvation = np.zeros(f, dtype=bool)
    cooldown = np.zeros((f, cfg.objects), dtype=int)
    targets = np.full(f, -1, dtype=int)
    actions = ["exploring"] * f
    events, frames, curves = [], [], []
    new_hazard_contacts = set()
    new_hazard_injuries = 0
    shared_warnings = 0
    warning_refusals_same_object = warning_refusals_different_object = 0
    observed_vectors, observed_objects = {}, {}
    with ExitStack() as stack:
        personal = (
            [_shard(stack, str(i), world.space.dim) for i in range(f)]
            if mode != "none"
            else [None] * f
        )
        shared = _shard(stack, "shared", world.space.dim) if mode == "shared" else None
        previous_epoch = -1
        for tick in range(cfg.steps):
            epoch = tick // cfg.epoch_steps
            nodes = world.epochs[epoch]
            if epoch != previous_epoch:
                targets[:] = -1
                cooldown[:] = 0
                previous_epoch = epoch
            pending = []
            for fly in range(f):
                if not alive[fly]:
                    continue
                energy[fly] -= cfg.energy_cost
                if energy[fly] <= 0:
                    alive[fly] = False
                    starvation[fly] = True
                    actions[fly] = "exhausted"
                    continue
                available = [
                    (
                        float(
                            np.hypot(
                                n["x"] - positions[fly, 0], n["y"] - positions[fly, 1]
                            )
                        ),
                        j,
                    )
                    for j, n in enumerate(nodes)
                    if cooldown[fly, j] <= tick
                ]
                nearest = min(available, default=(float("inf"), -1))
                target = nearest[1] if nearest[0] <= cfg.sense_radius else -1
                targets[fly] = target
                if target >= 0:
                    node = nodes[target]
                    wanted = np.arctan2(
                        node["y"] - positions[fly, 1], node["x"] - positions[fly, 0]
                    )
                    difference = (wanted - heading[fly] + np.pi) % (2 * np.pi) - np.pi
                    heading[fly] += np.clip(difference, -0.42, 0.42)
                    actions[fly] = "approaching"
                else:
                    heading[fly] += world.wander[tick, fly]
                    actions[fly] = "exploring"
                positions[fly] += cfg.speed * np.array(
                    [np.cos(heading[fly]), np.sin(heading[fly])]
                )
                for dimension, bound in ((0, cfg.width), (1, cfg.height)):
                    if (
                        positions[fly, dimension] < 2
                        or positions[fly, dimension] > bound - 2
                    ):
                        positions[fly, dimension] = np.clip(
                            positions[fly, dimension], 2, bound - 2
                        )
                        heading[fly] += np.pi / 2
                if target < 0:
                    continue
                node = nodes[target]
                if (
                    np.hypot(
                        node["x"] - positions[fly, 0], node["y"] - positions[fly, 1]
                    )
                    > cfg.contact_radius
                ):
                    continue
                vector = world.scent(epoch, target, fly, tick)
                hits = pipeline.retrieve(
                    memory, personal[fly], shared, vector, fly, mode
                )
                validate_hits(hits)
                if control == "exact":
                    hits = [
                        h
                        for h in hits
                        if np.array_equal(observed_vectors[h.id], vector)
                    ]
                warning = float(memory.decide(hits)) if mode != "none" else 0.0
                if not np.isfinite(warning) or not 0 <= warning <= 1:
                    raise ValueError(
                        "memory.decide must return a score between zero and one."
                    )
                neural = brain.respond(
                    warning, world.neural_seed(fly, node["id"], brain.recordings.seeds)
                )
                # The post-action observer alone reads the hidden meal outcome.
                harmful = node["kind"] >= 3
                outcome = None
                reported = None
                if neural["feeding"]:
                    outcome = -1 if harmful else 1
                    if harmful:
                        injury[fly] += 1
                        energy[fly] -= cfg.harmful_energy
                        actions[fly] = "hurt"
                    else:
                        safe[fly] += 1
                        energy[fly] = min(100.0, energy[fly] + cfg.safe_energy)
                        actions[fly] = "fed"
                    if mode != "none":
                        reported = (
                            int(world.labels[tick, fly])
                            if control == "shuffled"
                            else outcome
                        )
                        point = Point(
                            tick * f + fly + 1,
                            {"odor": vector},
                            {
                                "outcome": reported,
                                "step": tick,
                                "source_fly": fly,
                            },
                        )
                        pending.append((fly, point))
                        observed_vectors[point.id] = vector
                        observed_objects[point.id] = node["id"]
                    cooldown[fly, target] = tick + 30
                else:
                    refusals[fly] += not harmful
                    actions[fly] = "refused"
                    cooldown[fly, target] = tick + 65
                if node["kind"] == 5 and fly not in new_hazard_contacts:
                    new_hazard_contacts.add(fly)
                    new_hazard_injuries += bool(neural["feeding"])
                foreign = [h for h in hits if h.payload["source_fly"] != fly]
                personal_hits = [h for h in hits if h.payload["source_fly"] == fly]
                personal_warning = (
                    float(memory.decide(personal_hits)) if mode == "shared" else warning
                )
                personal_neural = brain.respond(personal_warning, neural["seed"])
                shared_changed_decision = (
                    bool(foreign)
                    and personal_neural["feeding"]
                    and not neural["feeding"]
                )
                shared_warnings += shared_changed_decision
                if hits and not neural["feeding"]:
                    strongest = max(hits, key=lambda h: h.score)
                    same_object = observed_objects[strongest.id] == node["id"]
                    warning_refusals_same_object += same_object
                    warning_refusals_different_object += not same_object
                if injury[fly] >= cfg.injuries_to_die or energy[fly] <= 0:
                    alive[fly] = False
                    # Energy lost to a poisoned meal is a poison death.
                    starvation[fly] = False
                    actions[fly] = "dead"
                heading[fly] += np.pi
                if record:
                    events.append(
                        {
                            "tick": tick,
                            "fly": fly,
                            "object": node["id"],
                            "position": positions[fly].round(3).tolist(),
                            "vector": vector,
                            "outcome": outcome,
                            "reported_outcome": reported,
                            "action": actions[fly],
                            "warning": warning,
                            "neural": neural,
                            "without_shared": personal_neural,
                            "shared_changed_decision": bool(shared_changed_decision),
                            "spectator_hazard": bool(harmful),
                            "hits": [
                                {"id": h.id, "score": float(h.score), **h.payload}
                                for h in hits
                            ],
                        }
                    )
            # Every query on this step sees only earlier observations.
            for fly, point in pending:
                pipeline.observe(memory, personal[fly], shared, point, mode)
            if record and (tick % 2 == 0 or tick == cfg.steps - 1):
                frames.append(
                    {
                        "tick": tick,
                        "flies": [
                            [
                                round(float(positions[i, 0]), 3),
                                round(float(positions[i, 1]), 3),
                                round(float(heading[i]), 3),
                                round(max(0, float(energy[i])), 1),
                                int(injury[i]),
                                bool(alive[i]),
                                int(safe[i]),
                                actions[i],
                            ]
                            for i in range(f)
                        ],
                    }
                )
            if tick % 10 == 0 or tick == cfg.steps - 1:
                curves.append(
                    {
                        "tick": tick,
                        "alive": int(alive.sum()),
                        "fed": int((alive & (safe >= cfg.minimum_meals)).sum()),
                        "safe": int(safe.sum()),
                        "harmful": int(injury.sum()),
                    }
                )
        summary = {
            "total": f,
            "alive": int(alive.sum()),
            "fed": int((alive & (safe >= cfg.minimum_meals)).sum()),
            "safe_meals": int(safe.sum()),
            "harmful_meals": int(injury.sum()),
            "safe_refusals": int(refusals.sum()),
            "starvation_deaths": int(starvation.sum()),
            "poison_deaths": int((~alive & ~starvation).sum()),
            "shared_warnings": int(shared_warnings),
            "warning_refusals_same_object": int(warning_refusals_same_object),
            "warning_refusals_different_object": int(warning_refusals_different_object),
            "new_hazard_first_contacts": len(new_hazard_contacts),
            "new_hazard_first_injuries": int(new_hazard_injuries),
        }
    result = {
        "mode": mode,
        "control": control,
        "config": asdict(cfg),
        "summary": summary,
        "world_hash": world.fingerprint,
        "nodes": world.public_nodes() if record else [],
        "frames": frames,
        "events": events,
        "curves": curves,
        "neural_trials": {
            key: spikes(
                key,
                brain.recordings.data["protocol"]["neuron_indices"]["sugar"][0],
                brain.recordings.data["protocol"]["neuron_indices"]["bitter"][0],
                brain.recordings.data["protocol"]["neuron_indices"]["MN9"][0],
            )
            for key in {e["neural"]["trial_id"] for e in events}
            | {brain.recordings.key(0, e["neural"]["seed"]) for e in events}
        }
        if record
        else {},
        "code": code_label,
        "neural_source": "recorded",
        "engine": "Qdrant Edge 0.8.0",
        "wall_seconds": round(perf_counter() - started, 3),
    }

    result["chapters"] = chapters(result) if record else []
    return result


def compare(cfg=None, *, reference=True, record=True, control="normal"):
    cfg = cfg or Config()
    world = World(cfg, control)
    return [
        simulate(
            cfg, mode, reference=reference, control=control, record=record, world=world
        )
        for mode in ("none", "personal", "shared")
    ]


def probe(run, event, *, reference=True, exclude_ids=()):
    """Rebuild the exact pre-contact memory and query it again."""
    memory, pipeline, _ = load_code(reference)
    cfg = Config(**run["config"])
    fly = event["fly"]
    with ExitStack() as stack:
        personal = [
            _shard(stack, f"probe-{i}", len(event["vector"])) for i in range(cfg.flies)
        ]
        shared = _shard(stack, "probe-shared", len(event["vector"]))
        for observed in run["events"]:
            if observed["tick"] >= event["tick"] or observed["outcome"] is None:
                continue
            point_id = observed["tick"] * cfg.flies + observed["fly"] + 1
            point = Point(
                point_id,
                {"odor": observed["vector"]},
                {
                    "outcome": observed.get("reported_outcome", observed["outcome"]),
                    "step": observed["tick"],
                    "source_fly": observed["fly"],
                },
            )
            pipeline.observe(
                memory, personal[observed["fly"]], shared, point, run["mode"]
            )
        original = pipeline.retrieve(
            memory, personal[fly], shared, event["vector"], fly, run["mode"]
        )
        validate_hits(original)
        if run["control"] == "exact":
            vector_by_id = {
                e["tick"] * cfg.flies + e["fly"] + 1: e["vector"] for e in run["events"]
            }
            original = [
                h
                for h in original
                if np.array_equal(vector_by_id[h.id], event["vector"])
            ]
        old = {h["id"]: h for h in event["hits"]}
        same = {h.id for h in original} == set(old) and all(
            abs(h.score - old[h.id]["score"]) < 1e-6
            and all(h.payload[k] == old[h.id][k] for k in h.payload)
            for h in original
        )
        baseline_warning = (
            float(memory.decide(original)) if run["mode"] != "none" else 0.0
        )
        baseline = FlyBrain().respond(baseline_warning, event["neural"]["seed"])
        if not same or baseline != event["neural"]:
            raise ValueError(
                "The rebuilt memory differs from the saved contact. Run this stage again."
            )
        if not exclude_ids:
            return {
                "warning": baseline_warning,
                "neural": baseline,
                "hits": [
                    {"id": h.id, "score": float(h.score), **h.payload} for h in original
                ],
            }
        for shard in [*personal, shared]:
            shard.update(UpdateOperation.delete_points(list(exclude_ids)))
        hits = pipeline.retrieve(
            memory, personal[fly], shared, event["vector"], fly, run["mode"]
        )
        warning = float(memory.decide(hits)) if run["mode"] != "none" else 0.0
        neural = FlyBrain().respond(warning, event["neural"]["seed"])
        return {
            "warning": warning,
            "neural": neural,
            "hits": [{"id": h.id, "score": float(h.score), **h.payload} for h in hits],
        }
