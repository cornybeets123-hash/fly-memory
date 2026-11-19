# Which recorded condition behaves like a hive?

The webinar records four conditions on matched seeds. Two use shared evidence: the **shared hive** and **inherited memory** (the earlier frozen-pool design, restored beside it). This note asks which one shows hive behaviour, and how the demo should describe each.

**Conclusion.** The shared hive is the hive. Inherited memory is a handoff between groups: useful, and worth showing, but a different mechanism. Say so on screen and in the talk, and do not present the two as variants of one idea.

## What makes a hive

Many agents write to one memory while they act, and read what the others wrote. Four properties follow.

| Property | Shared hive | Inherited memory |
| --- | --- | --- |
| One bank that agents write to | Yes. Every fly upserts into one shard. | No. Newcomers write nothing (`publish=False`). |
| Written and read during the same run | Yes. Writes land after each 100 ms cycle, so one fly's finding is readable by every fly on the next cycle. | No. The pool is finished before any newcomer starts. |
| Starts empty and fills | Yes. Zero observations at 0 s. | No. Full at 0 s and constant. |
| Reads its own writes | Yes, by design (`everyone=True`). | Cannot. A newcomer publishes nothing, and its own earlier observations are not in the pool. |
| No read of a future write | Audited: hive hits whose write time is after the decision must be zero. | Not applicable. The pool is immutable. |
| Controlled comparison | Weaker. Benefit depends on how fast memory fills. | Stronger. Every newcomer sees the same pool. |

On the first four properties the hive matches and inherited memory does not. Inherited memory's advantage is the last row: it isolates the effect of a fixed body of experience, which is why it was the original comparison.

## What the recordings show

`_maintainer/hive_fidelity.py` reads a prepared recording directory and prints these measures. It reads saved evidence only.

```sh
uv run python _maintainer/hive_fidelity.py                  # _internal/artifacts/webinar-hive
uv run python _maintainer/hive_fidelity.py path/to/dir
```

The figures below come from a **small smoke recording (8 flies, seeds 50000-50007)** made to develop the script. They show the shape of each mechanism. They are not outcome claims, and the exit counts at this size must not be quoted. Replace them with the 200-fly recording before the webinar.

| Measure | Shared hive | Inherited |
| --- | --- | --- |
| Observations stored at 0 s / 60 s / end | 0 / 50 / 124 | 147 / 147 / 147 |
| Retrieved hits that came from the fly itself | 8% | 0% |
| Median time of the first applied memory | 23.2 s | 4.3 s |
| Share of searches that changed a decision, 0-30 s to 150-180 s | 23% rising to 46% (dips to 11% at 30-60 s) | about 50%, flat |
| Reads of a write made after the decision | 0 | not applicable |

The last two rows carry the argument. Inherited memory helps from the first junction and stays level, because the evidence was complete on arrival. The hive starts weak and improves as the flies fill the bank. That curve is the signature of a shared memory under construction, and the inherited condition cannot produce it.

## Cautions

- **Self-reads.** About one in ten applied hive decisions used the fly's own earlier observation. The hive is "learning from everyone, including yourself", not purely "learning from others". If the 200-fly recording shows a much larger share, add a hive variant that excludes the fly's own entries. `memory.recall` already supports `exclude_fly`, so it is a small change.
- **Early-run weakness.** The hive can look worse early. That is expected and worth narrating, not hiding.
- **Replay, not a service.** Both conditions are recorded runs on one local shard. They show retrieval behaviour, not the contention, latency or consistency of a networked shared store.
- **Different questions.** A gap between the two conditions mixes two effects: how much experience there is, and when it arrives. Do not read it as a ranking.

## How the demo labels them

- Hive: "One memory, empty at start, written and read by every fly."
- Inherited: "A frozen pool from a finished group. Newcomers only read it."
- The README states that inherited memory is a handoff, not a hive.
