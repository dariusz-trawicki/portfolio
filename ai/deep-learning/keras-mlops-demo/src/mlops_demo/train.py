"""Training pipeline.

data -> validation -> split -> training -> evaluation -> bundle -> quality gate -> (promotion)

Usage:  python -m mlops_demo.train --promote
Exit code 3 means "the gate rejected the model", so CI can use this as a blocking step.
"""
from __future__ import annotations

import argparse
import json
import logging
import platform
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import keras
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from . import __version__, registry
from .config import ARTIFACTS_DIR, MLFLOW_EXPERIMENT, MLFLOW_URI, TARGET, GateConfig, TrainConfig
from .data import fingerprint, generate_customers, validate
from .drift import build_reference
from .evaluation import class_weights, classification_metrics, fit_baseline, pick_threshold
from .gate import run_gate, to_report
from .model import build_model
from .predictor import Predictor, load_production, save_bundle
from .preprocessing import Preprocessor

log = logging.getLogger("train")


class Tracker:
    """Thin wrapper around MLflow. When `uri` is None every method is a no-op (e.g. in tests)."""

    def __init__(self, uri: str | None, experiment: str):
        self.enabled = uri is not None
        if self.enabled:
            import mlflow
            self.mlflow = mlflow
            mlflow.set_tracking_uri(uri)
            mlflow.set_experiment(experiment)

    def start(self, run_name: str) -> str | None:
        return self.mlflow.start_run(run_name=run_name).info.run_id if self.enabled else None

    def end(self, ok: bool = True) -> None:
        if self.enabled:
            self.mlflow.end_run(status="FINISHED" if ok else "FAILED")

    def params(self, d: dict) -> None:
        if self.enabled:
            self.mlflow.log_params({k: str(v) for k, v in d.items()})

    def metrics(self, d: dict, step: int | None = None) -> None:
        if self.enabled:
            self.mlflow.log_metrics({k: float(v) for k, v in d.items()}, step=step)

    def tags(self, d: dict) -> None:
        if self.enabled:
            self.mlflow.set_tags({k: str(v) for k, v in d.items()})

    def artifacts(self, path: Path, name: str) -> None:
        if self.enabled:
            self.mlflow.log_artifacts(str(path), artifact_path=name)


class EpochLogger(keras.callbacks.Callback):
    def __init__(self, tracker: Tracker, every: int = 5):
        super().__init__()
        self.tracker, self.every = tracker, every

    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}
        self.tracker.metrics(logs, step=epoch)  # learning curves in the MLflow UI
        if epoch == 0 or (epoch + 1) % self.every == 0:
            log.info("  epoch %3d  loss %.4f  val_loss %.4f  val_auc %.4f  val_pr_auc %.4f", epoch + 1,
                     logs["loss"], logs["val_loss"], logs["val_auc"], logs["val_pr_auc"])


def split(df: pd.DataFrame, cfg: TrainConfig):
    """Stratified split (preserves the churn rate): train / validation / test."""
    rest, test = train_test_split(df, test_size=cfg.test_size, stratify=df[TARGET], random_state=cfg.seed)
    train, val = train_test_split(rest, test_size=cfg.val_size / (1 - cfg.test_size), stratify=rest[TARGET], random_state=cfg.seed)
    return [d.reset_index(drop=True) for d in (train, val, test)]


def run_training(cfg: TrainConfig, artifacts_dir: Path, tracking_uri: str | None = None, promote: bool = False,
                 gate_cfg: GateConfig = GateConfig()) -> dict:
    artifacts_dir = Path(artifacts_dir)
    keras.utils.set_random_seed(cfg.seed)  # reproducibility: same data + seed gives the same result

    # 1. data + validation
    df = generate_customers(cfg.n_rows, seed=cfg.seed)
    validate(df)
    train, val, test = split(df, cfg)
    y_tr, y_va, y_te = (d[TARGET].to_numpy() for d in (train, val, test))
    log.info("data: train=%d val=%d test=%d, churn=%.1f%%, fingerprint=%s", len(train), len(val), len(test), 100 * df[TARGET].mean(), fingerprint(df))

    version = registry.next_version(artifacts_dir)
    tracker = Tracker(tracking_uri, MLFLOW_EXPERIMENT)
    run_id = tracker.start(version)
    try:
        tracker.params({**asdict(cfg), "gate": asdict(gate_cfg)})
        tracker.tags({"data_fingerprint": fingerprint(df), "backend": keras.backend.backend(), "keras": keras.__version__})

        # 2. training
        pre = Preprocessor.fit(train)
        X_tr, X_va, X_te = (pre.transform(d) for d in (train, val, test))
        model = build_model(pre, X_tr["numeric"], cfg)
        log.info("training %s (%s parameters, backend %s)", version, f"{model.count_params():,}", keras.backend.backend())
        history = model.fit(
            X_tr, y_tr.reshape(-1, 1).astype("float32"),
            validation_data=(X_va, y_va.reshape(-1, 1).astype("float32")),
            epochs=cfg.max_epochs, batch_size=cfg.batch_size, verbose=0,
            class_weight=class_weights(y_tr) if cfg.use_class_weights else None,
            callbacks=[
                keras.callbacks.EarlyStopping("val_pr_auc", mode="max", patience=cfg.patience, restore_best_weights=True),
                keras.callbacks.ReduceLROnPlateau("val_loss", factor=0.5, patience=max(cfg.patience // 2, 1)),
                EpochLogger(tracker),
            ],
        )

        # 3. evaluation: the threshold is picked on validation, results are reported on test
        p_va = model.predict(X_va, batch_size=1024, verbose=0).reshape(-1)
        p_te = model.predict(X_te, batch_size=1024, verbose=0).reshape(-1)
        threshold = pick_threshold(y_va, p_va)
        m_val, m_test = classification_metrics(y_va, p_va, threshold), classification_metrics(y_te, p_te, threshold)
        baseline = fit_baseline(train, y_tr, test, y_te)
        log.info("test: AUC %.4f | PR-AUC %.4f | precision %.3f | recall %.3f | baseline AUC %.4f",
                 m_test["roc_auc"], m_test["pr_auc"], m_test["precision"], m_test["recall"], baseline["roc_auc"])
        tracker.metrics({f"test_{k}": v for k, v in m_test.items()} | {f"baseline_{k}": v for k, v in baseline.items()})

        # 4. bundle (model + preprocessing + metadata + reference distributions for monitoring)
        epochs_run = len(history.history["loss"])
        metadata = {
            "version": version, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "threshold": threshold, "metrics": {"validation": m_val, "test": m_test}, "baseline_test": baseline,
            "training": {"epochs_run": epochs_run, "best_epoch": int(np.argmax(history.history["val_pr_auc"])) + 1,
                         "n_train": len(train), "n_val": len(val), "n_test": len(test)},
            "data": {"fingerprint": fingerprint(df), "n_rows": len(df), "churn_rate": float(df[TARGET].mean())},
            "config": asdict(cfg),
            "environment": {"python": platform.python_version(), "keras": keras.__version__,
                            "backend": keras.backend.backend(), "numpy": np.__version__, "package": __version__},
            "mlflow_run_id": run_id,
        }
        bundle = registry.bundle_dir(artifacts_dir, version)
        save_bundle(bundle, model, pre, metadata, build_reference(train, scores=p_te))

        # 5. quality gate: the challenger (freshly LOADED FROM DISK!) vs the baseline and the champion
        challenger = Predictor.load(bundle)
        roundtrip = float(np.max(np.abs(challenger.predict_df(test) - p_te)))
        checks = run_gate(challenger=challenger, test_df=test, y_test=y_te, baseline=baseline,
                          champion=load_production(artifacts_dir), roundtrip_diff=roundtrip, cfg=gate_cfg)
        report = to_report(checks)
        (bundle / "gate_report.json").write_text(json.dumps(report, indent=2))
        for c in checks:
            log.info("  [%s] %-28s %s", "OK  " if c.passed else "FAIL", c.name, c.detail)

        tracker.tags({"gate_passed": report["passed"]})
        tracker.artifacts(bundle, "bundle")

        # 6. promote only if the gate passed
        promoted = False
        if report["passed"] and promote:
            registry.promote(artifacts_dir, version, reason=f"gate passed, AUC {m_test['roc_auc']:.4f}")
            promoted = True
        log.info("result: %s %s", version, "-> PRODUCTION" if promoted else ("(gate passed, run with --promote to deploy)" if report["passed"] else "REJECTED by the quality gate"))
        tracker.end(ok=True)
        return {"version": version, "passed": report["passed"], "promoted": promoted, "metrics": m_test,
                "baseline": baseline, "checks": report["checks"], "bundle": str(bundle)}
    except BaseException:
        tracker.end(ok=False)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the churn model")
    parser.add_argument("--rows", type=int, default=TrainConfig.n_rows)
    parser.add_argument("--epochs", type=int, default=TrainConfig.max_epochs)
    parser.add_argument("--seed", type=int, default=TrainConfig.seed)
    parser.add_argument("--promote", action="store_true", help="set as production if the quality gate passes")
    parser.add_argument("--no-mlflow", action="store_true")
    parser.add_argument("--class-weights", action="store_true", help="use class weights (inflates probabilities, see the gate)")
    parser.add_argument("--artifacts", default=str(ARTIFACTS_DIR))
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = replace(TrainConfig(), n_rows=args.rows, max_epochs=args.epochs, seed=args.seed,
                  use_class_weights=args.class_weights)
    result = run_training(cfg, Path(args.artifacts), None if args.no_mlflow else MLFLOW_URI, args.promote)
    sys.exit(0 if result["passed"] else 3)


if __name__ == "__main__":
    main()
