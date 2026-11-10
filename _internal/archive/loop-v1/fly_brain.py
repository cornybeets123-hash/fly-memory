"""The brain receives a target bearing. Its actual neural activity supplies steering."""

import math


def encode_bearing(error):
    """Use Doodle Fly's LC10a bearing adapter, with rates in hertz."""
    offset = 100 * error
    if abs(offset) < 12.48:
        return 0.0, 0.0
    rate = 14 + 66 * math.sqrt(min(1, (abs(offset) - 12.48) / 170))
    return (rate, 0.0) if offset < 0 else (0.0, rate)


class FlyBrain:
    """Keep the connectome fixed. Change sensory input when the target changes."""

    def __init__(self, kernel, fly, seed):
        self.kernel, self.fly, self.seed = kernel, fly, seed

    def step(self, bearing, scan=False, trace=False):
        left, right = (50.0, 0.0) if scan else encode_bearing(bearing)
        # The worker integrates 138,639 neurons and reads six descending cells per side.
        # Its fixed decoder returns steering from those measured spike counts.
        neural = self.kernel.step(self.fly, self.seed, left, right, trace=trace)
        return left, right, neural
