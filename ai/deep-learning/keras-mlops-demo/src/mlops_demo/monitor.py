"""Drift monitoring: compares recent predictions from the log with the training distributions.

Usage:       python -m mlops_demo.monitor --window 1000
Exit codes:  0 = OK or warning, 1 = ALERT (retraining recommended), 3 = no data

Why it matters: labels (did the customer actually leave?) arrive weeks later.
Drift in features and model scores is visible IMMEDIATELY, so it is an early-warning system.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from .config import ARTIFACTS_DIR
from .drift import compare
from .predictor import load_production


def load_log(path: Path, window: int) -> tuple[pd.DataFrame, "pd.Series", float]:
    lines = [ln for ln in path.read_text().splitlines() if ln.strip()][-window:]
    rows = [json.loads(ln) for ln in lines]
    df = pd.DataFrame([r["features"] for r in rows])
    scores = pd.Series([r["probability"] for r in rows])
    unknown_rate = sum(bool(r["unknown_categories"]) for r in rows) / max(len(rows), 1)
    return df, scores, unknown_rate


def main() -> None:
    parser = argparse.ArgumentParser(description="Data drift monitoring")
    parser.add_argument("--artifacts", default=str(ARTIFACTS_DIR))
    parser.add_argument("--log", default=None)
    parser.add_argument("--window", type=int, default=1000, help="number of most recent predictions to analyze")
    parser.add_argument("--min-samples", type=int, default=500)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    artifacts = Path(args.artifacts)
    predictor = load_production(artifacts)
    log_path = Path(args.log or artifacts / "prediction_log.jsonl")
    if predictor is None or not log_path.exists():
        print("No production model or prediction log, nothing to monitor.")
        sys.exit(3)

    df, scores, unknown_rate = load_log(log_path, args.window)
    report = compare(predictor.reference, df, scores.to_numpy(), min_samples=args.min_samples)
    report["unknown_category_rate"] = round(unknown_rate, 4)

    print(f"Monitoring model {predictor.version}: window of {report['n']} predictions (reference: {predictor.reference['n']} training rows)")
    if not report["enough_data"]:
        print(f"NOTE: fewer than {args.min_samples} samples, PSI is inflated by noise and will not trigger an alert.")
    print(f"{'feature':<20}{'PSI':>8}  status")
    rows = {**report["features"], **({"(model score)": report["score"]} if report["score"] else {})}
    for name, r in sorted(rows.items(), key=lambda kv: -kv[1]["psi"]):
        print(f"{name:<20}{r['psi']:>8.3f}  {r['status'].upper()}")
    print(f"unknown categories in requests: {unknown_rate:.1%}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2))
    if report["alert"]:
        print("\nALERT: major drift (PSI >= 0.25). Recommended: check the data source and schedule retraining.")
        sys.exit(1)
    print("\nOK: no major drift.")


if __name__ == "__main__":
    main()
