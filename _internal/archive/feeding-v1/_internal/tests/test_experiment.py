"""Check retrieval causality, observation boundaries, and reproducible worlds."""

from contextlib import ExitStack

import pytest
from qdrant_edge import Point

from _internal import answers
from _internal.brain import RecordedBrain
from _internal.checks import check
from _internal.experiment import Config, World, _shard, compare, probe, simulate
from _internal.neural_display import spikes


@pytest.fixture(scope="module")
def runs():
    return {r["mode"]: r for r in compare()}


def test_real_edge_workshop_contracts():
    assert check("personal", reference=True) == "Personal memory passed."
    assert check("shared", reference=True) == "Shared memory passed."


def test_world_and_inputs_are_matched_across_modes(runs):
    assert len({r["world_hash"] for r in runs.values()}) == 1
    inputs = {}
    for run in runs.values():
        assert run["nodes"] == runs["none"]["nodes"]
        for event in run["events"]:
            key = (event["fly"], event["object"], event["tick"])
            value = (event["vector"], event["neural"]["seed"])
            assert inputs.setdefault(key, value) == value
    assert all(
        e["warning"] == 0 and e["neural"]["feeding"] for e in runs["none"]["events"]
    )


def test_deterministic_repetition(runs):
    repeat = simulate(Config(), "shared")
    assert repeat["events"] == runs["shared"]["events"]
    assert repeat["frames"] == runs["shared"]["frames"]


def test_every_retrieved_point_is_an_earlier_observed_meal(runs):
    for run in runs.values():
        sources = {
            e["tick"] * 12 + e["fly"] + 1: e
            for e in run["events"]
            if e["outcome"] is not None
        }
        for event in run["events"]:
            for hit in event["hits"]:
                assert set(hit) == {"id", "score", "outcome", "step", "source_fly"}
                source = sources[hit["id"]]
                assert source["tick"] == hit["step"] < event["tick"]
                assert source["fly"] == hit["source_fly"]
                assert source["outcome"] == hit["outcome"] == -1
                if run["mode"] == "personal":
                    assert source["fly"] == event["fly"]


def test_shared_query_also_runs_when_personal_memory_matches():
    with ExitStack() as stack:
        personal, shared = [_shard(stack, n, 3) for n in ("p", "s")]
        for shard, source, point_id in [
            (personal, 0, 1),
            (shared, 1, 2),
            (shared, 0, 3),
        ]:
            answers.remember(
                shard,
                Point(
                    point_id,
                    {"odor": [1.0, 0.0, 0.0]},
                    {"outcome": -1, "source_fly": source, "step": 1},
                ),
            )
        hits = answers.retrieve(answers, personal, shared, [1.0, 0.0, 0.0], 0, "shared")
        assert {h.id for h in hits} == {1, 2}


def test_remove_relevant_memory_changes_fixed_checkpoint(runs):
    run = runs["shared"]
    event = next(e for e in run["events"] if e["tick"] == 13 and e["fly"] == 7)
    original = probe(run, event)
    removed = probe(run, event, exclude_ids=[113])
    irrelevant = probe(run, event, exclude_ids=[999999])
    assert not original["neural"]["feeding"]
    assert removed["neural"]["feeding"] and not removed["hits"]
    assert original == irrelevant
    assert original["neural"]["seed"] == removed["neural"]["seed"]
    assert event["shared_changed_decision"]
    assert event["without_shared"]["feeding"]


def test_personal_similarity_generalizes_to_a_different_food_object(runs):
    run = runs["personal"]
    event = next(e for e in run["events"] if e["tick"] == 125 and e["fly"] == 11)
    hit = event["hits"][0]
    source = next(
        e
        for e in run["events"]
        if e["tick"] == hit["step"] and e["fly"] == hit["source_fly"]
    )
    assert source["object"] != event["object"]
    assert 0.72 < hit["score"] < 1.0
    assert not event["neural"]["feeding"]
    assert probe(run, event, exclude_ids=[hit["id"]])["neural"]["feeding"]


def test_simultaneous_new_poison_injuries_are_not_hidden(runs):
    run = runs["shared"]
    events = [e for e in run["events"] if e["tick"] == 357 and e["outcome"] == -1]
    assert len(events) == 2
    assert all(not e["hits"] for e in events)


def test_hidden_outcome_changes_no_input_or_pre_meal_decision():
    cfg = Config()
    original = World(cfg)
    changed = World(cfg)
    first = simulate(cfg, "none", world=original)
    event = first["events"][0]
    node = next(n for n in changed.epochs[0] if n["id"] == event["object"])
    node["kind"] = 0 if node["kind"] >= 3 else 3
    second = simulate(cfg, "none", world=changed)
    assert first["events"][0]["vector"] == second["events"][0]["vector"]
    assert first["events"][0]["neural"] == second["events"][0]["neural"]
    assert first["events"][0]["outcome"] != second["events"][0]["outcome"]
    assert [f[:3] for f in first["frames"][0]["flies"]] == [
        f[:3] for f in second["frames"][0]["flies"]
    ]


def test_single_neuron_display_uses_exact_archived_spikes():
    bank = RecordedBrain()
    idx = bank.data["protocol"]["neuron_indices"]
    key = bank.key(200, 103)
    trace = spikes(key, idx["sugar"][0], idx["bitter"][0], idx["MN9"][0])
    assert len(trace["motor"]) == bank.trials[key]["readouts_hz"]["MN9"][0]
    assert len(trace["bitter"]) > len(trace["motor"])


def test_empty_and_invalid_modes_have_clear_errors():
    with pytest.raises(ValueError, match="Choose"):
        simulate(Config(), "unknown")
    with pytest.raises(ValueError, match="seed"):
        Config(seed=-1)


def test_personal_story_shows_the_source_injury_first(runs):
    first, general = runs["personal"]["chapters"][:2]
    assert first["event"]["fly"] == general["event"]["fly"] == 11
    assert first["event"]["tick"] == 52
    assert general["event"]["tick"] == 125
    assert (
        general["witness_id"] == first["event"]["tick"] * 12 + first["event"]["fly"] + 1
    )


@pytest.mark.parametrize("seed", [2001, 2003])
def test_new_poison_story_cites_the_new_poison(seed):
    run = simulate(Config(seed=seed), "personal")
    later = next(
        (
            c
            for c in run["chapters"]
            if "witness_id" in c and c["title"] == "The new warning works."
        ),
        None,
    )
    if later is None:
        return  # Some worlds do not produce a later refusal of this poison.
    event = later["event"]
    source = next(
        e for e in run["events"] if e["tick"] * 12 + e["fly"] + 1 == later["witness_id"]
    )
    for e in [event, source]:
        assert (
            next(n for n in run["nodes"][e["tick"] // 100] if n["id"] == e["object"])[
                "variant"
            ]
            == 5
        )
    assert source["tick"] < event["tick"]


def test_probe_replays_shuffled_reports_and_actual_write_pipeline():
    run = simulate(Config(), "shared", control="shuffled")
    event = next(e for e in run["events"] if e["hits"])
    rebuilt = probe(run, event)
    assert rebuilt["hits"] == event["hits"]
    assert rebuilt["neural"] == event["neural"]


def test_contact_noise_changes_exact_vectors_but_keeps_world_reproducible():
    a, b = World(Config()), World(Config())
    assert a.scent(0, 0, 0, 10) == b.scent(0, 0, 0, 10)
    assert a.scent(0, 0, 0, 10) != a.scent(0, 0, 0, 11)


def test_exact_vector_control_cannot_reuse_noisy_observations(runs):
    exact = compare(control="exact")
    for run in exact:
        assert run["summary"]["alive"] == runs["none"]["summary"]["alive"]
        assert run["summary"]["safe_meals"] == runs["none"]["summary"]["safe_meals"]
        assert (
            run["summary"]["harmful_meals"] == runs["none"]["summary"]["harmful_meals"]
        )
        assert all(not e["hits"] for e in run["events"])
