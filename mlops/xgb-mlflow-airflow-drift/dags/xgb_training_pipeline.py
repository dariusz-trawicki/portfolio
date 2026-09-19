"""Training pipeline: data -> random search -> register -> champion/challenger -> update reference."""
from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.operators.python import get_current_context

from mlops_demo.config import TRAIN_PATH  # lightweight import (no xgboost/mlflow at parse time)


@dag(
    dag_id="xgb_training_pipeline",
    description="Train XGBoost, register in MLflow, promote the champion if better",
    schedule=None,  # triggered manually or by xgb_drift_monitor
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    params={
        "data_path": Param(str(TRAIN_PATH), type="string", description="CSV file with training data"),
        "n_trials": Param(8, type="integer", minimum=1, maximum=50, description="Random search trials"),
        "min_improvement": Param(0.02, type="number", description="Min. relative RMSE improvement needed to replace the champion"),
    },
    tags=["mlops", "xgboost"],
)
def xgb_training_pipeline():
    @task
    def prepare_data() -> str:
        from mlops_demo.data import ensure_baseline

        ensure_baseline()  # first run: generates the baseline train.csv
        return get_current_context()["params"]["data_path"]

    @task
    def train(data_path: str) -> dict:
        from mlops_demo.training import train_candidates

        n_trials = get_current_context()["params"]["n_trials"]
        return train_candidates(data_path, n_trials=n_trials)

    @task
    def register(train_result: dict, data_path: str) -> str:
        from mlops_demo.training import register_model

        return register_model(train_result["run_id"], data_path)

    @task
    def evaluate_and_promote(version: str, data_path: str) -> dict:
        from mlops_demo.training import evaluate_and_promote as promote

        min_improvement = get_current_context()["params"]["min_improvement"]
        result = promote(version, data_path, min_improvement=min_improvement)
        print(f"Champion/challenger result: {result}")
        return result

    @task
    def update_reference(promo: dict, data_path: str) -> None:
        """If the new model became champion, its training data becomes the new drift reference."""
        import shutil

        from mlops_demo.config import REFERENCE_PATH

        if promo["promoted"]:
            REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(data_path, REFERENCE_PATH)
            print(f"reference.csv updated from {data_path}")
        else:
            print("Model was not promoted - reference left unchanged.")

    path = prepare_data()
    result = train(path)
    version = register(result, path)
    promo = evaluate_and_promote(version, path)
    update_reference(promo, path)


xgb_training_pipeline()
