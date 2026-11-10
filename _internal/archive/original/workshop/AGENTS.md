# Workshop agent instructions

Read the root instructions and this directory's README before editing.

- During exercises, do not read or copy `solutions/` unless the participant explicitly requests the solution.
- Complete participant exercises in `student_memory.py`.
- Use pinned Qdrant Edge APIs and current official documentation.
- Keep seeds, potential contacts, neural recordings, and motor thresholds fixed during retrieval exercises.
- Start every personal shard empty. Store only observed meal outcomes and observation times in point payloads.
- Keep hidden outcomes, positions, recipe names, and future observations out of retrieval and sensory-input decisions.
- Preserve matched neural seeds across conditions and memory interventions.
- Test participant hooks with `WORKSHOP_EXERCISE=1 uv run pytest tests/test_memory.py -q`.
- Report safe feeding, harmful feeding, and survival together. Include held-out seed 3000 and failed controls.
- Label recorded neural responses and live calculations accurately. Movement and the brain layout are engineered visuals.
- Keep simulation visuals prominent, text short, and Qdrant visible.
- Preserve the original experiment files and other applications' services.
