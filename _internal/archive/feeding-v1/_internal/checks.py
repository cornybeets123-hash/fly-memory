"""Small, real-engine checks for the two live-coding steps."""

from contextlib import ExitStack
from math import sqrt

from qdrant_edge import Point

from .experiment import _shard, load_code


def check(stage, reference=False):
    memory, pipeline, _ = load_code(reference)
    with ExitStack() as stack:
        personal = _shard(stack, "check-personal", 3)
        shared = _shard(stack, "check-shared", 3)
        warning = Point(
            1, {"odor": [1.0, 0.0, 0.0]}, {"outcome": -1, "step": 1, "source_fly": 0}
        )
        safe = Point(
            2, {"odor": [0.0, 1.0, 0.0]}, {"outcome": 1, "step": 2, "source_fly": 1}
        )
        memory.remember(personal, warning)
        memory.remember(personal, safe)
        hits = memory.recall(personal, [0.99, 0.01, 0.0])
        assert hits and hits[0].id == 1, "Recall the similar harmful experience."
        assert 0.9 < memory.decide(hits) <= 1, "Use the strongest harmful score."
        assert hits[0].payload == {"outcome": -1, "step": 1, "source_fly": 0}, (
            "Return the observed payload with with_payload=True."
        )
        assert not memory.recall(personal, [0.65, 0.0, sqrt(1 - 0.65**2)]), (
            "Apply the 0.72 similarity threshold."
        )
        assert memory.recall(personal, [0.80, 0.0, 0.60]), (
            "Keep a harmful observation above the threshold."
        )
        assert memory.decide([]) == 0, "An empty memory supplies no warning."
        assert not memory.recall(personal, [0.0, 1.0, 0.0]), (
            "Filter on observed harmful outcomes."
        )
        # A safe exact match must still be excluded after similarity is eligible.
        fresh = _shard(stack, "check-safe", 3)
        memory.remember(fresh, safe)
        assert not memory.recall(fresh, [0.0, 1.0, 0.0]), (
            "Filter on observed harmful outcomes."
        )
        many = _shard(stack, "check-limit", 3)
        for i in range(5):
            memory.remember(
                many,
                Point(
                    100 + i,
                    {"odor": [1.0, i * 0.01, 0.0]},
                    {"outcome": -1, "step": i, "source_fly": 0},
                ),
            )
        assert len(memory.recall(many, [1.0, 0.0, 0.0])) == 3, (
            "Return at most LIMIT=3 observations."
        )
        if stage == "shared":
            pipeline.observe(memory, personal, shared, warning, "shared")
            assert not memory.recall(shared, [1.0, 0.0, 0.0], exclude_fly=0), (
                "Exclude the querying fly's own observations."
            )
            empty = _shard(stack, "check-empty", 3)
            other_hits = pipeline.retrieve(
                memory, empty, shared, [0.99, 0.01, 0.0], 1, "shared"
            )
            assert other_hits and other_hits[0].payload["source_fly"] == 0, (
                "Retrieve another fly's experience."
            )
            local = Point(
                3,
                {"odor": [1.0, 0.0, 0.0]},
                {"outcome": -1, "step": 3, "source_fly": 1},
            )
            memory.remember(empty, local)
            both = pipeline.retrieve(
                memory, empty, shared, [1.0, 0.0, 0.0], 1, "shared"
            )
            assert {h.id for h in both} == {1, 3}, (
                "Keep personal hits and add shared hits."
            )
    return f"{stage.capitalize()} memory passed."
