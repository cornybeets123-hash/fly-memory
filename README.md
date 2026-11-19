# Give a fly a memory

This branch contains the webinar demo. Run `uv run run.py` and open http://127.0.0.1:8766.

Select **Play comparison** to race 200 flies without memory against 200 flies that share one memory. Both crowds use one clock and matched seeds. Playback runs at 4× and stops at the labeled 60-second checkpoint, after about 15 seconds. The shared memory starts empty. Every fly writes its completed observations into the same Qdrant shard and reads every fly's entries, so later junctions benefit from earlier visits by any fly.

When the personal and inherited recordings exist, two more panes join the race, in the order No memory, Personal, Inherited, Shared hive. Personal flies read only their own completed observations. Inherited flies start after a finished personal-memory group and read its frozen pool. They publish nothing and never read themselves. That is a handoff between groups, not a hive.

Each maze shows recorded fly positions, with counts where flies overlap. Eight labeled close-ups follow distinct trials in each crowd. The small fly grid shows every trial outcome.

Select **Why did this fly turn?** to pause at a recorded use of shared memory. Inspect the captured view, source observation, changed sensory input, and actual neural choice. **Replay this turn** shows the recorded passage at normal speed. The timeline can inspect the full 180-second trial. **Completed results and failed attempts** contains every condition and both stopped attempts.

**Demo controls** contains the personal-memory and inherited-memory conditions, the eight-fly live demo, and population preparation. The larger maze has eight forks and a 180-second limit. The recorded comparison and live demo use the same sensory adapter, fixed wiring, and movement code. Playback speed changes the display clock.

Select **Prepare the recorded comparison** before the webinar if the recordings are missing. Preparation computes 800 real trials across the four conditions: no memory, personal, inherited (the personal group's frozen pool), and the shared hive. The 200 shared-memory flies run as one group in one process because they share one shard. It saves progress under `_internal/artifacts/webinar-hive/`. Run preparation from the terminal with `uv run python -m _internal.maze.webinar_population`. Completed groups resume when the source hashes match. The population display uses recorded trajectories and sampled neural frames.

Run `uv run run.py --workshop` for the original workshop starter, or add `--solution` for its completed reference. The original workshop instructions follow.


A 45-minute AI Dev Day workshop about retrieval. Watch the presenter, or use the same files.

## Run

Clone the [workshop repository](https://github.com/qdrant-labs/fly-memory) before the session. Use Python 3.12, Node.js 22.18 or later, and uv.

```sh
git clone --depth 1 https://github.com/qdrant-labs/fly-memory.git
cd fly-memory
uv sync --locked
uv run run.py
```

Open http://127.0.0.1:8766.

## Build

| File | Change |
| --- | --- |
| `memory.py` | Store an observed experience and retrieve similar views. |
| `pipeline.py` | Let a newcomer retrieve another fly's experience. |
| `fly_brain.py` | Read the real sensory adapter and neural steering interface. |

Save the file, then click **Run again**. Eight flies run with matched seeds. Select a fly to inspect its brain and Qdrant results.

```sh
uv run run.py --check personal
uv run run.py --check shared
```

## Presenter

```sh
uv run run.py --solution
```

This runs the completed reference code. The [presenter guide](_maintainer/presenter.md) contains the timing and build steps.

Qdrant Edge runs inside the app. The neural readout selects visible openings and controls every turn. The application supplies the sensory mapping, perception, and forward movement. See the [model and data notices](_internal/brain/data/NOTICE.md).
