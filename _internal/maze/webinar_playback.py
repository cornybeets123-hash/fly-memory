"""Serve intact recordings while retaining explicitly stopped attempts as failures."""

import hashlib
import json
import os
import shutil
import signal
from functools import lru_cache
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from . import webinar_population as producer
from .presentation import record

router = APIRouter(prefix="/api/hive")
export_lock = Lock()


def recording_sources_match(source):
    """A new playback reader does not invalidate unchanged simulation source files."""
    required = {
        "_internal/maze/simulation.py",
        "_internal/maze/cohort.py",
        "_internal/maze/neural.ts",
        "_internal/maze/webinar_world.py",
        "fly_brain.py",
    }
    if not required.issubset(source):
        return False
    stamps = []
    for name, digest in sorted(source.items()):
        if name == "_internal/maze/webinar_playback.py":
            continue  # This module only reads completed records. It never generates runs.
        path = (producer.ROOT / name).resolve()
        if not path.is_relative_to(producer.ROOT) or not path.is_file():
            return False
        stat = path.stat()
        stamps.append((str(path), digest, stat.st_mtime_ns, stat.st_size))
    return _hashes_match(tuple(stamps))


@lru_cache(maxsize=4)
def _hashes_match(stamps):
    return all(
        hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest
        for path, digest, _, _ in stamps
    )


def stopped_attempt(run):
    """Recognize an explicit safe stop, including its recorded terminal event."""
    summary = run["summary"]
    stops = [event for event in run["events"] if event["kind"] == "no_decision"]
    if (
        not summary["no_decision"]
        or summary["exit"]
        or summary["collisions"]
        or summary["longest_stall_s"] > 1
        or len(stops) != 1
    ):
        return None
    stop = stops[0]
    if stop.get("reason") not in {"ambiguous_options", "zero_readout"}:
        return None
    if abs(stop["time"] - summary["time_ms"]) > 20:
        return None
    if any(not decision.get("decision_readout") for decision in run["decisions"]):
        return None
    return {
        "fly": run["owner"],
        "seed": run["seed"],
        "reason": stop["reason"],
        "time_ms": summary["time_ms"],
    }


@lru_cache(maxsize=6)
def _review(path_string, modified_ns):
    path = Path(path_string)
    data = producer.read_json(path)
    blocking, failed = [], []
    rows = {
        f"{data['mode']}/{run['owner']}: movement failure": (i, run)
        for i, run in enumerate(data["flies"])
    }
    for error in data["audit_errors"]:
        row = rows.get(error)
        if row is not None:
            index, movement = row
            recorded = producer.read_gzip(
                path.parent / f"{data['mode']}-{index}.json.gz"
            )
            failure = stopped_attempt(recorded)
            if (
                failure is not None
                and recorded["summary"] == movement["summary"]
                and recorded["seed"] == movement["seed"]
            ):
                failed.append(failure)
                continue
        blocking.append(error)
    return {"evidence_errors": blocking, "behavior_failures": failed}


def review(mode):
    path = producer.DIRECTORY / f"{mode}.json"
    return _review(str(path), path.stat().st_mtime_ns)


@router.get("/status")
def status():
    path = producer.DIRECTORY / "status.json"
    if not path.exists():
        return {
            "state": "missing",
            "count": 1000,
            "done": 0,
            "total": 3000,
            "ready": [],
        }
    current = producer.read_json(path)
    if not recording_sources_match(current.get("source", {})):
        return {"state": "stale", "count": current["count"], "ready": []}
    current = {k: v for k, v in current.items() if k != "source"}
    reviews = {mode: review(mode) for mode in current["ready"]}
    current["evidence_errors"] = [
        error for r in reviews.values() for error in r["evidence_errors"]
    ]
    current["behavior_failures"] = {
        mode: r["behavior_failures"] for mode, r in reviews.items()
    }
    if current["state"] in {"ready", "audit_failed"} and not current["evidence_errors"]:
        current["state"] = (
            "ready_with_failures"
            if any(current["behavior_failures"].values())
            else "ready"
        )
    if current["state"] == "computing":
        try:
            os.kill(current["pid"], 0)
        except (KeyError, ProcessLookupError):
            current["state"] = "interrupted"
    return current


def available(mode):
    if mode not in producer.MODES:
        raise HTTPException(404, "Unknown memory condition.")
    current = status()
    if mode not in current["ready"]:
        raise HTTPException(409, "This condition has not finished computing.")
    checked = review(mode)
    if checked["evidence_errors"]:
        raise HTTPException(
            409, "Recorded evidence failed validation. Inspect the preparation log."
        )
    return current


@router.post("/prepare")
def prepare():
    current = status()
    if current["state"] in {"computing", "ready", "ready_with_failures"}:
        return current
    if current["state"] != "missing":
        raise HTTPException(
            409, "Archive the earlier hive artifacts before preparing this version."
        )
    return producer.launch()


@router.post("/cancel")
def cancel():
    current = status()
    if current["state"] == "computing":
        pid = current["pid"]
        if os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGTERM)
            original = producer.read_json(producer.DIRECTORY / "status.json")
            producer.write_json(
                producer.DIRECTORY / "status.json", {**original, "state": "cancelled"}
            )
    return status()


@router.get("/{mode}/fly/{index}")
def detail(mode: str, index: int):
    current = available(mode)
    if not 0 <= index < current["count"]:
        raise HTTPException(404, "Unknown fly.")
    run = producer.read_gzip(producer.DIRECTORY / f"{mode}-{index}.json.gz")
    observations = []
    if mode == "shared":
        ids = {
            hit["id"] for d in run["decisions"] for v in d["views"] for hit in v["hits"]
        }
        observations = [
            record(producer.restored_episode(e))
            for e in producer.read_gzip(producer.DIRECTORY / "pool.json.gz")
            if e["id"] in ids
        ]
    return {
        "run": run,
        "initial_memories": observations,
        "behavior_failure": stopped_attempt(run),
    }


@router.get("/{mode}")
def overview(mode: str):
    available(mode)
    original = producer.DIRECTORY / f"{mode}.json"
    checked = review(mode)
    output = producer.DIRECTORY / f"playback-{mode}.json"
    metadata = producer.DIRECTORY / f"playback-{mode}-review.json"
    stamp = {"modified_ns": original.stat().st_mtime_ns, "review": checked}
    # Stream the large recording directly. Add the classification to a separate copy.
    with export_lock:
        if (
            not output.exists()
            or not metadata.exists()
            or producer.read_json(metadata) != stamp
        ):
            temporary = output.with_suffix(".tmp")
            shutil.copyfile(original, temporary)
            with temporary.open("r+b") as stream:
                stream.seek(-1, os.SEEK_END)
                if stream.read(1) != b"}":
                    raise HTTPException(
                        409, "The recording has an unexpected JSON format."
                    )
                stream.seek(-1, os.SEEK_END)
                stream.write(
                    b"," + json.dumps(checked, separators=(",", ":")).encode()[1:]
                )
            temporary.replace(output)
            producer.write_json(metadata, stamp)
    return FileResponse(output, media_type="application/json")
