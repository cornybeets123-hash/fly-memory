from fastapi.testclient import TestClient

from workshop.server import app, run_lock, runs

client = TestClient(app)


def test_app_runs_without_docker_or_external_credentials(monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "http://127.0.0.1:1")
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/api/status").json()["recorded_trials"] == 48
    assert len(client.get("/api/brain").json()["trials"]) == 48
    response = client.post("/api/run", json={})
    assert response.status_code == 200
    run = response.json()
    surgery = client.post(
        "/api/intervention",
        json={"run_id": run["id"], "fly": 6, "step": 5, "point_id": 5},
    )
    assert surgery.status_code == 200
    assert surgery.json()["changed_decision"]


def test_api_rejects_bad_settings_and_concurrent_neural_runs():
    assert client.post("/api/run", json={"flies": 100}).status_code == 422
    assert client.post("/api/run", json={"threshold": 1.1}).status_code == 422
    assert client.post("/api/run", json={"mode": "oracle"}).status_code == 422
    assert client.post("/api/run", json={"unknown": 1}).status_code == 422
    with run_lock:
        assert client.post("/api/run", json={}).status_code == 409
    assert (
        client.post(
            "/api/intervention",
            json={"run_id": "0" * 32, "fly": 6, "step": 5, "point_id": 5},
        ).status_code
        == 404
    )


def test_student_failures_are_explicit_and_baseline_still_runs(monkeypatch):
    from workshop import student_memory

    def unfinished(*args):
        raise NotImplementedError("student_memory.store is unfinished")

    monkeypatch.setattr(student_memory, "store", unfinished)
    monkeypatch.setenv("WORKSHOP_EXERCISE", "1")
    response = client.post("/api/run", json={})
    assert response.status_code == 501
    assert "student_memory" in response.json()["detail"]
    assert not run_lock.locked()
    assert client.post("/api/run", json={"mode": "none", "flies": 1}).status_code == 200


def test_cache_is_bounded_and_missing_points_are_actionable():
    runs.clear()
    for seed in range(7):
        result = client.post(
            "/api/run", json={"mode": "none", "flies": 1, "seed": seed}
        ).json()
    assert len(runs) == 6
    response = client.post(
        "/api/intervention",
        json={"run_id": result["id"], "fly": 0, "step": 1, "point_id": 1},
    )
    assert response.status_code == 422
    assert not run_lock.locked()
