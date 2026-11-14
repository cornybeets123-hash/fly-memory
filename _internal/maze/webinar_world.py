"""Eight locally observed forks. Geometry never supplies a route to the controller."""

import math
from bisect import bisect_left, bisect_right

import numpy as np

from .observer import AXIS_VECTORS, RADII, beams
from .workshop_world import WorkshopWorld


class WebinarWorld(WorkshopWorld):
    id = "webinar-maze-v1"
    launch = (260, 1180, -math.pi / 2)
    start_line = (220, 300, 1140)
    exit_marker = (980, 280)
    deadline = 180
    junction_centers = (
        (260, 900),
        (620, 900),
        (620, 1260),
        (980, 1260),
        (980, 900),
        (1340, 900),
        (1340, 540),
        (980, 540),
    )

    def __init__(self):
        self.rectangles = [
            (220, 300, 860, 1300),
            (0, 660, 860, 940),
            (0, 80, 860, 1300),
            (0, 300, 1220, 1300),
            (580, 660, 640, 1300),
            (340, 1020, 1220, 1300),
            (940, 1020, 860, 1560),
            (720, 1640, 860, 940),
            (1300, 1380, 500, 940),
            (940, 1640, 500, 580),
            (940, 1020, 240, 800),
        ]
        # An exact lookup over rectangle boundaries, including their open edges.
        # It accelerates the same geometry tests without quantizing the current pose.
        self._edges = [
            np.array(sorted({r[i] for r in self.rectangles for i in pair}))
            for pair in ((0, 1), (2, 3))
        ]
        samples = []
        for edge in self._edges:
            intervals = np.r_[edge[0] - 1, (edge[:-1] + edge[1:]) / 2, edge[-1] + 1]
            sample = np.empty(len(edge) * 2 + 1)
            sample[::2], sample[1::2] = intervals, edge
            samples.append(sample)
        from .world import World

        self._floor = World.free(self, samples[0][None, :], samples[1][:, None])
        self._edge_lists = [edge.tolist() for edge in self._edges]
        self.validate_layout()
        self.walls = self._wall_segments()
        self.landmarks = self._natural_scenery()

    def free(self, x, y):
        if np.isscalar(x) and np.isscalar(y):
            ix = bisect_left(self._edge_lists[0], x) + bisect_right(
                self._edge_lists[0], x
            )
            iy = bisect_left(self._edge_lists[1], y) + bisect_right(
                self._edge_lists[1], y
            )
            return self._floor[iy, ix]
        indices = [
            np.searchsorted(edge, value, side="left")
            + np.searchsorted(edge, value, side="right")
            for edge, value in zip(self._edges, (x, y))
        ]
        return self._floor[indices[1], indices[0]]

    def _forward(self, x, y, heading, clearance=0):
        # The caller uses only the center ray. Preserve the original two-unit samples.
        px, py = x + math.cos(heading) * RADII, y + math.sin(heading) * RADII
        clear = self.free(px, py)
        if clearance:
            for dx, dy in (
                (clearance, 0),
                (-clearance, 0),
                (0, clearance),
                (0, -clearance),
            ):
                clear &= self.free(px + dx, py + dy)
        blocked = ~clear
        return float(RADII[np.argmax(blocked)]) if blocked.any() else 130.0

    def forward(self, x, y, heading):
        return self._forward(x, y, heading)

    def motion_forward(self, x, y, heading):
        return self._forward(x, y, heading, clearance=15)

    def validate_layout(self):
        for x0, x1, y0, y1 in self.rectangles:
            if min(x1 - x0, y1 - y0) != 80:
                raise ValueError("The observer requires 80-unit corridors.")
        for x, y in self.junction_centers:
            directions = beams(self, x, y)
            if sum(d is None for d in directions) != 3:
                raise ValueError(f"The fork at {(x, y)} needs three visible arms.")
            for i, d in enumerate(directions):
                if d is None:
                    distance = np.arange(1, 176)
                    axis = AXIS_VECTORS[i]
                    if not self.free(
                        x + axis[0] * distance, y + axis[1] * distance
                    ).all():
                        raise ValueError("Each junction arm needs 175 clear units.")
                    heading = i * math.pi / 2 + math.pi
                    if len(self.openings(x, y, heading)) != 2:
                        raise ValueError(
                            "Each fork approach needs two visible options."
                        )
        if len(self.openings(*self.launch)) != 1:
            raise ValueError("Spawn must have one visible forward opening.")

    def _natural_scenery(self):
        # A fixed rule over all visible floor area. Neither outcomes nor fork IDs enter it.
        rng = np.random.default_rng(self.scenery_seed)
        palette = (
            (51, 112, 78),
            (66, 135, 89),
            (99, 126, 65),
            (61, 114, 100),
            (89, 143, 92),
            (109, 137, 68),
        )
        marks = []
        for _ in range(80000):
            x, y = rng.uniform(0, 1640), rng.uniform(240, 1560)
            radius = float(rng.uniform(8, 15))
            if not self.free(x, y) or self.wall_clearance(x, y) < radius + 3:
                continue
            if any(
                math.hypot(x - lx, y - ly) < radius + lr + 3 for lx, ly, _, lr in marks
            ):
                continue
            marks.append(
                (float(x), float(y), palette[int(rng.integers(len(palette)))], radius)
            )
            if len(marks) == 180:
                return marks
        raise ValueError("The declared scenery did not fit in the webinar maze.")

    @staticmethod
    def exit_reached(x, y):
        return 945 < x < 1015 and y < 295

    @staticmethod
    def returned_to_start(x, y):
        return 220 < x < 300 and 1130 < y < 1150
