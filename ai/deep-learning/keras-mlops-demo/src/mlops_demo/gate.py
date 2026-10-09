"""Quality gate: an automated decision on whether a new model (challenger) may replace the production one (champion).

In CI/CD this step replaces "I think it's better". Every check is explicit, has a
threshold in GateConfig and leaves a trace in gate_report.json.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from .config import CATEGORICAL, FEATURES, GateConfig
from .evaluation import slice_auc
from .predictor import Predictor


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def _latency_p95_ms(predictor: Predictor, df: pd.DataFrame, n: int = 100) -> float:
    records = df[FEATURES].head(n).to_dict("records")
    predictor.predict_records(records[:1])  # warm-up (JIT compilation is not part of the measurement)
    times = []
    for rec in records:
        t0 = time.perf_counter()
        predictor.predict_records([rec])
        times.append((time.perf_counter() - t0) * 1000)
    return float(np.percentile(times, 95))


def run_gate(*, challenger: Predictor, test_df: pd.DataFrame, y_test: np.ndarray, baseline: dict,
             champion: Predictor | None, roundtrip_diff: float, cfg: GateConfig) -> list[Check]:
    p = challenger.predict_df(test_df)
    auc = float(roc_auc_score(y_test, p))
    gap = abs(float(p.mean()) - float(y_test.mean()))
    checks = [
        Check("min_auc", auc >= cfg.min_auc, f"AUC {auc:.4f} (required >= {cfg.min_auc})"),
        # AUC only measures ranking. The API field is called "probability", so the values
        # must make sense as numbers too. This catches e.g. class weights or a wrong loss.
        Check("calibration_in_the_large", gap <= cfg.max_calibration_gap,
              f"mean prediction {p.mean():.3f} vs observed churn {y_test.mean():.3f} (gap {gap:.3f}, limit {cfg.max_calibration_gap})"),
        Check("beats_baseline", auc >= baseline["roc_auc"] + cfg.min_lift_over_baseline,
              f"AUC {auc:.4f} vs logistic regression {baseline['roc_auc']:.4f}"),
    ]

    if champion is None:
        checks.append(Check("no_regression_vs_champion", True, "no production model yet (first version)"))
    else:
        # Both models are scored on THE SAME fresh test set, not on their own training-time metrics.
        champ_auc = float(roc_auc_score(y_test, champion.predict_df(test_df)))
        checks.append(Check("no_regression_vs_champion", auc >= champ_auc - cfg.max_regression,
                            f"challenger {auc:.4f} vs champion {champ_auc:.4f} (tolerance {cfg.max_regression})"))

    for col in CATEGORICAL:
        slices = slice_auc(test_df, y_test, p, col, cfg.min_slice_n)
        worst = min(slices.items(), key=lambda kv: kv[1]["roc_auc"], default=None)
        if worst is None:
            checks.append(Check(f"slice_auc:{col}", True, "segments too small, skipped"))
        else:
            checks.append(Check(f"slice_auc:{col}", worst[1]["roc_auc"] >= cfg.min_slice_auc,
                                f"weakest segment '{worst[0]}': AUC {worst[1]['roc_auc']:.4f} (n={worst[1]['n']})"))

    checks.append(Check("serialization_roundtrip", roundtrip_diff <= cfg.max_roundtrip_diff,
                        f"max difference after save and load: {roundtrip_diff:.2e}"))
    p95 = _latency_p95_ms(challenger, test_df)
    checks.append(Check("latency_p95_ms", p95 <= cfg.max_p95_latency_ms, f"p95 = {p95:.1f} ms (limit {cfg.max_p95_latency_ms})"))
    return checks


def passed(checks: list[Check]) -> bool:
    return all(c.passed for c in checks)


def to_report(checks: list[Check]) -> dict:
    return {"passed": passed(checks), "checks": [asdict(c) for c in checks]}
