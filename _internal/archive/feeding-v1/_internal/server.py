"""Local presentation service. All simulation work stays in this process."""

import hashlib
import inspect
import json
import traceback
from collections import OrderedDict
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import answers
from .experiment import ROOT, Config, World, probe, simulate

app = FastAPI(title="Fly memory", docs_url=None, redoc_url=None)
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")
reference_mode = False
cache = OrderedDict()
run_lock = Lock()


class Request(BaseModel):
    mode: str = Field(default="none", pattern="^(none|personal|shared)$")
    seed: int = Field(default=2000, ge=0, le=1_000_000)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    return {
        "reference": reference_mode,
        "code": "Completed code" if reference_mode else "Your code",
        "brain": "Recorded neural trials",
        "engine": "Qdrant Edge",
        "ready": True,
    }


def code_error(error):
    frames = [
        f
        for f in traceback.extract_tb(error.__traceback__)
        if Path(f.filename).name in {"memory.py", "pipeline.py"}
    ]
    location = (
        f"{Path(frames[-1].filename).name}, line {frames[-1].lineno}: "
        if frames
        else ""
    )
    if isinstance(error, SyntaxError):
        location = f"{Path(error.filename).name}, line {error.lineno}: "
    return HTTPException(422, f"{location}{type(error).__name__}: {str(error)[:360]}")


@app.post("/api/run")
def run(request: Request):
    if not run_lock.acquire(blocking=False):
        raise HTTPException(409, "The experiment is running. Please wait.")
    try:
        digest = hashlib.sha256(
            b"".join((ROOT / f).read_bytes() for f in ("memory.py", "pipeline.py"))
        ).hexdigest()
        cfg = Config(seed=request.seed)
        world = World(cfg)
        modes = (
            ("none",)
            if request.mode == "none"
            else ("none", "personal")
            if request.mode == "personal"
            else ("personal", "shared")
        )
        results = []
        for mode in modes:
            key = (mode, request.seed, reference_mode, digest)
            if key not in cache:
                cache[key] = simulate(cfg, mode, reference=reference_mode, world=world)
            results.append(cache[key])
        while len(cache) > 12:
            cache.popitem(last=False)
        return {"runs": results, "mode": request.mode, "code": results[-1]["code"]}
    except NotImplementedError as error:
        raise HTTPException(501, str(error)) from error
    except SyntaxError as error:
        raise HTTPException(
            422, f"{Path(error.filename).name}, line {error.lineno}: {error.msg}"
        ) from error
    except Exception as error:
        if reference_mode:
            raise
        raise code_error(error) from error
    finally:
        run_lock.release()


@app.get("/api/lesson/{stage}")
def lesson(stage: str):
    if stage == "personal":
        return {
            "file": "memory.py",
            "instruction": "Store an observation. Retrieve similar warnings. Use the strongest match.",
            "code": "\n\n".join(
                inspect.getsource(getattr(answers, n))
                for n in ("remember", "recall", "decide")
            ),
            "check": "uv run run.py --check personal",
        }
    if stage == "shared":
        return {
            "file": "pipeline.py",
            "instruction": "Query other flies' memories. Publish observed meals.",
            "code": "\n\n".join(
                inspect.getsource(getattr(answers, n)) for n in ("retrieve", "observe")
            ),
            "check": "uv run run.py --check shared",
        }
    raise HTTPException(404, "Choose personal or shared memory.")


@app.post("/api/verify")
def verify(payload: dict):
    from .brain import RecordedBrain
    from .live import LiveProxy

    bitter = payload.get("bitter")
    seed = payload.get("seed")
    if bitter not in (0, 50, 100, 150, 200) or seed not in RecordedBrain().seeds:
        raise HTTPException(422, "Select an existing neural trial.")
    if not run_lock.acquire(blocking=False):
        raise HTTPException(409, "The experiment is running. Please wait.")
    proxy = LiveProxy(timeout=60)
    try:
        return proxy.response(bitter, seed)
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error
    finally:
        proxy.close()
        run_lock.release()


@app.get("/api/evaluation")
def evaluation():
    path = Path(__file__).parent / "data/evaluation.json"
    if not path.exists():
        raise HTTPException(404, "The evaluation has not been generated.")
    return json.loads(path.read_text())


class ProbeRequest(Request):
    tick: int = Field(ge=0, le=1200)
    fly: int = Field(ge=0, le=23)
    exclude_ids: list[int] = Field(default_factory=list, max_length=100)


@app.post("/api/probe")
def probe_decision(request: ProbeRequest):
    if not run_lock.acquire(blocking=False):
        raise HTTPException(409, "The experiment is running. Please wait.")
    try:
        digest = hashlib.sha256(
            b"".join((ROOT / f).read_bytes() for f in ("memory.py", "pipeline.py"))
        ).hexdigest()
        saved = cache.get((request.mode, request.seed, reference_mode, digest))
        if saved is None:
            raise HTTPException(
                409, "Run this stage again before inspecting its memory."
            )
        event = next(
            (
                e
                for e in saved["events"]
                if e["tick"] == request.tick and e["fly"] == request.fly
            ),
            None,
        )
        if event is None:
            raise HTTPException(404, "This contact does not exist.")
        return probe(
            saved, event, reference=reference_mode, exclude_ids=request.exclude_ids
        )
    except HTTPException:
        raise
    except Exception as error:
        raise code_error(error) from error
    finally:
        run_lock.release()
