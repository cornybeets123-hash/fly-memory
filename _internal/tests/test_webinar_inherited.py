"""The inherited condition reads a frozen pool and never publishes."""

import math

import pytest
from qdrant_edge import Point

from _internal.maze import memory
from _internal.maze import webinar_inherited as inherited
from _internal.maze import webinar_population as producer
from _internal.maze.simulation import Episode
from _internal.maze.vision import encode, image_hash, snapshot
from _internal.maze.webinar_world import WebinarWorld


@pytest.fixture
def frozen_pool(tmp_path):
    world = WebinarWorld()
    image = snapshot(world, 260, 900, math.pi)
    vector = encode(image)
    payload = {
        "source_fly": "A3",
        "snapshot": image_hash(image),
        "captured_at_ms": 100,
        "observed_at_ms": 10000,
        "world": world.id,
        "protocol": world.protocol,
        "outcome": "dead_end",
    }
    episode = Episode(Point(7, {"view": vector}, payload), image)
    producer.save_gzip(
        tmp_path / inherited.POOL, [producer.serialized_episode(episode)]
    )
    producer.write_json(tmp_path / inherited.ATLAS, {"7": [2, "west"]})
    yield tmp_path, world, vector
    inherited.close()


def test_conditions_map_to_the_simulator_modes():
    assert producer.MODES == ("none", "personal", "inherited", "shared")
    assert producer.SIMULATED == {"inherited": "shared", "shared": "hive"}
    assert set(producer.POOLS) == {"inherited", "shared"}
    assert producer.POOLS["inherited"] != producer.POOLS["shared"]


def test_pool_is_loaded_once_and_searchable_by_every_newcomer(frozen_pool):
    directory, world, vector = frozen_pool
    episodes, atlas, shard = inherited.pool(directory)
    assert inherited.pool(directory)[2] is shard
    assert [e.point.payload["source_fly"] for e in episodes] == ["A3"]
    assert atlas == {7: (2, "west")}
    hits = memory.recall(
        shard, vector, world.id, exclude_fly="B1", protocol=world.protocol, owner="B1"
    )
    assert [h.payload["source_fly"] for h in hits] == ["A3"]
    # A newcomer's own observations are never in the pool, so it cannot read itself.
    assert all(h.payload["source_fly"] != "B1" for h in hits)


def test_closing_releases_the_worker_pool(frozen_pool):
    directory, _, _ = frozen_pool
    inherited.pool(directory)
    inherited.close()
    assert inherited._resident is None
    inherited.close()
