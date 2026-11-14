"""Step independent brains on one clock, with completed evidence between stages."""

from contextlib import ExitStack

from .simulation import steps

SIZE = 8
DEFAULT_SEED = 300
DEADLINE = 65


def batches(
    kernel,
    world,
    mode,
    seeds,
    backend,
    shard,
    history=(),
    disconnect=False,
    progress=None,
    owner_offset=0,
    trace=True,
    history_loaded=False,
):
    """Publish every 100 ms. Apply writes after all eight current-cycle decisions."""
    results = [None] * len(seeds)
    latest = [None] * len(seeds)
    writes = []
    # Completed history is immutable during this stage. Load it once for the group.
    loaded = history_loaded
    if mode == "shared" and shard is not None and not loaded:
        for episode in history:
            backend.remember(shard, episode.point)
        loaded = True
    with ExitStack() as cleanup:
        active = {}
        for index, seed in enumerate(seeds):
            simulation = steps(
                kernel,
                world,
                seed=seed,
                mode=mode,
                owner=f"{'B' if mode == 'shared' else 'A'}{owner_offset + index + 1}",
                history=history if mode == "shared" else (),
                duration=getattr(world, "deadline", DEADLINE),
                trace=trace,
                backend=backend,
                shard=shard,
                control="mute" if disconnect else "normal",
                # All B brains read the completed A group. No B can read another B's future.
                publish=mode != "shared",
                writes=writes,
                history_loaded=loaded,
            )
            cleanup.callback(simulation.close)
            active[index] = simulation
        cycle = 0
        while active:
            for index, simulation in list(active.items()):
                try:
                    latest[index] = next(simulation)
                except StopIteration as finished:
                    results[index] = finished.value
                    del active[index]
                    if progress:
                        progress(sum(r is not None for r in results), len(seeds))
            for writer, storage, point in writes:
                writer.remember(storage, point)
            writes.clear()
            cycle += 1
            if cycle % 5 == 0 or not active:
                yield {
                    "ms": max(f["ms"] for f in latest if f is not None),
                    "flies": latest,
                    "completed": results,
                }
    return results


def simulate(*args, **kwargs):
    """Run the same group scheduler for checks, exports, and the live service."""
    simulation = batches(*args, **kwargs)
    try:
        while True:
            next(simulation)
    except StopIteration as finished:
        return finished.value
    finally:
        simulation.close()


def movement(result):
    """Reuse a real earlier run as the comparison, with only its movement data."""
    return {
        "owner": result["owner"],
        "seed": result["seed"],
        "summary": result["summary"],
        "frames": [
            {key: frame[key] for key in ("ms", "x", "y", "heading")}
            for frame in result["frames"]
            if frame["ms"] % 100 == 0 or frame is result["frames"][-1]
        ],
    }


def totals(results):
    summaries = [result["summary"] for result in results]
    return {
        "count": len(results),
        "exited": sum(s["exit"] for s in summaries),
        "mean_time_ms": sum(s["time_ms"] for s in summaries) / len(summaries),
        "mean_path": sum(s["path"] for s in summaries) / len(summaries),
        "returns": sum(s["returns"] for s in summaries),
        "dead_ends": sum(s["detours"] for s in summaries),
        "collisions": sum(s["collisions"] for s in summaries),
        "queries": sum(
            v.get("search_ms") is not None
            for r in results
            for d in r["decisions"]
            for v in d["views"]
        ),
        "memory_uses": sum(
            v["applied"] for r in results for d in r["decisions"] for v in d["views"]
        ),
    }
