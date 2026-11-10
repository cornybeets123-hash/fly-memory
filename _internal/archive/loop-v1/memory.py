"""BUILD 1. Store an observed experience, then search for a similar view."""

from qdrant_edge import Query, QueryRequest, UpdateOperation  # noqa: F401

MIN_SCORE = 0.94
CONFLICT_MARGIN = 0.02


def remember(shard, point):
    """Add the supplied observation to Qdrant."""
    # TODO: Upsert this point with UpdateOperation.upsert_points.
    raise NotImplementedError("Implement remember() in memory.py.")


def recall(shard, vector, scope):
    """Search the view vector. Apply the supplied eligibility filter."""
    # TODO: Query.Nearest(vector, using="view"), limit=10,
    # score_threshold=MIN_SCORE, filter=scope, with_payload=True.
    raise NotImplementedError("Implement recall() in memory.py.")


def decide(hits):
    """Use the best evidence per outcome. Abstain when outcomes conflict."""
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
    if opened is not None and dead.score - opened.score < CONFLICT_MARGIN:
        return None
    return dead
