"""Model bundle and Predictor: the only path from a raw record to a probability.

A bundle (one version directory) holds everything needed to serve the model, so it
can be copied to another machine and works without the rest of the project:
    model.keras            weights + architecture + normalization
    preprocessing.json     category vocabularies
    metadata.json          metrics, threshold, data fingerprint, library versions
    reference_stats.json   training feature distributions (baseline for drift detection)
    gate_report.json       quality-gate result
"""
from __future__ import annotations

import json
from pathlib import Path

import keras
import numpy as np
import pandas as pd

from . import registry
from .preprocessing import Preprocessor


def save_bundle(path: Path, model: keras.Model, pre: Preprocessor, metadata: dict, reference: dict) -> None:
    path.mkdir(parents=True, exist_ok=True)
    model.save(path / "model.keras")
    (path / "preprocessing.json").write_text(json.dumps(pre.to_dict(), indent=2))
    (path / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (path / "reference_stats.json").write_text(json.dumps(reference, indent=2))


class Predictor:
    def __init__(self, model: keras.Model, pre: Preprocessor, metadata: dict, reference: dict):
        self.model, self.preprocessor, self.metadata, self.reference = model, pre, metadata, reference

    @classmethod
    def load(cls, path: Path) -> "Predictor":
        path = Path(path)
        return cls(
            keras.saving.load_model(path / "model.keras", compile=False),
            Preprocessor.from_dict(json.loads((path / "preprocessing.json").read_text())),
            json.loads((path / "metadata.json").read_text()),
            json.loads((path / "reference_stats.json").read_text()),
        )

    @property
    def version(self) -> str:
        return self.metadata["version"]

    @property
    def threshold(self) -> float:
        return float(self.metadata["threshold"])

    def predict_df(self, df: pd.DataFrame) -> np.ndarray:
        inputs = self.preprocessor.transform(df.reset_index(drop=True))
        if len(df) <= 2048:
            out = self.model.predict_on_batch(inputs)
        else:
            out = self.model.predict(inputs, batch_size=1024, verbose=0)
        return np.asarray(out, dtype="float64").reshape(-1)

    def predict_records(self, records: list[dict]) -> np.ndarray:
        return self.predict_df(pd.DataFrame.from_records(records))


def load_production(artifacts: Path) -> Predictor | None:
    version = registry.production_version(artifacts)
    return Predictor.load(registry.bundle_dir(artifacts, version)) if version else None
