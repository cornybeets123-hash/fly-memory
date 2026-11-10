"""The participant contract tests real Edge behavior, including reversibility."""

import os

import pytest

from workshop.memory import ExperienceMemory


@pytest.fixture
def memory():
    with ExperienceMemory(3, student=os.getenv("WORKSHOP_EXERCISE") == "1") as instance:
        yield instance


def test_observed_experience_is_searchable_and_payload_is_minimal(memory):
    memory.remember(1, [1.0, 0.0, 0.0], -1, 3)
    memory.remember(2, [0.0, 1.0, 0.0], 1, 4)
    recalled = memory.recall([0.99, 0.1, 0.0], 0.6, 1)
    assert recalled["hits"][0]["id"] == 1
    assert 0.99 < recalled["hits"][0]["score"] < 1
    assert recalled["bitter_hz"] == 200
    record = memory.shard.retrieve([1], with_payload=True, with_vector=False)[0]
    assert record.payload == {"outcome": -1, "tick": 3}


def test_threshold_and_exact_key_controls_reject_unseen_vector(memory):
    memory.remember(1, [1.0, 0.0, 0.0], -1, 0)
    assert not memory.recall([0.8, 0.6, 0], 0.9, 1)["hits"]
    assert not memory.recall([0.99, 0.1, 0], 0.6, 1, mode="exact")["hits"]
    assert memory.recall([1.0, 0.0, 0.0], 0.6, 1, mode="exact")["bitter_hz"] == 200


def test_harm_filter_and_nearest_neighbor_budget(memory):
    memory.remember(1, [0.9, 0.1, 0], -1, 0)
    memory.remember(2, [1.0, 0.0, 0.0], 1, 1)
    assert memory.recall([1.0, 0.0, 0.0], 0.6, 1)["bitter_hz"] == 0
    assert memory.recall([1.0, 0.0, 0.0], 0.6, 1, mode="harm")["bitter_hz"] == 200
    assert len(memory.recall([1.0, 0.0, 0.0], 0.6, 2)["hits"]) == 2


def test_delete_restore_and_personal_isolation(memory):
    memory.remember(1, [1.0, 0.0, 0.0], -1, 0)
    with ExperienceMemory(3) as other:
        assert other.recall([1.0, 0.0, 0.0], 0.6, 1)["hits"] == []
    point = memory.delete(1)
    assert memory.recall([1.0, 0.0, 0.0], 0.6, 1)["bitter_hz"] == 0
    memory.restore(point)
    assert memory.recall([1.0, 0.0, 0.0], 0.6, 1)["bitter_hz"] == 200
    with pytest.raises(KeyError):
        memory.delete(99)


def test_evidence_uses_both_outcomes_and_empty_recall_is_naive():
    if os.getenv("WORKSHOP_EXERCISE") == "1":
        from workshop.student_memory import evidence as vote
    else:
        from solutions.memory import evidence as vote
    assert vote([]) == 0
    assert vote([{"score": 0.7, "outcome": -1}]) == pytest.approx(1.0), (
        "Normalize the outcome vote by total cosine weight. The framework scales by cosine afterward."
    )
    assert vote([{"score": 0.9, "outcome": -1}]) > 0
    assert vote([{"score": 0.9, "outcome": 1}]) < 0
    assert vote([{"score": 0.9, "outcome": -1}, {"score": 0.8, "outcome": 1}]) > 0


def test_missing_outcome_and_closed_shards_are_not_silently_accepted(memory):
    with pytest.raises(ValueError):
        memory.remember(1, [1.0, 0.0, 0.0], 0, 0)
    memory.close()
    memory.close()


def test_application_can_reopen_a_durable_edge_memory(tmp_path):
    path = tmp_path / "personal-memory"
    with ExperienceMemory(3, path=path) as first:
        first.remember(7, [1.0, 0.0, 0.0], -1, 20)
    with ExperienceMemory(3, path=path) as next_session:
        assert next_session.recall([0.99, 0.01, 0.0], 0.6, 1)["hits"][0]["id"] == 7
        next_session.remember(8, [0.0, 1.0, 0.0], 1, 0)
        with pytest.raises(ValueError, match="already exists"):
            next_session.remember(7, [0.0, 0.0, 1.0], 1, 1)
        removed = next_session.delete(7)
        next_session.restore(removed)
    with ExperienceMemory(3, path=path) as restored:
        assert set(restored.points) == {7, 8}
        assert restored.recall([1.0, 0.0, 0.0], 0.6, 1)["bitter_hz"] == 200


def test_similarity_strength_reaches_intermediate_neural_response(memory):
    from workshop.brain import RecordedBrain

    memory.remember(1, [1.0, 0.0, 0.0], -1, 0)
    recalled = memory.recall([0.7, (1 - 0.7**2) ** 0.5, 0], 0.6, 1)
    assert recalled["bitter_hz"] == 150
    brain = RecordedBrain()
    assert not brain.response(recalled["bitter_hz"], 100)["feeding"]
    assert brain.response(recalled["bitter_hz"], 102)["feeding"]
