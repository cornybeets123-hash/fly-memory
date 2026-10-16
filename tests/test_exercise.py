import sys

import pytest

from workshop.__main__ import main


def test_cli_evaluation_runs_participant_hooks_in_exercise_mode(monkeypatch, tmp_path):
    from workshop import student_memory

    def unfinished(*args):
        raise NotImplementedError("student_memory.store is unfinished")

    monkeypatch.setattr(student_memory, "store", unfinished)
    monkeypatch.setenv("WORKSHOP_EXERCISE", "1")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "workshop",
            "evaluate",
            "--modes",
            "balanced",
            "--seeds",
            "2000",
            "--output",
            str(tmp_path / "evaluation.json"),
        ],
    )
    with pytest.raises(NotImplementedError, match="student_memory"):
        main()
