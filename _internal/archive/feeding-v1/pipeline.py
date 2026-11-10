"""TASK 2. Add the shared query and publish each observed experience."""


def retrieve(memory, personal, shared, vector, fly, mode):
    if mode == "none":
        return []
    hits = memory.recall(personal, vector)
    if mode == "shared":
        # Add other flies' experiences to the personal results.
        raise NotImplementedError("Task 2: query shared memory, excluding this fly")
    return hits


def observe(memory, personal, shared, point, mode):
    if mode == "none":
        return
    memory.remember(personal, point)
    if mode == "shared":
        # Publish the observed meal. Never publish a retrieved guess.
        raise NotImplementedError("Task 2: write this observation to shared memory")
