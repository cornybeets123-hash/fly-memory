"""Local-only presenter service. Recompile saved learner files on each run."""

import hashlib
import inspect
import traceback
from collections import OrderedDict
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import answers
from .scene import ROOT, Config, simulate

app = FastAPI(title="Borrowed instinct", docs_url=None, redoc_url=None)
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")
reference_mode = False
cache = OrderedDict()
run_lock = Lock()


class Request(BaseModel):
    mode: str = Field(default="none", pattern="^(none|personal|shared)$")
    seed: int = Field(default=2000, ge=0, le=1_000_000)
    control: str = Field(default="normal", pattern="^(normal|no_replay|no_motor)$")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    return {
        "code": "Completed code" if reference_mode else "Your code",
        "brain": "Live FlyWire v783 LIF computation",
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
        modes = ("none",) if request.mode == "none" else ("none", request.mode)
        results = []
        for mode in modes:
            control = request.control if mode == request.mode else "normal"
            key = (mode, request.seed, control, reference_mode, digest)
            if key not in cache:
                cache[key] = simulate(
                    Config(seed=request.seed), mode, reference_mode, control
                )
            results.append(cache[key])
        while len(cache) > 10:
            cache.popitem(last=False)
        return {"runs": results, "mode": request.mode, "code": results[-1]["code"]}
    except Exception as error:
        if reference_mode:
            raise
        raise code_error(error) from error
    finally:
        run_lock.release()


@app.get("/api/lesson/{stage}")
def lesson(stage: str):
    names = (
        ("remember", "recall", "decide")
        if stage == "personal"
        else ("retrieve", "observe")
    )
    if stage not in {"personal", "shared"}:
        raise HTTPException(404, "Choose personal or shared memory.")
    return {
        "file": "memory.py" if stage == "personal" else "pipeline.py",
        "code": "\n\n".join(inspect.getsource(getattr(answers, n)) for n in names),
        "check": f"uv run run.py --check {stage}",
    }
