"""BUILD 2. Read other flies' episodes. Publish directly observed experiences."""


def retrieve(memory, personal, shared, vector, fly, mode):
    if mode == "none":
        return []
    hits = memory.recall(personal, vector)
    if mode == "shared":
        raise NotImplementedError("Build 2: add shared hits, excluding this fly")
    return hits


def observe(memory, personal, shared, point, mode):
    if mode == "none":
        return
    memory.remember(personal, point)
    if mode == "shared":
        raise NotImplementedError("Build 2: publish the observed episode")
