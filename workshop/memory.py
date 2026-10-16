"""Personal episodic memory on the real, embedded Qdrant Edge engine."""

from __future__ import annotations

from math import ceil, isfinite
from pathlib import Path
from tempfile import TemporaryDirectory

from qdrant_edge import (
    Distance,
    EdgeConfig,
    EdgeShard,
    EdgeVectorParams,
    Point,
    ScrollRequest,
    UpdateOperation,
)


class ExperienceMemory:
    """Own one isolated shard. Point payloads contain outcome and time only."""

    def __init__(self, dim, *, student=False, path=None):
        self._temp = TemporaryDirectory(prefix="fly-memory-") if path is None else None
        directory = Path(self._temp.name) if self._temp else Path(path)
        existing = directory.exists() and any(directory.iterdir())
        directory.mkdir(parents=True, exist_ok=True)
        self._closed = False
        if student:
            from workshop import student_memory

            self._hooks = student_memory
        else:
            from solutions import memory as reference

            self._hooks = reference
        try:
            config = EdgeConfig(
                vectors={"odor": EdgeVectorParams(size=dim, distance=Distance.Cosine)},
                max_search_threads=1,
            )
            self.shard = (EdgeShard.load if existing else EdgeShard.create)(
                str(directory), config
            )
        except BaseException:
            if self._temp:
                self._temp.cleanup()
            raise
        self.points = {}
        if existing:
            offset = None
            while True:
                rows, offset = self.shard.scroll(
                    ScrollRequest(
                        limit=100, offset=offset, with_payload=True, with_vector=True
                    )
                )
                for row in rows:
                    self.points[row.id] = {
                        "id": row.id,
                        "vector": row.vector["odor"],
                        **row.payload,
                    }
                if offset is None:
                    break

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self.shard.close()
            finally:
                if self._temp:
                    self._temp.cleanup()

    def remember(self, point_id, vector, outcome, tick):
        if outcome not in (-1, 1):
            raise ValueError(
                "An experience must be an observed harmful or nourishing meal."
            )
        if point_id in self.points:
            raise ValueError(
                "Memory ID already exists. Use a new ID for each experience."
            )
        point = Point(point_id, {"odor": vector}, {"outcome": outcome, "tick": tick})
        self._hooks.store(self.shard, point)
        self.points[point_id] = {
            "id": point_id,
            "vector": vector,
            "outcome": outcome,
            "tick": tick,
        }

    def recall(self, vector, threshold, top_k, *, mode="balanced", margin=0.0):
        if mode == "none":
            return {"hits": [], "evidence": 0.0, "confidence": 0.0, "bitter_hz": 0}
        hits = self._hooks.search(
            self.shard,
            vector,
            threshold,
            top_k,
            mode == "harm",
        )
        rows = [{"id": h.id, "score": float(h.score), **h.payload} for h in hits]
        if mode == "exact":
            rows = [h for h in rows if self.points[h["id"]]["vector"] == vector]
        value = float(self._hooks.evidence(rows))
        # This engineered sensory interface is fixed across experimental conditions.
        if not isfinite(value) or not -1 <= value <= 1:
            raise ValueError("Evidence must be a finite value between -1 and 1.")
        confidence = (
            (value - margin) / (1 - margin) * max((h["score"] for h in rows), default=0)
            if value > margin
            else 0.0
        )
        confidence = min(1.0, max(0.0, confidence))
        bitter = min(200, ceil(confidence * 4) * 50)
        return {
            "hits": rows,
            "evidence": value,
            "confidence": confidence,
            "bitter_hz": bitter,
        }

    def delete(self, point_id):
        if point_id not in self.points:
            raise KeyError("This memory does not exist in this encounter's history.")
        point = self.points[point_id]
        self.shard.update(UpdateOperation.delete_points([point_id]))
        del self.points[point_id]
        return point

    def restore(self, point):
        self.remember(point["id"], point["vector"], point["outcome"], point["tick"])
