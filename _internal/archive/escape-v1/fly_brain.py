"""The visible brain adapter. Wiring and sensory recordings stay fixed."""

from _internal.escape.kernel import Kernel


class FlyBrain:
    """Replay observed sensory events. Read escape activity from the neural model."""

    def __init__(self, kernel: Kernel, fly, seed):
        self.kernel, self.fly, self.seed = kernel, fly, seed

    def respond(self, threat_visible, warning_ms, recording=None, **options):
        # Natural input continues. Replay adds the episode's original input events.
        return self.kernel.encounter(
            self.fly,
            self.seed,
            threat_visible,
            warning_ms,
            recording,
            **options,
        )

    @staticmethod
    def reaches_refuge(response, clearance_ms=45, strike_ms=200):
        # The body is an engineered actor. Only measured DNp01 activity starts it.
        onset = response["first_motor_ms"]
        return onset is not None and onset + clearance_ms <= strike_ms
