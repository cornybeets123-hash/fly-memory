# Simulated Fly Brain, Persistent Trauma

Build personal agent memory around the unchanged Shiu et al. fly brain model. Qdrant Edge stores observed experiences and retrieves similar sensory encounters. Recall recruits bitter sensory input. The model's feeding motor output determines whether the fly eats.

## Run the workshop

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run these commands from the repository root:

```bash
uv sync --locked
uv run uvicorn workshop.server:app --host 127.0.0.1 --port 8766
```

Open <http://127.0.0.1:8766>. The default run compares 16 independent personal memories against matched no-memory lives. The core needs no Docker, API key, model download, or LLM service. Use a coding agent of your choice for the exercises.

The repository includes 48 real neural recordings and their raw spike files. Every memory operation runs through Qdrant Edge in your Python process. Each encounter selects a recorded one-second neural trial by its stimulus and a fixed seed. The UI labels this `RECORDED TRIAL`.

Read the [facilitator plan](FACILITATOR.md) for the 45-minute sequence, expected results, recovery steps, and discussion prompts.

## Follow the causal loop

1. The fly encounters a new designed odor mixture derived from measured DoOR receptor responses.
2. Qdrant searches the fly's earlier experiences in 24 dimensions. The memory map displays a fixed two-dimensional projection.
3. Positive aversion evidence, scaled by the strongest cosine score, recruits 50, 100, 150, or 200 Hz of bitter input. Sugar stays at 150 Hz.
4. The unchanged brain model produces spikes. Left MN9 activity above 10 Hz means feeding.
5. A meal reveals nourishment or sickness. The fly writes that observation. Refusal reveals no outcome and creates no memory.

The UI highlights the actual returned memory points, cosine scores, sensory inputs, and motor response. Select another fly to inspect its isolated history. Use the timeline to inspect an encounter. The progress chart compares identical potential encounters and neural seeds.

## Verify a contact live

Install the optional simulator and download the pinned upstream source:

```bash
uv sync --locked --extra brain
uv run python -m workshop setup-brain
uv run python -m workshop verify --trial p9-sugar-bitter-200-seed-103
```

Restart the app after installing the optional dependencies. `Verify live` reruns the selected stimulus through all 127,400 neurons and 14,687,178 synaptic connections. It checks named population spike traces and motor rates against the recording. One simulated second took roughly nine wall seconds on the development laptop. Live verification checks upstream file hashes before building the network.

For the intervention, select Fly 07, encounter six, and memory five. `Delete a memory` reconstructs its exact pre-contact shard, queries it, deletes that point, queries again, restores it, and queries again. The replayed MN9 response changes from 4 Hz to 78 Hz and returns to 4 Hz. `Verify all three live` runs all three neural conditions again. A redundant memory may have no effect; the UI reports that result.

## Participant exercises

Start the exercise server after stopping the solution server on the same port:

```bash
WORKSHOP_EXERCISE=1 uv run uvicorn workshop.server:app --host 127.0.0.1 --port 8766
```

Implement `store`, `search`, and `evidence` in [student_memory.py](student_memory.py). The framework owns shard lifecycle, point IDs, observation timing, and experiment controls. The reference implementation is separate from the participant module. Ask for it if you need a worked solution.

```bash
WORKSHOP_EXERCISE=1 uv run pytest tests/test_memory.py -q
WORKSHOP_EXERCISE=1 uv run python -m workshop evaluate --output artifacts/student-evaluation.json
```

These tests intentionally fail until the hooks are complete. They require actual Edge writes, cosine ranking, threshold handling, payload filtering, isolation, deletion, and restoration. `No memory` remains available while the exercise is incomplete.

Use `WORKSHOP_EXERCISE=1` for every participant evaluation command. The server's environment prefix does not apply to another command or terminal. The evaluation commands in the following reference section use the facilitator solution unless you add this prefix.

After the contract passes, solve the retrieval challenges:

- Predict how raw versus centered receptor responses affect relevance, then measure both.
- Compare one, three, and five neighbors on the same seeds. Explain a harmful recall that extra safe neighbors dilute.
- Tune thresholds on seed 2000. Evaluate the unchanged settings on seed 3000.
- Compare harmful-only memory against both outcomes. Report safe refusals as well as survival.
- Remove the distinguishing cue. Explain why retrieval cannot recover information absent from the observation.
- Run the single-point intervention. Identify when deletion changes a decision and when another memory makes it redundant.

Keep neural parameters and hidden environmental outcomes fixed. Ask the coding agent to produce evidence for each proposed improvement.

## Keep a memory across sessions

After the hooks pass, run:

```bash
WORKSHOP_EXERCISE=1 uv run python -m workshop sessions --output artifacts/session-memory.json
```

The first session observes one harmful meal and closes its shard. A new instance reloads that shard from disk before a different mixture. With the same neural seed, empty memory gives 78 Hz and feeding. Reopened memory gives 4 Hz and refusal. The command saves the shard under `state/` and records its path. It starts a new directory each time.

"Unfamiliar" means a new noisy mixture with a recognizable cue. Every harmful mixture shares a designed cue. Cue removal tests this limit.

## Reproduce the evaluation

```bash
uv run pytest -q
uv run python -m workshop evaluate --seeds 2000 3000 4000 5000 --output artifacts/evaluation.json
uv run python -m workshop evaluate --top-k 5 --output artifacts/neighbors-five.json
uv run python -m workshop evaluate --representation raw --output artifacts/raw-vectors.json
uv run python -m workshop evaluate --marker 0 --output artifacts/no-cue.json
```

The checked [evaluation](data/evaluation.json) uses real Edge queries and recorded whole-brain responses. Each life starts empty. A third harmful meal ends the life. Success also requires at least 12 safe meals in 40 potential encounters.

<details>
<summary>Full results for all five policies and four cohorts</summary>

| Seed | Policy | Survived and fed | Safe meals | Harmful meals | Safe refusals |
| --- | --- | ---: | ---: | ---: | ---: |
| 2000 | No memory | 0/16 | 82 | 48 | 0 |
| 2000 | Exact match | 0/16 | 82 | 48 | 0 |
| 2000 | Harmful memories | 15/16 | 359 | 33 | 29 |
| 2000 | Both outcomes | 15/16 | 382 | 33 | 6 |
| 2000 | Random outcomes | 0/16 | 63 | 48 | 50 |
| 3000 | No memory | 0/16 | 77 | 48 | 0 |
| 3000 | Exact match | 0/16 | 77 | 48 | 0 |
| 3000 | Harmful memories | 13/16 | 355 | 35 | 19 |
| 3000 | Both outcomes | 7/16 | 318 | 41 | 3 |
| 3000 | Random outcomes | 3/16 | 109 | 44 | 103 |
| 4000 | No memory | 0/16 | 95 | 48 | 0 |
| 4000 | Exact match | 0/16 | 95 | 48 | 0 |
| 4000 | Harmful memories | 14/16 | 385 | 34 | 27 |
| 4000 | Both outcomes | 13/16 | 396 | 35 | 3 |
| 4000 | Random outcomes | 5/16 | 127 | 40 | 145 |
| 5000 | No memory | 0/16 | 106 | 48 | 0 |
| 5000 | Exact match | 0/16 | 106 | 48 | 0 |
| 5000 | Harmful memories | 14/16 | 352 | 34 | 56 |
| 5000 | Both outcomes | 14/16 | 398 | 34 | 10 |
| 5000 | Random outcomes | 1/16 | 102 | 44 | 117 |

</details>

Exact matching is a constructed floor: noisy observations have unique vectors, so it cannot recall. Use no memory, random outcomes, and cue removal as the other controls.

Harmful-only memory matches or beats both outcomes in every cohort: 56/64 versus 49/64 successful lives. Both outcomes produce more safe meals overall, with fewer safe refusals. The default uses both outcomes as a policy to investigate. On seed 3000, harmful-only memory also eats more safe food and fewer harmful meals. The worked failure follows.

Seed 3000 is held out from participant tuning, but its result is known to the facilitator. Additional [validation cohorts](data/evaluation.json), tested after settings were fixed, reach 13/16 and 14/16 with both outcomes. No memory reaches zero on both. These designed habitats demonstrate a mechanism; they do not establish biological learning or broad benchmark performance.

On seed 2000, 32 contacts receive 150 Hz and 165 receive 200 Hz. One fly still feeds under recalled bitter input. Seed 3000 has three such contacts. At 150 Hz, one of eight neural seeds feeds; the other seven refuse. The graded interface uses the measured response, including this variation. The mapping itself remains engineered.

For an application that retains memory across sessions, pass `path="state/personal-memory"` to `ExperienceMemory(24, ...)` instead of using temporary storage. Closing and reopening this path retains the actual Edge shard and its observed outcomes. Allocate new point IDs across sessions; duplicate IDs raise an error. The experiment deliberately uses fresh temporary shards to preserve its matched controls.

### Inspect a misleading safe memory

On seed 3000, select Fly 02, encounter 22. The closest memory is nourishing point three at cosine 0.780. The fly eats a harmful mixture. In the same pre-contact history, harmful point five scores 0.776. A harmful-only filter recalls it, recruits 200 Hz, and changes MN9 left from 81 Hz to zero. Inspect the [captured query comparison](data/masking-example.json). Reproduce it with `WORKSHOP_EXERCISE=1 uv run python tools/inspect_recall.py`. The closest match can be the wrong evidence for the action.

## Boundaries and provenance

The connectome and synaptic weights stay fixed. Stimulation follows the upstream Poisson-input protocol, including zero refractory period on stimulated cells. Recall-to-bitter mapping, the feeding gate, odor mixtures, sickness, and body movement are engineered. The system learns through external experience storage. It claims no biological plasticity. The brain view shows named population activity in a schematic layout, rather than anatomical neuron positions.

The measured DoOR data covers nine single odorants and 24 complete receptor columns. Linear mixtures, recipe variation, sensor noise, and a 30% acetophenone lure cue are designed. Cue removal and random outcomes are negative controls. The vector contains receptor responses only. Payloads contain observed outcome and time only.

Each response reuses one of eight neural seeds per stimulus. The trials reset to a naive network state. This is event-based neural replay, rather than continuous neural control of a body. Verify live checks selected contacts under the same reset protocol. The model's P9 walking drive and sugar-associated halting are measured; the approach path is scripted.

See [data provenance](data/NOTICE.md), [brain adapter](brain.py), and [sensory representation](senses.py). Regenerate all recordings with `uv run --extra brain python tools/record_brain.py --output artifacts/new-brain-bank`. This takes about eight minutes and requires the pinned source.

## Troubleshooting

An HTTP 409 means another experiment or live calculation is running. An HTTP 501 names an unfinished participant hook. An HTTP 422 means invalid settings or a memory absent from that encounter's history. An HTTP 404 means a run expired from the six-run cache. Rerun the experiment. An HTTP 503 reports missing live dependencies or another runtime failure; inspect the server log.

A clone can use the complete recorded experiment offline after installing packages. The optional live brain clone downloads the upstream source and connectome. An existing brain checkout is preserved and checked against recorded hashes. Use one app process because run histories and the live network are process-local.

## Official references

- [Qdrant Edge quickstart](https://qdrant.tech/documentation/edge/edge-quickstart/) covers embedded shards and explicit optimization.
- [Reading data](https://qdrant.tech/documentation/edge/edge-api/reading-data/) covers nearest-neighbor queries and payload selection.
- [Shiu et al. 2024](https://www.nature.com/articles/s41586-024-07763-9) describes the computational brain model.
- [Sapkal et al. 2024](https://www.nature.com/articles/s41586-024-07854-7) describes walking and halting circuits.
- [DoOR 2.0](https://doi.org/10.1038/srep21841) describes the receptor-response data.
