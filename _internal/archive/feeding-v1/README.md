# Give a fly a memory

A 45-minute lesson on retrieval. Watch a fly colony fail, build personal memory, then share experience through Qdrant Edge.

In the download, open `fly-memory-offline.html` to explore without installation.

To code, install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv sync --locked
uv run run.py
```

Open **http://127.0.0.1:8766**. Start with **No memory**.

| Step | Edit | Check |
| --- | --- | --- |
| 1. Store and retrieve experience. | `memory.py` | `uv run run.py --check personal` |
| 2. Share observed experience. | `pipeline.py` | `uv run run.py --check shared` |

Click **Run again** after each change. The server reads your saved code.

Open this folder in VS Code to show only the workshop files.

Read [`fly_brain.py`](fly_brain.py) to see how a warning changes the brain input. **Build memory** shows each task and its completed code.

Rehearse with `uv run run.py --solution`. The screen labels completed code clearly.

The fly uses a fixed computational brain. The demo replays computed neural trials. Movement, poisoned food, energy, and death use designed rules. Hazard labels belong to the audience view.

[Slides](https://docs.google.com/presentation/d/1aj-Nia6P6c8aZw6a_gu1u8tqcZn0tQ2mNLOttiZOWCI/edit) · [Presenter guide](_maintainer/presenter.md) · [Model and data sources](_internal/data/NOTICE.md)
