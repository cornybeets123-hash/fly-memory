"""Selected individual spike times from the archived model trials."""

from functools import lru_cache
from pathlib import Path

import numpy as np


@lru_cache(maxsize=48)
def spikes(trial_id, sugar_index, bitter_index, motor_index):
    path = Path(__file__).parent / "data" / "spikes" / f"{trial_id}.npz"
    with np.load(path) as data:
        return {
            name: data["time_s"][data["neuron_index"] == index].round(5).tolist()
            for name, index in (
                ("sugar", sugar_index),
                ("bitter", bitter_index),
                ("motor", motor_index),
            )
        }
