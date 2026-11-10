# Evaluation

Two groups of eight use held-out neural seeds 50000–50015. Each stage keeps the maze, initial pose, body parameters, and matched neural seeds fixed. Every attempt has a 65-second deadline.

| Mode | Exited | Mean time, capped at 65 s | Mean path, world units | START returns | Dead ends | Collisions | Longest stall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| No memory | 5/16 | 56.1 s | 3177 | 28 | 9 | 0 | 0.0 s |
| Personal memory | 9/16 | 52.4 s | 2942 | 17 | 14 | 0 | 0.0 s |
| Shared memory | 16/16 | 19.3 s | 1122 | 0 | 0 | 0 | 0.0 s |

Personal memory starts empty for each owner. A personal fly can retrieve only its own completed observations. Shared newcomers read the completed observations from all eight A flies. This pool stays unchanged while the B group runs.

All ownership and outcome checks passed. The audit found zero wrong-place matches, incorrect stored outcomes, false exclusions, repeated adverse entries with applied evidence, collisions, or normal-mode decisions without a neural readout. Shared queries returned only completed A observations.

The opening development group uses seeds 300–307. It produced four exits without memory, six with personal memory, and eight with shared memory. Focus A6/B6 shows the mechanism. Other flies and unsuccessful attempts remain visible.

The UI reports each local Qdrant call in milliseconds. This includes request and filter handling. It excludes image encoding and neural computation. These tiny local searches do not measure production-scale latency. Cosine measures descriptor similarity, not outcome probability.

The brain can turn left or right with equal sensory input. Its learned wiring and noise create a left bias. Retrieval changes the sensory input to fixed neural wiring. The application supplies perception, the option mapping, and forward motion.

The independent dense neural checks passed four cases, including persistent state. The earlier controller ablations and paired single-fly audit remain in `_internal/archive/three-fork-single-evaluation/`. They use a different shared-pool protocol.

Source hashes describe the measured run. The report lists later release changes. They preserve normal-mode movement and retrieval.

The full records, scores, source hashes, and audit results are in [evaluation.json](evaluation.json). The protocol is in [evaluation-protocol.json](evaluation-protocol.json). These results describe one fixed maze and a scene-specific descriptor. They establish neither general maze solving nor biological planning.
