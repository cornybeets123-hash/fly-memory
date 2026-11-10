"""The integration slice: local visibility, ordinary landmarks, and hidden endpoints."""

import math
from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from .vision import relative

LOOK = 100
STEP = 0.02
SPEED = 60
YAW = 2


@dataclass
class Opening:
    bearing: float
    width: float


class World:
    id = "junction-layout-v1"

    # Geometry supplies rendering, local sensing, and collision. Policy never sees rectangles.
    def __init__(self, hidden_end=500):
        if not math.isfinite(hidden_end) or hidden_end < 390:
            raise ValueError("The terminal segment must span at least 170 units.")
        self.rectangles = [
            (0, 300, -40, 40),
            (220, 300, -260, 40),
            (220, hidden_end, -260, -180),
            (220, 300, -40, 300),
            (220, 640, 220, 300),
        ]
        self.landmarks = [
            (239, -56, (51, 112, 78), 11),
            (278, -112, (66, 135, 89), 8),
            (276, 62, (99, 126, 65), 13),
            (242, 125, (61, 114, 100), 10),
            (105, 22, (83, 126, 88), 9),
        ]
        self.validate_layout()
        self.walls = self._wall_segments()

    def _wall_segments(self):
        xs = sorted({r[i] for r in self.rectangles for i in (0, 1)})
        ys = sorted({r[i] for r in self.rectangles for i in (2, 3)})
        walls = []
        for x in xs:
            for a, b in pairwise(ys):
                mid = (a + b) / 2
                if self.free(x - 0.001, mid) != self.free(x + 0.001, mid):
                    walls.append((x, a, x, b))
        for y in ys:
            for a, b in pairwise(xs):
                mid = (a + b) / 2
                if self.free(mid, y - 0.001) != self.free(mid, y + 0.001):
                    walls.append((a, y, b, y))
        return np.array(walls, dtype=float)

    def wall_clearance(self, x, y):
        """Evaluation only. Exact point-to-wall distance in the rectangle union."""
        start, end = self.walls[:, :2], self.walls[:, 2:]
        delta = end - start
        amount = (((x, y) - start) * delta).sum(axis=1) / (delta * delta).sum(axis=1)
        nearest = start + np.clip(amount, 0, 1)[:, None] * delta
        return float(np.linalg.norm(nearest - (x, y), axis=1).min())

    def validate_layout(self):
        """Validate this fixed integration layout, rather than accept arbitrary mazes."""
        for x0, x1, y0, y1 in self.rectangles:
            if min(x1 - x0, y1 - y0) != 80:
                raise ValueError("The observer requires 80-unit corridors and squares.")
        for indices in ((0, 1), (2, 3)):
            boundaries = sorted({r[i] for r in self.rectangles for i in indices})
            if any(0 < b - a < 4 for a, b in pairwise(boundaries)):
                raise ValueError("Wall features must span at least four units.")
        if self.rectangles[2][1] - self.rectangles[2][0] < 170:
            raise ValueError("The terminal segment must span at least 170 units.")
        for x, y, dx, dy in ((220, 0, -1, 0), (260, -40, 0, -1), (260, 40, 0, 1)):
            distance = np.arange(1, 136)
            if not self.free(x + dx * distance, y + dy * distance).all():
                raise ValueError("Each junction arm needs 135 clear units.")

    def free(self, x, y):
        result = np.zeros(np.broadcast_shapes(np.shape(x), np.shape(y)), dtype=bool)
        for x0, x1, y0, y1 in self.rectangles:
            result |= (x > x0) & (x < x1) & (y > y0) & (y < y1)
        return result

    def ranges(self, x, y, heading, full=False, clearance=0):
        degrees = np.arange(-180, 180, 4) if full else np.arange(-100, 104, 4)
        angles = heading + np.deg2rad(degrees)
        radius = np.arange(2, 132, 2)
        px = x + np.cos(angles)[:, None] * radius
        py = y + np.sin(angles)[:, None] * radius
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
        first = np.argmax(blocked, axis=1)
        distances = np.where(blocked.any(axis=1), radius[first], 130)
        return degrees, distances

    def openings(self, x, y, heading, full=False, clearance=15):
        degrees, distances = self.ranges(x, y, heading, full, clearance=clearance)
        groups = []
        current = []
        for degree, distance in zip(degrees, distances):
            if distance >= LOOK:
                current.append(float(degree))
            elif current:
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        if full and len(groups) > 1 and distances[0] >= LOOK and distances[-1] >= LOOK:
            groups[0] = groups[-1] + groups[0]
            groups.pop()
        result = []
        for group in groups:
            if len(group) < 2:
                continue
            angle = math.atan2(
                np.sin(np.deg2rad(group)).mean(), np.cos(np.deg2rad(group)).mean()
            )
            result.append(Opening(angle, len(group) * 4))
        return result

    def forward(self, x, y, heading):
        _, distances = self.ranges(x, y, heading)
        return float(distances[25])

    def motion_forward(self, x, y, heading):
        _, distances = self.ranges(x, y, heading, clearance=15)
        return float(distances[25])

    def fits(self, x, y):
        return all(
            bool(self.free(x + dx, y + dy))
            for dx, dy in ((0, 0), (5, 0), (-5, 0), (0, 5), (0, -5))
        )

    @staticmethod
    def exit_reached(x, y):
        return x > 585 and 225 < y < 295


def sensory_drive(error):
    """Pinned Doodle bearing encoder: 78*.16 pixel dead zone, offset=100*error."""
    dx = 100 * error
    if abs(dx) < 12.48:
        return 0.0, 0.0
    hz = 14 + 66 * math.sqrt(min(1, (abs(dx) - 12.48) / 170))
    return (hz, 0.0) if dx < 0 else (0.0, hz)


def choose(openings, excluded, incoming=None, preference="left"):
    """One-hop application policy. Only relative visible bearings enter this function."""
    candidates = [
        i
        for i, o in enumerate(openings)
        if incoming is None or abs(relative(o.bearing - incoming)) > 0.55
    ]
    if not candidates:
        candidates = list(range(len(openings)))
    allowed = [i for i in candidates if not excluded[i]]
    all_excluded = bool(candidates and not allowed)
    if not allowed:
        allowed = candidates
    if not allowed:
        return None, all_excluded
    return sorted(
        allowed, key=lambda i: openings[i].bearing, reverse=preference == "right"
    )[0], all_excluded
