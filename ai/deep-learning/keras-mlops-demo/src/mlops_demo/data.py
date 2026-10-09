"""Data: synthetic customer generator, schema validation, dataset fingerprint.

The data is synthetic, so the project runs offline and we know the "true" mechanism
that generates the labels. This lets us inject controlled drift (the `drift` parameter)
and check that monitoring catches it.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from .config import CATEGORICAL, FEATURES, TARGET


class DataValidationError(ValueError):
    pass


def _choice(rng: np.random.Generator, values: list[str], p, n: int) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, None)
    return rng.choice(values, size=n, p=p / p.sum())


def generate_customers(n: int, seed: int = 0, drift: float = 0.0) -> pd.DataFrame:
    """Sample `n` customers. `drift` in [0, 1] simulates a changing world:
    price increases, more fiber customers, more new customers, and a behavioural
    shift (a competitor fighting for fiber customers)."""
    rng = np.random.default_rng(seed)
    d = float(np.clip(drift, 0.0, 1.0))

    contract = _choice(rng, CATEGORICAL["contract"], np.array([0.55, 0.25, 0.20]) + d * np.array([0.15, -0.08, -0.07]), n)
    internet = _choice(rng, CATEGORICAL["internet_service"], np.array([0.35, 0.45, 0.20]) + d * np.array([-0.10, 0.18, -0.08]), n)
    payment = _choice(rng, CATEGORICAL["payment_method"], [0.35, 0.20, 0.30, 0.15], n)

    fiber = internet == "fiber"
    mtm = contract == "month_to_month"

    tenure = rng.gamma(2.0, 12.0, n) + np.select([contract == "one_year", contract == "two_year"], [6, 14], 0)
    tenure = np.clip(tenure * (1 - 0.4 * d), 0, 72).astype(int)

    monthly = 25 + np.select([internet == "dsl", fiber], [20, 45], 0) + rng.normal(0, 10, n) + 12 * d
    monthly = np.clip(monthly, 18, 130).round(2)

    lam = (0.8 + 0.5 * fiber + 0.4 * (tenure < 6)) * (1 + 0.5 * d)
    calls = np.clip(rng.poisson(lam), 0, 30)
    senior = rng.binomial(1, 0.16, n)

    # Hidden mechanism: a linear part plus non-linearities and interactions that a
    # linear model cannot capture (so the network has a real chance to beat the baseline).
    z = (
        -1.9
        + 1.2 * mtm - 0.9 * (contract == "two_year")
        - 0.030 * tenure
        + 0.010 * (monthly - 65)
        + 0.0007 * (monthly - 65) ** 2        # U-shape: both very cheap and very expensive plans churn
        + 0.30 * calls
        + 0.3 * (payment == "e_check")
        + 0.3 * senior
        + 1.6 * (fiber & (monthly > 85))      # fiber price sensitivity (interaction)
        + 1.2 * (mtm & (calls >= 3))          # unhappy customers without a contract (interaction)
        + 0.9 * (mtm & (payment == "e_check"))
        + 1.5 * np.exp(-tenure / 5.0) * mtm   # early churn (non-linearity)
        + 0.8 * d * fiber                      # concept drift (competition)
        + rng.normal(0, 0.3, n)
    )
    churn = (rng.random(n) < 1 / (1 + np.exp(-z))).astype(int)

    return pd.DataFrame({
        "tenure_months": tenure, "monthly_charges": monthly, "support_calls_90d": calls,
        "is_senior": senior, "contract": contract, "payment_method": payment,
        "internet_service": internet, TARGET: churn,
    })


RANGES = {
    "tenure_months": (0, 120), "monthly_charges": (0, 500),
    "support_calls_90d": (0, 100), "is_senior": (0, 1),
}


def validate(df: pd.DataFrame, *, require_label: bool = True, expected_rate=(0.02, 0.60)) -> None:
    """DATA quality gate. Bad data means a bad model, so stop the pipeline early."""
    required = FEATURES + ([TARGET] if require_label else [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DataValidationError(f"missing columns: {missing}")

    problems = []
    for c in required:
        if (nulls := int(df[c].isna().sum())):
            problems.append(f"{c}: {nulls} missing values")
    for c, (lo, hi) in RANGES.items():
        if (bad := int(((df[c] < lo) | (df[c] > hi)).sum())):
            problems.append(f"{c}: {bad} values outside [{lo}, {hi}]")
    for c, allowed in CATEGORICAL.items():
        if (bad := int((~df[c].isin(allowed)).sum())):
            problems.append(f"{c}: {bad} unknown categories")
    if require_label:
        if not set(df[TARGET].unique()) <= {0, 1}:
            problems.append("label outside {0, 1}")
        elif not expected_rate[0] <= df[TARGET].mean() <= expected_rate[1]:
            problems.append(f"suspicious churn rate: {df[TARGET].mean():.3f}")
    if problems:
        raise DataValidationError("; ".join(problems))


def fingerprint(df: pd.DataFrame) -> str:
    """Content hash of the dataset, stored with the model: we always know WHAT it was trained on."""
    digest = pd.util.hash_pandas_object(df, index=False).to_numpy().tobytes()
    return hashlib.sha256(digest).hexdigest()[:16]
