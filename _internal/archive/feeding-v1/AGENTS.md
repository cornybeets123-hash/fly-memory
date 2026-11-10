# Workshop instructions

Read `~/.claude/CLAUDE.md` and applicable project instructions.

- Edit `memory.py` for personal memory and `pipeline.py` for shared memory.
- Keep the brain adapter visible in `fly_brain.py`. Keep application plumbing in `_internal/`.
- Attendees use the same files as the presenter.
- Keep world schedules, matched neural seeds, recording inputs, and feeding threshold fixed when comparing retrieval changes.
- Store only directly observed outcomes, observation times, and source fly IDs. Keep spectator labels outside the decision pipeline.
- Apply shared writes after all decisions on the current step.
- Label neural replay, live computation, engineered movement, and simulated poison accurately.
- Report survival, safe feeding, and harm together. Preserve failed controls and declared evaluation seeds.
- Preserve original work in `_internal/archive/`. Exclude that folder from workshop downloads.
- Run `uv run pytest` and `uv run ruff check` on changed Python files.
- Do not commit or push without explicit approval.
