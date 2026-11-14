"""Prepare real matched trials in bounded groups, and serve their recorded evidence."""

import argparse
import base64
import gzip
import hashlib
import json
import os
import signal
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from time import perf_counter

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams, Point

from . import cohort, memory
from .cohort_evaluate import audit
from .kernel import Kernel
from .presentation import pack, record
from .simulation import Episode
from .webinar_evaluate import OUTCOMES
from .webinar_world import WebinarWorld
from .workshop_evaluate import capture_frame, freeze, place

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "_internal/artifacts/webinar-hive"
MODES = ("none", "personal", "shared")
router = APIRouter(prefix="/api/hive")
_job = None
_job_lock = Lock()
_worker_kernel = None
_worker_world = None
_worker_history = None
_worker_shard = None


def signature(count=1000, seed=50000):
    return hashlib.sha256(
        json.dumps(
            {
                "source": freeze(),
                "count": count,
                "seed": seed,
                "world": WebinarWorld.id,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, separators=(",", ":")))
    temporary.replace(path)


def read_json(path):
    return json.loads(path.read_text())


def save_gzip(path, data):
    temporary = path.with_suffix(".tmp")
    with gzip.open(temporary, "wt") as output:
        json.dump(data, output, separators=(",", ":"))
    temporary.replace(path)


def read_gzip(path):
    with gzip.open(path, "rt") as source:
        return json.load(source)


def serialized_episode(episode):
    return {
        "id": str(episode.point.id),
        "vector": episode.point.vector,
        "payload": episode.point.payload,
        "pixels": base64.b64encode(episode.image.tobytes()).decode(),
    }


def restored_episode(item):
    image = np.frombuffer(base64.b64decode(item["pixels"]), dtype=np.uint8).reshape(
        64, 64, 3
    )
    return Episode(Point(int(item["id"]), item["vector"], item["payload"]), image)


def close_worker():
    if _worker_shard is not None:
        _worker_shard.close()
    if _worker_kernel is not None:
        _worker_kernel.close()


def initialize_worker():
    from multiprocessing.util import Finalize

    global _worker_kernel, _worker_world
    _worker_kernel, _worker_world = Kernel(), WebinarWorld()
    Finalize(None, close_worker, exitpriority=10)


def run_batch(mode, offset, seeds, directory):
    """One worker advances a small group. Personal stores remain owner-filtered."""
    from tempfile import TemporaryDirectory

    global _worker_history, _worker_shard
    directory = Path(directory)
    history, source_atlas = [], {}
    if mode == "shared":
        if _worker_history is None:
            _worker_history = [
                restored_episode(e) for e in read_gzip(directory / "pool.json.gz")
            ]
            location = directory / f"edge-{os.getpid()}"
            location.mkdir(exist_ok=True)
            _worker_shard = EdgeShard.create(
                str(location),
                EdgeConfig(
                    vectors={
                        "view": EdgeVectorParams(size=192, distance=Distance.Cosine)
                    }
                ),
            )
            for episode in _worker_history:
                memory.remember(_worker_shard, episode.point)
        history = _worker_history
        source_atlas = {
            int(k): tuple(v) for k, v in read_json(directory / "atlas.json").items()
        }
    with TemporaryDirectory(prefix="webinar-batch-") as temporary:
        path = Path(temporary) / "edge"
        path.mkdir()
        shard = (
            _worker_shard
            if mode == "shared"
            else EdgeShard.create(
                str(path),
                EdgeConfig(
                    vectors={
                        "view": EdgeVectorParams(size=192, distance=Distance.Cosine)
                    }
                ),
            )
        )
        try:
            results = cohort.simulate(
                _worker_kernel,
                _worker_world,
                mode,
                seeds,
                memory,
                shard,
                history=history,
                owner_offset=offset,
                history_loaded=mode == "shared",
            )
            checked = audit({mode: results}, _worker_world, OUTCOMES, source_atlas)
            atlas, episodes, movements = {}, [], []
            for i, result in enumerate(results):
                decisions = {
                    d.get("capture_time", d["time"]): d for d in result["decisions"]
                }
                for episode in result["episodes"]:
                    payload = episode.point.payload
                    event = next(
                        e
                        for e in result["events"]
                        if e["kind"] == "observed"
                        and e["observed_at_ms"] == payload["observed_at_ms"]
                    )
                    capture = payload["captured_at_ms"] - (
                        payload["observed_at_ms"] - event["time"]
                    )
                    decision = decisions[capture]
                    view = decision["views"][decision["choice"]]
                    atlas[str(episode.point.id)] = place(
                        _worker_world, capture_frame(result, decision), view, OUTCOMES
                    )
                    if mode == "personal":
                        episodes.append(serialized_episode(episode))
                packed = pack(result, _worker_world)
                captures = {
                    d.get("capture_time", d["time"]) for d in result["decisions"]
                }
                captures.update(d["time"] for d in result["decisions"])
                packed["frames"] = [
                    f
                    for f in packed["frames"]
                    if f["ms"] % 100 == 0
                    or f["ms"] in captures
                    or f is packed["frames"][-1]
                ]
                save_gzip(directory / f"{mode}-{offset + i}.json.gz", packed)
                movement = cohort.movement(result)
                movement["frames"] = [
                    f
                    for f in movement["frames"]
                    if f["ms"] % 200 == 0 or f is movement["frames"][-1]
                ]
                movements.append(movement)
            batch = {
                "brain": _worker_kernel.info,
                "offset": offset,
                "movements": movements,
                "atlas": atlas,
                "episodes": episodes,
                "audit": checked,
            }
            save_gzip(directory / f"batch-{mode}-{offset}.json.gz", batch)
            return offset
        finally:
            if mode != "shared":
                shard.close()


def aggregate(rows):
    size = len(rows)
    return {
        "count": size,
        "exited": sum(r["summary"]["exit"] for r in rows),
        "mean_time_ms": sum(r["summary"]["time_ms"] for r in rows) / size,
        "mean_path": sum(r["summary"]["path"] for r in rows) / size,
        "returns": sum(r["summary"]["returns"] for r in rows),
        "dead_ends": sum(r["summary"]["detours"] for r in rows),
        "collisions": sum(r["summary"]["collisions"] for r in rows),
    }


def prepare(directory=DIRECTORY, count=1000, seed=50000, workers=8):
    """Resume completed groups only when their code and declared seeds match."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    status_path = directory / "status.json"
    fingerprint = signature(count, seed)
    if status_path.exists() and read_json(status_path).get("signature") != fingerprint:
        raise ValueError(
            "Recorded trials use different source code. Choose a new output directory or archive the old one."
        )
    started = perf_counter()
    state = {
        "pid": os.getpid(),
        "signature": fingerprint,
        "count": count,
        "seed": seed,
        "done": 0,
        "total": count * 3,
        "state": "computing",
        "mode": "none",
        "ready": [],
        "summary": {},
        "world": WebinarWorld.id,
        "deadline_seconds": WebinarWorld.deadline,
        "source": freeze(),
        "errors": [],
        "workers": workers,
    }
    write_json(status_path, state)
    chunks = [
        (offset, list(range(seed + offset, seed + min(offset + 8, count))))
        for offset in range(0, count, 8)
    ]
    try:
        with ProcessPoolExecutor(
            max_workers=workers, initializer=initialize_worker
        ) as executor:
            for mode in MODES:
                state["mode"] = mode
                completed = {
                    offset
                    for offset, _ in chunks
                    if (directory / f"batch-{mode}-{offset}.json.gz").exists()
                }
                state["done"] += sum(
                    len(seeds) for offset, seeds in chunks if offset in completed
                )
                write_json(status_path, state)
                futures = [
                    executor.submit(run_batch, mode, offset, seeds, str(directory))
                    for offset, seeds in chunks
                    if offset not in completed
                ]
                for future in as_completed(futures):
                    offset = future.result()
                    state["done"] += min(8, count - offset)
                    state["wall_seconds"] = round(perf_counter() - started, 1)
                    write_json(status_path, state)
                    print(
                        json.dumps(
                            {
                                k: state[k]
                                for k in ("mode", "done", "total", "wall_seconds")
                            }
                        ),
                        flush=True,
                    )
                batches = [
                    read_gzip(directory / f"batch-{mode}-{offset}.json.gz")
                    for offset, _ in chunks
                ]
                rows = [r for batch in batches for r in batch["movements"]]
                errors = [e for batch in batches for e in batch["audit"]["errors"]]
                state["errors"].extend(f"{mode}: {e}" for e in errors)
                state["summary"][mode] = aggregate(rows)
                state["summary"][mode]["false_exclusions"] = sum(
                    b["audit"]["false_exclusions"] for b in batches
                )
                state["summary"][mode]["memory_uses"] = sum(
                    b["audit"]["memory_uses"] for b in batches
                )
                state["summary"][mode]["queries"] = sum(
                    b["audit"]["query_count"] for b in batches
                )
                if mode == "personal":
                    save_gzip(
                        directory / "pool.json.gz",
                        [e for b in batches for e in b["episodes"]],
                    )
                    write_json(
                        directory / "atlas.json",
                        {k: v for b in batches for k, v in b["atlas"].items()},
                    )
                    state["memory_count"] = sum(len(b["episodes"]) for b in batches)
                write_json(
                    directory / f"{mode}.json",
                    {
                        "mode": mode,
                        "flies": rows,
                        "summary": state["summary"][mode],
                        "audit_errors": errors,
                        "brain": batches[0]["brain"],
                    },
                )
                state["ready"].append(mode)
                write_json(status_path, state)
        state["state"] = "ready" if not state["errors"] else "audit_failed"
        state["wall_seconds"] = round(perf_counter() - started, 1)
        write_json(status_path, state)
        return state
    except BaseException as error:
        state.update(state="failed", detail=str(error))
        write_json(status_path, state)
        raise


@router.get("/status")
def status():
    path = DIRECTORY / "status.json"
    if not path.exists():
        return {
            "state": "missing",
            "count": 1000,
            "done": 0,
            "total": 3000,
            "ready": [],
        }
    result = read_json(path)
    if result.get("signature") != signature():
        return {**result, "state": "stale", "ready": []}
    if result.get("state") == "computing":
        try:
            os.kill(result["pid"], 0)
        except (KeyError, ProcessLookupError):
            result["state"] = "interrupted"
    return {k: v for k, v in result.items() if k != "source"}


@router.post("/prepare")
def launch():
    global _job
    with _job_lock:
        if _job is not None and _job.poll() is None:
            return status()
        current = status()
        if current["state"] == "computing":
            return current
        if current["state"] in {"ready", "stale", "audit_failed"}:
            if current["state"] != "ready":
                raise HTTPException(
                    409,
                    "Archive the earlier hive artifacts before preparing this version.",
                )
            return current
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        with (DIRECTORY / "compute.log").open("a") as log:
            _job = subprocess.Popen(
                [sys.executable, "-m", "_internal.maze.webinar_population"],
                cwd=ROOT,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        return {**current, "state": "starting"}


@router.post("/cancel")
def cancel():
    with _job_lock:
        if _job is not None and _job.poll() is None:
            os.killpg(_job.pid, signal.SIGTERM)
            current = status()
            current.update(state="cancelled")
            write_json(DIRECTORY / "status.json", current)
    return status()


def available(mode):
    if mode not in MODES:
        raise HTTPException(404, "Unknown memory condition.")
    current = status()
    if mode not in current["ready"]:
        raise HTTPException(409, "This condition has not finished computing.")
    return current


@router.get("/{mode}/fly/{index}")
def detail(mode: str, index: int):
    current = available(mode)
    if not 0 <= index < current["count"]:
        raise HTTPException(404, "Unknown fly.")
    result = read_gzip(DIRECTORY / f"{mode}-{index}.json.gz")
    observations = []
    if mode == "shared":
        ids = {
            hit["id"]
            for d in result["decisions"]
            for v in d["views"]
            for hit in v["hits"]
        }
        observations = [
            record(restored_episode(e))
            for e in read_gzip(DIRECTORY / "pool.json.gz")
            if e["id"] in ids
        ]
    return {"run": result, "initial_memories": observations}


@router.get("/{mode}")
def overview(mode: str):
    available(mode)
    return FileResponse(DIRECTORY / f"{mode}.json", media_type="application/json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=50000)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, default=DIRECTORY)
    args = parser.parse_args()
    if (
        not 1 <= args.count <= 1000
        or not 1 <= args.workers <= 8
        or not 0 <= args.seed <= 1000000 - args.count
    ):
        parser.error("Use 1–1000 flies, 1–8 workers, and seeds within 0–1000000.")
    result = prepare(args.output, args.count, args.seed, args.workers)
    raise SystemExit(0 if result["state"] == "ready" else 1)
