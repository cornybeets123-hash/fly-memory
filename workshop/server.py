"""Local experiment service. Every query runs on a real Qdrant Edge shard."""

import logging
import os
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from workshop.brain import RecordedBrain
from workshop.live import LiveProxy
from workshop.senses import OdorSpace
from workshop.simulation import Config, intervention, run

app = FastAPI(title="Fly Memory · Qdrant Edge", docs_url="/api/docs")
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")
run_lock = Lock()
runs = OrderedDict()
_live_brain = None


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: int = Field(default=2000, ge=0, le=1_000_000)
    mode: str = Field(
        default="balanced", pattern="^(none|exact|harm|balanced|shuffled)$"
    )
    flies: int = Field(default=16, ge=1, le=16)
    encounters: int = Field(default=40, ge=12, le=80)
    threshold: float = Field(default=0.60, ge=0, le=1)
    top_k: int = Field(default=1, ge=1, le=10)
    representation: str = Field(default="centered", pattern="^(raw|centered)$")
    noise: float = Field(default=0.015, ge=0, le=0.2)
    marker: float = Field(default=0.30, ge=0, le=0.5)
    margin: float = Field(default=0, ge=0, le=1)


class InterventionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(pattern="^[a-f0-9]{32}$")
    fly: int = Field(ge=0, le=15)
    step: int = Field(ge=0, le=79)
    point_id: int = Field(ge=1, le=80)
    live: bool = False


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trial_id: str = Field(pattern="^p9-sugar-bitter-(0|50|100|150|200)-seed-10[0-7]$")


def student_mode():
    return os.getenv("WORKSHOP_EXERCISE") == "1"


def guarded(action):
    if not run_lock.acquire(blocking=False):
        raise HTTPException(409, "An experiment is running. Wait for it to finish.")
    try:
        return action()
    except HTTPException:
        raise
    except NotImplementedError as error:
        raise HTTPException(501, str(error)) from error
    except (ValueError, KeyError) as error:
        raise HTTPException(422, str(error)) from error
    except Exception as error:
        logging.getLogger(__name__).exception("Experiment failed")
        message = (
            str(error)
            if isinstance(error, (FileNotFoundError, RuntimeError))
            else "Check the Python server log."
        )
        if os.getenv("QDRANT_API_KEY"):
            message = message.replace(os.environ["QDRANT_API_KEY"], "[redacted]")
        raise HTTPException(503, message[:400]) from error
    finally:
        run_lock.release()


def live_brain(bank):
    global _live_brain
    if _live_brain is None:
        _live_brain = LiveProxy()
    return _live_brain


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status():
    try:
        bank = RecordedBrain()
        ready, count = True, len(bank.trials)
    except (OSError, ValueError):
        ready, count = False, 0
    return {
        "backend": "Qdrant Edge 0.8.0",
        "ready": ready,
        "recorded_trials": count,
        "live_available": (
            Path(__file__).resolve().parents[1] / "brain/model.py"
        ).exists(),
        "exercise": student_mode(),
        "busy": run_lock.locked(),
    }


@app.get("/api/brain")
def brain_recordings():
    return RecordedBrain().data


@app.post("/api/run")
def experiment(request: RunRequest):
    def execute():
        result = run(Config(**request.model_dump()), student=student_mode())
        runs[result["id"]] = result
        while len(runs) > 6:
            runs.popitem(last=False)
        return result

    return guarded(execute)


@app.post("/api/intervention")
def memory_surgery(request: InterventionRequest):
    def execute():
        result = runs.get(request.run_id)
        if result is None:
            raise HTTPException(404, "This run has expired. Run the experiment again.")
        bank = RecordedBrain()
        return intervention(
            result,
            request.fly,
            request.step,
            request.point_id,
            bank,
            live=live_brain(bank) if request.live else None,
            student=student_mode(),
        )

    return guarded(execute)


@app.post("/api/verify")
def verify(request: VerifyRequest):
    def execute():
        bank = RecordedBrain()
        row = bank.trials.get(request.trial_id)
        if row is None:
            raise HTTPException(404, "Unknown recorded trial.")
        return live_brain(bank).response(
            int(row["stimulation_hz"]["bitter"]), row["seed"]
        )

    return guarded(execute)


@app.post("/api/benchmark")
def benchmark(request: RunRequest):
    def execute():
        bank, space = RecordedBrain(), OdorSpace()
        results = []
        for seed in (2000, 3000):
            for mode in ("none", "exact", "harm", "balanced", "shuffled"):
                cfg = Config(**{**request.model_dump(), "seed": seed, "mode": mode})
                result = run(
                    cfg,
                    brain=bank,
                    space=space,
                    record=False,
                    baseline=False,
                    student=student_mode(),
                )
                results.append({"config": asdict(cfg), "summary": result["summary"]})
        return {
            "results": results,
            "neural_source": "recorded",
            "engine": "Qdrant Edge 0.8.0",
        }

    return guarded(execute)
