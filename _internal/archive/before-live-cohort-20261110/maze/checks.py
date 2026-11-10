"""Check the saved build through real Qdrant queries and neural navigation."""

from pathlib import Path
from tempfile import TemporaryDirectory

from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams

from . import learner, memory
from .kernel import Kernel
from .simulation import run
from .workshop_world import WorkshopWorld


def check(stage, reference=False):
    backend = memory if reference else learner.load()
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
