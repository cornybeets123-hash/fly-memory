"""Compile saved workshop files on each run. Keep the SDK path identical."""

from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def read_module(name):
    path = ROOT / f"{name}.py"
    module = ModuleType(f"workshop_{name}")
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)  # noqa: S102
    return module


def load():
    memory, pipeline = read_module("memory"), read_module("pipeline")

    def recall(shard, vector, world, exclude_fly=None, protocol=None, owner="A"):
        if vector is None:
            return []
        scope = pipeline.scope(world, protocol, owner, shared=exclude_fly is not None)
        return memory.recall(shard, vector, scope)

    return SimpleNamespace(
        remember=memory.remember, recall=recall, decide=memory.decide
    )
