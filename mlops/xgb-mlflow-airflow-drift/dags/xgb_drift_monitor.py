"""Monitoring: feature drift + champion quality on production data. Triggers retraining on drift."""
from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import get_current_context
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

from mlops_demo.config import PRODUCTION_PATH  # lightweight import (no xgboost/mlflow at parse time)


@dag(
    dag_id="xgb_drift_monitor",
    description="Detects data drift and (optionally) triggers xgb_training_pipeline",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    params={
        "alpha": Param(0.01, type="number", description="KS-test p-value threshold"),
        "drift_share_threshold": Param(0.3, type="number", description="Share of drifted features that triggers retraining"),
    },
    tags=["mlops", "monitoring"],
)
def xgb_drift_monitor():
    @task
    def check_drift() -> dict:
        import mlflow
        import pandas as pd

        from mlops_demo.config import EXPERIMENT_DRIFT, REFERENCE_PATH, REPORTS_DIR
        from mlops_demo.data import TARGET
        from mlops_demo.drift import compute_drift, save_report
        from mlops_demo.training import champion_metrics_on, init_mlflow

        ctx = get_current_context()
        params = ctx["params"]

        if not REFERENCE_PATH.exists():
            return {"status": "no_reference", "drift_detected": False, "message": "Run xgb_training_pipeline first."}
        if not PRODUCTION_PATH.exists():
            return {"status": "no_production_data", "drift_detected": False, "message": "Run simulate_production_data first."}

        reference, current = pd.read_csv(REFERENCE_PATH), pd.read_csv(PRODUCTION_PATH)
        report = compute_drift(reference, current, alpha=params["alpha"])
        report["drift_detected"] = report["drift_share"] >= params["drift_share_threshold"]
        report["champion_on_production"] = champion_metrics_on(current) if TARGET in current else None

        path = save_report(report, REPORTS_DIR / f"drift_{ctx['ts_nodash']}.json")

        for name, f in report["features"].items():
            print(f"{name:20s} KS={f['ks_stat']:.3f} PSI={f['psi']:.3f} mean {f['ref_mean']} -> {f['cur_mean']} {'DRIFT' if f['drifted'] else ''}")
        print(f"drift_share={report['drift_share']:.2f} (threshold {params['drift_share_threshold']}), champion on production: {report['champion_on_production']}")

        init_mlflow(EXPERIMENT_DRIFT)
        with mlflow.start_run(run_name=f"drift-{ctx['ts_nodash']}"):
            metrics = {"drift_share": report["drift_share"], "n_drifted": report["n_drifted"]}
            metrics.update({f"ks_{c}": v["ks_stat"] for c, v in report["features"].items()})
            if report["champion_on_production"]:
                metrics["champion_rmse_prod"] = report["champion_on_production"]["rmse"]
            mlflow.log_metrics(metrics)
            mlflow.log_artifact(str(path))

        return {
            "status": "ok",
            "drift_detected": bool(report["drift_detected"]),
            "drift_share": report["drift_share"],
            "drifted_features": report["drifted_features"],
            "champion_on_production": report["champion_on_production"],
        }

    @task.branch
    def decide(result: dict) -> str:
        print(result)
        return "trigger_retraining" if result["drift_detected"] else "no_action"

    trigger_retraining = TriggerDagRunOperator(
        task_id="trigger_retraining",
        trigger_dag_id="xgb_training_pipeline",
        conf={"data_path": str(PRODUCTION_PATH), "triggered_by": "xgb_drift_monitor"},
        wait_for_completion=False,
    )
    no_action = EmptyOperator(task_id="no_action")

    decide(check_drift()) >> [trigger_retraining, no_action]


xgb_drift_monitor()
