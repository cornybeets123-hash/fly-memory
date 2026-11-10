"""Audit recorded neural responses against actual spike files and fixed inputs."""

import hashlib
import json

import numpy as np

from _internal.brain import BANK_PATH, RecordedBrain


def test_all_48_recordings_match_raw_spikes_and_declared_motor_gate():
    bank = RecordedBrain()
    assert len(bank.trials) == 48
    assert bank.data["provenance"]["neuron_count"] == 127400
    for trial in bank.trials.values():
        path = BANK_PATH.parent / trial["raw_spikes_file"]
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest() == trial["raw_spikes_sha256"]
        )
        with np.load(path) as spikes:
            indices, times = spikes["neuron_index"], spikes["time_s"]
            assert np.all((times >= 0) & (times < trial["duration_s"]))
            assert len(indices) == trial["total_spikes"]
            for group in ("MN9", "FG", "P9-oDN1"):
                for side, index in enumerate(
                    bank.data["protocol"]["neuron_indices"][group]
                ):
                    hist = np.histogram(
                        times[indices == index],
                        bins=bank.data["protocol"]["bin_edges_s"],
                    )[0]
                    assert hist.tolist() == trial["traces"][group][side]
                    assert (
                        sum(hist) / trial["duration_s"]
                        == trial["readouts_hz"][group][side]
                    )
        assert trial["feeding"] == (trial["readouts_hz"]["MN9"][0] > bank.gate)


def test_replay_uses_measured_response_and_preserves_intermediate_variation():
    bank = RecordedBrain()
    assert all(bank.response(0, s)["feeding"] for s in bank.seeds)
    assert not any(bank.response(200, s)["feeding"] for s in bank.seeds)
    assert sum(bank.response(150, s)["feeding"] for s in bank.seeds) == 1
    assert bank.response(150, 102)["readouts_hz"]["MN9"][0] == 13
    assert bank.response(200, 103)["readouts_hz"]["MN9"][0] == 4


def test_bundled_data_has_pinned_sources_and_no_missing_response_values():
    odors = json.loads((BANK_PATH.parent / "odors.json").read_text())
    assert odors["source"]["license"] == "CC BY-SA 4.0"
    assert len(odors["receptors"]) == 24
    assert all(
        len(o["response"]) == 24 and np.isfinite(o["response"]).all()
        for o in odors["odorants"]
    )
