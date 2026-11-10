"""BUILD 2. Let a newcomer retrieve another fly's observed experience."""

from qdrant_edge import FieldCondition, Filter, MatchValue


def scope(world, protocol, fly, shared=False):
    """Use compatible observations from the current memory scope."""
    must = [
        FieldCondition("world", match=MatchValue(world)),
        FieldCondition("protocol", match=MatchValue(protocol)),
    ]
    # TODO: In shared mode, exclude this fly instead of selecting it.
    must.append(FieldCondition("source_fly", match=MatchValue(fly)))
    return Filter(must=must)
