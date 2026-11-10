"""BUILD 1. Store an observation. Retrieve an episode. Select its input recording."""

from qdrant_edge import (  # noqa: F401
    FieldCondition,
    Filter,
    MatchValue,
    Query,
    QueryRequest,
    UpdateOperation,
)

from _internal.escape.kernel import PROTOCOL  # noqa: F401

MIN_SIMILARITY = 0.98


def remember(shard, point):
    """Upsert the supplied observed episode."""
    raise NotImplementedError("Build 1: implement remember")


def recall(shard, vector, exclude_fly=None):
    """Search cue vectors. Filter arena and protocol. Return three hits with payloads."""
    raise NotImplementedError("Build 1: implement recall")


def decide(hits):
    """Select the nearest recording. Abstain on empty or tied conflicting evidence."""
    ranked = sorted(hits, key=lambda hit: hit.score, reverse=True)
    if not ranked:
        return
    best = ranked[0]
    if any(
        best.score - other.score < 0.002
        and best.payload["sweep"] != other.payload["sweep"]
        for other in ranked[1:]
    ):
        return
    # Return the recording reference. Safe episodes also contain sensory input.
    raise NotImplementedError("Build 1: return the selected input recording")
