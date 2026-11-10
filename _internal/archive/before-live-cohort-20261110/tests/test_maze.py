"""Regressions for false observations, visibility, and retrieval evidence handling."""

import math

import numpy as np
import pytest
from qdrant_edge import Distance, EdgeConfig, EdgeShard, EdgeVectorParams, Point

from _internal.maze import memory
from _internal.maze.kernel import Kernel
from _internal.maze.observer import CornerGuard, Observer, beams
from _internal.maze.simulation import run
from _internal.maze.vision import encode, snapshot
from _internal.maze.world import World


def test_full_world_observation_sweep():
    world = World()
    tested = 0
    for x in range(5, 640, 5):
        for y in range(-255, 300, 5):
            if not world.fits(x, y):
                continue
            observer = Observer()
            for _ in range(3):
                reading = observer.update(world, x, y, 0)
            expected_junction = 220 < x < 300 and -40 < y < 40
            expected_terminal = (
                x < 35
                and -40 < y < 40
                or x > 465
                and -260 < y < -180
                or x > 605
                and 220 < y < 300
            )
            assert reading.junction == expected_junction, (x, y, reading)
            assert reading.terminal == expected_terminal, (x, y, reading)
            tested += 1
    assert tested == 3397


def test_sliver_counterexamples_and_range_boundary():
    for x, y in ((264.9, -164.97), (275, -135), (280, -135)):
        reading = Observer().update(World(), x, y, -math.pi / 2)
        assert not reading.junction and not reading.terminal
    assert beams(World(), 170, 0)[0] == 130
    assert beams(World(), 168, 0)[0] is None


def test_debounce_and_incoming_on_partially_visible_approach():
    world, observer = World(), Observer()
    observer.update(world, 203, -5, 0)  # Only the beam behind the fly reaches 130.
    assert beams(world, 203, -5)[2] is None
    entries = []
    for x in (221, 219) * 5:
        entries.append(observer.update(world, x, -5, -0.4).entered)
    assert not any(entries)
    for _ in range(3):
        reading = observer.update(world, 225, -5, -0.4)
        entries.append(reading.entered)
    assert sum(entries) == 1
    assert abs(abs(reading.incoming) - math.pi) < 1e-9
    for x in (221, 219) * 5:
        assert not observer.update(world, x, -5, -0.4).entered
    assert observer.inside


def test_layout_limits_and_hidden_endpoint_visibility():
    for end in (340, 380):
        with pytest.raises(ValueError, match="170"):
            World(end)
    for end in (500, 580, 620):
        World(end)
    world = World()
    world.rectangles[0] = (0, 300, -40, 39)
    with pytest.raises(ValueError, match="80"):
        world.validate_layout()
    for pose in ((206, -5, -math.pi / 2), (260, -120, -math.pi / 2), (330, -220, 0)):
        images = [snapshot(World(end), *pose) for end in (500, 580, 620)]
        assert all(np.array_equal(images[0], other) for other in images[1:])
        assert encode(images[0]) == encode(images[1])
        assert beams(World(500), *pose[:2]) == beams(World(620), *pose[:2])
    assert World().wall_clearance(480, -220) == 20
    assert World().wall_clearance(260, -220) == 40


def test_corner_scan_distinguishes_continuation_from_reversal():
    world = World()
    guard = CornerGuard.start((None, None, 18, 28), (-10, -25))
    assert guard is not None and guard.continuation == 0 and guard.incoming == 1
    # Moving 40 units can still leave the fly inside the corner.
    assert guard.check(beams(world, 267.525, -206.358)) is None
    for _ in range(3):
        continued = guard.check(beams(world, 320, -220))
    assert continued is True
    for _ in range(3):
        reversed_direction = guard.check(beams(world, 260, -160))
    assert reversed_direction is False
    assert guard.check((30, 30, 30, 30)) is None
    assert CornerGuard.start((None, 40, None, 40), (10, 0)) is None
    assert CornerGuard.start((None, None, 18, 28), (1, -2)) is None
    assert CornerGuard.start((None, None, 18, 28), (-20, -20)) is None
    minimum = World(390)
    minimum_guard = CornerGuard.start(beams(minimum, 237.4, -233.4), (-10, -25))
    for _ in range(3):
        result = minimum_guard.check(beams(minimum, 320, -220))
    assert result is True


def test_shorter_trip_stays_inconclusive_before_a_separate_exit():
    with Kernel() as kernel:
        result = run(kernel, World(390), seed=2000, duration=25)
    first = result["decisions"][0]
    first_snapshot = first["views"][first["choice"]]["snapshot"]
    observations = [e for e in result["events"] if e["kind"] == "observed"]
    assert all(e["snapshot"] != first_snapshot for e in observations)
    assert any(
        e["kind"] == "inconclusive" and e["captured_at_ms"] == first["time"] + 100
        for e in result["events"]
    )
    assert result["summary"]["exit"]
    assert observations[-1]["outcome"] == "open"
    assert observations[-1]["captured_at_ms"] > first["time"] + 100


def test_edge_filters_and_duplicate_conflict(tmp_path):
    (tmp_path / "edge").mkdir()
    shard = EdgeShard.create(
        str(tmp_path / "edge"),
        EdgeConfig(
            vectors={"view": EdgeVectorParams(size=192, distance=Distance.Cosine)}
        ),
    )
    vector = [1.0] + [0.0] * 191

    def point(identifier, score, outcome="dead_end", **extra):
        payload = {
            "world": World.id,
            "protocol": memory.PROTOCOL,
            "source_fly": "A",
            "outcome": outcome,
            **extra,
        }
        return Point(
            identifier,
            {"view": [score, math.sqrt(1 - score**2)] + [0.0] * 190},
            payload,
        )

    try:
        for i in range(3):
            memory.remember(shard, point(i, 0.999 - i * 0.001))
        hits = memory.recall(shard, vector, World.id)
        assert len(hits) == 3 and memory.decide(hits) is not None
        memory.remember(shard, point(4, 0.995, "open"))
        hits = memory.recall(shard, vector, World.id)
        assert hits[3].payload["outcome"] == "open"
        assert memory.decide(hits) is None
        memory.remember(shard, point(5, 1.0, world="other"))
        memory.remember(shard, point(6, 1.0, protocol="observer-v1"))
        assert len(memory.recall(shard, vector, World.id)) == 4
        assert memory.recall(shard, vector, World.id, exclude_fly="A") == []
    finally:
        shard.close()
