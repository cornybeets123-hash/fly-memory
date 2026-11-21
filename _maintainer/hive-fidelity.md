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

The figures below come from the **200-fly recording** (seeds 50000-50199, 180-second limit), prepared on 2026-11-21.

| Measure | Shared hive | Inherited |
| --- | --- | --- |
| Observations stored at 0 s / 60 s / end | 0 / 1,423 / 2,033 | 3,488 / 3,488 / 3,488 |
| Retrieved hits that came from the fly itself | 0% (rounded) | 0% |
| Applied evidence from the fly's own writes | 1% | 0% |
| Distinct flies that supplied applied evidence | 82 | 195 |
| Flies that used memory | 199 / 200 | 200 / 200 |
| Median time of the first applied memory | 23.2 s | 4.3 s |
| Share of searches that changed a decision, 0-30 s to 150-180 s | 26%, then 43-44%, rising to 50% | 50% while flies remain (all exited by 60 s) |
| Reads of a write made after the decision | 0 | not applicable |

The memory and timing rows carry the argument. Inherited memory helps from the first junction and stays level, because the evidence was complete on arrival. The hive starts empty and its effect rises as the flies fill the bank. That curve is the signature of a shared memory under construction, and the inherited condition cannot produce it.

Outcomes, for context only (not a ranking; see Cautions):

| Condition | Exits | Mean time |
| --- | --- | --- |
| No memory | 61 / 200 | 160.9 s |
| Personal | 101 / 200 | 146.8 s |
| Inherited | 200 / 200 | 49.5 s |
| Shared hive | 200 / 200 | 76.1 s |

One no-memory fly (A51, seed 50050) stopped at an ambiguous fork at 132.7 s. The page lists it as a visible behaviour failure.

## Cautions

- **Self-reads.** About 1% of applied hive decisions used the fly's own earlier observation. That is down from about one in ten in the 8-fly smoke recording. At 200 flies the hive is almost entirely "learning from others", although self-reads stay allowed by design. No self-excluding variant is needed. `memory.recall` supports `exclude_fly` if one is ever wanted.
- **Early explorers supply the evidence.** 82 flies supplied all applied hive evidence. Early flies explore with an empty memory, and later flies reuse what they found. That is expected for a hive, and worth narrating.
- **Early-run weakness.** The hive can look worse early. That is expected and worth narrating, not hiding.
- **Replay, not a service.** Both conditions are recorded runs on one local shard. They show retrieval behaviour, not the contention, latency or consistency of a networked shared store.
- **Different questions.** A gap between the two conditions mixes two effects: how much experience there is, and when it arrives. Do not read it as a ranking.

## How the demo labels them

- Hive: "One memory, empty at start, written and read by every fly."
- Inherited: "A frozen pool from a finished group. Newcomers only read it."
- The README states that inherited memory is a handoff, not a hive.
