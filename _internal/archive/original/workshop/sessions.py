"""Close and reopen one personal Edge shard before an unfamiliar mixture."""

from workshop.brain import RecordedBrain
from workshop.memory import ExperienceMemory
from workshop.senses import OdorSpace
from workshop.simulation import Config, world


def session_probe(path, *, student=False):
    brain, space, cfg = RecordedBrain(), OdorSpace(), Config()
    contacts = world(cfg, space, 6)
    training, transfer = contacts[4], contacts[5]
    seed = brain.seed_for(6, transfer["step"])
    with ExperienceMemory(space.dim, student=student) as empty:
        naive_recall = empty.recall(transfer["vector"], cfg.threshold, cfg.top_k)
        naive = brain.response(naive_recall["bitter_hz"], seed)
    with ExperienceMemory(space.dim, path=path, student=student) as first:
        if first.points:
            raise ValueError(
                "This session probe needs an empty path. Choose a new directory."
            )
        meal = brain.response(0, brain.seed_for(6, training["step"]))
        if not meal["feeding"]:
            raise ValueError("The training encounter did not produce an observed meal.")
        outcome = -1 if training["harmful"] else 1
        first.remember(5, training["vector"], outcome, training["step"])
    # The new instance loads its points from the persisted native shard.
    with ExperienceMemory(space.dim, path=path, student=student) as reopened:
        recall = reopened.recall(transfer["vector"], cfg.threshold, cfg.top_k)
        remembered = brain.response(recall["bitter_hz"], seed)
    return {
        "path": str(path),
        "training_encounter": 5,
        "transfer_encounter": 6,
        "distinct_observation": training["vector"] != transfer["vector"],
        "same_neural_seed": seed,
        "empty_memory": {"recall": naive_recall, "neural": naive},
        "reopened_memory": {"recall": recall, "neural": remembered},
        "changed_decision": naive["feeding"] != remembered["feeding"],
    }
