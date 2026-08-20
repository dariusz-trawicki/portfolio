"""
Compares a reference window (oldest available data) with
a recent window (last `recent_hours`) pulled from the real feature store.
The KS test remains the primary method (PSI is unreliable with small
samples / low-variance features - see the fix from the original session),
PSI is computed as a supplementary, informational-only signal.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats

from .config import FEATURE_COLUMNS

KS_ALPHA = 0.01  # KS test significance threshold
PSI_BINS = 10
PSI_WARN_THRESHOLD = 0.25


def _psi(reference: np.ndarray, current: np.ndarray, bins: int = PSI_BINS) -> float:
    # bins based on quantiles of the reference window, guarded against a
    # degenerate distribution (near-constant feature)
    quantiles = np.linspace(0, 1, bins + 1)
    edges = np.unique(np.quantile(reference, quantiles))
    if len(edges) < 3:
        return 0.0  # not enough variance for PSI to make sense
    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)
    ref_pct = np.clip(ref_counts / max(len(reference), 1), 1e-6, None)
    cur_pct = np.clip(cur_counts / max(len(current), 1), 1e-6, None)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def detect_drift(df: pd.DataFrame, reference_frac: float = 0.3) -> dict:
    """Splits the dataset chronologically into a reference window (oldest
    `reference_frac`) and a current window (the rest), then computes KS +
    PSI for every feature. Returns per-feature metrics plus an overall
    `drift_detected` flag."""
    df = df.sort_values("event_ts")
    split_idx = max(int(len(df) * reference_frac), 1)
    reference, current = df.iloc[:split_idx], df.iloc[split_idx:]

    if len(current) < 5:
        return {"drift_detected": False, "reason": "not enough recent data", "per_feature": {}}

    per_feature = {}
    n_drifted = 0
    for col in FEATURE_COLUMNS:
        ref_vals = reference[col].dropna().to_numpy()
        cur_vals = current[col].dropna().to_numpy()
        if len(ref_vals) < 5 or len(cur_vals) < 5:
            continue
        ks_stat, ks_pvalue = stats.ks_2samp(ref_vals, cur_vals)
        psi_val = _psi(ref_vals, cur_vals)
        drifted = ks_pvalue < KS_ALPHA
        n_drifted += int(drifted)
        per_feature[col] = {
            "ks_statistic": float(ks_stat),
            "ks_pvalue": float(ks_pvalue),
            "psi": psi_val,
            "drifted_ks": drifted,
            "drifted_psi": psi_val > PSI_WARN_THRESHOLD,
        }

    drift_detected = n_drifted >= 2  # drift is considered significant when >=2 features have shifted
    return {
        "drift_detected": drift_detected,
        "n_features_drifted_ks": n_drifted,
        "n_reference": len(reference),
        "n_current": len(current),
        "per_feature": per_feature,
    }
