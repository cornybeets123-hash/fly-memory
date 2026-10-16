# Facilitator plan: 45 minutes

## Promise

Participants build and test external agent memory. They learn how representation, neighbor selection, and thresholds affect decisions. The fly makes those effects visible. The same experiments apply to an agent's failed tool calls, a robot's past observations, or a recommendation system's feedback.

The core showcase is Qdrant Edge inside a decision loop. It needs no server round trip. Every displayed match comes from the engine. Shared memory and server synchronization are future extensions; keep them outside this session.

## Prepare before the room arrives

1. Clone the repository and run `uv sync --locked`.
2. Run `uv run pytest -q` and `uv run python -m workshop evaluate`.
3. Start the app on port 8766. Check `/api/status` and open the browser.
4. Install `uv sync --locked --extra brain` and run `uv run python -m workshop setup-brain` for live verification.
5. Verify trial `p9-sugar-bitter-200-seed-103` from the CLI. Keep the app on a single worker.
6. Keep the solution server ready. Participants complete the three hooks in exercise mode.
7. Use a visible timer. Reserve the last five minutes for controls and transfer to attendees' own systems.

Preinstall packages when network access is weak. The bundled trial recordings support the complete retrieval experiment without downloading the model. Live verification is a facilitator check, not a requirement for every laptop.

## Run of show

| Minutes | What participants do | What they should learn |
| --- | --- | --- |
| 0 to 5 | Watch Fly 07 learn from a bad meal, then compare matched lives. | External memory can change decisions while model parameters stay fixed. |
| 5 to 9 | Launch the app and identify query, stored experience, input modulation, and motor readout. | Retrieval belongs inside a measurable decision loop. |
| 9 to 17 | Implement the three memory hooks with a coding agent. Pass the memory contract. | Store observed evidence, search by similarity, and interpret outcomes separately. |
| 17 to 26 | Predict and test raw versus centered vectors, thresholds, and neighbor counts. | More returned context can dilute a useful result. Representation sets the relevance boundary. |
| 26 to 34 | Delete and restore one memory. Reopen a persistent shard. Run the live intervention on the facilitator laptop. | A controlled intervention tests whether recall caused the change. |
| 34 to 40 | Evaluate on seed 3000, then remove the distinguishing cue or randomize outcomes. | Held-out results expose limits. Retrieval cannot repair missing information or unreliable feedback. |
| 40 to 45 | Map the loop to participants' own systems and present one measured result. | Carry the experimental method into agent memory, robotics, recommendations, or another retrieval application. |

## First demonstration

Keep `All experiences`, seed 2000, top one, and threshold 0.60. Fly 07 is the fixed subject, not a selected winner. Let the first six encounters play. Show the activity schematic and actual spikes alongside the memory map.

- Encounter three: the fly eats a harmful pear mixture. Its observed outcome creates memory three.
- Encounter five: a harmful mixed-fruit meal creates memory five.
- Encounter six: a different banana mixture recalls memory five at cosine 0.812. Bitter input reaches 200 Hz. MN9 left reaches 4 Hz, so the fly refuses.
- Select encounter six and click `Delete a memory`. Removing point five changes MN9 left to 78 Hz. Restoring it returns MN9 left to 4 Hz.
- Click `Verify all three live` if the source is installed. The interface will show live calculations and compare all three conditions.

Say: "The connectome stayed fixed. The retrieved experience changed an input. We can remove that experience and test its effect."

The approach path is engineered. The view is a schematic. The motor response is recorded from the unchanged neural model. State these boundaries early.

At 150 Hz, seven neural seeds refuse and one feeds. Compare those traces to see why a retrieved warning does not directly dictate the action.

## Coding-agent prompts

### Build the memory loop

> Read workshop/AGENTS.md and workshop/README.md. Implement store, search, and evidence in workshop/student_memory.py using the installed Qdrant Edge API. Run WORKSHOP_EXERCISE=1 uv run pytest tests/test_memory.py -q. Keep brain parameters, worlds, observation timing, and evaluation seeds unchanged. Explain the named vector, threshold direction, payload filter, and evidence calculation. Show the test output.

### Investigate a retrieval failure

> Predict how top five will differ from top one in this sparse personal history. Prefix participant evaluation commands with WORKSHOP_EXERCISE=1. Evaluate both on seeds 2000 and 3000 using the same brain recordings. Report survival plus enough feeding, harmful meals, and safe refusals. Inspect one actual harmful recall that changes when neighbors are added. Recommend a setting and explain its tradeoff. Do not change the world to improve the score.

For the failure example, use seed 3000, Fly 02, encounter 22. A nourishing neighbor scores 0.780 and hides harmful evidence at 0.776. The [query comparison](data/masking-example.json) holds the pre-contact history fixed. Explain why the nearest experience need not support the safest action.

During the intervention block, run `WORKSHOP_EXERCISE=1 uv run python -m workshop sessions`. Closing and reopening the shard changes feeding from 78 Hz to 4 Hz on a new mixture. The result records the on-disk memory path. Clarify that unfamiliar mixtures retain a recognizable designed cue.

### Test the representation

> Compare raw and centered receptor vectors on both cohorts. Explain why the fixed center uses the input library, not outcome labels. Inspect a pair of queries whose relevant neighbor changes. Keep the query dimension, observed feedback, and neural gate fixed. Report failures as well as improvements.

### Design a transfer

> Choose one application you build. Define its observation, query vector, stored outcome, retrieval policy, downstream action, and success metric. Propose a matched no-memory control and a memory deletion test. Identify feedback the system can observe and labels it cannot know before acting.

## Acceptance checks

The memory contract passes against participant hooks. Every recalled point predates the encounter. Every written outcome follows a meal. No hidden hazard label enters a vector or query. One real deletion changes the recorded motor response and restoration recovers it. A live rerun matches the recorded named traces on the facilitator machine.

Participants report both calibration and held-out results. They preserve the no-memory, random-outcome, and missing-cue controls. Exact matching is a constructed floor because observations never repeat exactly. They explain at least one result where a plausible retrieval change makes the application worse.

## Results to expect

The checked default gives 15/16 successful lives on seed 2000 and 7/16 on seed 3000. Additional fixed-setting cohorts 4000 and 5000 reach 13/16 and 14/16. No memory and exact matching give zero in every cohort.

Across all four cohorts, harmful-only memory matches or beats both outcomes on successful lives: 56/64 versus 49/64. Both outcomes produce more safe meals overall, with fewer safe refusals. Participants investigate that cost in successful lives. Seed 3000 provides the worked failure example.

These are end-to-end environment experiments using recorded neural responses and real Edge retrieval. They reuse eight neural seeds per input. The live intervention verifies selected contacts; it does not turn every replay into a fresh neural calculation.

## Recovery

An unfinished hook should produce a named 501 response, rather than a blank simulation. Use `No memory` while debugging. Restart the same server after editing Python files. Keep port 8766 for the demo.

If the live source or optional dependencies fail, keep the recorded intervention and show the raw spike integrity tests. Explain the limitation. If deletion has no effect, select Fly 07, encounter six, and point five under the default configuration. Later histories can contain redundant evidence.

If attendees finish the hooks early, ask them to produce a failure on held-out data. A passing API call is the start of the exercise.
