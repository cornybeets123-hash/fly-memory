"""Completed workshop code for rehearsal and facilitator recovery."""

from qdrant_edge import (
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
    shard.update(UpdateOperation.upsert_points([point]))


def recall(shard, vector, exclude_fly=None):
    return shard.query(
        QueryRequest(
            query=Query.Nearest(vector, using="odor"),
            limit=LIMIT,
            score_threshold=MIN_SIMILARITY,
            filter=Filter(
                must=[FieldCondition("outcome", match=MatchValue(-1))],
                must_not=[FieldCondition("source_fly", match=MatchValue(exclude_fly))]
                if exclude_fly is not None
                else None,
            ),
            with_payload=True,
        )
    )


def decide(hits):
    score = max(
        (hit.score for hit in hits if hit.payload["outcome"] == -1), default=0.0
    )
    return min(1.0, max(0.0, score))


def retrieve(memory, personal, shared, vector, fly, mode):
    if mode == "none":
        return []
    hits = memory.recall(personal, vector)
    if mode == "shared":
        hits += memory.recall(shared, vector, exclude_fly=fly)
    return hits


def observe(memory, personal, shared, point, mode):
    if mode == "none":
        return
    memory.remember(personal, point)
    if mode == "shared":
        memory.remember(shared, point)
