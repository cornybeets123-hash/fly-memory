"""TASK 1. Edit these three functions. Each experience follows an observed meal."""

from qdrant_edge import (  # noqa: F401
    FieldCondition,
    Filter,
    MatchValue,
    Query,
    QueryRequest,
    UpdateOperation,
)

LIMIT = 3
MIN_SIMILARITY = 0.72


def remember(shard, point):
    """Store this observed experience in the given Qdrant Edge shard."""
    raise NotImplementedError("Task 1: implement memory.remember")


def recall(shard, vector, exclude_fly=None):
    """Find up to LIMIT harmful experiences with score >= MIN_SIMILARITY. Exclude a fly when supplied."""
    raise NotImplementedError("Task 1: implement memory.recall")


def decide(hits):
    """Return the strongest harmful score, clipped to [0, 1]. Empty means zero."""
    raise NotImplementedError("Task 1: implement memory.decide")
