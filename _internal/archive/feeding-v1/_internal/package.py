"""Build one offline replay and one download containing the same workshop files."""

import base64
import inspect
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from . import answers
from .experiment import ROOT, compare, probe


def export():
    target = ROOT / "artifacts/delivery"
    target.mkdir(parents=True, exist_ok=True)
    if not (ROOT / "_maintainer/slides.pdf").is_file():
        raise RuntimeError(
            "Save the current deck as _maintainer/slides.pdf before packaging."
        )
    static = Path(__file__).parent / "static"
    runs = compare()
    probes = {}
    for run in runs:
        for chapter in run["chapters"]:
            event = chapter["event"]
            if not event["hits"]:
                continue
            hit = max(event["hits"], key=lambda h: h["score"])
            probes[f"{run['mode']}:{event['tick']}:{event['fly']}"] = probe(
                run, event, exclude_ids=[hit["id"]]
            )
    lessons = {}
    for stage, names, file, instruction in [
        (
            "personal",
            ("remember", "recall", "decide"),
            "memory.py",
            "Store an observation. Retrieve similar warnings. Use the strongest match.",
        ),
        (
            "shared",
            ("retrieve", "observe"),
            "pipeline.py",
            "Query other flies' memories. Publish observed meals.",
        ),
    ]:
        lessons[stage] = {
            "file": file,
            "instruction": instruction,
            "check": f"uv run run.py --check {stage}",
            "code": "\n\n".join(
                inspect.getsource(getattr(answers, name)) for name in names
            ),
        }
    data = {"runs": runs, "probes": probes, "lessons": lessons}

    def uri(name):
        mime = "image/svg+xml" if name.endswith("svg") else "font/woff2"
        return (
            f"data:{mime};base64,"
            + base64.b64encode((static / name).read_bytes()).decode()
        )

    html = (static / "index.html").read_text()
    css = (
        (static / "style.css")
        .read_text()
        .replace("/static/fonts/mona.woff2", uri("fonts/mona.woff2"))
    )
    html = re.sub(
        r'<link\b[^>]*href="/static/style\.css"[^>]*>',
        lambda _: f"<style>{css}</style>",
        html,
    )
    html = html.replace("/static/qdrant.svg", uri("qdrant.svg")).replace(
        "/static/qdrant-mark.svg", uri("qdrant-mark.svg")
    )
    html = html.replace(
        '<script src="/static/fly.js"></script>',
        "<script>" + (static / "fly.js").read_text() + "</script>",
    )
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace(
        '<script src="/static/app.js"></script>',
        "<script>window.WORKSHOP_DATA="
        + payload
        + ";</script><script>"
        + (static / "app.js").read_text()
        + "</script>",
    )
    if re.search(r'(?:src|href)="/static/', html):
        raise RuntimeError("An offline asset still requires the server.")
    offline = target / "fly-memory-offline.html"
    offline.write_text(html)
    bundle = target / "fly-memory-workshop.zip"
    included = [
        "README.md",
        "AGENTS.md",
        "run.py",
        "fly_brain.py",
        "memory.py",
        "pipeline.py",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".vscode/settings.json",
    ]
    with ZipFile(bundle, "w", ZIP_DEFLATED) as archive:
        for name in included:
            archive.write(ROOT / name, f"fly-memory/{name}")
        for folder in ("_internal", "_maintainer"):
            for path in sorted((ROOT / folder).rglob("*")):
                if not path.is_file() or any(
                    p in {"archive", "__pycache__", ".DS_Store"} for p in path.parts
                ):
                    continue
                if (
                    folder == "_maintainer"
                    and "assets" in path.relative_to(ROOT / folder).parts
                    and path.name != "NOTICE.md"
                ):
                    continue
                archive.write(path, "fly-memory/" + str(path.relative_to(ROOT)))
        archive.write(offline, "fly-memory/fly-memory-offline.html")
    (target / "manifest.json").write_text(
        json.dumps(
            {
                "offline": offline.name,
                "workshop": bundle.name,
                "seed": runs[0]["config"]["seed"],
                "world_hash": runs[0]["world_hash"],
                "source": "Computed neural replay with completed retrieval code",
                "files": included,
                "probe_count": len(probes),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Offline replay: {offline}\nWorkshop download: {bundle}")
    return offline, bundle
