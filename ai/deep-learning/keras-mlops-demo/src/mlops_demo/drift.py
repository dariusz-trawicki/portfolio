"""Data-drift detection with PSI (Population Stability Index).

PSI compares a feature's production distribution with its training distribution:
    PSI = sum over bins of (a - e) * ln(a / e),   e = expected, a = actual
Rule of thumb: < 0.1 stable, 0.1 to 0.25 moderate shift, > 0.25 major shift.

Practical caveat: on small samples PSI is inflated by sampling noise
(roughly n_bins / n), so below `min_samples` we draw no conclusions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CATEGORICAL, NUMERIC

EPS = 1e-4
WARN, ALERT = 0.10, 0.25


def psi(expected, actual) -> float:
    e = np.clip(np.asarray(expected, dtype=float), EPS, None)
    a = np.clip(np.asarray(actual, dtype=float), EPS, None)
    e, a = e / e.sum(), a / a.sum()
    return float(np.sum((a - e) * np.log(a / e)))


def status(value: float) -> str:
    return "alert" if value >= ALERT else "warn" if value >= WARN else "ok"


def _props_continuous(x: np.ndarray, inner_edges: list[float]) -> np.ndarray:
    idx = np.searchsorted(inner_edges, x, side="right")
    return np.bincount(idx, minlength=len(inner_edges) + 1) / max(len(x), 1)


def _props_discrete(series: pd.Series, values: list) -> np.ndarray:
    counts = [(series == v).sum() for v in values]
    other = len(series) - sum(counts)  # values never seen in training
    return np.array(counts + [other], dtype=float) / max(len(series), 1)


def _describe(series: pd.Series, discrete: bool, n_bins: int, max_discrete: int) -> dict:
    values = sorted(series.unique().tolist())
    if discrete or len(values) <= max_discrete:
        kind, spec = "discrete", {"values": values}
        props = _props_discrete(series, values)
    else:
        inner = np.unique(np.quantile(series, np.linspace(0, 1, n_bins + 1)[1:-1])).tolist()
        kind, spec = "continuous", {"edges": inner}
        props = _props_continuous(series.to_numpy(), inner)
    return {"kind": kind, **spec, "props": props.tolist()}


def build_reference(df: pd.DataFrame, scores: np.ndarray | None = None, n_bins: int = 10, max_discrete: int = 12) -> dict:
    ref = {"features": {}, "n": int(len(df))}
    for col in NUMERIC:
        ref["features"][col] = _describe(df[col], False, n_bins, max_discrete)
    for col in CATEGORICAL:
        ref["features"][col] = _describe(df[col], True, n_bins, max_discrete)
    if scores is not None:
        ref["score"] = _describe(pd.Series(scores), False, n_bins, max_discrete=0)
    return ref


def _current_props(spec: dict, series: pd.Series) -> np.ndarray:
    if spec["kind"] == "discrete":
        return _props_discrete(series, spec["values"])
    return _props_continuous(series.to_numpy(), spec["edges"])


def compare(reference: dict, df: pd.DataFrame, scores: np.ndarray | None = None, min_samples: int = 500) -> dict:
    """Return a report: PSI and status for every feature and for the model-score distribution."""
    report = {"n": int(len(df)), "enough_data": len(df) >= min_samples, "features": {}, "score": None}
    for name, spec in reference["features"].items():
        if name in df.columns:
            value = psi(spec["props"], _current_props(spec, df[name]))
            report["features"][name] = {"psi": round(value, 4), "status": status(value)}
    if scores is not None and "score" in reference:
        value = psi(reference["score"]["props"], _current_props(reference["score"], pd.Series(scores)))
        report["score"] = {"psi": round(value, 4), "status": status(value)}

    all_psi = [v["psi"] for v in report["features"].values()] + ([report["score"]["psi"]] if report["score"] else [])
    report["max_psi"] = max(all_psi, default=0.0)
    report["alert"] = bool(report["enough_data"] and report["max_psi"] >= ALERT)
    return report
