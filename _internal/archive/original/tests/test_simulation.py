from dataclasses import replace

import pytest

from workshop.brain import RecordedBrain
from workshop.senses import OdorSpace
from workshop.simulation import Config, intervention, run, world


@pytest.fixture(scope="module")
def learned():
    return run(Config())


def test_progress_and_heldout_transfer_use_both_survival_and_safe_feeding(learned):
    assert learned["baseline"]["summary"]["thriving"] == 0
    assert learned["summary"]["thriving"] >= 12
    assert (
        learned["summary"]["safe_meals"] > learned["baseline"]["summary"]["safe_meals"]
    )
    assert (
        learned["summary"]["late_poison_meals"]
        < learned["summary"]["early_poison_meals"]
    )
    heldout = run(Config(seed=3000), record=False)
    assert heldout["summary"]["thriving"] > heldout["baseline"]["summary"]["thriving"]
    assert (
        heldout["summary"]["safe_meals"]
        > 3 * heldout["baseline"]["summary"]["safe_meals"]
    )
    assert heldout["baseline"]["summary"]["thriving"] == 0


def test_every_recall_precedes_observation_and_no_refusal_fabricates_a_memory(learned):
    for fly, history in enumerate(learned["histories"]):
        by_id = {p["id"]: p for p in learned["memories"][fly]}
        for event in history:
            for hit in event["recall"]["hits"]:
                assert hit["tick"] < event["step"]
                assert by_id[hit["id"]]["fly"] == fly
                assert set(hit) == {"id", "score", "outcome", "tick"}
            if event["write"]:
                assert event["neural"]["feeding"]
                assert event["write"]["outcome"] == event["observed_outcome"]
            if not event["neural"]["feeding"]:
                assert event["observed_outcome"] is None
                assert event["write"] is None


def test_surgery_changes_real_neural_response_and_restore_recovers_it(learned):
    data = intervention(learned, 6, 5, 5, RecordedBrain())
    assert data["changed_decision"] and data["restored_decision"]
    assert data["before"]["neural"]["readouts_hz"]["MN9"][0] == 4
    assert data["after"]["neural"]["readouts_hz"]["MN9"][0] == 78
    assert data["before"] == data["restored"]
    assert data["after"]["recall"]["hits"] == []
    with pytest.raises(KeyError):
        intervention(learned, 6, 5, 30, RecordedBrain())


def test_worlds_are_matched_and_observations_never_repeat_exactly():
    cfg, space = Config(), OdorSpace()
    original = world(cfg, space, 6)
    assert original == world(replace(cfg, mode="none", top_k=5), space, 6)
    assert len({tuple(c["vector"]) for c in original}) == cfg.encounters
    assert all(len(c["vector"]) == space.dim for c in original)


def test_reproducible_and_failed_controls_do_not_get_hidden_help(learned):
    assert run(Config(), record=False, baseline=False)["summary"] == learned["summary"]
    exact = run(Config(mode="exact"), record=False, baseline=False)
    assert exact["summary"]["thriving"] == 0
    no_cue = run(Config(marker=0), record=False, baseline=False)
    assert no_cue["summary"]["thriving"] == 0
    corrupted = run(Config(mode="shuffled"), record=False, baseline=False)
    assert corrupted["summary"]["thriving"] < learned["summary"]["thriving"]


def test_more_neighbors_can_make_retrieval_worse(learned):
    broad = run(Config(top_k=5), record=False, baseline=False)
    assert broad["summary"]["thriving"] < learned["summary"]["thriving"]


@pytest.mark.parametrize(
    "values",
    [
        {"flies": 0},
        {"seed": -1},
        {"encounters": 1000},
        {"mode": "shared"},
        {"threshold": 2},
        {"marker": 1},
        {"representation": "oracle"},
    ],
)
def test_config_rejects_invalid_settings(values):
    with pytest.raises(ValueError):
        Config(**values)


def test_default_uses_graded_input_and_neural_variation(learned):
    assert learned["summary"]["stimulus_counts"]["150"] > 0
    assert learned["summary"]["stimulus_counts"]["200"] > 0
    assert learned["summary"]["recalled_but_fed"] > 0


def test_intervention_rejects_a_changed_original_history(learned):
    from copy import deepcopy

    altered = deepcopy(learned)
    altered["histories"][6][5]["recall"]["evidence"] = 0
    with pytest.raises(ValueError, match="differs from the original"):
        intervention(altered, 6, 5, 5, RecordedBrain())


def test_live_mismatch_has_source_recovery_advice(learned):
    class MismatchedLive:
        def response(self, bitter, seed):
            return {
                **RecordedBrain().response(bitter, seed),
                "matches_recording": False,
            }

    with pytest.raises(RuntimeError, match="simulator versions"):
        intervention(learned, 6, 5, 5, RecordedBrain(), live=MismatchedLive())


def test_reopened_session_changes_a_novel_encounter(tmp_path):
    from workshop.sessions import session_probe

    result = session_probe(tmp_path / "personal-memory")
    assert result["distinct_observation"] and result["changed_decision"]
    assert result["empty_memory"]["neural"]["readouts_hz"]["MN9"][0] == 78
    assert result["reopened_memory"]["neural"]["readouts_hz"]["MN9"][0] == 4
