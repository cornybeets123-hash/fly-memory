# Workshop instructions

Read `~/.claude/CLAUDE.md`, project `CLAUDE.md`, and applicable project instructions.

- Edit `memory.py` for personal memory and `pipeline.py` for shared memory.
- Keep the brain adapter visible in `fly_brain.py`. Keep plumbing in `_internal/maze/` and `_internal/brain/`.
- Attendees use the presenter's files.
- Keep worlds, initial poses, neural seeds, noise streams, and body parameters fixed across memory comparisons. Sensor input follows the current pose.
- Store directly observed views and completed traversal outcomes with source, times, layout, and encoder/controller protocol.
- Preserve each view snapshot with a content hash. Never encode IDs, global coordinates, hidden topology, or outcomes into its vector.
- Apply writes after all current-cycle decisions. Never publish recalled guesses as observations.
- Keep raw results, selected evidence, applied policy changes, neural activity, and physical movement separate.
- Label live computation, recorded playback, fixed neural wiring, and engineered movement accurately.
- Report exit success, time, path length, detours, collisions, and false exclusions together. Preserve failed controls and declared seeds.
- Use an explicit local option-to-sensory mapping. The neural readout selects fork options and controls every physical turn. Forward motion is engineered.
- Pass the approved ten-seed integrated junction gate before new maze UI or slide work. No hidden route or direct motor fallback is approved.
- Display actual spikes and query results. Label schematic HNSW diagrams explicitly.
- Preserve previous work in `_internal/archive/`. Exclude archives from workshop downloads.
- Run `uv run pytest`, `uv run ruff check`, and the neural checks after runtime changes.
- Only the root agent edits project code. Review agents remain read-only.
- Do not commit or push without explicit approval.
