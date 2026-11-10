"""Completed workshop functions. Use these for rehearsal and recovery."""

from qdrant_edge import (
    FieldCondition,
    Filter,
    MatchValue,
    Query,
    QueryRequest,
    UpdateOperation,
)

from .kernel import PROTOCOL

MIN_SIMILARITY = 0.98


def remember(shard, point):
    shard.update(UpdateOperation.upsert_points([point]))


def recall(shard, vector, exclude_fly=None):
    return shard.query(
        QueryRequest(
            query=Query.Nearest(vector, using="cue"),
            limit=3,
            score_threshold=MIN_SIMILARITY,
            filter=Filter(
                must=[
                    FieldCondition("protocol", match=MatchValue(PROTOCOL)),
                    FieldCondition("arena", match=MatchValue("orchard")),
                ],
                must_not=[FieldCondition("source_fly", match=MatchValue(exclude_fly))]
                if exclude_fly is not None
                else None,
            ),
            with_payload=True,
        )
    )


def decide(hits):
    ranked = sorted(hits, key=lambda hit: hit.score, reverse=True)
    if not ranked:
        return None
    best = ranked[0]
    if any(
        best.score - other.score < 0.002
        and best.payload["sweep"] != other.payload["sweep"]
        for other in ranked[1:]
    ):
        return None
    return best.payload["recording"]


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
