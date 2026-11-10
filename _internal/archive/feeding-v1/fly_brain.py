"""Read the fly's feeding response. The model's wiring stays fixed."""

from math import ceil

from _internal.brain import RecordedBrain


class FlyBrain:
    """Replay a computed neural trial for the recalled warning."""

    def __init__(self):
        self.recordings = RecordedBrain()

    def respond(self, warning, seed):
        # Retrieval changes bitter input. Sugar and P9 stay at 150 Hz each.
        bitter_hz = min(200, max(0, ceil(warning * 4) * 50))
        return self.recordings.response(bitter_hz, seed)
