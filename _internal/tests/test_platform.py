"""Cross-platform helpers: Node version gate, line-ending digests, job control."""

import pytest

from _internal.maze import kernel


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("v20.17.0\n", False),
        ("v22.17.9", False),
        ("v22.18.0", True),
        ("v26.13.1", True),
        ("", False),
        ("garbage", False),
    ],
)
def test_node_version_gate(text, ok):
    assert kernel.node_version_ok(text) is ok


def test_old_node_fails_with_a_clear_message(monkeypatch):
    monkeypatch.setattr(kernel.shutil, "which", lambda name: "node")

    class Done:
        stdout = "v20.17.0\n"

    monkeypatch.setattr(kernel.subprocess, "run", lambda *a, **k: Done())
    with pytest.raises(RuntimeError, match=r"22\.18.*v20\.17\.0"):
        kernel.find_node()


def test_digest_ignores_line_endings_for_text_only(tmp_path):
    from _internal.maze.workshop_evaluate import file_digest

    lf, crlf = tmp_path / "a.py", tmp_path / "b.py"
    lf.write_bytes(b"x = 1\ny = 2\n")
    crlf.write_bytes(b"x = 1\r\ny = 2\r\n")
    assert file_digest(lf) == file_digest(crlf)
    first, second = tmp_path / "a.gz", tmp_path / "b.gz"
    first.write_bytes(b"a\nb")
    second.write_bytes(b"a\r\nb")
    assert file_digest(first) != file_digest(second)


def test_process_alive_and_tree_termination():
    import subprocess
    import sys

    from _internal.maze import jobs

    child = jobs.launch_group(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert jobs.process_alive(child.pid)
        assert jobs.terminate_tree(child.pid)
        child.wait(timeout=10)
        assert jobs.wait_gone(child.pid)
    finally:
        if child.poll() is None:
            child.kill()


def test_dead_pid_is_not_alive():
    import subprocess
    import sys

    from _internal.maze import jobs

    done = subprocess.run([sys.executable, "-c", "pass"], check=True)
    assert done.returncode == 0
    finished = subprocess.Popen([sys.executable, "-c", "pass"])
    finished.wait()
    assert not jobs.process_alive(finished.pid)


def test_heartbeat_staleness(tmp_path):
    import os
    import time

    from _internal.maze import jobs

    beat = tmp_path / "heartbeat"
    assert not jobs.heartbeat_stale(beat)  # absent: fall back to the PID check
    beat.write_text("x", encoding="utf-8")
    assert not jobs.heartbeat_stale(beat)
    old = time.time() - 600
    os.utime(beat, (old, old))
    assert jobs.heartbeat_stale(beat)


def test_replace_file_retries_then_succeeds(tmp_path, monkeypatch):
    from pathlib import Path

    from _internal.maze import jobs

    source, target = tmp_path / "a.tmp", tmp_path / "a"
    source.write_text("new", encoding="utf-8")
    real, calls = Path.replace, []

    def flaky(self, destination):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError
        return real(self, destination)

    monkeypatch.setattr(Path, "replace", flaky)
    jobs.replace_file(source, target)
    assert target.read_text(encoding="utf-8") == "new" and len(calls) == 3
