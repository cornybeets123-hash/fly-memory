# Fly Memory

Give a simulated fly brain personal memory with Qdrant Edge. Watch experiences become searchable points, recalled memories change sensory input, and neural responses determine feeding.

## Run

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```bash
uv sync --locked
uv run uvicorn workshop.server:app --host 127.0.0.1 --port 8766
```

Open <http://127.0.0.1:8766>. Qdrant Edge runs in-process. The core needs no Docker, API key, model download, or LLM service. Stop the server with `Ctrl+C`.

- [Participant guide and retrieval exercises](workshop/README.md).
- [45-minute facilitator plan and coding-agent prompts](workshop/FACILITATOR.md).
- [Participant hooks](workshop/student_memory.py).
- [Data provenance and scientific boundaries](workshop/data/NOTICE.md).

## The experiment

Sixteen flies start with separate, empty memories. They store observed meals and query 24 receptor-response dimensions. Retrieved evidence changes bitter sensory input to the unchanged Shiu et al. model: 127,400 neurons and 14,687,178 synaptic connections.

The app uses 48 labeled neural recordings, with raw spikes and source hashes for audit. Optional live verification reruns selected encounters through the complete model. The brain layout is schematic. Odor mixtures, sickness, movement, and the feeding gate are engineered.

Delete memory five for Fly 07 at encounter six. Feeding motor output changes from 4 Hz to 78 Hz. Restoring the memory returns it to 4 Hz.

Success requires survival and at least 12 safe meals. Across four cohorts, harmful-only memory produces 56/64 successful lives, both-outcome memory produces 49/64, and no memory produces zero. Both outcomes yield more safe meals overall and fewer safe refusals, but fewer flies succeed. Participants investigate why adding safe memories can hide a hazard. See the [complete evaluation](workshop/data/evaluation.json) and [worked failure](workshop/README.md#inspect-a-misleading-safe-memory).

## Check

```bash
uv run pytest -q
uv run ruff check workshop tests tools solutions
uv run python -m workshop evaluate
```

Optional live computation:

```bash
uv sync --locked --extra brain
uv run python -m workshop setup-brain
uv run python -m workshop verify --trial p9-sugar-bitter-200-seed-103
```

Live computation needs the upstream connectome and several gigabytes of RAM. See the [participant guide](workshop/README.md) for persistence, recording regeneration, and troubleshooting.

The original scripts, charts, and site remain available. Their setup and results are preserved in the [original experiment notes](docs/original-experiment.md). Add `--extra legacy` to `uv sync` when running the original Qdrant client scripts.
