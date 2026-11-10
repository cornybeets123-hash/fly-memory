"""Check the saved build through real Qdrant queries and neural navigation."""

from pathlib import Path
from tempfile import TemporaryDirectory

from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams, Point

from . import learner, memory
from .kernel import Kernel
from .simulation import run
from .workshop_world import WorkshopWorld


def check_eligibility(backend, stage):
    """Exercise the saved functions against eligible and incompatible records."""
    vector = [1.0] + [0.0] * 191
    records = [
        (1, WorkshopWorld.id, memory.PROTOCOL, "A"),
        (2, WorkshopWorld.id, memory.PROTOCOL, "B"),
        (3, "another-world", memory.PROTOCOL, "A"),
        (4, WorkshopWorld.id, "another-protocol", "A"),
        (5, "another-world", memory.PROTOCOL, "B"),
        (6, WorkshopWorld.id, "another-protocol", "B"),
        (7, WorkshopWorld.id, memory.PROTOCOL, "C"),
    ]
    with TemporaryDirectory() as directory:
        location = Path(directory) / "eligibility"
        location.mkdir()
        shard = EdgeShard.create(
            str(location),
            EdgeConfig(
                vectors={"view": EdgeVectorParams(size=192, distance=Distance.Cosine)}
            ),
        )
        try:
            for identifier, world, protocol, source in records:
                backend.remember(
                    shard,
                    Point(
                        identifier,
                        {"view": vector},
                        {
                            "world": world,
                            "protocol": protocol,
                            "source_fly": source,
                            "outcome": "returned",
                        },
                    ),
                )
            hits = backend.recall(
                shard, vector, WorkshopWorld.id, protocol=memory.PROTOCOL, owner="A"
            )
            if {int(hit.id) for hit in hits} != {1}:
                raise ValueError(
                    "Personal eligibility failed. recall() must require matching world, "
                    "protocol, and this fly's source."
                )
            if stage == "shared":
                hits = backend.recall(
                    shard,
                    vector,
                    WorkshopWorld.id,
                    protocol=memory.PROTOCOL,
                    owner="B",
                    exclude_fly="B",
                )
                if {int(hit.id) for hit in hits} != {1, 7}:
                    raise ValueError(
                        "Shared eligibility failed. scope() must require matching world "
                        "and protocol, and exclude this fly."
                    )
        finally:
            shard.close()


def check(stage, reference=False):
    backend = memory if reference else learner.load()
    check_eligibility(backend, stage)
    with Kernel() as kernel, TemporaryDirectory() as directory:
        world = WorkshopWorld()
        location = Path(directory) / "memory"
        location.mkdir()
        shard = EdgeShard.create(
            str(location),
            EdgeConfig(
                vectors={"view": EdgeVectorParams(size=192, distance=Distance.Cosine)}
            ),
        )
        try:
            personal = run(
                kernel,
                world,
                seed=305,
                mode="personal",
                duration=65,
                backend=backend,
                shard=shard,
            )
            if not personal["summary"]["exit"] or personal["summary"]["returns"] != 1:
                raise ValueError(
                    "The fly did not use its own completed circuit. Check remember() and recall()."
                )
            if stage == "personal":
                return "Personal memory passed."
            shared = run(
                kernel,
                world,
                seed=305,
                mode="shared",
                history=personal["episodes"],
                duration=65,
                backend=backend,
                shard=shard,
            )
            if not shared["summary"]["exit"] or shared["summary"]["returns"] != 0:
                raise ValueError(
                    "Shared memory did not retrieve Fly A's experience. Check pipeline.scope()."
                )
            assert all(
                v["selected"]["payload"]["source_fly"] == "A"
                for d in shared["decisions"]
                for v in d["views"]
                if v["selected"]
            )
            return "Shared memory passed."
        finally:
            shard.close()
