"""Real Edge checks for the two presenter-led builds."""

from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

from .scene import encode, load_code, point, shard


def check(stage, reference=False):
    memory, pipeline, _ = load_code(reference)
    with TemporaryDirectory(prefix="fly-check-") as temp, ExitStack() as stack:
        personal = shard(stack, Path(temp) / "personal")
        shared = shard(stack, Path(temp) / "shared")
        danger = point(10, encode(0), "A", 0, True, "observed-danger-inputs")
        safe = point(11, encode(0.10), "A", 0, False, "observed-safe-inputs")
        wrong_arena = point(
            12, encode(0.004), "B", 0, False, "kitchen-inputs", arena="kitchen"
        )
        wrong_protocol = point(
            13, encode(0.004), "B", 0, True, "old-inputs", protocol="old"
        )
        for p in (danger, safe, wrong_arena, wrong_protocol):
            memory.remember(personal, p)
        hits = memory.recall(personal, encode(0.004))
        assert hits and hits[0].id == 10, "Return the closest eligible orchard episode."
        assert {h.id for h in hits} == {10, 11}, (
            "Filter arena and protocol. Keep safe evidence."
        )
        assert memory.decide(hits) == "observed-danger-inputs", (
            "Return the winning input-recording reference."
        )
        assert (
            memory.decide(memory.recall(personal, encode(0.099)))
            == "observed-safe-inputs"
        ), "Safe episodes must rank and replay too."
        assert memory.decide([]) is None, "Return None for empty results."
        assert not memory.recall(personal, encode(1.4)), (
            "Apply the similarity threshold."
        )
        assert memory.decide(memory.recall(personal, encode(0.05))) is None, (
            "Abstain on effectively tied conflicting observations."
        )
        if stage == "shared":
            empty = shard(stack, Path(temp) / "empty")
            pipeline.observe(memory, personal, shared, danger, "shared")
            assert not memory.recall(shared, encode(0), exclude_fly="A"), (
                "Exclude the querying fly from shared results."
            )
            other = pipeline.retrieve(
                memory, empty, shared, encode(0.004), "B", "shared"
            )
            assert other and other[0].id == 10, (
                "Read the donor's episode from shared memory."
            )
            local = point(14, encode(0), "B", 1, True, "B-inputs")
            memory.remember(empty, local)
            assert {
                h.id
                for h in pipeline.retrieve(
                    memory, empty, shared, encode(0), "B", "shared"
                )
            } == {10, 14}, "Combine personal and shared results."
    return f"{stage.capitalize()} memory passed."
