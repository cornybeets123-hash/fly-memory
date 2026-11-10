"""Build the recorded fallback and a clean copy of the workshop files."""

import base64
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from . import server

ROOT = Path(__file__).resolve().parents[2]
MAINTAINER = ROOT / "_maintainer"


def backup():
    previous = server.reference_mode
    server.reference_mode = True
    try:
        with TestClient(server.app) as client:
            runs = {}
            for mode in ("none", "personal", "shared"):
                response = client.post("/api/run", json={"mode": mode})
                response.raise_for_status()
                runs[f"{mode}:normal"] = response.json()
    finally:
        server.reference_mode = previous
    dataset = {
        "world": runs["none:normal"]["world"],
        "positions_b64": base64.b64encode(
            (ROOT / "_internal/assets/brain-positions.bin").read_bytes()
        ).decode(),
        "runs": runs,
    }
    html = (server.STATIC / "index.html").read_text()
    css = (server.STATIC / "style.css").read_text()
    font = base64.b64encode(
        (ROOT / "_internal/assets/fonts/mona.woff2").read_bytes()
    ).decode()
    css = css.replace("/assets/fonts/mona.woff2", f"data:font/woff2;base64,{font}")
    html = html.replace(
        '<link rel="stylesheet" href="/static/style.css">', f"<style>{css}</style>"
    )
    for name in ("qdrant-mark.svg",):
        encoded = base64.b64encode(
            (ROOT / f"_internal/assets/{name}").read_bytes()
        ).decode()
        html = html.replace(f"/assets/{name}", f"data:image/svg+xml;base64,{encoded}")
    html = html.replace(
        '<script src="/assets/fly.js"></script>',
        "<script>" + (ROOT / "_internal/assets/fly.js").read_text() + "</script>",
    )
    data = json.dumps(dataset, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace(
        '<script src="/static/app.js"></script>',
        f"<script>window.WORKSHOP_DATA={data};</script><script>"
        + (server.STATIC / "app.js").read_text()
        + "</script>",
    )
    output = MAINTAINER / "fly-memory-offline.html"
    output.write_text(html)
    evidence = ROOT / "artifacts/maze-slides/demo.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(runs))
    return output


def archive():
    output = ROOT / "artifacts/fly-memory-workshop.zip"
    files = [
        ROOT / name
        for name in (
            "README.md",
            "run.py",
            "memory.py",
            "pipeline.py",
            "fly_brain.py",
            "pyproject.toml",
            "uv.lock",
            ".python-version",
            "AGENTS.md",
        )
    ]
    for folder in (
        "_internal/maze",
        "_internal/brain",
        "_internal/assets",
        "_internal/tests",
        "_maintainer",
        ".vscode",
    ):
        files.extend(
            p
            for p in (ROOT / folder).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        )
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=6) as zipped:
        for file in sorted(set(files)):
            zipped.write(file, "fly-memory/" + str(file.relative_to(ROOT)))
    return output


def export():
    print(backup())
    print(archive())
