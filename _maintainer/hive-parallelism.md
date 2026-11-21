# Hive parallelism (future improvement)

Status: investigated, not started. Not needed for the webinar. The recording is prepared once, in advance.

Written 2026-11-21 during the 200-fly regeneration on branch `hive-shared-memory`.

## Problem

The shared hive is one group of 200 flies on one worker (`webinar_population.py`, `groups["shared"]`). All 200 flies share one Qdrant shard on one clock, so the group cannot be split the way the other conditions are.

The other three conditions run 25 independent groups of 8 across 8 workers and use the whole machine. During the hive, 7 workers sit idle and the machine runs at about one core (about 12–15% CPU on 8 logical cores). `--workers` has no effect on the hive.

Measured on Windows 11, 8 logical cores, 15 GB RAM, Node 26:

| | No memory, Personal, Inherited | Shared hive |
| --- | --- | --- |
| Wall time, 200 flies | No memory 21 min, personal 18 min, inherited 7 min | 26.8 min. Hive flies exit early (mean 76 s). |
| CPU | about 8 cores | about 1 core: Python worker 0.72, Node 0.27 |
| Memory | about 260 MB per Node worker | Node about 1.1–1.2 GB (200 brains). Python worker grew steadily to about 2.3 GB. |

The full 800-trial preparation took 73 minutes. The hive is about 37% of that. Option B below would save about 20 minutes per full preparation. It is worth doing only for repeated preparation or larger crowds.

The hive status counter also stays at 600/800 until the whole hive batch returns. `prepare()` counts a batch only when its future completes, and `run_batch` does not pass `cohort.simulate`'s `progress` callback.

## Where the time goes

- The hive advances in 20 ms ticks (`world.STEP = 0.02`). A 180 s trial is 9,000 ticks.
- Each tick runs all 200 flies in turn (`cohort.batches`). Each fly's step makes one blocking JSON round trip to Node (`fly_brain.FlyBrain.step` → `kernel.Kernel.step`). That is about 1.8 million serial round trips.
- Python carries about 73% of the work: geometry, junction views, encoding, Qdrant searches, and JSON and pipe handling. Node carries about 27%: brain integration.
- The Python share has **not been profiled**. Profile before choosing an option.

## Option A: several Node workers, one Python process

Overlap brain calls across several Node kernels.

- If Node took no time at all, the hive would gain only about 1.35×.
- It needs `FlyBrain.step` split into send and receive halves. `fly_brain.py` is an attendee-facing file.
- **Not recommended.**

## Option B: split flies across processes, each with a copy of the shard (recommended)

Each of N worker processes owns about 200/N flies, its own Node kernel, and its own copy of the shard. Every tick:

1. Each worker advances its flies one tick, using the existing `simulation.steps` generators unchanged.
2. Each worker returns that tick's pending writes.
3. The coordinator merges the writes in fly order, matching the serial loop at `cohort.py` (the `writes` list), and sends them to every worker.
4. Every worker applies them to its copy, and the next tick starts.

This keeps the invariant "writes follow all current-cycle decisions". If the copies stay identical, results should be identical to the serial run.

| Area | Change | Size |
| --- | --- | --- |
| New `_internal/maze/hive_parallel.py` | Persistent workers, a barrier every tick, write broadcast, collect results | about 150–250 lines |
| `webinar_population.py` | Send the hive group to the new scheduler. Packing currently happens inside `run_batch` | about 30–50 lines |
| `cohort.py` | Expose the per-tick loop for reuse by workers | small |
| `simulation.py`, `fly_brain.py`, `memory.py`, `kernel.py` | No change. Episodes cross processes via `serialized_episode` / `restored_episode` | none |
| Tests | Equivalence test: a 16-fly hive run serially and in parallel gives identical decisions, episodes, outcomes and audit | about 50 lines |
| Side benefit | The coordinator knows when each fly finishes, so live hive progress ("87/200 flies") is easy to add | small |

Expected gain: about 4–6× on 8 cores, not 8×.
- Flies stay on their worker as others exit unevenly.
- Junction ticks cost more than plain ticks.
- The 9,000 barriers add roughly 10–30 s.

The hive would drop from about 1.5–2 h to about 20–30 min.

Risks to check:

1. **Identical search results across copies.** Same points in the same insert order should give identical results, ties included. The tiny shard is probably searched exhaustively, but this is an assumption. The equivalence test must prove it.
2. **Search timings.** `search_ms` is measured per process. It stays a real measurement, but it must be left out of the equivalence comparison.
3. **Regeneration.** The new module lives under `_internal/maze/`, which `workshop_evaluate.freeze()` hashes. The recording must be regenerated after the change.
4. **Cancel and heartbeat.** `jobs.terminate_tree` already stops the whole process tree. Check that it also stops the new workers, and that the heartbeat continues during the barrier loop.

Effort: half a day to a day, including the equivalence test, plus one regeneration.

## Option C: one batched Node request per tick (check first)

If profiling shows that JSON and pipe overhead dominates the Python share, send all 200 brain steps as one Node request per tick. This could give about 2× with less code than Option B, and the two combine. It needs the same send and receive split of `FlyBrain.step` as Option A, so it touches `fly_brain.py`. Keep its public behaviour identical for the workshop.

## First step

Profile a small hive before building anything. This takes about 10 minutes:

```sh
uv run python -m cProfile -o hive.prof -m _internal.maze.webinar_population --count 16 --seed 50000 --workers 1 --output <scratch dir>
uv run python -c "import pstats; pstats.Stats('hive.prof').sort_stats('cumulative').print_stats(30)"
```

The profile only covers the coordinating process. To see inside a worker, profile `cohort.simulate` directly for 16 hive flies with one `Kernel`. Choose Option C if most time is in `kernel.request` and `json`. Otherwise, choose Option B.

## Related: hive memory growth

The hive's Python worker grows for the whole run, at about 75 MB a minute in the 200-fly run. `run_batch` calls `cohort.simulate` with `trace=True`, so every fly keeps every per-tick frame until the whole group returns. `run_batch` only thins frames afterwards, keeping frames every 100 ms, the decision captures and the last frame. Other conditions never show this, because their groups hold 8 flies.

A fix would thin or save each fly's frames as soon as that fly finishes, or keep only the frames that `run_batch` saves. This caps memory without changing results. It changes `_internal/maze/` code, so it needs a fresh recording. It fits naturally with Option B, where each worker already returns finished flies.

## When to do it

- Re-running preparation often.
- Going beyond 200 flies. The hive's serial cost grows with flies × ticks, and its searches run over a growing shard.
- Preparing live during a session, where the frozen counter and the long wait are visible.
