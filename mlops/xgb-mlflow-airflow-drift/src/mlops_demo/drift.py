"""Lightweight drift monitoring: Kolmogorov-Smirnov test + PSI for every feature.

Deliberately implemented without Evidently: fewer dependencies and no version
conflicts with Airflow's pinned constraints. Swapping in Evidently's
DataDriftPreset would only touch `compute_drift`.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from .data import FEATURES


def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index using quantile bins of the reference sample."""
    edges = np.unique(np.quantile(reference, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.clip(np.histogram(reference, edges)[0] / len(reference), 1e-4, None)
    c = np.clip(np.histogram(current, edges)[0] / len(current), 1e-4, None)
    return float(np.sum((c - r) * np.log(c / r)))


def compute_drift(reference: pd.DataFrame, current: pd.DataFrame, alpha: float = 0.01, psi_min: float = 0.1) -> dict:
    """A feature is flagged when KS p-value < alpha AND PSI >= psi_min.

    Requiring both filters out false alarms: with large samples KS flags
    statistically significant but practically irrelevant differences.
    """
    features = {}
    for col in FEATURES:
        ks = ks_2samp(reference[col], current[col])
        p = psi(reference[col].to_numpy(), current[col].to_numpy())
        features[col] = {
            "ks_stat": round(float(ks.statistic), 4),
            "p_value": float(ks.pvalue),
            "psi": round(p, 4),
            "ref_mean": round(float(reference[col].mean()), 3),
            "cur_mean": round(float(current[col].mean()), 3),
            "drifted": bool(ks.pvalue < alpha and p >= psi_min),
        }
    drifted = [c for c, v in features.items() if v["drifted"]]
    return {
        "n_features": len(FEATURES),
        "n_drifted": len(drifted),
        "drift_share": len(drifted) / len(FEATURES),
        "drifted_features": drifted,
        "features": features,
    }


def save_report(report: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path
