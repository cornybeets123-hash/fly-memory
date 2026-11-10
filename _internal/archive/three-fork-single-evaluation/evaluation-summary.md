# Evaluation

The task uses one fixed three-fork maze, a circuit, two dead ends, and a 65-second deadline.

The 20 held-out neural seeds are 40000–40019. Each comparison keeps its initial pose, neural seed, scene, and body parameters fixed.

| Mode | Exited | Mean time, capped at 65 s | Adverse outcomes | Collisions | Longest stall |
| --- | --- | --- | --- | --- | --- |
| No memory | 2/20 | 62.9 s | 56 | 0 | 0.0 s |
| Personal memory | 8/20 | 58.1 s | 48 | 0 | 0.0 s |
| Shared memory | 19/20 | 24.3 s | 6 | 0 | 0.0 s |
| B with personal scope | 8/20 | 58.1 s | 48 | 0 | 0.0 s |

An adverse outcome is a completed START return or terminal wall. Mean time includes unfinished attempts at the deadline.

All correctness gates passed. The runs contain zero incorrect stored outcomes, wrong-place retrieval matches, false exclusions, or normal-mode decisions without a neural readout. In normal modes, no fly re-entered an adverse option while its matching evidence was applied.

No-memory runs selected left 74 times and right 16 times. The first fork selected left 18 times and right twice. The model has a left bias. The interface does not tune that bias away.

Within each matched seed, the maximum cross-entrance cosine among queried views was 0.774. The threshold was fixed at 0.90 before these runs. Different approaches can still produce weak same-entrance matches. The consumer abstains when recognition is insufficient.

The muted decision control produced an explicit no-decision failure. The reversed decision control entered an adverse option despite valid retrieved evidence. The independent dense neural checks passed four cases, including persistent state.

Example 305 was selected from development runs to make the teaching sequence visible. It is separate from the held-out cohort. No-memory missed the deadline, personal memory exited in 53.86 s, and shared memory exited in 19.32 s.

The full records, scores, source hashes, and audit results are in [evaluation.json](evaluation.json). The protocol is in [evaluation-protocol.json](evaluation-protocol.json).

These results describe this scene-specific descriptor, controller, and fixed maze. They do not establish general maze solving, biological planning, or vector-search scale performance.
