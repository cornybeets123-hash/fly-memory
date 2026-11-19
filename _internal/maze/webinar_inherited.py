"""Inherited memory: newcomers read a frozen pool left by a finished personal group.

This is the earlier shared-memory design, kept beside the hive for comparison. The pool is
complete before any newcomer starts. Newcomers only read it, and a newcomer never reads
its own observations, because it publishes none. Each worker loads the pool once into a
private shard that lives as long as the worker.
"""

import os
import shutil
import tempfile
from pathlib import Path

from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams

from . import memory

POOL = "pool.json.gz"  # Completed personal-group observations, with pixels.
ATLAS = "atlas.json"  # Evaluation-only identity of each pooled observation.
_resident = None  # (episodes, atlas, shard, location) for this worker process


def pool(directory):
    """Return (episodes, source atlas, shard) for the frozen pool, loading it once."""
    global _resident
    if _resident is None:
        # Imported here because the producer imports this module.
        from .webinar_population import read_gzip, read_json, restored_episode

        directory = Path(directory)
        episodes = [restored_episode(e) for e in read_gzip(directory / POOL)]
        atlas = {int(k): tuple(v) for k, v in read_json(directory / ATLAS).items()}
        location = tempfile.mkdtemp(prefix=f"webinar-pool-{os.getpid()}-")
        shard = EdgeShard.create(
            location,
            EdgeConfig(
                vectors={"view": EdgeVectorParams(size=192, distance=Distance.Cosine)}
            ),
        )
        for episode in episodes:
            memory.remember(shard, episode.point)
        _resident = (episodes, atlas, shard, location)
    return _resident[:3]


def close():
    global _resident
    if _resident is not None:
        _resident[2].close()
        shutil.rmtree(_resident[3], ignore_errors=True)
        _resident = None
