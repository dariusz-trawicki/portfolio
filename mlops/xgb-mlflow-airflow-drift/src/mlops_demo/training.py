"""Training (random search), Model Registry registration and champion/challenger promotion."""
from __future__ import annotations

from pathlib import Path

import mlflow
import mlflow.pyfunc
import mlflow.xgboost
import numpy as np
import pandas as pd
import xgboost as xgb
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from .config import CHAMPION_ALIAS, EXPERIMENT_TRAINING, MLFLOW_TRACKING_URI, MODEL_NAME
from .data import FEATURES, TARGET

RANDOM_STATE = 42


def init_mlflow(experiment: str | None = None) -> None:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    if experiment:
        mlflow.set_experiment(experiment)


def split_data(df: pd.DataFrame):
    """60/20/20 split. Deterministic, so the same file always yields the same test set."""
    train_val, test = train_test_split(df, test_size=0.2, random_state=RANDOM_STATE)
    train, val = train_test_split(train_val, test_size=0.25, random_state=RANDOM_STATE)
    return train, val, test


def regression_metrics(y_true, y_pred) -> dict:
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def _sample_params(rng: np.random.Generator) -> dict:
    return {
        "max_depth": int(rng.integers(3, 9)),
        "learning_rate": float(10 ** rng.uniform(-1.5, -0.7)),
        "subsample": float(rng.uniform(0.6, 1.0)),
        "colsample_bytree": float(rng.uniform(0.6, 1.0)),
        "min_child_weight": int(rng.integers(1, 10)),
        "reg_lambda": float(10 ** rng.uniform(-1, 1)),
    }


def train_candidates(data_path: str, n_trials: int = 8, seed: int = RANDOM_STATE) -> dict:
    """Random search. Every trial is a nested MLflow run; the best model is logged on the parent run."""
    init_mlflow(EXPERIMENT_TRAINING)
    df = pd.read_csv(data_path)
    train, val, test = split_data(df)
    rng = np.random.default_rng(seed)

    best = None
    with mlflow.start_run(run_name=f"search-{Path(data_path).stem}") as parent:
        mlflow.log_params({"data_path": str(data_path), "n_rows": len(df), "n_trials": n_trials})

        for i in range(n_trials):
            params = _sample_params(rng)
            with mlflow.start_run(run_name=f"trial-{i}", nested=True):
                model = xgb.XGBRegressor(
                    n_estimators=1000,
                    early_stopping_rounds=30,
                    tree_method="hist",
                    n_jobs=2,
                    random_state=seed,
                    **params,
                )
                model.fit(train[FEATURES], train[TARGET], eval_set=[(val[FEATURES], val[TARGET])], verbose=False)
                m = regression_metrics(val[TARGET], model.predict(val[FEATURES]))
                mlflow.log_params({**params, "best_iteration": int(model.best_iteration)})
                mlflow.log_metrics({f"val_{k}": v for k, v in m.items()})
            if best is None or m["rmse"] < best["val_rmse"]:
                best = {"model": model, "params": params, "val_rmse": m["rmse"]}

        test_m = regression_metrics(test[TARGET], best["model"].predict(test[FEATURES]))
        mlflow.log_params({f"best_{k}": v for k, v in best["params"].items()})
        mlflow.log_metrics({"val_rmse": best["val_rmse"], **{f"test_{k}": v for k, v in test_m.items()}})
        signature = infer_signature(train[FEATURES], best["model"].predict(train[FEATURES]))
        mlflow.xgboost.log_model(
            best["model"],
            artifact_path="model",
            signature=signature,
            input_example=train[FEATURES].head(3),
        )
        return {"run_id": parent.info.run_id, "val_rmse": best["val_rmse"], "test_rmse": test_m["rmse"]}


def register_model(run_id: str, data_path: str) -> str:
    """Register the model logged in `run_id` as a new version in the Model Registry."""
    init_mlflow()
    mv = mlflow.register_model(f"runs:/{run_id}/model", MODEL_NAME)
    MlflowClient().set_model_version_tag(MODEL_NAME, mv.version, "data_path", str(data_path))
    return str(mv.version)


def get_champion():
    try:
        return MlflowClient().get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS)
    except MlflowException:
        return None


def champion_metrics_on(df: pd.DataFrame) -> dict | None:
    """Metrics of the current champion on `df` (None if there is no champion yet)."""
    init_mlflow()
    champ = get_champion()
    if champ is None:
        return None
    model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{champ.version}")
    metrics = regression_metrics(df[TARGET], model.predict(df[FEATURES]))
    return {"version": str(champ.version), **metrics}


def evaluate_and_promote(version: str, data_path: str, min_improvement: float = 0.02) -> dict:
    """Champion/challenger gate: promote only if RMSE improves by at least `min_improvement`."""
    init_mlflow()
    client = MlflowClient()
    _, _, test = split_data(pd.read_csv(data_path))

    challenger = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{version}")
    ch = regression_metrics(test[TARGET], challenger.predict(test[FEATURES]))
    champ = champion_metrics_on(test)

    promoted = champ is None or ch["rmse"] < champ["rmse"] * (1 - min_improvement)
    client.set_model_version_tag(MODEL_NAME, version, "test_rmse", f"{ch['rmse']:.3f}")
    client.set_model_version_tag(MODEL_NAME, version, "promoted", str(promoted).lower())
    if promoted:
        client.set_registered_model_alias(MODEL_NAME, CHAMPION_ALIAS, version)

    return {
        "version": str(version),
        "promoted": bool(promoted),
        "challenger_rmse": ch["rmse"],
        "champion_version": champ["version"] if champ else None,
        "champion_rmse": champ["rmse"] if champ else None,
    }
