"""Check live-coding reloads and useful HTTP errors without changing root files."""

import pytest
from fastapi.testclient import TestClient

from _internal import experiment, server


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "reference_mode", True)
    server.cache.clear()
    return TestClient(server.app)


def test_server_and_checkpoint_requery(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/status").json()["code"] == "Completed code"
    data = client.post("/api/run", json={"mode": "shared", "seed": 2000}).json()
    assert [r["mode"] for r in data["runs"]] == ["personal", "shared"]
    r = client.post(
        "/api/probe",
        json={
            "mode": "shared",
            "seed": 2000,
            "tick": 13,
            "fly": 7,
            "exclude_ids": [113],
        },
    )
    assert r.status_code == 200 and r.json()["neural"]["feeding"]
    assert client.post("/api/run", json={"mode": "bad"}).status_code == 422
    assert client.post("/api/run", json={"seed": -1}).status_code == 422
    assert client.get("/api/lesson/missing").status_code == 404


def test_starter_runs_no_memory_but_names_unfinished_task(client, monkeypatch):
    monkeypatch.setattr(server, "reference_mode", False)
    assert client.post("/api/run", json={"mode": "none"}).status_code == 200
    r = client.post("/api/run", json={"mode": "personal"})
    assert r.status_code == 501 and "Task 1" in r.json()["detail"]


def test_saved_code_is_reloaded_without_bytecode_delay(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "ROOT", tmp_path)
    (tmp_path / "memory.py").write_text("value = 1\n")
    (tmp_path / "pipeline.py").write_text("value = 3\n")
    assert experiment.load_code()[0].value == 1
    (tmp_path / "memory.py").write_text("value = 2\n")
    assert experiment.load_code()[0].value == 2


def test_readable_syntax_error_releases_run_lock(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "reference_mode", False)
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(experiment, "ROOT", tmp_path)
    (tmp_path / "memory.py").write_text("def broken(\n")
    (tmp_path / "pipeline.py").write_text("value = 1\n")
    assert client.post("/api/run", json={"mode": "none"}).status_code == 200
    r = client.post("/api/run", json={"mode": "personal"})
    assert r.status_code == 422 and "memory.py, line 1" in r.json()["detail"]
    assert not server.run_lock.locked()


def test_import_error_points_to_the_edited_file(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "reference_mode", False)
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(experiment, "ROOT", tmp_path)
    (tmp_path / "memory.py").write_text("import missing_workshop_module_12345\n")
    (tmp_path / "pipeline.py").write_text("value = 1\n")
    r = client.post("/api/run", json={"mode": "personal"})
    assert r.status_code == 422 and "memory.py, line 1" in r.json()["detail"]
    assert "ModuleNotFoundError" in r.json()["detail"]
    assert not server.run_lock.locked()
