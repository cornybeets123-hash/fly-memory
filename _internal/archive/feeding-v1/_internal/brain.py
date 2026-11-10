"""Recorded and live responses of the unchanged Shiu whole-brain model.

Replay is explicit: the engine selects an actual seeded neural recording for its
stimulus. It never substitutes an outcome rule for a motor-neuron response.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from time import perf_counter

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BANK_PATH = Path(__file__).parent / "data" / "brain-bank.json"


class RecordedBrain:
    def __init__(self, path=BANK_PATH):
        self.data = json.loads(path.read_text())
        self.trials = {row["id"]: row for row in self.data["trials"]}
        self.seeds = self.data["protocol"]["seeds"]
        self.gate = self.data["protocol"]["gate"]["threshold_hz"]
        for bitter in (0, 50, 100, 150, 200):
            for seed in self.seeds:
                if self.key(bitter, seed) not in self.trials:
                    raise ValueError(
                        "The neural recording bank is incomplete. Regenerate it before running."
                    )

    @staticmethod
    def key(bitter, seed):
        return f"p9-sugar-bitter-{bitter}-seed-{seed}"

    def response(self, bitter, seed):
        row = self.trials[self.key(bitter, seed)]
        return {
            "trial_id": row["id"],
            "source": "recorded",
            "seed": seed,
            "bitter_hz": bitter,
            "sugar_hz": 150,
            "feeding": row["readouts_hz"]["MN9"][0] > self.gate,
            "readouts_hz": row["readouts_hz"],
        }


class LiveBrain:
    """Build one upstream network and restore its naive state for each contact."""

    def __init__(self, bank: RecordedBrain):
        try:
            import brian2 as b
            import pandas as pd
        except ImportError as error:
            raise RuntimeError(
                "Install the live brain with: uv sync --locked --extra brain"
            ) from error
        upstream = ROOT / "brain" / "model.py"
        if not upstream.exists():
            raise RuntimeError(
                "Download the pinned brain model with: uv run run.py --setup-brain"
            )
        for file in bank.data["provenance"]["files"]:
            if file["path"].startswith("brain/"):
                path = ROOT / file["path"]
                if (
                    not path.exists()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != file["sha256"]
                ):
                    raise RuntimeError(
                        f"Brain source differs from recorded provenance: {file['path']}"
                    )
        spec = importlib.util.spec_from_file_location("fly_workshop_shiu", upstream)
        self.model = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.model
        spec.loader.exec_module(self.model)
        self.b = b
        b.prefs.codegen.target = "numpy"
        # Brian2's timestep is part of the recorded protocol, not a speed knob.
        b.defaultclock.dt = bank.data["provenance"]["dt_s"] * b.second
        ids = pd.read_csv(
            ROOT / "brain/2023_03_23_completeness_630_final.csv", index_col=0
        ).index
        mapping = {int(neuron): index for index, neuron in enumerate(ids)}
        self.groups = {
            key: [mapping[int(neuron)] for neuron in values]
            for key, values in bank.data["protocol"]["neuron_ids"].items()
        }
        self.params = self.model.default_params
        self.neurons, self.synapses, self.monitor = self.model.create_model(
            ROOT / "brain/2023_03_23_completeness_630_final.csv",
            ROOT / "brain/2023_03_23_connectivity_630_final.parquet",
            self.params,
        )
        self.network = b.Network(self.neurons, self.synapses, self.monitor)
        self.network.store("naive")
        self.bank = bank

    def response(self, bitter, seed):
        b = self.b
        self.network.restore("naive")
        b.seed(seed)
        inputs = []
        for group, rate in {"P9": 150, "sugar": 150, "bitter": bitter}.items():
            if rate:
                for index in self.groups[group]:
                    self.neurons[index].rfc = 0 * b.ms
                    inputs.append(
                        b.PoissonInput(
                            self.neurons[index],
                            "v",
                            1,
                            rate * b.Hz,
                            self.params["w_syn"] * self.params["f_poi"],
                        )
                    )
        self.network.add(inputs)
        start = perf_counter()
        try:
            self.network.run(self.params["t_run"])
            indices = np.asarray(self.monitor.i[:])
            times = np.asarray(self.monitor.t[:] / b.second)
            counts = np.bincount(indices, minlength=len(self.neurons))
            duration = float(self.params["t_run"])
            readouts = {
                key: [float(counts[index]) / duration for index in self.groups[key]]
                for key in ("MN9", "P9-oDN1", "FG")
            }
            traces = {}
            for group, group_indices in self.groups.items():
                hist = [
                    np.histogram(
                        times[indices == index],
                        bins=self.bank.data["protocol"]["bin_edges_s"],
                    )[0].tolist()
                    for index in group_indices
                ]
                traces[group] = (
                    np.sum(hist, axis=0).tolist()
                    if group in ("sugar", "bitter")
                    else hist
                )
        finally:
            self.network.remove(inputs)
        recorded = self.bank.response(bitter, seed)
        return {
            **recorded,
            "source": "live",
            "readouts_hz": readouts,
            "traces": traces,
            "feeding": readouts["MN9"][0] > self.bank.gate,
            "matches_recording": readouts == recorded["readouts_hz"]
            and traces == self.bank.trials[recorded["trial_id"]]["traces"],
            "wall_seconds": round(perf_counter() - start, 3),
        }
