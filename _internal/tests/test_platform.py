"""Cross-platform helpers: Node version gate and line-ending digests."""

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
