"""The exact code taught on stage. Use it for notes and isolated validation."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REMEMBER = '''def remember(shard, point):
    """Add the supplied observation to Qdrant."""
    shard.update(UpdateOperation.upsert_points([point]))
'''

RECALL = '''def recall(shard, vector, scope):
    """Search the view vector. Apply the supplied eligibility filter."""
    return shard.query(QueryRequest(
        query=Query.Nearest(vector, using="view"),
        limit=10,
        score_threshold=MIN_SCORE,
        filter=scope,
        with_payload=True,
    ))
'''

SHARED_SCOPE = '''def scope(world, protocol, fly, shared=False):
    """Use compatible observations from the current memory scope."""
    must = [
        FieldCondition("world", match=MatchValue(world)),
        FieldCondition("protocol", match=MatchValue(protocol)),
    ]
    source = FieldCondition("source_fly", match=MatchValue(fly))
    if shared:
        return Filter(must=must, must_not=[source])
    return Filter(must=[*must, source])
'''


def replace_functions(source, replacements):
    lines = source.splitlines(keepends=True)
    nodes = [
        node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)
    ]
    for node in reversed(nodes):
        if node.name in replacements:
            lines[node.lineno - 1 : node.end_lineno] = [replacements[node.name]]
    return "".join(lines)


def completed_sources():
    memory = replace_functions(
        (ROOT / "memory.py").read_text(encoding="utf-8"),
        {"remember": REMEMBER, "recall": RECALL},
    )
    pipeline = replace_functions(
        (ROOT / "pipeline.py").read_text(encoding="utf-8"), {"scope": SHARED_SCOPE}
    )
    return {"memory": memory, "pipeline": pipeline}
