"""Exercise the real app path, including shared storage and saved-code refresh."""

from fastapi.testclient import TestClient

from _internal.maze import learner, server
from _maintainer.builds import completed_sources


def test_real_shared_shard_and_repeated_runs():
    server.reference_mode = True
    try:
        with TestClient(server.app) as client:
            direct = client.post("/api/run", json={"mode": "personal"})
            assert direct.status_code == 200
            assert direct.json()["initial_memories"] == []
            assert client.post("/api/run", json={"mode": "invalid"}).status_code == 422
            for _ in range(2):
                first = client.post("/api/run", json={"mode": "none"})
                assert first.status_code == 200, first.text
                assert first.json()["hero"]["summary"]["returns"] >= 2
                assert not first.json()["hero"]["summary"]["exit"]
            personal = client.post("/api/run", json={"mode": "personal"})
            assert personal.status_code == 200, personal.text
            personal_data = personal.json()
            assert personal_data["initial_memories"] == []
            assert personal_data["hero"]["summary"]["returns"] == 1
            assert personal_data["hero"]["summary"]["exit"]
            own = [
                v["selected"]
                for d in personal_data["hero"]["decisions"]
                for v in d["views"]
                if v["applied"]
            ]
            assert own and all(h["payload"]["source_fly"] == "A" for h in own)
            common = server.attempts[305]["pool"][0]
            for _ in range(2):
                shared = client.post("/api/run", json={"mode": "shared"})
                assert shared.status_code == 200, shared.text
                data = shared.json()
                assert data["hero"]["summary"]["exit"]
                assert data["hero"]["summary"]["returns"] == 0
                assert data["ghost"]["summary"]["returns"] == 1
                assert server.attempts[305]["pool"][0] is common
                assert data["brain"]["neurons"] == 138639
                chosen = [
                    v["selected"]
                    for d in data["hero"]["decisions"]
                    for v in d["views"]
                    if v["selected"]
                ]
                assert chosen and all(h["payload"]["source_fly"] == "A" for h in chosen)
                assert {h["id"] for h in own} <= {h["id"] for h in chosen}
                assert data["hero"]["decisions"][0]["time"] < min(
                    e["time"] for e in data["hero"]["events"] if e["kind"] == "observed"
                )
            disconnected = client.post(
                "/api/run", json={"mode": "shared", "disconnect": True}
            ).json()
            assert not disconnected["hero"]["summary"]["exit"]
            assert disconnected["ghost"]["mode"] == "shared"
            assert disconnected["ghost"]["summary"]["exit"]
            assert disconnected["ghost"]["summary"]["time_ms"] < 21000
    finally:
        server.reference_mode = False


def test_starter_error_and_recovery():
    server.reference_mode = False
    with TestClient(server.app) as client:
        assert client.post("/api/run", json={"mode": "none"}).status_code == 200
        response = client.post("/api/run", json={"mode": "personal"})
        assert response.status_code == 500
        assert "recall() in memory.py" in response.json()["detail"]
        assert client.post("/api/run", json={"mode": "none"}).status_code == 200


def test_saved_files_reload_without_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(learner, "ROOT", tmp_path)
    (tmp_path / "pipeline.py").write_text("def scope(*a, **kw): return 'eligible'\n")
    source = (
        "def remember(*a): pass\ndef decide(*a): pass\ndef recall(*a): return VALUE\n"
    )
    (tmp_path / "memory.py").write_text(source.replace("VALUE", "1"))
    assert learner.load().recall(None, [1], "world") == 1
    (tmp_path / "memory.py").write_text(source.replace("VALUE", "2"))
    assert learner.load().recall(None, [1], "world") == 2


def test_the_presenter_code_runs_end_to_end(tmp_path, monkeypatch):
    from _internal.maze.checks import check

    for name, source in completed_sources().items():
        (tmp_path / f"{name}.py").write_text(source)
    monkeypatch.setattr(learner, "ROOT", tmp_path)
    assert check("shared", reference=False) == "Shared memory passed."


def test_group_ownership_and_frozen_shared_pool():
    server.reference_mode = True
    try:
        with TestClient(server.app) as client:
            stages = {}
            for mode in ("none", "personal", "shared"):
                response = client.post(
                    "/api/run", json={"mode": mode, "seed": 305, "count": 2}
                )
                assert response.status_code == 200, response.text
                stages[mode] = response.json()
                data = stages[mode]
                assert data["cohort"]["seeds"] == [305, 306]
                assert len(data["flies"]) == 2
                for fly in data["flies"]:
                    for decision in fly["decisions"]:
                        for view in decision["views"]:
                            if mode == "none":
                                assert view["search_ms"] is None
                            elif view["vector"] is not None:
                                assert view["search_ms"] >= 0
                            for hit in view["hits"]:
                                assert (
                                    hit["payload"]["source_fly"] == fly["owner"]
                                    if mode == "personal"
                                    else hit["payload"]["source_fly"].startswith("A")
                                )
            assert [f["owner"] for f in stages["personal"]["flies"]] == ["A1", "A2"]
            assert [f["owner"] for f in stages["shared"]["flies"]] == ["B1", "B2"]
            assert len(stages["shared"]["initial_memories"]) == sum(
                len(f["observations"]) for f in stages["personal"]["flies"]
            )
            assert (
                stages["personal"]["comparisons"][0]["summary"]
                == stages["none"]["flies"][0]["summary"]
            )
            assert (
                stages["shared"]["comparisons"][0]["summary"]
                == stages["personal"]["flies"][0]["summary"]
            )
            repeated = client.post(
                "/api/run", json={"mode": "shared", "seed": 305, "count": 2}
            ).json()
            assert (
                repeated["cohort"]["summary"] == stages["shared"]["cohort"]["summary"]
            )
    finally:
        server.reference_mode = False
