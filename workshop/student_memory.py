"""Participant exercises. Keep orchestration, brain parameters, and worlds fixed.

Implement these functions using the native Qdrant Edge API.
Test the contract with WORKSHOP_EXERCISE=1.
"""

from qdrant_edge import (  # noqa: F401
    FieldCondition,
    Filter,
    MatchValue,
    Query,
    QueryRequest,
    UpdateOperation,
)


def store(shard, point):
    """Exercise 1: write this observed experience to the Edge shard."""
    raise NotImplementedError(
        "Complete student_memory.store, then run the memory contract."
    )


def search(shard, vector, threshold, top_k, harm_only=False):
    """Exercise 2: cosine search on 'odor', with payloads and optional outcome filter."""
    raise NotImplementedError(
        "Complete student_memory.search, then inspect actual matches in the UI."
    )


def evidence(hits):
    """Exercise 3: return signed aversion evidence in [-1, 1] from observed outcomes.

    A nourishing outcome is +1. A harmful outcome is -1. Return the weighted
    mean of negated outcomes, normalized by the sum of nonnegative cosine scores.
    One harmful hit must return +1 regardless of its score. The framework scales
    this vote by the strongest cosine afterward. Empty or zero-weight recall
    returns zero and preserves the brain's naive input.
    """
    raise NotImplementedError(
        "Complete student_memory.evidence and test held-out seeds."
    )
