"""Build one portable replay and the same editable workshop used on stage."""

import base64
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .scene import ROOT, simulate

STATIC = Path(__file__).parent / "static"


def computation_hash():
    files = [ROOT / "fly_brain.py", ROOT / "uv.lock"]
    files += sorted(Path(__file__).parent.glob("*.py"))
    files += sorted((Path(__file__).parent / "neural").glob("*.ts"))
    files += [
        Path(__file__).parent / "data" / name
        for name in ("graph.bin.gz", "neurons.bin.gz", "meta.json")
    ]
    return hashlib.sha256(b"".join(p.read_bytes() for p in files)).hexdigest()


def recordings():
    target = ROOT / "artifacts/escape-runs.json"
    digest = computation_hash()
    if target.exists():
        cached = json.loads(target.read_text())
        if cached.get("computation_hash") == digest:
            return cached
    runs = [
        simulate(mode=mode, reference=True) for mode in ("none", "personal", "shared")
    ]
    controls = {}
    for mode in ("none", "personal", "shared"):
        for control in ("no_replay", "no_motor"):
            controls[f"{mode}:{control}"] = simulate(
                mode=mode, reference=True, control=control
            )
    data = {
        "computation_hash": digest,
        "runs": runs,
        "controls": controls,
        "groups": json.loads((STATIC / "brain-groups.json").read_text()),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, separators=(",", ":")))
    return data


def export():
    target = ROOT / "artifacts/delivery"
    target.mkdir(parents=True, exist_ok=True)
    pdf = ROOT / "_maintainer/slides.pdf"
    if not pdf.exists():
        raise RuntimeError(
            "Export the current native deck to _maintainer/slides.pdf first."
        )
    data = recordings()
    data["positions_b64"] = base64.b64encode(
        (STATIC / "brain-positions.bin").read_bytes()
    ).decode()

    def uri(name):
        mime = "image/svg+xml" if name.endswith("svg") else "font/woff2"
        return (
            f"data:{mime};base64,"
            + base64.b64encode((STATIC / name).read_bytes()).decode()
        )

    html = (STATIC / "index.html").read_text()
    css = (
        (STATIC / "style.css")
        .read_text()
        .replace("/static/fonts/mona.woff2", uri("fonts/mona.woff2"))
    )
    html = re.sub(
        r'<link rel="stylesheet" href="/static/style.css">',
        lambda _: f"<style>{css}</style>",
        html,
    )
    html = html.replace("/static/qdrant-mark.svg", uri("qdrant-mark.svg"))
    html = html.replace(
        '<script src="/static/fly.js"></script>',
        "<script>" + (STATIC / "fly.js").read_text() + "</script>",
    )
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace(
        '<script src="/static/app.js"></script>',
        "<script>window.WORKSHOP_DATA="
        + payload
        + ";</script><script>"
        + (STATIC / "app.js").read_text()
        + "</script>",
    )
    if re.search(r'(?:src|href)="/static/', html):
        raise RuntimeError("The offline replay still depends on a server asset.")
    offline = target / "fly-memory-offline.html"
    offline.write_text(html)
    bundle = target / "fly-memory-workshop.zip"
    root_files = [
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
    included = []
    with ZipFile(bundle, "w", ZIP_DEFLATED) as archive:
        for name in root_files:
            archive.write(ROOT / name, f"fly-memory/{name}")
            included.append(name)
        for folder in ("_internal/escape", "_internal/tests", "_maintainer"):
            for path in sorted((ROOT / folder).rglob("*")):
                if not path.is_file() or any(
                    part in {"__pycache__", ".DS_Store"} for part in path.parts
                ):
                    continue
                if (
                    folder == "_maintainer"
                    and "assets" in path.parts
                    and path.name != "NOTICE.md"
                ):
                    continue
                name = str(path.relative_to(ROOT))
                archive.write(path, f"fly-memory/{name}")
                included.append(name)
        archive.write(offline, "fly-memory/fly-memory-offline.html")
    manifest = {
        "offline": offline.name,
        "workshop": bundle.name,
        "files": included,
        "seed": 2000,
        "world_hash": data["runs"][0]["world_hash"],
        "computation_hash": data["computation_hash"],
        "source": "Recorded live LIF computation and Qdrant Edge queries with completed code",
        "zip_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Offline replay: {offline}\nWorkshop download: {bundle}")
    return offline, bundle
