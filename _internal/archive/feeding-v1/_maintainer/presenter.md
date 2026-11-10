# Present the retrieval workshop

[Google Slides](https://docs.google.com/presentation/d/1aj-Nia6P6c8aZw6a_gu1u8tqcZn0tQ2mNLOttiZOWCI/edit) · [PDF backup](slides.pdf) · [Attendee download](https://drive.google.com/file/d/1OQzqriEYKj4KyG4AuuVJOAPegMhSYkqY/view)

**45 minutes. 20 slides. Two presenter-led builds.** Attendees can watch or edit the same files.

## Before the room opens

```sh
uv sync --locked
uv run run.py
```

Leave slide 20 with the download QR on screen while people arrive. Start the talk from slide one.

Open **http://127.0.0.1:8766**. Confirm the badge says **Your code**. Start with **No memory**.

For a completed rehearsal, use `uv run run.py --solution`. Stop that server before starting the coding workshop.

Press **F** for full screen. Press **Space** to reveal decisions. Use **Show colony** to compare populations.

## Run of show

| Time | Slides | Teach or do |
| --- | --- | --- |
| 0:00 to 1:20 | 1–2 | Introduce the project gallery. Distinguish the related models and controllers. |
| 1:20 to 4:00 | 3 | Run **No memory**. Reveal an injury and its repeat. Show the colony. |
| 4:00 to 7:00 | 4–5 | Explain spiking neurons and the purpose of vector search. Use the document example. |
| 7:00 to 14:00 | 6–10 | Explain encoders, cosine, a stored point, filters, and the actual query. |
| 14:00 to 17:00 | 11–12 | Explain when to write observations and how a retrieved warning changes the input. |
| 17:00 to 24:00 | 13 | Complete `remember`, `recall`, and `decide` in `memory.py`. Run the personal check. |
| 24:00 to 28:00 | 14 | Run **Personal**. Inspect observation 636. Remove it and requery, then restore it. Show the colonies. |
| 28:00 to 31:00 | 15 | Explain personal ownership, the shared shard, source exclusion, and observation timing. |
| 31:00 to 35:00 | 16 | Add the shared query and write in `pipeline.py`. Run the shared check. |
| 35:00 to 40:00 | 17 | Run **Shared**. Inspect point 113. Continue to the new poison and later retrieval. Compare colonies. |
| 40:00 to 43:00 | 18–19 | Explain survival with safe feeding, then map the design to an AI agent. |
| 43:00 to 45:00 | 20 | Show the download and take questions. |

Keep stage directions in the speaker notes. The slides teach the mechanism. If coding runs late, shorten colony playback and preserve questions.

## Build one: personal memory

Edit only `memory.py`. The imports, constants, Edge shards, and point construction are ready.

| Function | Implementation |
| --- | --- |
| `remember` | Upsert the supplied point. |
| `recall` | Query the named `odor` vector. Keep harmful outcomes, threshold 0.72, limit three, and returned payloads. Support source exclusion. |
| `decide` | Return the strongest harmful score, bounded to zero through one. Empty results return zero. |

```sh
uv run run.py --check personal
```

The query slide names the outcome filter `harmful` for readability. Construct that `Filter` in `recall`, or write it inline as the completed code does.

Show `fly_brain.py` before running the result. Save the file, then click **Run again**. The server reloads the saved retrieval code.

## Build two: shared memory

Edit only `pipeline.py`. Add these calls inside the existing shared-mode branches:

```python
# retrieve()
hits += memory.recall(shared, vector, exclude_fly=fly)

# observe()
memory.remember(shared, point)
```

```sh
uv run run.py --check shared
```

The source fly writes its own personal shard. The querying fly reads a different personal shard. The shared shard is common.

The caller supplies directly observed meals and buffers writes until all flies finish the current step. Refusals create no new food-safety observation.

## The evidence to point at

Use seed **2000** for the story. Each run starts with empty memories.

| Scene | Source and query | Result |
| --- | --- | --- |
| Personal | Fly 12, step 52, point 636. A different object at step 125 retrieves it at 0.933418 cosine. | Bitter 200 Hz. Left MN9 2 Hz. Refuses. |
| Personal intervention | Remove 636 at that same checkpoint. Keep the state and neural seed fixed. | No warning. Bitter 0 Hz. Left MN9 82 Hz. Would feed. |
| Shared | Fly 05, step nine, point 113. Fly 11 retrieves it at step 29 with 0.938814 cosine. | Another fly's observed harm supplies the warning. |
| New poison | Flies 03 and 11 both suffer harm on step 357. Fly 02 retrieves new-poison observations at step 517. | The later recorded trial gives left MN9 1 Hz and refusal. |

The measured checkpoints are in `_internal/data/workshop-evidence.json`. The new-poison observations are separate from point 113. The slide shows two separate evidence paths.

**Remove this memory and requery** compares one decision. It writes no outcome and leaves the colony unchanged. Other matching points can preserve a warning.

## Scientific boundaries

The unchanged Shiu model uses FlyWire v630: 127,400 neurons and 14,687,178 modeled connections. Every one-second trial resets the network. Weights stay fixed.

The demo replays computed trials. **Verify live** optionally recomputes one trial. It is separate from normal playback.

Sugar and P9 stimulation stay at 150 Hz each. Retrieval changes bitter stimulation. The P9 IDs use Sapkal's v630 annotations. Left MN9 above 10 Hz permits feeding in this adapter.

At 200 Hz bitter, all eight recorded seeds refuse. At 150 Hz, seed 102 gives MN9 13 Hz and feeds. An eligible score from 0.72 through 0.75 maps to 150 Hz, so query eligibility does not guarantee refusal.

The odor vectors use designed mixtures of measured receptor responses and fresh contact noise. They enter retrieval, rather than a modeled olfactory circuit. Movement, poison, energy, and death are engineered. Audience hazard marks never enter the decision pipeline.

The project gallery shows related systems with different models and controllers. Credits and screenshot provenance are in [assets/NOTICE.md](assets/NOTICE.md).

## Evaluation

All policies use the same 20 declared worlds, seeds 10000 through 10019.

| Policy | Mean alive / 12 | Mean safe meals | Mean poisoned meals |
| --- | --- | --- | --- |
| No memory | 0.25 | 82.7 | 35.75 |
| Personal | 5.35 | 185.1 | 30.0 |
| Shared | 12.0 | 219.9 | 3.1 |

Personal survival ranges from one to 11. The stage seed has 10 personal survivors and was selected for an inspectable story. These results describe the designed cue space and survival rules.

Each following shared-memory control uses five worlds:

| Control | Mean alive / 12 | Mean safe meals | Mean starved |
| --- | --- | --- | --- |
| Exact matching | 0.4 | 71.2 | 0 |
| Wrong labels | 0.2 | 10.4 | 11.2 |
| No useful cue | 6.2 | 40.2 | 5.6 |

Low poison alone is insufficient. A warning policy can refuse safe food and cause starvation. Similarity cannot repair false outcome labels.

Data: `_internal/data/evaluation.json`. Reproduce with `uv run run.py --evaluate`.

## Recovery and delivery

**Build memory** shows each task's completed code. Restore those functions, save, and click **Run again**.

Open `artifacts/delivery/fly-memory-offline.html` if the server fails. The downloaded ZIP places the same file at its root. It labels itself **Offline replay**. Open [slides.pdf](slides.pdf) if Google Slides cannot load.

Build the attendee ZIP and offline replay:

```sh
uv run run.py --export
```

The ZIP contains the same starter code, presenter guide, slide metadata, and PDF. It excludes the historical archive, caches, and full brain checkout. Update the existing Drive ZIP in place to preserve the QR link.

Before replacing the public ZIP, run:

```sh
uv run pytest
uv run ruff check
node --test _internal/tests/test_rerun.cjs
```

Optional original-model setup:

```sh
uv sync --locked --extra brain
uv run run.py --setup-brain
uv run run.py --verify
```

The measured cold API verification took 16.16 seconds on this machine. Test it before the event if you intend to use it.
