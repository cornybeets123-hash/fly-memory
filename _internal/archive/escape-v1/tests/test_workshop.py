"""Contract and causal checks for the public workshop path."""

from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest
from fastapi.testclient import TestClient

from _internal.escape import answers, server
from _internal.escape.checks import check
from _internal.escape.kernel import Kernel
from _internal.escape.scene import Config, encode, point, shard, simulate
from fly_brain import FlyBrain


@pytest.fixture(scope="session")
def paired():
    return {
        mode: simulate(mode=mode, reference=True, trace=False)
        for mode in ("none", "personal", "shared")
    }


def test_same_world_and_natural_input(paired):
    assert len({r["world_hash"] for r in paired.values()}) == 1
    baseline = {
        (e["cycle"], e["fly"]): e["neural"]["natural_input_hash"]
        for e in paired["none"]["events"]
    }
    for result in paired.values():
        assert all(
            baseline[e["cycle"], e["fly"]] == e["neural"]["natural_input_hash"]
            for e in result["events"]
        )


def test_failure_personal_and_shared_progression(paired):
    assert [r["summary"]["hits"] for r in paired.values()] == [12, 6, 0]
    assert [r["summary"]["survivors"] for r in paired.values()] == [0, 6, 6]
    assert all(
        r["summary"]["safe_feeding_retained_pct"] == 100 for r in paired.values()
    )
    assert all(e["escaped"] for e in paired["none"]["events"] if e["cycle"] == 3)
    first = next(
        e for e in paired["shared"]["events"] if e["fly"] == "A" and e["cycle"] == 1
    )
    selected = next(
        h
        for h in first["hits"]
        if h["payload"]["recording"] == first["selected_recording"]
    )
    assert selected["payload"]["source_fly"] == "Scout"
    assert all(h["payload"]["observed_cycle"] < first["cycle"] for h in first["hits"])


def test_hard_safe_evidence_and_index(paired):
    assert float(np.dot(encode(0), encode(0.10))) > answers.MIN_SIMILARITY
    quiet = next(
        e for e in paired["shared"]["events"] if e["fly"] == "A" and e["cycle"] == 2
    )
    assert quiet["selected_recording"] is not None
    assert quiet["neural"]["replay_events"] > 0
    assert quiet["neural"]["first_motor_ms"] is None
    assert quiet["hits"][0]["payload"]["sweep"] is False
    assert paired["shared"]["index"]["indexed_vectors"] > 0
    # Avoidance changes injury, while the direct observation still records a sweep.
    assert all(
        o["payload"]["sweep"]
        for o in paired["shared"]["observations"]
        if o["payload"]["observed_cycle"] in {1, 3, 5}
    )


def test_real_edge_build_checks():
    assert check("personal", True) == "Personal memory passed."
    assert check("shared", True) == "Shared memory passed."


def test_safe_episode_removal_changes_selected_input():
    with TemporaryDirectory() as d, ExitStack() as stack:
        q = shard(stack, Path(d) / "q")
        answers.remember(q, point(1, encode(0), "A", 0, True, "danger"))
        assert answers.decide(answers.recall(q, encode(0.10))) == "danger"
        answers.remember(q, point(2, encode(0.10), "A", 1, False, "quiet"))
        assert answers.decide(answers.recall(q, encode(0.10))) == "quiet"


def test_replay_causal_controls_and_continuous_state():
    with Kernel() as kernel:
        donor = kernel.encounter("Donor", 7, True, 30)
        baseline = kernel.encounter("Twin plain", 11, True, 30)
        memory = kernel.encounter("Twin recall", 11, True, 30, donor["recording"])
        blocked = kernel.encounter(
            "Disconnected", 11, True, 30, donor["recording"], disconnect=True
        )
        assert baseline["natural_input_hash"] == memory["natural_input_hash"]
        assert baseline["first_motor_ms"] > 170
        assert memory["first_motor_ms"] < 10
        assert blocked["first_motor_ms"] is None
        assert FlyBrain.reaches_refuge(memory)
        assert not FlyBrain.reaches_refuge({"first_motor_ms": None})
        second = kernel.encounter("Twin recall", 11, False, 30)
        assert second["start_ms"] == memory["end_ms"] == 600
        assert second["first_motor_ms"] is None
        with pytest.raises(ValueError, match="Unknown input recording"):
            kernel.encounter("Bad reference", 11, True, 30, "missing")


def test_fixed_clock_and_body_bounds():
    with pytest.raises(ValueError):
        Config(strike_ms=201)
    with pytest.raises(ValueError):
        Config(clearance_ms=0)


def test_api_validation_and_saved_code_invalidates_cache(monkeypatch, tmp_path):
    (tmp_path / "memory.py").write_text("pass\n")
    (tmp_path / "pipeline.py").write_text("pass\n")
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "reference_mode", True)
    calls = []

    def fake(cfg, mode, reference, control):
        calls.append((mode, control))
        return {"mode": mode, "code": "Completed code"}

    monkeypatch.setattr(server, "simulate", fake)
    server.cache.clear()
    with TestClient(server.app) as client:
        assert client.post("/api/run", json={"mode": "unknown"}).status_code == 422
        assert client.post("/api/run", json={"seed": -1}).status_code == 422
        for _ in range(2):
            assert client.post("/api/run", json={"mode": "personal"}).status_code == 200
        assert len(calls) == 2
        (tmp_path / "memory.py").write_text("pass # saved edit\n")
        assert client.post("/api/run", json={"mode": "personal"}).status_code == 200
        assert len(calls) == 4
    server.cache.clear()
