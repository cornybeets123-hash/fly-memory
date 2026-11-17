# AI Dev Day workshop redesign plan

This proposal turns the 45-minute AI Dev Day session into a guided retrieval lesson. Two matched habitats show multiple flies navigating with and without memory. Slides explain the model and retrieval, a browser exercise gives attendees one policy decision, and a final demonstration exposes both success and failure.

Keep the computational brain model. Improve the visible consequences of memory, add tested variation in sensory input, and keep the core exercise accessible without installation. The public title remains "Simulated Fly Brain, Persistent Trauma."

## Spatial survival demonstration

The main demo compares 16 flies without memory against 16 flies with personal memory. Each pair starts from the same conditions. Their routes diverge through different decisions. A shared-memory condition can follow after attendees understand personal memory.

Give the flies an energy budget that declines over time. Eating safe food replenishes energy. Harmful meals cause injury. Death can follow injury or energy depletion, so avoiding every meal cannot win. Show survival, safe meals, harmful meals, and remaining energy together.

The body controller selects targets, walks, and turns. Retrieved experience changes target selection and avoidance. At contact, the computational brain determines feeding through the measured motor response. These responsibilities must remain visible and accurately labeled.

Use recorded neural responses during the population simulation. Each contact selects its actual recorded condition and seed. Keep a live rerun available for a selected encounter. Multiple bodies can move simultaneously without running a complete neural simulation for every animation frame.

Keep world generation independent of action-dependent random-number consumption. Fix environmental schedules and draw observation noise from separate reproducible streams. Memory may change the visited locations and observed outcomes. It must not silently change future external events through an unrelated random-number sequence.

Reuse the current receptor representation, Edge memory, and brain adapter. Store only observed outcomes and observation times in memory payloads. Positions guide body movement; they do not become hidden retrieval labels. Reveal a harmful meal only after the fly observes its outcome.

The original spatial engine in `sim.py` already supplies moving flies, contact events, personal memory, shared memory, and a new hazard. A fresh check ran 16 flies for 400 steps on seeds zero, one, and two.

| Condition | Survivors on each seed | Safe meals on each seed | Harmful contacts on each seed |
|---|---|---|---|
| No memory | 2, 1, 0 | 40, 51, 34 | 45, 47, 48 |
| Personal memory | 2, 4, 7 | 40, 51, 53 | 45, 44, 40 |
| Shared memory | 16, 15, 16 | 71, 68, 80 | 7, 11, 6 |

These exploratory runs used the older controller and synthetic 64-dimensional odors. Personal memory uses array similarity; shared memory uses the legacy client. The controller does not use the connectome model. Its action-dependent respawns also require repair before a strict matched-world comparison.

Use this engine as a spatial scaffold. Measure the combined system before making survival claims. Personal memory must earn its benefit through learned experience. Shared memory must identify the earlier observation from another fly that supplied each warning.

The first implementation milestone is a working spatial comparison with inspectable decisions and fair world generation. Richer sensory channels follow that milestone.

## Decisions and conference requirements

Dylan confirmed a 45-minute slot and chose to keep the real brain model. The organizer confirmed no prerequisites. The workshop takes place on November 30. Draft slides are due November 11, and final files are due November 20. The November 6 email supersedes the older draft deadline in the guidelines.

The [speaker guidelines](https://docs.google.com/presentation/d/1jbW406I-W6NgLQU6FgsQPIlGaVW8oYBU/edit) specify theater seating, no audience power outlets, an offline fallback, and a helper. They require a 16:9 PowerPoint or Keynote file, text at least 24pt, and code blocks no longer than 15 lines. Their generic workshop duration is 40 minutes; Dylan's explicit 45-minute allocation governs this plan.

Teach concepts that transfer across retrieval implementations. Name Qdrant Edge when explaining the implementation. Keep company positioning, comparisons, customer logos, and product tours outside the lesson.

## Input feasibility results

The adapter currently fixes sugar and walking input at 150 Hz. Memory varies bitter input across five recorded levels. The underlying model accepts stimulation of additional mapped neuron groups.

A live investigation ran 39 new one-second trials across three fixed seeds: 100, 103, and 106. Each trial restored the same naive network. Model weights, connectivity, and the workshop's feeding gate stayed fixed. Feeding means MN9 left exceeds 10 Hz.

| Stimulation | MN9 left across three seeds | Observed result |
|---|---:|---|
| Sugar 50 Hz | 18–22 Hz | All three trials passed the feeding gate. |
| Sugar 50 Hz plus bitter 150 Hz | 0 Hz | All three trials refused. |
| Sugar 200 Hz | 90–93 Hz | All three trials passed the feeding gate. |
| Sugar 200 Hz plus bitter 150 Hz | 22–25 Hz | All three trials still fed. |
| Sugar 200 Hz plus bitter 200 Hz | 13–16 Hz | All three trials still fed at the current maximum warning. |
| Water 200 Hz | 24–31 Hz | All three trials passed the feeding gate. |
| Water 200 Hz plus bitter 150 Hz | 0–1 Hz | All three trials refused. |
| Sugar 150 Hz plus Ir94e 150 Hz | 39–55 Hz | This input did not suppress feeding under the tested conditions. |

The feeding probes also supplied the current 150 Hz walking drive. These are stimulation rates, not calibrated sugar or water concentrations. Stronger sugar input must not be described as biological hunger. The model omits internal state and several neuromodulatory mechanisms.

Mechanical stimulation of JON-CE activated the published grooming readouts: DN1 reached 12–15 Hz, DN2 reached 16–21 Hz, and aBN1 reached 49–54 Hz. JON-F produced zero in both descending readouts and 0–2 Hz in aBN1. This demonstrates pathway differences. It does not establish a simulated body's grooming behavior.

Version-matched v630 annotations provided olfactory neuron groups. The tests stimulated 29 left DM2 neurons, 21 left DM4 neurons, and their combination. The three conditions produced distinct downstream activity patterns across all three seeds. For example, the first DM2 projection-neuron readout reached 208–210 Hz under DM2 stimulation and 159–163 Hz under DM4 stimulation.

The smell test establishes input propagation and a repeatable difference between conditions. It does not establish natural odor recognition, navigation, or a complete odor-to-behavior model. The fixed 150 Hz stimulation is an engineered probe. Calibrating the existing odor library and handling receptors expressed together remain separate tasks.

The local notebook matched the pinned upstream notebook byte for byte. Experiment scripts, neuron IDs, source hashes, and results are archived under `artifacts/input-feasibility-2026-11-09/`.

## Recommended use of richer inputs

After the spatial comparison works, use variable sugar stimulation as the first sensory extension. It asks whether a correct memory can lose to competing sensory input. The measured answer is yes under the current warning range.

Keep the ordinary 150 Hz sugar condition for the participant challenge. Use the stronger 200 Hz condition as a deliberate failure demonstration. Explain that retrieval succeeded while the downstream action remained unsafe. Do not present a retrieval adjustment as a remedy when the strongest available warning still fails.

Develop true smell input as the next bounded experiment. Map a small set of receptors to version-matched olfactory neurons. Measure the resulting projection-neuron patterns before choosing a retrieval representation. Compare those patterns with the existing receptor vectors. Preserve the existing sensory representation as the working path until the new representation passes meaningful controls.

Keep water as a tested backup example. Keep mechanical stimulation and Ir94e in the appendix unless they explain a retrieval decision. Additional behavior must earn stage time through a clear learning outcome.

The model can accept more channels, but each channel needs a defined stimulus, a verified neuron mapping, and a useful measured readout. Continuous body control would require a separate protocol.

## Opening demonstration

Give the presenter two prominent habitat views, a population summary, and a dedicated scene player. The presenter can pause, select a fly, and inspect its decision.

1. Start both populations together. Let the room watch food seeking, injuries, energy use, and survival diverge.
2. Pause when a fly encounters something similar to an earlier harmful meal. Ask the room to predict its next action.
3. Zoom into the actual query, recalled experience, and neural feeding response. Resume the world and show the resulting movement or meal.
4. Restore the complete pre-decision state and remove the relevant memory. Rerun that branch with the same environmental schedule and random streams. Show whether its action and later route change.
5. Introduce a new hazard and compare adaptation. Add the shared-memory condition only when the personal-memory comparison is clear.

Preserve the existing Fly 07 intervention as a separate known example: removing point five changes 4 Hz to 78 Hz. Restoring it recovers 4 Hz. A new spatial encounter needs its own measured result; it must not inherit those numbers by assumption.

Keep the full body action, the selected memory, and one motor readout prominent. Reveal the vector and spike detail only when they answer the current question. Use an honest schematic for body movement and brain layout.

Start one live neural verification during the brain explanation. The tested baseline and warning trials matched their recordings at about 12 and 13 seconds. Use the recorded scene immediately if the live calculation fails. Live verification confirms that the model can reproduce the recording.

Reserve the stronger sugar lure for the results discussion. Ask whether successful retrieval guarantees a safe action before revealing its failure.

## Retrieval lessons

By the end, attendees should be able to explain one complete memory-assisted decision and identify where it failed.

- An observation becomes a vector. This example begins with receptor responses; text applications often use an embedding model.
- Similarity search finds related observations when exact values differ.
- Cosine similarity compares vector direction. A similarity score is not a probability of a safe action.
- Top-k limits the number of returned candidates. A threshold excludes candidates that are insufficiently similar.
- A payload filter controls which stored observations are eligible. It uses known metadata, not future outcomes.
- The decision rule interprets retrieved evidence. Retrieval quality and action quality require separate checks.
- A write follows observed feedback. Refusal supplies no meal outcome, so it creates no outcome memory.
- Evaluation measures useful behavior, including safe meals, harmful meals, and safe refusals. An unseen cohort tests the chosen policy.

Use the same fly encounter to introduce these concepts. Add a tool-failure example and a robot-observation example near the end. These provide three concrete applications without introducing another live system.

## Forty five minute run of show

| Minutes | Segment | Audience action |
|---|---|---|
| 0–5 | Open with the matched encounter and memory intervention. | Predict an action and choose a memory to remove. |
| 5–9 | Explain the computational brain, its inputs, and the engineered adapter. | Identify which part changes when memory changes. |
| 9–22 | Teach representation, similarity, retrieval controls, feedback, and decision rules. | Make two short predictions using visible examples. |
| 22–24 | Show the implementation and the complete memory loop. | Locate query, payload, decision, and write in the code. |
| 24–32 | Run the browser policy exercise. | Predict, test, inspect a failure, and freeze one policy. |
| 32–39 | Compare fresh-cohort results and inspect a failure. Show the stronger sugar lure if the expanded bank is ready. | Explain whether retrieval, evidence interpretation, or sensory competition caused the failure. |
| 39–43 | Transfer the loop to tool use and robotics. | Name an observation, outcome, and success measure for one application. |
| 43–45 | Answer questions and show the take-home package. | Save the code and experiment instructions. |

## Slide storyboard

Use about 24 simple frames, including demo cues and exercise screens. Several frames can progressively reveal one diagram. Keep additional experimental detail in backup slides.

| Frame | Subject | Visual or interaction |
|---|---|---|
| 1 | Survival with and without memory | Open on the two moving populations. |
| 2 | One fly's next decision | Pause and inspect the selected encounter. |
| 3 | The causal memory | Restore the checkpoint, remove one point, and compare the branch. |
| 4 | The brain's wiring | Explain the connectome and simplified neurons. |
| 5 | The model and the surrounding system | Distinguish computed spikes, external memory, engineered inputs, and schematic movement. |
| 6 | The memory loop | Follow one observation through retrieval, action, feedback, and storage. |
| 7 | An observation as numbers | Reveal the actual receptor-response vector. |
| 8 | Related sensory patterns | Compare two real response patterns. |
| 9 | Similarity | Explain direction and cosine with an illustrative projection. |
| 10 | Nearest candidates | Show actual returned IDs, scores, and outcomes. |
| 11 | Similarity threshold | Show a query with and without a qualifying match. |
| 12 | Neighbor count | Hold the query fixed and vary the candidate budget. |
| 13 | Payload filters | Show eligibility based on observed outcomes. |
| 14 | The decision rule | Compare a weighted vote with a harmful-evidence warning. |
| 15 | Writing memory | Reveal feedback only after the action. |
| 16 | Retrieval failures | Connect missing information, corrupted feedback, and unsuitable evidence interpretation to their controls. |
| 17 | Implementation | Show a short query and the surrounding loop. Name Qdrant Edge here. |
| 18 | Exercise objective | Define success, available settings, and the prediction requirement. |
| 19 | Exercise timer and help | Keep the task and progressive hints readable throughout the activity. |
| 20 | Calibration results | Show safe meals, harmful meals, refusals, and successful lives together. |
| 21 | Fresh cohort | Evaluate the frozen policy before further tuning. |
| 22 | One failure explained | Inspect one retrieved point and its downstream effect. Use the stronger lure only with clear input labels. |
| 23 | Transfer to applications | Map the same loop to tool failures and robot observations. |
| 24 | Resources and questions | Provide the working package, papers, and next experiment. |

Every displayed code block must fit within 15 lines. Use at least 24pt text and test the projected slide, not just the editor view. Keep source citations in notes and place necessary experiment labels on screen.

## Browser exercise

The required activity is a retrieval-policy experiment. It works without Python installation, Docker, an API account, or a coding agent.

Give attendees three choices: neighbor count, similarity threshold, and evidence rule. A compact initial grid uses k values of one, three, and five; thresholds of 0.50, 0.60, 0.70, and 0.80; and two evidence rules. That produces 24 policies.

Each attendee predicts a result, evaluates the calibration scenario, inspects one mistake, and freezes a policy. The next screen reveals results from previously unseen scenarios. Later tuning uses another fresh evaluation set.

A static browser package can contain summaries and selected traces generated by real Qdrant Edge runs. Label these as precomputed retrieval results and recorded neural trials. Include only the histories needed for explanation. One complete current run serializes to about 1.50 MB, or 447 KB compressed, so duplicating full histories for every policy is wasteful.

Use a show of hands for room comparisons. The activity must remain useful without a submission service. A downloaded browser package supports offline participation; if initial delivery fails, the presenter runs the same exercise with paired discussion and visible candidate cards.

Provide a complete runnable repository and an optional coding exercise after the session. Attendees should explain their policy themselves, even when they later use a coding agent.

## A measured correction to the current lesson

Opus challenged the claim that more neighbors inherently worsen retrieval. The current evidence rule averages observed outcomes, so safe examples can outweigh a warning. A separate experiment changed only that evidence rule.

| Known cohort and policy | Successful lives | Safe meals | Harmful meals | Safe refusals |
|---|---:|---:|---:|---:|
| Seed 2000, five neighbors, current weighted vote | 4/16 | 210 | 44 | 2 |
| Seed 2000, five neighbors, warn on any harmful hit | 15/16 | 362 | 33 | 26 |
| Seed 3000, five neighbors, current weighted vote | 0/16 | 168 | 48 | 2 |
| Seed 3000, five neighbors, warn on any harmful hit | 12/16 | 352 | 36 | 18 |

The changed rule retained the same potential encounters, vector representation, retrieval settings, brain recordings, and input-scaling mechanism. Different actions changed later observations and memory histories. With one neighbor, both rules produced identical summaries.

Teach the trade-off: evidence interpretation can recover successful lives while increasing safe refusals. These are exploratory results on already-known cohorts. Validate new recommendations on fresh cohorts.

Seed 3000 already appears in prompts and published results. Use it for diagnosis. Select and freeze new evaluation scenarios before viewing their outcomes.

## Implementation sequence

1. **Preserve the evidence.** Archive the completed probes, neuron mappings, hashes, and negative results. Keep the current 150 Hz baseline as a regression reference.
2. **Generalize the stimulus interface.** Use one stimulus description across recorded lookup, live computation, the worker process, simulation, and verification. Include every input rate and seed in trial identity. Remove the bitter-only assumption from the shared adapter, rather than adding separate special cases.
3. **Record a curated taste grid.** Start with sugar rates of 50, 150, and 200 Hz. Combine them with the existing five bitter levels and eight seeds. The existing 40 taste trials can be reused only when protocol identity is verified. Eight P9-only baselines remain separate. Preserve raw spikes and regenerate integrity checks.
4. **Build the spatial simulation and presenter controls.** Reuse current memory and brain components with an explicit movement controller. Add energy, fair environmental schedules, checkpoints, and a population comparison. Preserve exact pre-decision state for memory interventions. Make the known encounter replay available as a fallback.
5. **Build the finite browser exercise.** Generate policy artifacts from actual engine runs. Include source and protocol provenance. Separate calibration from reveal, and avoid the current shared lock and six-run cache.
6. **Develop the smell experiment separately.** Confirm receptor mappings and resolve receptors expressed together. Calibrate stimulation. Test whether neural response vectors improve a useful retrieval decision. Add it to the main workshop only after that result exists.
7. **Author and rehearse the deck.** Prioritize the November 11 draft and November 20 final file. Include presenter cues, participant instructions, visible source labels, and a recorded fallback.

The fuller taste grid contains 120 trials before the eight walking baselines. If 40 existing trials remain reusable, 80 new trials are needed. At the measured 12–15 seconds per taste trial, serial computation is approximately 16–20 minutes, plus setup. This estimate covers recording computation only.

## Acceptance checks

**Scientific behavior:** reproduce the current default summaries and the 4/78/4 Hz intervention after changing the stimulus interface. Reconstruct recorded rates and traces from raw spikes. Keep model sources pinned and document each new mapping.

**Spatial behavior:** verify that visited locations determine encounters, and that meals require contact and the neural feeding response. Verify energy depletion and injury. Check that intervention branches share environmental schedules and random streams. Preserve the no-memory and corrupted-memory controls.

**Stage scenes:** test removal of both relevant and irrelevant points. Test restoration and deliberate outcome corruption. Report neural-seed variation. A scene presented as reliable should produce the same decision in at least seven of eight recorded seeds.

**Evaluation:** predeclare scenarios and settings before checking results. Show safe feeding, harmful feeding, and safe refusals together. Preserve missing-cue and corrupted-feedback controls. Separate a retrieval failure from a downstream action failure.

**Delivery:** test cold starts, one-key reset, offline presenter use, and the browser package without external calls after loading. Keep a recording available. Assign the helper to attendee access and timing.

**Learning:** rehearse with five builders who are new to search. At least four should complete the browser task within eight minutes and explain one real retrieved point. Ask which point passes the threshold, how the rule uses its outcome, and which intervention tests its effect.

**Language:** describe measured wiring, simplified neurons, computed spikes, external memory, engineered input mapping, and schematic movement accurately. A two-dimensional display projection does not replace the actual query vector.

## Sources and consultation

- [Public AI Dev session page](https://ai-dev.deeplearning.ai/speakers/dylan-couzon).
- [Organizer email with updated slide deadlines and no prerequisites](https://mail.google.com/mail/u/?authuser=dylan.couzon%40qdrant.com#all/1a1b1fb70688db21).
- [Speaker guidelines](https://docs.google.com/presentation/d/1jbW406I-W6NgLQU6FgsQPIlGaVW8oYBU/edit).
- [Shiu and colleagues, computational brain model](https://www.nature.com/articles/s41586-024-07763-9).
- [Pinned upstream input definitions and experimental sweeps](https://github.com/philshiu/Drosophila_brain_model/blob/91bdd1e7dcf193f3e7ca5a8933497fcef63b7960/figures.ipynb).
- [Version-matched v630 classification data](https://github.com/murthylab/flywire-network-analysis/tree/ee4944c03429edf857a6b10bcf98bea7dcef35b8/v630_data).
- [Pinned DoOR receptor mappings](https://github.com/ropensci/DoOR.data/blob/db323a496577c4b4a72b5c2fcd1859e07521ffb5/data/door_mappings.csv).
- [Current workshop source](https://github.com/qdrant-labs/fly-memory/tree/a75aa682d4f5b2f29a2141ca4bf400eda0a194ad/workshop).

Opus 5.5 reviewed the source and challenged the design in two cc consultations. Its strongest criticism was: "The opening does not lack wow because the visuals are weak. It lacks wow because the cause is hidden."

The recommendation keeps that causal focus. The live probes also establish that broader input pathways are available. Their role in the workshop depends on whether they clarify the retrieval decision.

