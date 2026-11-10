"""Measured single-odorant responses; explicitly designed mixtures and noise."""

import json
from pathlib import Path

import numpy as np

DATA = Path(__file__).parent / "data"


class OdorSpace:
    def __init__(self):
        self.data = json.loads((DATA / "odors.json").read_text())
        self.receptors = self.data["receptors"]
        self.responses = {
            r["name"]: np.array(r["response"]) for r in self.data["odorants"]
        }
        self.mean = np.array(self.data["normalization"]["fixed_mean"])
        self.recipes = self.data["recipes"]
        # Fit a fixed visual projection to the odorant library, never outcome labels.
        matrix = np.stack(list(self.responses.values())) - self.mean
        self.projection = np.linalg.svd(matrix, full_matrices=False)[2][:2].T

    @property
    def dim(self):
        return len(self.receptors)

    def encode(self, receptor_response, representation="centered"):
        vector = np.array(receptor_response, dtype=float)
        if representation == "centered":
            vector -= self.mean
        norm = np.linalg.norm(vector)
        if norm == 0 or not np.isfinite(norm):
            raise ValueError("The receptor pattern has no finite direction.")
        return (vector / norm).tolist()

    def project(self, vector):
        return (np.array(vector) @ self.projection).tolist()

    def sample(self, family, harmful, rng, *, noise=0.015, marker=0.30):
        names = list(self.responses)
        weights = np.array([self.recipes[family].get(key, 0) for key in names])
        weights *= np.exp(rng.normal(0, 0.25, len(names)))
        weights /= weights.sum()
        if harmful:
            weights *= 1 - marker
            weights[names.index("acetophenone")] += marker
        response = weights @ np.stack(list(self.responses.values()))
        response += rng.normal(0, noise, self.dim)
        return response.tolist()
