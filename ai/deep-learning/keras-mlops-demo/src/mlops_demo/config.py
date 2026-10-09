"""Shared configuration: data schema, hyperparameters, quality-gate thresholds."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = Path(os.environ.get("MLOPS_ARTIFACTS", ROOT / "artifacts"))
MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{ROOT / 'mlflow.db'}")
MLFLOW_EXPERIMENT = "churn-demo"

# --- data schema (single source of truth for training, the API and monitoring) ---
NUMERIC = ["tenure_months", "monthly_charges", "support_calls_90d", "is_senior"]
CATEGORICAL = {
    "contract": ["month_to_month", "one_year", "two_year"],
    "payment_method": ["card", "bank_transfer", "e_check", "mail"],
    "internet_service": ["dsl", "fiber", "none"],
}
FEATURES = NUMERIC + list(CATEGORICAL)
TARGET = "churn"


@dataclass(frozen=True)
class TrainConfig:
    seed: int = 42
    n_rows: int = 20_000
    test_size: float = 0.2
    val_size: float = 0.2
    hidden: tuple[int, ...] = (64, 32)
    emb_dim: int = 4
    dropout: float = 0.3
    l2: float = 1e-4
    lr: float = 1e-3
    batch_size: int = 256
    max_epochs: int = 60
    patience: int = 8
    # Class weights improve sensitivity to the minority class but INFLATE the predicted
    # probabilities (the model stops being calibrated). Not needed at ~30% churn.
    use_class_weights: bool = False


@dataclass(frozen=True)
class GateConfig:
    """Quality-gate thresholds. A model that fails any of them never reaches production."""

    min_auc: float = 0.75                 # absolute quality floor
    min_lift_over_baseline: float = 0.0   # must be at least as good as logistic regression
    max_calibration_gap: float = 0.05     # |mean prediction - observed churn rate|
    max_regression: float = 0.005         # allowed drop vs the production model
    min_slice_auc: float = 0.65           # no customer segment may be "forgotten"
    min_slice_n: int = 150                # minimum segment size to be evaluated
    max_roundtrip_diff: float = 1e-4      # save -> load must not change predictions
    max_p95_latency_ms: float = 250.0     # single-prediction latency budget
