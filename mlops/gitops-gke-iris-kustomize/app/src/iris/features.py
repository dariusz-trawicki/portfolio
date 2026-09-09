"""Iris feature preprocessor — used identically in training and serving.

Standardization (z-score) based on statistics from the training data.
Saved as JSON, not a scikit-learn pickle — the serving image then
doesn't need a dependency on sklearn.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

FEATURE_NAMES = [
    "sepal_length_cm",
    "sepal_width_cm",
    "petal_length_cm",
    "petal_width_cm",
]

CLASS_NAMES = ["setosa", "versicolor", "virginica"]


@dataclass
class Preprocessor:
    mean: list[float]
    std: list[float]

    @classmethod
    def fit(cls, x: np.ndarray) -> Preprocessor:
        mean = x.mean(axis=0)
        std = x.std(axis=0)
        std[std == 0] = 1.0  # guard against division by zero
        return cls(mean=mean.tolist(), std=std.tolist())

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - np.array(self.mean)) / np.array(self.std)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self)))

    @classmethod
    def load(cls, path: Path) -> Preprocessor:
        return cls(**json.loads(path.read_text()))
