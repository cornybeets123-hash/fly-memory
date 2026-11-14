"""Local presenter service. Every run recomputes neural activity and Qdrant queries."""

import json
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Literal

import anyio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams
from starlette.concurrency import run_in_threadpool

from . import cohort, learner, memory
from .kernel import Kernel
from .presentation import delta, pack, record, scene
from .simulation import run
from .workshop_world import WorkshopWorld as World

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).with_name("static")
lock = Lock()
attempts = OrderedDict()
worker = None
reference_mode = False
webinar_mode = False
progress = {"done": 0, "total": 0}


def clear_pool(state):
    pool = state.pop("pool", None)
    if pool:
        pool[0].close()
        pool[1].cleanup()


def memory_shard(state):
    if "pool" not in state:
        directory = TemporaryDirectory(prefix="fly-shared-memory-")
        location = Path(directory.name) / "qdrant"
        location.mkdir()
        shard = EdgeShard.create(
            str(location),
            EdgeConfig(
                vectors={"view": EdgeVectorParams(size=192, distance=Distance.Cosine)}
            ),
        )
        state["pool"] = shard, directory
    return state["pool"][0]


@asynccontextmanager
async def lifespan(app):
    global worker
    yield
    for state in attempts.values():
        clear_pool(state)
    if worker is not None:
        worker.close()
        worker = None
    attempts.clear()


app = FastAPI(title="Find the exit", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/assets", StaticFiles(directory=ROOT / "_internal/assets"), name="assets")


class Request(BaseModel):
    mode: Literal["none", "personal", "shared"] = "none"
    seed: int = Field(default=305, ge=0, le=1_000_000)
    disconnect: bool = False
    count: int = Field(default=1, ge=1, le=cohort.SIZE)


def kernel():
    global worker
    if worker is None:
        worker = Kernel()
    return worker


@app.get("/")
def index():
    return FileResponse(STATIC / ("webinar.html" if webinar_mode else "index.html"))


@app.get("/api/status")
def status():
    return {
        "world": scene(World()),
        "ready": True,
        "source": "Computed now",
        "protocol": "maze-display-v1",
        "code": "Completed code" if reference_mode else "Your code",
        "group_size": cohort.SIZE,
        "default_seed": cohort.DEFAULT_SEED,
        "webinar": webinar_mode,
        "deadline_ms": getattr(World, "deadline", cohort.DEADLINE) * 1000,
    }


@app.post("/api/run")
def compute(request: Request):
    global worker
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "A neural run is already being computed.")
    try:
        model, world = kernel(), World()
        key = request.seed if request.count == 1 else (request.seed, request.count)
        state = attempts.setdefault(key, {})
        attempts.move_to_end(key)
        while len(attempts) > 3:
            _, removed = attempts.popitem(last=False)
            clear_pool(removed)
        if request.count > 1:
            return compute_group(model, world, state, request)
        if request.mode in {"none", "personal"}:
            history, variant, duration = [], 0, getattr(world, "deadline", 65)
        else:
            if "personal" not in state:
                raise HTTPException(
                    409, "Run Personal memory before sharing its experience."
                )
            history = state["personal"]["episodes"]
            variant, duration = 0, getattr(world, "deadline", 65)
        backend = memory if reference_mode or request.mode == "none" else learner.load()
        common = None
        if request.mode != "none" and not request.disconnect:
            if request.mode == "personal":
                clear_pool(state)
            common = memory_shard(state)
        hero = run(
            model,
            world,
            seed=request.seed,
            mode=request.mode,
            history=history,
            duration=duration,
            pose_variant=variant,
            trace=True,
            control="mute" if request.disconnect else "normal",
            backend=backend,
            shard=common,
        )
        ghost = None
        if request.mode != "none" or request.disconnect:
            ghost = run(
                model,
                world,
                seed=request.seed,
                mode="personal"
                if request.mode == "shared" and not request.disconnect
                else request.mode,
                owner="B" if request.mode == "shared" else "A",
                history=history,
                duration=duration,
                pose_variant=variant,
                trace=True,
                control="normal"
                if request.disconnect or request.mode == "shared"
                else "no_memory",
                backend=backend,
            )
        if not request.disconnect:
            state[request.mode] = hero
            if request.mode == "none":
                clear_pool(state)
                state.pop("personal", None)
                state.pop("shared", None)
        return {
            "mode": request.mode,
            "hero": pack(hero, world),
            "ghost": pack(ghost, world) if ghost else None,
            "initial_memories": [record(e) for e in history],
            "world": scene(world),
            "brain": model.info,
            "source": "Computed now",
            "disconnect": request.disconnect,
            "code": "Completed code" if reference_mode else "Your code",
        }
    except HTTPException:
        raise
    except Exception as error:
        if worker is not None:
            worker.close()
            worker = None
        raise HTTPException(500, f"The run stopped: {error}") from error
    finally:
        lock.release()


@app.get("/api/progress")
def computation_progress():
    return progress


def prepare_group(state, request):
    """Use the same memory scopes for streamed and complete responses."""
    mode = request.mode
    progress.update(done=0, total=request.count)
    if mode == "shared" and "personal" not in state:
        raise HTTPException(
            409, "Run the Personal memory group before sharing its experience."
        )
    if mode in {"none", "personal"} and not request.disconnect:
        clear_pool(state)
        state.pop("shared", None)
        state.pop("personal", None)
    history = (
        [
            episode
            for result in state.get("personal", [])
            for episode in result["episodes"]
        ]
        if mode == "shared"
        else []
    )
    backend = memory if reference_mode or mode == "none" else learner.load()
    seeds = [(request.seed + i) % 1_000_001 for i in range(request.count)]
    return history, backend, seeds


def group_payload(model, world, state, request, history, seeds, results):
    mode = request.mode
    prior = "none" if mode == "personal" else "personal" if mode == "shared" else None
    if webinar_mode and mode == "shared":
        prior = "none"
    comparisons = (
        state.get(mode if request.disconnect else prior, [])
        if prior or request.disconnect
        else []
    )
    stages = {
        name: cohort.totals(state[name])
        for name in ("none", "personal", "shared")
        if name in state
    }
    if webinar_mode and stages:
        from .webinar_evaluate import summaries

        stages = summaries({name: state[name] for name in stages}, world)
    return {
        "mode": mode,
        "flies": [pack(result, world) for result in results],
        "comparisons": [cohort.movement(result) for result in comparisons],
        "initial_memories": [record(e) for e in history],
        "world": scene(world),
        "brain": model.info,
        "source": "Computed now",
        "disconnect": request.disconnect,
        "code": "Completed code" if reference_mode else "Your code",
        "comparison_mode": prior,
        "cohort": {
            "seeds": seeds,
            "deadline_ms": getattr(world, "deadline", cohort.DEADLINE) * 1000,
            "summary": (
                stages.get(mode) if not request.disconnect else cohort.totals(results)
            )
            if results
            else None,
            "stages": stages,
        },
    }


def compute_group(model, world, state, request):
    """Drain the same clock used by the live display."""
    mode = request.mode
    history, backend, seeds = prepare_group(state, request)
    results = cohort.simulate(
        model,
        world,
        mode,
        seeds,
        backend,
        memory_shard(state) if mode != "none" and not request.disconnect else None,
        history=history,
        disconnect=request.disconnect,
        progress=lambda done, total: progress.update(done=done, total=total),
    )
    if not request.disconnect:
        state[mode] = results
    return group_payload(model, world, state, request, history, seeds, results)


@app.post("/api/live")
def live(request: Request):
    """Stream actual frames and evidence for all flies, on one simulation clock."""
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "A neural run is already being computed.")
    try:
        model, world = kernel(), World()
        key = (request.seed, request.count)
        state = attempts.setdefault(key, {})
        attempts.move_to_end(key)
        while len(attempts) > 3:
            _, removed = attempts.popitem(last=False)
            clear_pool(removed)
        history, backend, seeds = prepare_group(state, request)
        shard = (
            memory_shard(state)
            if request.mode != "none" and not request.disconnect
            else None
        )
    except HTTPException:
        lock.release()
        raise
    except Exception as error:
        lock.release()
        raise HTTPException(500, f"The run stopped: {error}") from error

    def messages():
        global worker
        simulation = cohort.batches(
            model,
            world,
            request.mode,
            seeds,
            backend,
            shard,
            history=history,
            disconnect=request.disconnect,
            progress=lambda done, total: progress.update(done=done, total=total),
        )
        cursors = [{} for _ in seeds]
        completed = set()
        committed = False
        try:
            initial = group_payload(model, world, state, request, history, seeds, [])
            initial["flies"] = [
                {
                    "owner": f"{'B' if request.mode == 'shared' else 'A'}{i + 1}",
                    "seed": seed,
                    "mode": request.mode,
                    "summary": {
                        "time_ms": getattr(world, "deadline", cohort.DEADLINE) * 1000,
                        "exit": False,
                    },
                    "frames": [],
                    "decisions": [],
                    "events": [],
                    "observations": [],
                }
                for i, seed in enumerate(seeds)
            ]
            yield {"type": "begin", "data": initial}
            while True:
                try:
                    batch = next(simulation)
                except StopIteration as finished:
                    results = finished.value
                    break
                updates = []
                for i, result in enumerate(batch["flies"]):
                    update = {"index": i, **delta(result, world, cursors[i])}
                    if batch["completed"][i] is not None and i not in completed:
                        update["summary"] = batch["completed"][i]["summary"]
                        completed.add(i)
                    updates.append(update)
                yield {"type": "batch", "ms": batch["ms"], "flies": updates}
            if not request.disconnect:
                state[request.mode] = results
            committed = True
            measured = {
                name: cohort.totals(state[name])
                for name in ("none", "personal", "shared")
                if name in state
            }
            if webinar_mode and not request.disconnect:
                from .webinar_evaluate import summaries

                measured = summaries({name: state[name] for name in measured}, world)
            yield {
                "type": "complete",
                "summary": measured.get(request.mode, cohort.totals(results))
                if not request.disconnect
                else cohort.totals(results),
                "stages": measured,
            }
        except Exception as error:  # noqa: BLE001 - report saved-code failures in the stream
            try:
                simulation.close()
            except (RuntimeError, ValueError, OSError):
                pass  # A stopped worker cannot accept session cleanup requests.
            if worker is model:
                worker = None
                model.close()
            yield {"type": "error", "detail": f"The live run stopped: {error}"}
        finally:
            try:
                simulation.close()
            finally:
                if (
                    not committed
                    and request.mode == "personal"
                    and not request.disconnect
                ):
                    clear_pool(state)

    iterator = messages()
    sentinel = object()

    async def send():
        try:
            while True:
                message = await run_in_threadpool(next, iterator, sentinel)
                if message is sentinel:
                    break
                yield "data: " + json.dumps(message, separators=(",", ":")) + "\n\n"
        finally:
            with anyio.CancelScope(shield=True):
                try:
                    await run_in_threadpool(iterator.close)
                finally:
                    lock.release()

    return StreamingResponse(
        send(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
