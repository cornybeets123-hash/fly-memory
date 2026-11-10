# Present the workshop

[Google Slides](https://docs.google.com/presentation/d/1aj-Nia6P6c8aZw6a_gu1u8tqcZn0tQ2mNLOttiZOWCI/edit) · [PDF](slides.pdf) · [Download](https://drive.google.com/file/d/1OQzqriEYKj4KyG4AuuVJOAPegMhSYkqY/view)

**45 minutes. 16 slides. Two presenter-led builds.** Attendees can watch or use the same files.

## Prepare

Use Python 3.12, Node.js 22.18 or later, and uv.

```sh
uv sync --locked
uv run run.py
```

Open http://127.0.0.1:8766. Open `memory.py`, `pipeline.py`, and `fly_brain.py` in the editor.

Rehearse with `uv run run.py --solution`. Stop that server before the coding session. Keep `slides.pdf` and `fly-memory-offline.html` ready.

## Run of show

| Time | Slides | Action |
| --- | --- | --- |
| 0–3 | 1 | Run **No memory**. Show the repeated loop. |
| 3–6 | 2–3 | Introduce the projects and the brain interface. |
| 6–15 | 4–9 | Teach retrieval, encoding, search, filters, and completed observations. |
| 15–23 | 10 | Implement `remember` and `recall` in `memory.py`. |
| 23–26 | 11 | Run **Personal memory**. A starts empty and learns during this run. |
| 26–29 | 12 | Introduce B. Explain whose experience each mode can use. |
| 29–33 | 13 | Implement shared scope in `pipeline.py`. |
| 33–38 | 14 | Run **Shared memory**. Compare B with its personal-memory ghost. |
| 38–42 | 15 | Map the pipeline to an AI agent. |
| 42–45 | 16 | Share the download and take questions. |

## Make the distinction explicit

| Mode | Starting experience | What changes the choice? |
| --- | --- | --- |
| No memory | No experience enters searchable memory. | The same local rule repeats the loop. |
| Personal memory | A starts empty. | A recalls its own completed circuit during this run. |
| Shared memory | B has no observations of its own. | B retrieves the same A record before taking the circuit. |

The audit log retains observations for inspection. The opening No memory demo supplies no records to Personal memory. **Run again resets A’s personal memory.** Shared mode uses A’s actual completed return record. Its gray comparison is B with personal scope. That B must learn independently.

## Build one

Replace `remember` and `recall` in `memory.py`. Keep the imports and supplied consumer.

```python
def remember(shard, point):
    """Add the supplied observation to Qdrant."""
    shard.update(UpdateOperation.upsert_points([point]))

def recall(shard, vector, scope):
    """Search the view vector. Apply the supplied eligibility filter."""
    return shard.query(QueryRequest(
        query=Query.Nearest(vector, using="view"),
        limit=10,
        score_threshold=MIN_SCORE,
        filter=scope,
        with_payload=True,
    ))
```

```sh
uv run run.py --check personal
```

Save. Select **Personal memory**. Show A’s first loop, its stored observation, and its second choice.

## Build two

Replace `scope` in `pipeline.py`.

```python
def scope(world, protocol, fly, shared=False):
    """Use compatible observations from the current memory scope."""
    must = [
        FieldCondition("world", match=MatchValue(world)),
        FieldCondition("protocol", match=MatchValue(protocol)),
    ]
    source = FieldCondition("source_fly", match=MatchValue(fly))
    if shared:
        return Filter(must=must, must_not=[source])
    return Filter(must=[*must, source])
```

```sh
uv run run.py --check shared
```

Save. Select **Shared memory**. Point to **Observed by A. Used by B.** Show B’s personal-memory ghost learning later.

## Controls and recovery

Press **R** to recompute the selected mode. Press **Space** to pause. Use **1**, **2**, and **3** to select stages in order. The speed button cycles through 2×, 1×, and 4× playback.

Each click computes the neural run and Qdrant queries before playback. The screen states **Computed now**. The offline HTML states **Recorded fallback** and opens without a server. It cannot run edited code.

If a build fails, read the displayed error. Check the saved file with `--check`. Use the completed functions here for recovery. Restart with `--solution` only when you need to skip coding.

Optional: select **Disconnect steering**. Retrieval and spikes still compute. Physical yaw becomes zero. Restore steering before the next stage.

## Explain the engineering accurately

The fixed FlyWire connectome controls every physical turn through the neural readout. The application engineers local perception, opening choice, and forward movement. A memory changes the selected bearing, which changes LC10a input and subsequent neural activity. Qdrant stores external observations. The workshop keeps neural wiring fixed.

The camera uses local visibility. The 192-value toy descriptor averages image columns, centers RGB values, and normalizes them. The vector contains pixels only. The payload retains source, outcome, times, world, protocol, and snapshot hash. A record becomes available after a completed observation.

The demo uses Qdrant Edge inside one Python process. Shared access uses the shard A wrote. The workshop does not implement network synchronization. The HNSW slide is schematic. The tiny collection supports no scale-performance claim.

See [evaluation](evaluation-summary.md), [model notices](../_internal/brain/data/NOTICE.md), and [slide notes](slides.json) for evidence and sources.
