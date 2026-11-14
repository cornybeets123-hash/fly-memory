"""Stopped attempts remain playable. Corrupt evidence and changed runtime stay blocked."""

import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from _internal.maze import webinar_playback as playback
from _internal.maze import webinar_population as producer


@pytest.fixture
def recording(tmp_path, monkeypatch):
    monkeypatch.setattr(producer, "DIRECTORY", tmp_path)
    monkeypatch.setattr(playback, "recording_sources_match", lambda source: True)
    run = {
        "owner": "A51",
        "seed": 50050,
        "summary": {
            "exit": False,
            "no_decision": True,
            "collisions": 0,
            "longest_stall_s": 0,
            "time_ms": 132680,
        },
        "events": [
            {
                "kind": "no_decision",
                "time": 132680,
                "reason": "ambiguous_options",
                "count": 1,
            }
        ],
        "decisions": [{"decision_readout": -0.4}],
        "frames": [],
        "observations": [],
    }
    producer.save_gzip(tmp_path / "none-0.json.gz", run)
    producer.write_json(
        tmp_path / "none.json",
        {
            "mode": "none",
            "flies": [copy.deepcopy(run)],
            "summary": {"count": 1, "exited": 0},
            "audit_errors": ["none/A51: movement failure"],
        },
    )
    producer.write_json(
        tmp_path / "status.json",
        {
            "state": "audit_failed",
            "source": {},
            "count": 1,
            "ready": ["none"],
            "summary": {"none": {"count": 1, "exited": 0}},
            "errors": ["none: none/A51: movement failure"],
        },
    )
    playback._review.cache_clear()
    app = FastAPI()
    app.include_router(playback.router)
    return tmp_path, run, TestClient(app)


def test_stopped_attempt_remains_in_playback_and_original_audit_is_preserved(recording):
    path, _, client = recording
    status = client.get("/api/hive/status").json()
    assert status["state"] == "ready_with_failures"
    assert not status["evidence_errors"]
    assert status["behavior_failures"]["none"][0]["seed"] == 50050
    data = client.get("/api/hive/none").json()
    assert data["audit_errors"] == ["none/A51: movement failure"]
    assert not data["evidence_errors"]
    assert len(data["flies"]) == data["summary"]["count"] == 1
    assert data["summary"]["exited"] == 0
    detail = client.get("/api/hive/none/fly/0").json()
    assert detail["run"]["summary"]["no_decision"]
    assert detail["behavior_failure"]["reason"] == "ambiguous_options"
    assert producer.read_json(path / "status.json")["state"] == "audit_failed"


@pytest.mark.parametrize(
    "issue", ["wrong-place match 0.99", "Personal fly borrowed A7"]
)
def test_evidence_errors_still_block_a_condition_with_a_stopped_attempt(
    recording, issue
):
    path, _, client = recording
    data = producer.read_json(path / "none.json")
    data["audit_errors"].append(issue)
    producer.write_json(path / "none.json", data)
    assert client.get("/api/hive/none").status_code == 409
    state = client.get("/api/hive/status").json()
    assert state["state"] == "audit_failed"
    assert state["evidence_errors"] == [issue]


@pytest.mark.parametrize(
    "corruption", ["collision", "missing_event", "zero_decision", "different_summary"]
)
def test_unexplained_or_unsafe_failure_still_blocks_playback(recording, corruption):
    path, run, client = recording
    if corruption == "collision":
        run["summary"]["collisions"] = 1
    elif corruption == "missing_event":
        run["events"] = []
    elif corruption == "zero_decision":
        run["decisions"][0]["decision_readout"] = 0
    else:
        run["summary"]["time_ms"] += 100
    producer.save_gzip(path / "none-0.json.gz", run)
    assert client.get("/api/hive/none").status_code == 409


def test_reader_updates_preserve_recordings_but_changed_controller_invalidates_them():
    source = producer.freeze()
    assert playback.recording_sources_match(source)
    source["_internal/maze/webinar_playback.py"] = "an earlier playback reader"
    assert playback.recording_sources_match(source)
    source["_internal/maze/cohort.py"] = "a different controller protocol"
    assert not playback.recording_sources_match(source)
