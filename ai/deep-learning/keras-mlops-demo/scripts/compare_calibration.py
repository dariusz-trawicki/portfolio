"""Compare two trained bundles on fresh data: ranking (AUC) vs calibration.

Reproduces the class-weights finding from the README:

    python -m mlops_demo.train --no-mlflow --artifacts exp/no_weights
    python -m mlops_demo.train --no-mlflow --artifacts exp/class_weights --class-weights
    python scripts/compare_calibration.py exp/no_weights exp/class_weights
"""
import sys

import numpy as np
from scipy.stats import spearmanr

from mlops_demo.config import FEATURES
from mlops_demo.data import generate_customers
from mlops_demo.predictor import Predictor

BINS = [0.2, 0.4, 0.6, 0.8]
LABELS = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]


def main(dir_a: str, dir_b: str) -> None:
    a = Predictor.load(f"{dir_a}/models/v0001")
    b = Predictor.load(f"{dir_b}/models/v0001")
    df = generate_customers(5000, seed=123)  # fresh customers neither model has seen
    pa, pb = a.predict_df(df[FEATURES]), b.predict_df(df[FEATURES])

    print(f"observed churn rate:          {df.churn.mean():.3f}")
    print(f"mean prediction  A ({dir_a}): {pa.mean():.3f}")
    print(f"mean prediction  B ({dir_b}): {pb.mean():.3f}")
    print(f"rank correlation (Spearman):  {spearmanr(pa, pb).statistic:.4f}")
    print(f"thresholds: A {a.threshold:.3f} | B {b.threshold:.3f}")
    agree = np.mean((pa >= a.threshold) == (pb >= b.threshold))
    print(f"decision agreement (each model at its own threshold): {agree:.1%}")

    print("\nreliability: model says ~X%  ->  observed churn in that bucket")
    for name, p in [("A", pa), ("B", pb)]:
        bins = np.digitize(p, BINS)
        row = [f"{label}: {df.churn[bins == k].mean():.0%}" for k, label in enumerate(LABELS) if (bins == k).sum() >= 50]
        print(f"  {name}  " + " | ".join(row))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
