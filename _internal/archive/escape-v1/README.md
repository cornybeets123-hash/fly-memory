# Give a fly a memory

A 45-minute retrieval workshop for AI builders. Watch a fly fail, add personal memory, then let a new fly use shared experience.

[Google Slides](https://docs.google.com/presentation/d/1aj-Nia6P6c8aZw6a_gu1u8tqcZn0tQ2mNLOttiZOWCI/edit) · [Presenter guide](_maintainer/presenter.md)

## Start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Node.js 22.18 or later](https://nodejs.org/en/download).

```sh
uv sync --locked
uv run run.py
```

Open **http://127.0.0.1:8766**. Select **No memory**, then **Run experiment**.

## Build

| File | Change |
| --- | --- |
| `memory.py` | Store and retrieve personal episodes. |
| `pipeline.py` | Read and publish shared episodes. |
| `fly_brain.py` | Inspect how recalled inputs reach the brain. |

```sh
uv run run.py --check personal
uv run run.py --check shared
```

Save each build. Select its stage and click **Run again**.

Use `uv run run.py --solution` for a completed rehearsal. Open `fly-memory-offline.html` for the recorded backup.

The demo computes a fixed FlyWire neural model. Qdrant Edge retrieves sensory recordings. The arena and movement are engineered. [Sources and licenses](_internal/escape/data/NOTICE.md).
