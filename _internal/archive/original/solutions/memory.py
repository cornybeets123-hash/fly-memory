"""Facilitator reference for the three retrieval exercises."""

from qdrant_edge import (
    FieldCondition,
    Filter,
    MatchValue,
    Query,
    QueryRequest,
    UpdateOperation,
)


def store(shard, point):
    shard.update(UpdateOperation.upsert_points([point]))


def search(shard, vector, threshold, top_k, harm_only=False):
    return shard.query(
        QueryRequest(
            query=Query.Nearest(vector, using="odor"),
            limit=top_k,
            score_threshold=threshold,
            filter=Filter(must=[FieldCondition("outcome", match=MatchValue(-1))])
            if harm_only
            else None,
            with_payload=True,
            with_vector=False,
        )
    )


def evidence(hits):
    """Signed evidence from observed outcomes, with cosine-weighted neighbors."""
    total = sum(max(h["score"], 0) for h in hits)
    return (
        sum(-h["outcome"] * max(h["score"], 0) for h in hits) / total if total else 0.0
    )
