"""Independent brains share a clock for playback and completed evidence between stages."""

from .simulation import run

SIZE = 8
DEFAULT_SEED = 300
DEADLINE = 65


def simulate(
    kernel,
    world,
    mode,
    seeds,
    backend,
    shard,
    history=(),
    disconnect=False,
    progress=None,
):
    """Keep personal evidence private and freeze the shared pool during the B group."""
    results = []
    for index, seed in enumerate(seeds):
        results.append(
            run(
                kernel,
                world,
                seed=seed,
                mode=mode,
                owner=f"{'B' if mode == 'shared' else 'A'}{index + 1}",
                history=history if mode == "shared" else (),
                duration=DEADLINE,
                trace=True,
                backend=backend,
                shard=shard,
                control="mute" if disconnect else "normal",
                # All B brains read the completed A group. No B can read another B's future.
                publish=mode != "shared",
            )
        )
        if progress:
            progress(index + 1, len(seeds))
    return results


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
