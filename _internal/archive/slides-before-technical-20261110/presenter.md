# Present the workshop

[Google Slides](https://docs.google.com/presentation/d/1aj-Nia6P6c8aZw6a_gu1u8tqcZn0tQ2mNLOttiZOWCI/edit) · [PDF](slides.pdf) · [Download](https://drive.google.com/file/d/1OQzqriEYKj4KyG4AuuVJOAPegMhSYkqY/view)

**45 minutes. 16 slides. Two presenter-led builds.** Attendees can watch or use the same files.

## Prepare

Use Python 3.12, Node.js 22.18 or later, and uv.

```sh
uv sync --locked
uv run run.py
```

Open http://127.0.0.1:8766. Confirm **Your code**. Open `memory.py`, `pipeline.py`, and `fly_brain.py` in the editor.

Rehearse with `uv run run.py --solution`. Stop that server before the coding session. Keep `slides.pdf` and `fly-memory-offline.html` ready.

## Run of show

| Time | Slides | Action |
| --- | --- | --- |
| 0–3 | 1 | Run **No memory**. Show eight brains exploring and count the exits. |
| 3–6 | 2–3 | Introduce the projects and the neural input interface. |
| 6–15 | 4–9 | Explain retrieval, vectors, search, filters, and observations. |
| 15–23 | 10 | Implement `remember` and `recall` in `memory.py`. |
| 23–26 | 11 | Run **Personal memory**. Select A6. Show its own returned observation. |
| 26–29 | 12 | Introduce B and shared experience. |
| 29–33 | 13 | Implement shared scope in `pipeline.py`. |
| 33–38 | 14 | Run **Shared memory**. Select B6. Show the returned A record and the earlier personal run. |
| 38–42 | 15 | Map retrieval to an AI agent. |
| 42–45 | 16 | Share the download and take questions. |

## Use the slides

Use the captured fly view throughout the concept slides. The encoder, vector comparison, filter, record, and write sequence use the same example. Switch to the editor for each build. The slide shows the function roles; the notes contain the exact code.

On slide 14, each dot position represents the same held-out seed across modes. Filled dots reached the exit. Report the full measures in the notes together. On slide 15, compare fly input with agent context without introducing another task.

## Make ownership clear

| Mode | Starting experience | What can change the choice? |
| --- | --- | --- |
| No memory | No experience enters searchable memory. | Balanced input lets the brain explore. |
| Personal memory | Each A fly starts empty. | Each A fly retrieves only its own completed observations. |
| Shared memory | Each B fly starts without its own observations. | Each B fly can retrieve the completed A group’s observations. |

The opening No memory demo supplies no records to Personal memory. **Run again resets each A fly’s searchable memory.** Shared B flies read all completed A observations. B flies cannot read other B flies from this group. The gray path replays the selected fly’s earlier matched run.

## Build one

Replace `remember` and `recall` in `memory.py`. Keep the supplied consumer.

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

Save. Select **Personal memory**. Select **A6**. Click **Replay memory** after its first match. Point to **A6 observed it. A6 uses it.** The neural choice input changes from **30/30 Hz** to **0/30 Hz**.

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

Save. Select **Shared memory**. Click **Replay memory**. Select **B6**. Point to the A source and B consumer. The new group uses completed A observations before entering those routes.

## Controls and recovery

The opening group uses eight declared seeds, **300–307**. A6/B6 is selected first. The benchmark slide reports 16 fresh seeds, **50000–50015**.

**New group** samples eight new seeds. Personal and Shared retain those seeds. Reload the page to restore the opening group. Some no-memory flies find the exit by chance.

Select a numbered fly to inspect its brain and retrieval. The large counter shows the group’s exits. A green line under a fly means it exited. Pink means its time expired.

Show the query view, returned observation, source, **Returned**, **Cosine**, and **Search · ms**. Cosine measures visual similarity. It is not a success probability. Search time measures the local Qdrant call. It excludes encoding and neural computation. **Inspect evidence** shows ranked records and raw data.

Press **R** to run the selected mode. Press **Space** to pause. Use **1**, **2**, and **3** to select stages in order. The speed button cycles through 2×, 1×, and 4× display speed. The display continues through memory events. Pause manually or select Replay memory to explain a match.

Each click streams all eight independent brains and actual Qdrant queries on one simulation clock. Movement, captured views, completed observations, and spikes arrive during computation. The flies do not interact physically. The screen states **Live computation**, then **Computed now** when computation ends. The display advances only through computed frames. The offline HTML states **Recorded fallback**. It opens without a server and repeats group 300–307. Recorded search times remain labelled as recorded playback. It cannot execute edited Python.

If a build fails, read the displayed error and run its `--check` command. Use the completed functions here for recovery. Restart with `--solution` when you need to skip coding.

Optional: select **Disconnect steering**. Input and spikes still compute. Physical yaw and branch readout become zero. The attempt ends when the brain cannot select an option. Restore the connection before continuing.

## Explain the boundary

The neural readout selects fork options and controls turns. The application supplies the option mapping and forward movement. Retrieval changes input to fixed wiring. No memory means no external episodic retrieval. Neural and controller state still evolve.

`returned` means a START crossing. `dead_end` means a terminal wall. `open` means another junction or the exit.

See [evaluation](evaluation-summary.md), [model notices](../_internal/brain/data/NOTICE.md), and [slide notes](slides.json) for definitions, evidence, and sources.
