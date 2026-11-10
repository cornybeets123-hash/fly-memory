# Present the Workshop

[Google Slides](https://docs.google.com/presentation/d/1aj-Nia6P6c8aZw6a_gu1u8tqcZn0tQ2mNLOttiZOWCI/edit) · [PDF backup](slides.pdf) · [Attendee download](https://drive.google.com/file/d/1OQzqriEYKj4KyG4AuuVJOAPegMhSYkqY/view)

**45 minutes. 18 slides. Two presenter-led builds.** People can watch or edit the same files.

## Prepare

Install Node.js 22.18 or later. Run:

```sh
uv sync --locked
uv run run.py
```

Open **http://127.0.0.1:8766**. Confirm **Your code**. Open `memory.py`, `pipeline.py`, and `fly_brain.py` in the editor.

Rehearse separately with `uv run run.py --solution`. Stop that server before starting the coding workshop.

Keep the PDF and `fly-memory-offline.html` ready. The offline file contains recorded computation and Qdrant results. It does not run edited code.

## Run of Show

| Time | Slides | Do |
| --- | --- | --- |
| 0–3 | 1 | Run **No memory**. Show the first hit and the repeat failure. |
| 3–4 | 2 | Introduce the fly-brain project gallery. |
| 4–10 | 3–6 | Teach retrieval, encoders, similarity, and eligibility filters. |
| 10–14 | 7–10 | Explain the neural model, stored episode, and observation boundary. |
| 14–23 | 11 | Build personal memory. Check the saved code. |
| 23–27 | 12 | Run **Personal**. Compare the matched repeat with its baseline ghost. |
| 27–31 | 13 | Explain shared evidence and source ownership. |
| 31–35 | 14 | Add the shared read and write. Check the code. |
| 35–39 | 15 | Run **Shared**. Show Scout's episode and a quiet lookalike. |
| 39–42 | 16–17 | Show controls and map the contract to an AI agent. |
| 42–45 | 18 | Show the download and take questions. |

Start the failure demo before teaching the concepts. The gallery follows the failure.

## Build Personal Memory

Edit `memory.py`. Complete `remember`, `recall`, and the final return in `decide`.

The query uses the named `cue` vector. Return three hits above 0.98 with payloads. Filter `arena="orchard"` and the supplied `PROTOCOL`. Support optional source exclusion. Keep safe episodes eligible.

```sh
uv run run.py --check personal
```

Show `fly_brain.py`. Save the build. Select **Personal** and run again.

Personal playback opens at the matched repeat. Earlier computed scenes include the fly's first injury and observation. The ghost shows the same scene without memory.

## Build Shared Memory

Add these calls in `pipeline.py`:

```python
# retrieve(), inside the shared branch
hits += memory.recall(shared, vector, exclude_fly=fly)

# observe(), inside the shared branch
memory.remember(shared, point)
```

```sh
uv run run.py --check shared
```

Select **Shared** and run again. Recipients begin with empty personal memory. Scout directly observed earlier threat and quiet cycles. Shared access supplies those episodes before recipients meet the threat.

Completed functions are in `_internal/escape/answers.py`. Use `--solution` if recovery is faster than debugging on stage.

## Point at the Mechanism

Pause and scrub the timeline. Compare current looming input with recalled input, DNp01 firing, and refuge clearance.

Open **Inspect query**. Show the actual score, source, observation cycle, arena filter, and input-recording reference.

Click **Mute recall**. Retrieval remains visible, but early neural input disappears. Click **Restore full path**. **Disable escape readout** keeps the spikes and removes escape movement.

The safe lookalike is inside the danger episode's similarity threshold. Its closer quiet episode produces sensory activity without an escape. Similarity supplies relevant evidence. The downstream neural response supplies the action.

## Controls and Limits

The declared evaluation uses 20 held-out seeds, with six flies per seed. Read `_internal/escape/data/evaluation.json` for results and timing sensitivity. Seven controls use five seeds each.

This is an engineered partial-visibility task. A clear-view threat gives the normal reflex enough time. The screen hides other approaches. Refuge clearance takes 45 ms by design. Two hits end a fly's run.

The model has 138,639 neurons and 15,091,983 connections. Wiring stays fixed. Replay adds recorded sensory input. The runtime uses Doodle Fly's Float32 LIF implementation with Shiu-style parameters. Dense checks validate its optimization, including continuous-state replay. Brian2 equivalence and biological escape timing remain unestablished.

Cue vectors use engineered features. Their clean separation does not validate a text embedding model. The shared shard runs inside one process. The retrieval diagram shows actual returned records. The HNSW slide uses a schematic.

## Keys and Backups

**Space** pauses. **Right arrow** advances a scene. **F** enters full screen. **Run again** resets the experiment and reloads saved learner code.

Run `uv run run.py --export` after changing the deck or implementation. It rebuilds the PDF-backed download and offline replay. Keep the native deck, PDF, guide, and download together.
