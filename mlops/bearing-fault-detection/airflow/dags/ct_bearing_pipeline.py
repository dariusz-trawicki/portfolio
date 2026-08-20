"""
Continuous Training (CT) DAG for bearing fault detection.

Flow:
  build_dataset          -> CSV snapshot from the feature store (Postgres), logged as an MLflow artifact
  check_drift            -> KS (+ PSI as a supplementary signal) on a reference vs. current window, logged to MLflow
  decide_retrain (branch) -> retrain if drift was detected OR if no champion exists yet (bootstrap)
  train_and_register     -> train the IF + RF models, log to MLflow, register as "challenger"
  skip_retrain           -> no-op when there is no drift
  validate_and_promote   -> compare challenger vs. champion, possibly flip the "champion" alias
  notify_serving         -> best-effort HTTP call to serving-api so it reloads the model immediately

Schedule: every 15 minutes (for demo purposes - in production this would
typically be @daily or event-driven). Adjust `schedule_interval` as needed.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta

import mlflow
from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.operators.empty import EmptyOperator

from common.config import DRIFT_EXPERIMENT, MLFLOW_TRACKING_URI
from common.dataset import build_dataset_snapshot
from common.drift import detect_drift
from common.promote import validate_and_promote
from common.train import train_and_register
from common.dataset import load_feature_dataset

log = logging.getLogger(__name__)

default_args = {
    "owner": "mlops-bearings",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}


def _task_build_dataset(**context) -> str:
    path = build_dataset_snapshot(since_hours=None)
    context["ti"].xcom_push(key="dataset_path", value=path)
    return path


def _task_check_drift(**context) -> dict:
    df = load_feature_dataset(since_hours=None, require_labels=True)
    result = detect_drift(df)

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(DRIFT_EXPERIMENT)
    with mlflow.start_run(run_name="drift_check"):
        mlflow.log_metric("drift_detected", int(result["drift_detected"]))
        mlflow.log_metric("n_features_drifted_ks", result.get("n_features_drifted_ks", 0))
        for feature, stats_ in result.get("per_feature", {}).items():
            mlflow.log_metric(f"ks_pvalue__{feature}", stats_["ks_pvalue"])
            mlflow.log_metric(f"psi__{feature}", stats_["psi"])

    context["ti"].xcom_push(key="drift_result", value=result)
    return result


def _champions_exist() -> bool:
    """Checks whether both models (anomaly + classifier) already have a
    champion registered in MLflow. Used to force the first training run
    (bootstrap) regardless of the drift detection outcome."""
    import mlflow
    from mlflow.exceptions import MlflowException
    from common.config import ANOMALY_MODEL_NAME, CHAMPION_ALIAS, CLASSIFIER_MODEL_NAME

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = mlflow.tracking.MlflowClient()
    try:
        client.get_model_version_by_alias(ANOMALY_MODEL_NAME, CHAMPION_ALIAS)
        client.get_model_version_by_alias(CLASSIFIER_MODEL_NAME, CHAMPION_ALIAS)
        return True
    except MlflowException:
        return False


def _decide_retrain(**context) -> str:
    drift_result = context["ti"].xcom_pull(key="drift_result", task_ids="check_drift")
    run_number = context["dag_run"].run_id  # used only for logging context
    log.info("Drift result: %s (run=%s)", drift_result, run_number)

    if not _champions_exist():
        log.info("No champion registered in MLflow yet (first run) -> forcing training")
        return "train_and_register"

    if drift_result.get("drift_detected"):
        log.info("Drift detected -> triggering retraining")
        return "train_and_register"

    log.info("No significant drift -> skipping retraining this cycle")
    return "skip_retrain"


def _task_train(**context) -> dict:
    dataset_path = context["ti"].xcom_pull(key="dataset_path", task_ids="build_dataset")
    return train_and_register(dataset_path)


def _task_validate_and_promote(**context) -> dict:
    return validate_and_promote()


def _task_notify_serving(**context) -> None:
    import os
    import requests

    serving_url = os.environ.get("SERVING_API_URL", "http://serving-api:8000")
    try:
        resp = requests.post(f"{serving_url}/reload-model", timeout=5)
        log.info("serving-api reloaded: %s", resp.status_code)
    except Exception as exc:  # noqa: BLE001
        # Best-effort: serving-api will eventually pick up the new model on
        # its own; this failure should not block the DAG.
        log.warning("Could not notify serving-api (%s) - this does not block the DAG", exc)


with DAG(
    dag_id="ct_bearing_pipeline",
    description="Continuous Training for bearing fault detection (build_dataset -> drift -> retrain -> promote)",
    default_args=default_args,
    schedule_interval=timedelta(minutes=15),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["mlops", "bearings", "continuous-training"],
) as dag:

    build_dataset = PythonOperator(
        task_id="build_dataset",
        python_callable=_task_build_dataset,
    )

    check_drift = PythonOperator(
        task_id="check_drift",
        python_callable=_task_check_drift,
    )

    decide_retrain = BranchPythonOperator(
        task_id="decide_retrain",
        python_callable=_decide_retrain,
    )

    train_and_register_task = PythonOperator(
        task_id="train_and_register",
        python_callable=_task_train,
    )

    skip_retrain = EmptyOperator(task_id="skip_retrain")

    validate_and_promote_task = PythonOperator(
        task_id="validate_and_promote",
        python_callable=_task_validate_and_promote,
        trigger_rule="none_failed_min_one_success",
    )

    notify_serving = PythonOperator(
        task_id="notify_serving",
        python_callable=_task_notify_serving,
        trigger_rule="all_done",
    )

    build_dataset >> check_drift >> decide_retrain
    decide_retrain >> train_and_register_task >> validate_and_promote_task
    decide_retrain >> skip_retrain
    [validate_and_promote_task, skip_retrain] >> notify_serving
