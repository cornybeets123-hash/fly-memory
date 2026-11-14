"""The larger maze preserves current-pose sensing and original captured evidence."""

import math

import numpy as np
import pytest
from qdrant_edge import Point

from _internal.maze.simulation import Episode
from _internal.maze.vision import encode, image_hash, snapshot
from _internal.maze.webinar_population import restored_episode, serialized_episode
from _internal.maze.webinar_world import WebinarWorld
from _internal.maze.world import World


@pytest.fixture(scope="module")
def world():
    return WebinarWorld()


def test_optimized_geometry_matches_rectangle_union_at_edges_and_current_poses(world):
    rng = np.random.default_rng(2026)
    x = np.r_[rng.uniform(-20, 1660, 3000), world._edges[0]]
    y = np.r_[rng.uniform(220, 1580, 3000), world._edges[1]]
    grid_x, grid_y = np.meshgrid(world._edges[0], world._edges[1])
    assert np.array_equal(world.free(grid_x, grid_y), World.free(world, grid_x, grid_y))
    size = min(len(x), len(y))
    assert np.array_equal(
        world.free(x[:size], y[:size]), World.free(world, x[:size], y[:size])
    )
    for px, py in zip(x[:100], y[:100]):
        assert world.free(float(px), float(py)) == World.free(
            world, float(px), float(py)
        )
    for _ in range(100):
        px, py = rng.uniform(0, 1640), rng.uniform(240, 1560)
        heading = rng.uniform(-math.pi, math.pi)
        assert world.forward(px, py, heading) == World.forward(world, px, py, heading)
        assert world.motion_forward(px, py, heading) == World.motion_forward(
            world, px, py, heading
        )


def test_recorded_observation_roundtrip_preserves_pixels_vector_and_provenance(world):
    image = snapshot(world, 260, 900, math.pi)
    vector = encode(image)
    episode = Episode(
        Point(
            2**63 + 99,
            {"view": vector},
            {
                "source_fly": "A17",
                "snapshot": image_hash(image),
                "captured_at_ms": 100,
                "observed_at_ms": 10000,
                "world": world.id,
                "protocol": world.protocol,
                "outcome": "returned",
            },
        ),
        image,
    )
    restored = restored_episode(serialized_episode(episode))
    assert restored.point.id == episode.point.id
    assert restored.point.payload == episode.point.payload
    assert restored.point.vector == episode.point.vector
    assert np.array_equal(restored.image, image)
    assert image_hash(restored.image) == restored.point.payload["snapshot"]
