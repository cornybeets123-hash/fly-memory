"""Local presenter service. Every run recomputes neural activity and Qdrant queries."""

from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams

from . import learner, memory
from .kernel import Kernel
from .presentation import pack, record, scene
from .simulation import run
from .workshop_world import WorkshopWorld as World

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).with_name("static")
lock = Lock()
attempts = OrderedDict()
worker = None
reference_mode = False


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
    seed: int = Field(default=2000, ge=0, le=1_000_000)
    disconnect: bool = False


def kernel():
    global worker
    if worker is None:
        worker = Kernel()
    return worker


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    return {
        "world": scene(World()),
        "ready": True,
        "source": "Computed now",
        "protocol": "maze-display-v1",
        "code": "Completed code" if reference_mode else "Your code",
    }


@app.post("/api/run")
def compute(request: Request):
    global worker
    if not lock.acquire(blocking=False):
        raise HTTPException(409, "A neural run is already being computed.")
    try:
        model, world = kernel(), World()
        state = attempts.setdefault(request.seed, {})
        attempts.move_to_end(request.seed)
        while len(attempts) > 3:
            _, removed = attempts.popitem(last=False)
            clear_pool(removed)
        if request.mode == "none":
            history, variant, duration = [], 0, 45
        elif request.mode == "personal":
            if "none" not in state:
                raise HTTPException(409, "Run No memory first.")
            history, variant, duration = [], 0, 45
        else:
            if "personal" not in state:
                raise HTTPException(
                    409, "Run Personal memory before sharing its experience."
                )
            history = state["personal"]["episodes"]
            variant, duration = 0, 45
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
