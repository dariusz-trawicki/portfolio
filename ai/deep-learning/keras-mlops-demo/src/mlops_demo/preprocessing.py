"""Preprocessing: ONE implementation shared by training, the API and monitoring.

The most common silent production failure is training/serving skew: one piece of
code prepares training data and a different one prepares requests. Here both paths
call exactly the same class, and the category vocabularies are saved with the model.
Numeric normalization lives inside the model (a Normalization layer), so its means
and variances are weights stored in the .keras file.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import CATEGORICAL, NUMERIC


@dataclass
class Preprocessor:
    numeric: list[str]
    vocabs: dict[str, list[str]]  # index 0 is reserved for "unknown category" (OOV)

    @classmethod
    def fit(cls, df: pd.DataFrame) -> "Preprocessor":
        return cls(list(NUMERIC), {c: sorted(df[c].unique().tolist()) for c in CATEGORICAL})

    def transform(self, df: pd.DataFrame) -> dict[str, np.ndarray]:
        out = {"numeric": df[self.numeric].to_numpy(dtype="float32")}
        for col, vocab in self.vocabs.items():
            lookup = {v: i + 1 for i, v in enumerate(vocab)}
            ids = df[col].map(lookup).fillna(0).astype("int32").to_numpy()
            out[col] = ids.reshape(-1, 1)
        return out

    def unknown_categories(self, record: dict) -> list[str]:
        """Fields whose value the model never saw during training (mapped to the OOV bucket)."""
        return [c for c, vocab in self.vocabs.items() if record.get(c) not in vocab]

    def to_dict(self) -> dict:
        return {"numeric": self.numeric, "vocabs": self.vocabs}

    @classmethod
    def from_dict(cls, d: dict) -> "Preprocessor":
        return cls(d["numeric"], d["vocabs"])
