"""The attendee checks must reject missing or incorrect eligibility conditions."""

from types import SimpleNamespace

import pytest
from qdrant_edge import FieldCondition, Filter, MatchValue, Query, QueryRequest

from _internal.maze import learner, memory
from _internal.maze.checks import check_eligibility


def test_reference_eligibility_contract():
    check_eligibility(memory, "shared")


@pytest.mark.parametrize("omitted", ["world", "protocol", "source_fly", "all"])
def test_check_rejects_missing_saved_conditions(monkeypatch, omitted):
    def scope(world, protocol, fly, shared=False):
        fields = {"world": world, "protocol": protocol, "source_fly": fly}
        must = [
            FieldCondition(key, match=MatchValue(value))
            for key, value in fields.items()
            if key != omitted
            and omitted != "all"
            and (key != "source_fly" or not shared)
        ]
        return Filter(
            must=must,
            must_not=[FieldCondition("source_fly", match=MatchValue(fly))]
            if shared and omitted not in {"source_fly", "all"}
            else None,
        )

    def recall(shard, vector, eligibility):
        return shard.query(
            QueryRequest(
                query=Query.Nearest(vector, using="view"),
                limit=10,
                score_threshold=0.90,
                filter=eligibility,
                with_payload=True,
            )
        )

    monkeypatch.setattr(
        learner,
        "read_module",
        lambda name: (
            SimpleNamespace(
                remember=memory.remember, recall=recall, decide=memory.decide
            )
            if name == "memory"
            else SimpleNamespace(scope=scope)
        ),
    )
    with pytest.raises(ValueError, match="eligibility failed"):
        check_eligibility(learner.load(), "shared")


def test_personal_build_cannot_pass_shared_check():
    def recall(shard, vector, world, exclude_fly=None, protocol=None, owner="A"):
        return memory.recall(shard, vector, world, protocol=protocol, owner=owner)

    backend = SimpleNamespace(remember=memory.remember, recall=recall)
    check_eligibility(backend, "personal")
    with pytest.raises(ValueError, match="Shared eligibility failed"):
        check_eligibility(backend, "shared")
