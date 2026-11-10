"""Download and verify the pinned upstream model for optional live computation."""

import hashlib
import subprocess

from .brain import ROOT, RecordedBrain


def setup_brain():
    bank = RecordedBrain()
    directory = ROOT / "brain"
    if not directory.exists():
        subprocess.run(
            [
                "git",
                "clone",
                "https://github.com/philshiu/Drosophila_brain_model",
                str(directory),
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(directory),
                "checkout",
                bank.data["provenance"]["upstream_sha"],
            ],
            check=True,
        )
    for item in bank.data["provenance"]["files"]:
        if item["path"].startswith("brain/"):
            path = ROOT / item["path"]
            if (
                not path.exists()
                or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]
            ):
                raise RuntimeError(
                    f"Source checksum differs: {path}. Existing files were preserved."
                )
    print("Pinned brain source and connectome checksums verified.")
