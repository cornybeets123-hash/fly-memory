"""Completed retrieval functions for rehearsal and matched evaluation runs."""

from qdrant_edge import (
    FieldCondition,
    Filter,
    MatchValue,
    Query,
    QueryRequest,
    UpdateOperation,
)

PROTOCOL = "maze-texture192-neural-choice-v1"
MIN_SCORE = 0.90
MARGIN = 0.02


def remember(shard, point):
    shard.update(UpdateOperation.upsert_points([point]))


def recall(shard, vector, world, exclude_fly=None, protocol=PROTOCOL, owner="A"):
    if vector is None:
        return []
    return shard.query(
        QueryRequest(
            query=Query.Nearest(vector, using="view"),
            limit=10,
            score_threshold=MIN_SCORE,
            filter=Filter(
                must=[
                    FieldCondition("world", match=MatchValue(world)),
                    FieldCondition("protocol", match=MatchValue(protocol)),
                ]
                + (
                    []
                    if exclude_fly
                    else [FieldCondition("source_fly", match=MatchValue(owner))]
                ),
                must_not=[FieldCondition("source_fly", match=MatchValue(exclude_fly))]
                if exclude_fly
                else None,
            ),
            with_payload=True,
        )
    )


def decide(hits):
    best = {}
    for hit in hits:
        outcome = hit.payload["outcome"]
        if outcome not in best or hit.score > best[outcome].score:
            best[outcome] = hit
    adverse = [best[k] for k in ("dead_end", "returned") if k in best]
    dead = max(adverse, key=lambda hit: hit.score) if adverse else None
    opened = best.get("open")
    if dead is None:
        return None
    if opened is not None and dead.score - opened.score < MARGIN:
        return None
    return dead
