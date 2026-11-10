# Give a fly a memory

A 45-minute AI Dev Day workshop about retrieval. Watch the presenter, or use the same files.

## Run

Use Python 3.12, Node.js 22.18 or later, and uv.

```sh
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
