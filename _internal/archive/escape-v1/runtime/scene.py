"""Fixed sensory schedules, observed episodes, and an engineered refuge task."""

import hashlib
import json
import math
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
    EdgeOptimizersConfig,
    EdgeShard,
    EdgeVectorParams,
    HnswIndexConfig,
    Point,
    Query,
    QueryRequest,
)

from fly_brain import FlyBrain

from . import answers
from .kernel import PROTOCOL, Kernel

ROOT = Path(__file__).resolve().parents[2]
FLIES = ["A", "B", "C", "D", "E", "F"]


@dataclass(frozen=True)
class Config:
    seed: int = 2000
    clearance_ms: float = 45.0
    strike_ms: int = 200
    injuries_to_die: int = 2

    def __post_init__(self):
        if not 0 <= self.seed <= 1_000_000:
            raise ValueError("Choose a seed between zero and 1000000.")
        if not 20 <= self.clearance_ms <= 90:
            raise ValueError("Clearance time must stay between 20 and 90 milliseconds.")
        if self.strike_ms != 200:
            raise ValueError(
                "This sensory protocol fixes the strike at 200 milliseconds."
            )


def encode(phase):
    """Encode the currently measured pulse pattern, without future event labels."""
    vector = np.array(
        [math.cos(phase), math.sin(phase), 0.04, -0.03, 0.02, 0.01, -0.02, 0.03]
    )
    return (vector / np.linalg.norm(vector)).tolist()


def schedule(cfg):
    rng = np.random.default_rng(cfg.seed)
    # The screen hides approach in the two ambushes. Clear-view reflex is retained.
    cycles = [
        ("Quiet pulse", False, 30),
        ("Behind the screen", True, 30),
        ("Similar, but safe", False, 30),
        ("Clear view", True, 80),
        ("Another safe pulse", False, 30),
        ("The ambush returns", True, 25),
    ]
    return [
        {
            "cycle": cycle,
            "title": title,
            "sweep": sweep,
            "lead_ms": lead,
            "phases": [
                (0.0 if sweep else 0.10) + float(rng.uniform(-0.008, 0.008))
                for _ in FLIES
            ],
        }
        for cycle, (title, sweep, lead) in enumerate(cycles)
    ]


def load_code(reference=False):
    if reference:
        return answers, answers, "Completed code"

    def read(name):
        path = ROOT / f"{name}.py"
        module = SimpleNamespace(__name__=f"workshop_{name}", __file__=str(path))
        exec(compile(path.read_text(), str(path), "exec"), module.__dict__)  # noqa: S102
        return module

    return read("memory"), read("pipeline"), "Your code"


def shard(stack, path):
    path.mkdir(parents=True)
    result = EdgeShard.create(
        str(path),
        EdgeConfig(
            vectors={"cue": EdgeVectorParams(size=8, distance=Distance.Cosine)},
            hnsw_config=HnswIndexConfig(
                m=8, ef_construct=64, full_scan_threshold=0, max_indexing_threads=1
            ),
            optimizers=EdgeOptimizersConfig(indexing_threshold=1),
        ),
    )
    stack.callback(result.close)
    return result


def serialize(hit):
    return {"id": hit.id, "score": hit.score, "payload": hit.payload}


def point(
    point_id,
    vector,
    source,
    cycle,
    sweep,
    recording,
    arena="orchard",
    protocol=PROTOCOL,
):
    return Point(
        point_id,
        {"cue": vector},
        {
            "source_fly": source,
            "observed_cycle": cycle,
            "sweep": sweep,
            "recording": recording,
            "protocol": protocol,
            "arena": arena,
        },
    )


def simulate(cfg=None, mode="none", reference=False, control="normal", trace=True):
    if mode not in {"none", "personal", "shared"}:
        raise ValueError("Choose none, personal, or shared memory.")
    cfg = cfg or Config()
    memory, pipeline, code = load_code(reference)
    world = schedule(cfg)
    fingerprint = hashlib.sha256(json.dumps(world, sort_keys=True).encode()).hexdigest()
    events, observations, donor = [], [], None
    harms = {fly: 0 for fly in FLIES}
    safe_ms = {fly: 0 for fly in FLIES}
    false_jumps = {fly: 0 for fly in FLIES}
    with ExitStack() as stack:
        temp = Path(stack.enter_context(TemporaryDirectory(prefix="fly-memory-")))
        kernel = stack.enter_context(Kernel())
        personal = {fly: shard(stack, temp / fly) for fly in FLIES}
        shared = shard(stack, temp / "shared")
        # The same observed scout experience exists in every run. Only shared mode reads it.
        donor = kernel.encounter("Scout", cfg.seed + 99, True, 30, trace=False)
        donor_point = point(1, encode(0.008), "Scout", -1, True, donor["recording"])
        if control != "remove_donor":
            answers.remember(shared, donor_point)
            observations.append(
                {
                    "id": 1,
                    "vector": encode(0.008),
                    "payload": donor_point.payload,
                    "scope": "shared",
                }
            )
        # A second directly observed orchard cycle supplies the near-safe episode.
        safe_donor = kernel.encounter("Scout", cfg.seed + 99, False, 30)
        safe_point = point(2, encode(0.10), "Scout", -1, False, safe_donor["recording"])
        if control not in {"remove_safe", "remove_donor"}:
            answers.remember(shared, safe_point)
            observations.append(
                {
                    "id": 2,
                    "vector": encode(0.10),
                    "payload": safe_point.payload,
                    "scope": "shared",
                }
            )
        # Another arena has a different cue association. Its source observes a safe cycle.
        kitchen = kernel.encounter("Kitchen Scout", cfg.seed + 100, False, 30)
        row = point(
            3,
            encode(0),
            "Kitchen Scout",
            -1,
            False,
            kitchen["recording"],
            arena="kitchen",
        )
        answers.remember(shared, row)
        observations.append(
            {"id": 3, "vector": encode(0), "payload": row.payload, "scope": "shared"}
        )
        shared.optimize()
        for cycle in world:
            writes = []
            for fly_index, fly in enumerate(FLIES):
                if harms[fly] >= cfg.injuries_to_die:
                    continue
                vector = encode(cycle["phases"][fly_index])
                query_start = perf_counter()
                hits = pipeline.retrieve(
                    memory, personal[fly], shared, vector, fly, mode
                )
                query_ms = (perf_counter() - query_start) * 1000
                candidates = []
                if trace and fly_index == 0 and mode != "none":
                    for current in (
                        [personal[fly], shared] if mode == "shared" else [personal[fly]]
                    ):
                        candidates += [
                            serialize(h)
                            for h in current.query(
                                QueryRequest(
                                    query=Query.Nearest(vector, using="cue"),
                                    limit=5,
                                    with_payload=True,
                                )
                            )
                        ]
                if control == "no_recall":
                    hits = []
                recording = memory.decide(hits) if mode != "none" else None
                if control == "no_replay":
                    recording = None
                if control == "always_escape":
                    recording = donor["recording"]
                if control == "irrelevant_replay":
                    recording = safe_donor["recording"]
                brain = FlyBrain(kernel, fly, cfg.seed + fly_index + 1)
                result = brain.respond(
                    cycle["sweep"],
                    cycle["lead_ms"],
                    recording,
                    trace=trace and fly_index == 0,
                    disconnect=control == "disconnect",
                )
                onset = result["first_motor_ms"]
                if control == "no_motor":
                    onset = None
                clear_at = onset + cfg.clearance_ms if onset is not None else None
                escaped = brain.reaches_refuge(
                    {"first_motor_ms": onset}, cfg.clearance_ms, cfg.strike_ms
                )
                hit = bool(cycle["sweep"] and not escaped)
                harms[fly] += int(hit)
                false_jump = bool(not cycle["sweep"] and onset is not None)
                false_jumps[fly] += int(false_jump)
                feeding = (
                    0 if cycle["sweep"] else (300 if onset is None else min(300, onset))
                )
                safe_ms[fly] += feeding
                event_id = 100 + cycle["cycle"] * len(FLIES) + fly_index
                event = {
                    "id": event_id,
                    "cycle": cycle["cycle"],
                    "fly": fly,
                    "title": cycle["title"],
                    "cue": vector,
                    "phase": cycle["phases"][fly_index],
                    "sweep": cycle["sweep"],
                    "lead_ms": cycle["lead_ms"],
                    "hits": [serialize(h) for h in hits],
                    "query_ms": round(query_ms, 3),
                    "candidates": candidates,
                    "selected_recording": recording,
                    "neural": result,
                    "action_ms": onset,
                    "clear_at_ms": clear_at,
                    "hit": hit,
                    "escaped": bool(cycle["sweep"] and escaped),
                    "false_jump": false_jump,
                    "safe_feeding_ms": feeding,
                    "injuries": harms[fly],
                    "alive": harms[fly] < cfg.injuries_to_die,
                }
                events.append(event)
                # The complete observation window has ended. An avoided sweep still occurred.
                observed = point(
                    event_id,
                    vector,
                    fly,
                    cycle["cycle"],
                    cycle["sweep"],
                    result["recording"],
                )
                writes.append((fly, observed, vector))
            # No fly can read another fly's future or same-cycle observation.
            for fly, observed, vector in writes:
                if control == "remove_safe" and not observed.payload["sweep"]:
                    continue
                pipeline.observe(memory, personal[fly], shared, observed, mode)
                if mode != "none":
                    observations.append(
                        {
                            "id": observed.id,
                            "vector": vector,
                            "payload": observed.payload,
                            "scope": fly,
                        }
                    )
            if mode != "none" and cycle["cycle"] in {2, 5}:
                for current in personal.values():
                    current.optimize()
            if mode == "shared" and cycle["cycle"] in {2, 5}:
                shared.optimize()
        index_info = shared.info()
        indexed_vectors = index_info.indexed_vectors_count
        return {
            "mode": mode,
            "code": code,
            "config": asdict(cfg),
            "world_hash": fingerprint,
            "world": world,
            "events": events,
            "observations": observations,
            "brain": kernel.info,
            "control": control,
            "donor": {k: v for k, v in donor.items() if k != "trace"},
            "index": {
                "engine": "Qdrant Edge 0.8.0",
                "indexed_vectors": indexed_vectors,
                "hnsw": "m=8, ef_construct=64",
            },
            "summary": {
                "survivors": sum(n < cfg.injuries_to_die for n in harms.values()),
                "hits": sum(harms.values()),
                "false_jumps": sum(false_jumps.values()),
                "safe_feeding_ms": round(sum(safe_ms.values()), 1),
                "safe_feeding_available_ms": 5400,
                "safe_feeding_retained_pct": round(sum(safe_ms.values()) / 54, 1),
            },
        }
