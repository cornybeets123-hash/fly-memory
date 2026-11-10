"""A visible returning circuit and an exit, with outcome-blind scenery."""

import math

import numpy as np

from .observer import AXIS_VECTORS, beams
from .world import World


class WorkshopWorld(World):
    id = "workshop-loop-v1"
    protocol = "maze-column192-axis-camera-loop-v2"
    launch = (260, 580, -math.pi / 2)
    exit_marker = (825, 260)
    junction_centers = ((260, 260),)
    scenery_seed = 2026

    def __init__(self, scenery=True, swapped=False):
        self.rectangles = [
            (220, 300, 220, 660),
            (0, 860, 220, 300),
            (0, 80, 220, 660),
            (0, 300, 580, 660),
        ]
        self.validate_layout()
        self.walls = self._wall_segments()
        self.landmarks = self._natural_scenery() if scenery else []
        if not scenery:
            self.id += "-undecorated"
        if swapped:
            self.landmarks = self._swapped_scenery()
            self.id += "-swapped"

    def validate_layout(self):
        for x0, x1, y0, y1 in self.rectangles:
            if min(x1 - x0, y1 - y0) != 80:
                raise ValueError("The observer requires 80-unit corridors.")
        for x, y in self.junction_centers:
            directions = beams(self, x, y)
            if sum(d is None for d in directions) != 3:
                raise ValueError("Each declared junction needs three visible arms.")
            for i, d in enumerate(directions):
                if d is not None:
                    continue
                axis = AXIS_VECTORS[i]
                distance = np.arange(1, 176)
                if not self.free(x + axis[0] * distance, y + axis[1] * distance).all():
                    raise ValueError(
                        "Each junction arm needs 135 clear units beyond its square."
                    )
        if bool(self.free(400, 620)):
            raise ValueError("The direct start-to-exit shortcut must stay closed.")

    def _natural_scenery(self):
        # One declared seed and one rule over all floor area. Outcomes are never read.
        rng = np.random.default_rng(self.scenery_seed)
        palette = (
            (51, 112, 78),
            (66, 135, 89),
            (99, 126, 65),
            (61, 114, 100),
            (89, 143, 92),
            (109, 137, 68),
        )
        landmarks = []
        for _ in range(20000):
            x, y = rng.uniform(0, 860), rng.uniform(0, 660)
            radius = float(rng.uniform(8, 15))
            if not self.free(x, y) or self.wall_clearance(x, y) < radius + 3:
                continue
            if any(
                math.hypot(x - lx, y - ly) < radius + lr + 3
                for lx, ly, _, lr in landmarks
            ):
                continue
            color = palette[int(rng.integers(len(palette)))]
            landmarks.append((float(x), float(y), color, radius))
            if len(landmarks) == 72:
                return landmarks
        raise ValueError("The declared natural scenery did not fit in the maze.")

    def _swapped_scenery(self):
        # Evaluation counterfactual only. Rotate nearby landmark sets between paired arms.
        swapped = []
        for x, y, color, radius in self.landmarks:
            if 40 < abs(x - 260) < 220 and abs(y - 260) < 40:
                x, y = 520 - x, 520 - y
            elif 40 < abs(y - 260) < 220 and abs(x - 620) < 40:
                x, y = 1240 - x, 520 - y
            swapped.append((x, y, color, radius))
        return swapped

    @staticmethod
    def exit_reached(x, y):
        return x > 805 and 225 < y < 295

    @staticmethod
    def returned_to_start(x, y):
        # An observed task outcome at the painted start line, never policy input.
        return 220 < x < 300 and 570 < y < 590
