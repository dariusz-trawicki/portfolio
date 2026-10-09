"""Metrics, decision-threshold selection, slice evaluation and the baseline model."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import CATEGORICAL, FEATURES, NUMERIC


def class_weights(y: np.ndarray) -> dict[int, float]:
    """Churners are rarer than non-churners. "Balanced" weights equalize each class's share of the loss."""
    n, pos = len(y), int(y.sum())
    return {0: n / (2 * (n - pos)), 1: n / (2 * pos)}


def pick_threshold(y: np.ndarray, p: np.ndarray) -> float:
    """F1-maximizing threshold. Chosen on VALIDATION, never on test (that would be leakage)."""
    prec, rec, thr = precision_recall_curve(y, p)
    f1 = 2 * prec[:-1] * rec[:-1] / np.clip(prec[:-1] + rec[:-1], 1e-12, None)
    return float(thr[int(np.argmax(f1))])


def classification_metrics(y: np.ndarray, p: np.ndarray, threshold: float) -> dict[str, float]:
    pred = p >= threshold
    tp = int((pred & (y == 1)).sum())
    fp = int((pred & (y == 0)).sum())
    fn = int((~pred & (y == 1)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),  # more informative under class imbalance
        "brier": float(brier_score_loss(y, p)),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / max(precision + recall, 1e-12),
        "threshold": float(threshold),
        "positive_rate": float(pred.mean()),
        "base_rate": float(y.mean()),
        "mean_prediction": float(np.mean(p)),  # should be close to base_rate if the model is calibrated
    }


def slice_auc(df: pd.DataFrame, y: np.ndarray, p: np.ndarray, col: str, min_n: int) -> dict[str, dict]:
    """AUC for each value of a column. An average can hide a segment the model serves badly."""
    out = {}
    for value, idx in df.reset_index(drop=True).groupby(col).indices.items():
        if len(idx) < min_n or len(set(y[idx])) < 2:
            continue
        out[str(value)] = {"n": int(len(idx)), "roc_auc": float(roc_auc_score(y[idx], p[idx]))}
    return out


def fit_baseline(train: pd.DataFrame, y_train: np.ndarray, test: pd.DataFrame, y_test: np.ndarray) -> dict[str, float]:
    """Simple baseline (logistic regression). The network must beat it to justify its complexity."""
    pipe = Pipeline([
        ("prep", ColumnTransformer([
            ("num", StandardScaler(), NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore"), list(CATEGORICAL)),
        ])),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])
    pipe.fit(train[FEATURES], y_train)
    p = pipe.predict_proba(test[FEATURES])[:, 1]
    return {"roc_auc": float(roc_auc_score(y_test, p)), "pr_auc": float(average_precision_score(y_test, p))}
