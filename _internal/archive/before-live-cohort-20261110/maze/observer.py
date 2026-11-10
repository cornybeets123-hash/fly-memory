"""An engineered local observer for the declared axis-aligned maze geometry."""

import math
from dataclasses import dataclass

import numpy as np

from .vision import relative

AXES = np.arange(4) * math.pi / 2
AXIS_VECTORS = np.array([[1, 0], [0, 1], [-1, 0], [0, -1]])
RADII = np.arange(2, 132, 2)


@dataclass(frozen=True)
class Reading:
    ranges: tuple
    junction: bool
    terminal: bool
    entered: bool = False
    released: bool = False
    incoming: float = math.pi


def beams(world, x, y):
    """Return four current range measurements. None means clear through 130 units."""
    clear = world.free(
        x + AXIS_VECTORS[:, 0, None] * RADII,
        y + AXIS_VECTORS[:, 1, None] * RADII,
    )
    blocked = ~clear
    return tuple(float(RADII[np.argmax(row)]) if row.any() else None for row in blocked)


class Observer:
    def __init__(self):
        self.inside = False
        self.on = 0
        self.off = 0
        self.approach = 0.0
        self.incoming = math.pi

    def update(self, world, x, y, heading):
        ranges = beams(world, x, y)
        continuing = [i for i, distance in enumerate(ranges) if distance is None]
        raw_junction = len(continuing) >= 3
        entered = released = False
        if not self.inside and not raw_junction and continuing:
            # A compass direction, never a place identifier or route instruction.
            self.approach = float(
                min(
                    (AXES[i] + sign * math.pi for i in continuing for sign in (0, 1)),
                    key=lambda a: abs(relative(a - heading)),
                )
            )
        self.on = self.on + 1 if raw_junction else 0
        self.off = self.off + 1 if not raw_junction else 0
        if not self.inside and self.on == 3:
            self.inside = entered = True
            self.incoming = relative(self.approach + math.pi)
        elif self.inside and self.off == 3:
            self.inside = False
            released = True
        terminal = False
        if len(continuing) == 1:
            direction = continuing[0]
            opposite = ranges[(direction + 2) % 4]
            sides = [ranges[(direction + i) % 4] for i in (1, 3)]
            terminal = (
                opposite is not None
                and opposite < 35
                and all(side is not None for side in sides)
                and sum(sides) <= 90
            )
        return Reading(ranges, self.inside, terminal, entered, released, self.incoming)


@dataclass
class CornerGuard:
    incoming: int
    continuation: int
    forward_ticks: int = 0
    reverse_ticks: int = 0

    @classmethod
    def start(cls, ranges, displacement):
        clear = [i for i, distance in enumerate(ranges) if distance is None]
        if len(clear) != 2 or (clear[0] - clear[1]) % 2 == 0:
            return None
        distance = math.hypot(*displacement)
        if distance < 10:
            return None
        alignment = [-np.dot(displacement, AXIS_VECTORS[i]) / distance for i in clear]
        if max(alignment) <= 0 or abs(alignment[0] - alignment[1]) < 0.2:
            return None
        incoming = max(clear, key=lambda i: -np.dot(displacement, AXIS_VECTORS[i]))
        return cls(incoming, next(i for i in clear if i != incoming))

    def check(self, ranges):
        def corridor(axis):
            sides = (ranges[axis], ranges[(axis + 2) % 4])
            return all(s is not None for s in sides) and sum(sides) <= 90

        forward, reverse = corridor(self.incoming), corridor(self.continuation)
        self.forward_ticks = self.forward_ticks + 1 if forward and not reverse else 0
        self.reverse_ticks = self.reverse_ticks + 1 if reverse and not forward else 0
        if self.forward_ticks == 3:
            return True
        if self.reverse_ticks == 3:
            return False
        return None
