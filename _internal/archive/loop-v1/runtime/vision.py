"""A local, visibility-masked overhead snapshot. Outcomes never enter encoding."""

import hashlib
import math

import numpy as np

SIZE = 64


def camera_axes(openings, ranges, heading):
    """Associate visible apertures with clear local compass beams."""
    clear = [i for i, distance in enumerate(ranges) if distance is None]
    chosen, ambiguous = [], set()
    for index, opening in enumerate(openings):
        ranked = sorted(
            (abs(relative(i * math.pi / 2 - heading - opening.bearing)), i)
            for i in clear
        )
        if (
            not ranked
            or ranked[0][0] > math.pi / 3
            or (len(ranked) > 1 and abs(ranked[0][0] - ranked[1][0]) < 1e-9)
        ):
            chosen.append(None)
            ambiguous.add(index)
        else:
            chosen.append(ranked[0][1])
    for index, axis in enumerate(chosen):
        if axis is not None and chosen.count(axis) > 1:
            ambiguous.add(index)
    return [
        None if i in ambiguous else axis * math.pi / 2 for i, axis in enumerate(chosen)
    ], sorted(ambiguous)


def snapshot(world, x, y, bearing, illumination=1.0):
    cross, forward = np.meshgrid(
        np.linspace(-70, 70, SIZE), np.linspace(145, -15, SIZE)
    )
    px = x + forward * np.cos(bearing) - cross * np.sin(bearing)
    py = y + forward * np.sin(bearing) + cross * np.cos(bearing)
    visible = np.ones(px.shape, dtype=bool)
    distance = np.hypot(px - x, py - y)
    for fraction in np.linspace(0, 1, 48):
        # Show the first wall surface, with no view through it.
        active = distance * fraction < distance - 3
        clear = world.free(x + (px - x) * fraction, y + (py - y) * fraction)
        visible &= ~active | clear
    floor = world.free(px, py)
    image = np.full((*px.shape, 3), [26, 34, 49], dtype=float)
    image[visible & floor] = [222, 216, 193]
    image[visible & ~floor] = [108, 125, 137]
    for lx, ly, color, radius in world.landmarks:
        mark = ((px - lx) ** 2 + (py - ly) ** 2 < radius**2) & visible & floor
        image[mark] = color
    return np.clip(image * illumination, 0, 255).astype(np.uint8)


def encode(image):
    # Pool depth to tolerate motion along the viewed corridor. Keep lateral color.
    # This transparent toy encoder uses pixels only: 64 columns times RGB = 192.
    small = image.astype(float).mean(axis=0)
    small -= small.mean(axis=0, keepdims=True)
    vector = small.ravel()
    norm = np.linalg.norm(vector)
    return (vector / norm).tolist() if norm > 1e-9 else None


def image_hash(image):
    return hashlib.sha256(image.tobytes()).hexdigest()


def relative(angle):
    return math.atan2(math.sin(angle), math.cos(angle))
