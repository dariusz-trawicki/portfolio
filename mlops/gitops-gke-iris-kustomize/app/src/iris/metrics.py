"""Prometheus metrics: technical health plus a cheap drift signal.

The input feature histogram lets Grafana compare the production
distribution with the training distribution — a substitute for a full
tool like Evidently, good enough for demo purposes.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

PREDICTIONS_TOTAL = Counter(
    "iris_predictions_total", "Number of predictions served", ["predicted_class"]
)

PREDICTION_CONFIDENCE = Histogram(
    "iris_prediction_confidence",
    "Distribution of model prediction confidence",
    buckets=(0.25, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0),
)

PREDICTION_LATENCY = Histogram(
    "iris_prediction_latency_seconds", "Time to serve a single prediction"
)

FEATURE_VALUE = Histogram(
    "iris_feature_value",
    "Distribution of input feature values — signal for drift detection",
    ["feature"],
    buckets=(0, 1, 2, 3, 4, 5, 6, 7, 8),
)
