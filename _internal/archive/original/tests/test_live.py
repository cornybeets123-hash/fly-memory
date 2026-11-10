"""Exercise process failure and cleanup without loading the neural network."""

import os
import time

import pytest

from workshop.live import LiveProxy


def transport_worker(connection):
    while True:
        bitter, seed = connection.recv()
        if bitter == -1:
            os._exit(2)
        if bitter == -2:
            time.sleep(10)
        connection.send((True, {"dose": bitter, "seed": seed}))


def test_crashed_worker_is_replaced_on_retry():
    proxy = LiveProxy(timeout=5, worker=transport_worker)
    try:
        with pytest.raises(RuntimeError, match="Retry"):
            proxy.response(-1, 100)
        assert proxy.process is None
        assert proxy.response(150, 102) == {"dose": 150, "seed": 102}
    finally:
        proxy.close()


def test_timeout_terminates_work_before_releasing_caller():
    proxy = LiveProxy(timeout=0.5, worker=transport_worker)
    try:
        with pytest.raises(RuntimeError, match="timed out"):
            proxy.response(-2, 100)
        assert proxy.process is None
        proxy.timeout = 5
        assert proxy.response(200, 103)["dose"] == 200
    finally:
        proxy.close()
