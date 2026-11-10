# AI Dev Day workshop

Read `~/.claude/CLAUDE.md` and [AGENTS.md](AGENTS.md). They own the shared guidance and simulation invariants.

## Purpose and flow

This is a 45-minute conference workshop for AI builders, including retrieval beginners. Teach retrieval through a fun worked example. Prioritize intuitive visuals, visible evidence, and transfer to other workloads. Keep Qdrant branding accurate and avoid sales language.

The flow is: context, no-memory demo, retrieval lesson, personal-memory build, personal demo, shared-memory lesson, shared-memory build, shared demo, and conclusion. The presenter codes; attendees can download the same files. The 16 Google Slides use minimal text, diagrams, and detailed notes. Use the same fly views throughout the concepts. Keep the visuals simple while teaching the technical mechanisms. The demos teach behavior; the slides teach how retrieval works and which design choices matter. Use short formulas, signatures, field names, and predicates when they explain the mechanism. Keep full executable functions in speaker notes and the editor. Repeat a visual when it explains a new step or a useful comparison. The conclusion maps the design choices to other systems.

## Edit surfaces

| File | Role |
| --- | --- |
| `memory.py` | Build one: implement `remember` and `recall`. Preserve the supplied decision consumer. |
| `pipeline.py` | Build two: change `scope` so newcomers can retrieve another fly's observations. |
| `fly_brain.py` | Explain the real sensory adapter and neural readout. Attendees need not edit it. |

The starter TODOs are intentional. `--solution` runs the completed reference without changing these files. The VS Code explorer shows only these three files and the README.

Runtime and tests live in `_internal/`. Presenter materials and evaluation live in `_maintainer/`. Generated files live in `_internal/artifacts/`. Earlier work and the unused upstream checkout remain in `_internal/archive/`. Downloads exclude `_internal/artifacts/` and `_internal/archive/`.

## Brain and memory boundaries

The fixed FlyWire model integrates 138,639 neurons. Its actual neural readout selects fork options and controls physical yaw. The application supplies perception, option mapping, and forward movement. Retrieval changes sensory input to fixed wiring. Preserve the measured left bias and explicit zero-readout failure. See `fly_brain.py` and AGENTS.md for the protocol.

Eight independent brains use matched seeds across stages. They advance on one simulation clock and stream movement and evidence during computation. Writes follow all current-cycle decisions. Personal A flies start empty and retrieve only their own completed observations. New B flies retrieve the completed A group. B observations are not published during this comparison. Failures remain visible. The gray comparison reuses the selected seed's actual earlier run.

Qdrant Edge searches 192-dimensional scene-specific view descriptors with cosine threshold 0.90. Store completed observations with source and capture evidence. `returned` means crossing START, `dead_end` means a terminal wall, and `open` means another opening or exit.

Show actual returns, cosine scores, local query-call times, and spikes. Cosine measures similarity, not outcome confidence. Search time excludes encoding and neural computation. HNSW diagrams are schematic; the tiny shard supports no production-scale latency claim.

## Handoff: 2026-11-10

The opening group uses seeds 300–307 and focuses A6/B6. It produced four, six, and eight exits across the stages. **New group** samples fresh seeds. The held-out evaluation uses 50000–50015: 5/16, 9/16, and 16/16 exits within 65 seconds. See [evaluation details](_maintainer/evaluation-summary.md) for full measures and limitations.

The last release passed 14 Python tests, three JavaScript checks, four dense neural checks, and the ownership audit. Astra found no route fallback or blocker. Work inline. Dylan rejected repeated or parallel reviews. Preserve the current design during manual finishing.

Start with [the presenter guide](_maintainer/presenter.md) for timing, exact builds, controls, and recovery. [Slide notes](_maintainer/slides.json) contain the lesson details.

```sh
uv run run.py                         # Workshop starter code; http://127.0.0.1:8766
uv run run.py --solution              # Completed rehearsal code
uv run run.py --check personal        # Check the saved first build
uv run run.py --check shared          # Check the saved second build
uv run pytest
uv run ruff check
node --test _internal/tests/test_maze_rerun.cjs
uv run run.py --verify                # Dense neural integration checks
uv run run.py --evaluate              # Recompute declared held-out groups
uv run run.py --export                # Recompute offline playback and build the ZIP
```

Keep the native deck, notes, PDF, offline HTML, and ZIP synchronized. Export writes `_internal/artifacts/fly-memory-workshop.zip`.

- [Google Slides](https://docs.google.com/presentation/d/1aj-Nia6P6c8aZw6a_gu1u8tqcZn0tQ2mNLOttiZOWCI/edit)
- [Existing public ZIP](https://drive.google.com/file/d/1OQzqriEYKj4KyG4AuuVJOAPegMhSYkqY/view). Replace its bytes to preserve the slide QR link.

The live display streams all eight flies without automatic event holds. The ten-seed gate and opening-group frames match the previous release. Live stream, ownership, and cancellation checks passed.

At handoff, the local server runs completed rehearsal code. Stop it before starting a session with the starter code. Git changes remain uncommitted. Do not commit or push without Dylan's explicit instruction.
