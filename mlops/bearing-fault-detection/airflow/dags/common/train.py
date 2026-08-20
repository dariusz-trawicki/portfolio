"""
Uses real MLflow: experiments/runs/parameters/
metrics plus the Model Registry (registering a new model version under the
`challenger` alias).

Cascade: the Isolation Forest (anomaly detector, trained EXCLUSIVELY on the
`normal` class) is the entry gate; the Random Forest (fault-type
classifier) is trained on every labeled class, so serving can run it
conditionally, only when the Isolation Forest flags a sample as an anomaly
- see `serving/app.py` for the cascade implementation at inference time.
"""
from __future__ import annotations
import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.model_selection import train_test_split

from .config import (
    ANOMALY_MODEL_NAME, CHALLENGER_ALIAS, CLASSIFIER_MODEL_NAME,
    FEATURE_COLUMNS, MLFLOW_TRACKING_URI, TRAINING_EXPERIMENT,
)


def train_and_register(dataset_path: str) -> dict:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(TRAINING_EXPERIMENT)

    df = pd.read_csv(dataset_path)
    X = df[FEATURE_COLUMNS]
    y = df["fault_type"]

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.25, stratify=y, random_state=42
    )

    result = {}
    with mlflow.start_run(run_name="train_challenger") as run:
        mlflow.log_param("n_samples_train", len(X_train))
        mlflow.log_param("n_samples_val", len(X_val))
        mlflow.log_param("features", FEATURE_COLUMNS)

        # --- 1. Isolation Forest: 'normal' samples only ---
        X_train_normal = X_train[y_train == "normal"]
        iso_forest = IsolationForest(n_estimators=200, contamination=0.05, random_state=42)
        iso_forest.fit(X_train_normal)

        y_val_binary = (y_val != "normal").astype(int)
        iso_pred = (iso_forest.predict(X_val) == -1).astype(int)
        anomaly_f1 = f1_score(y_val_binary, iso_pred)
        mlflow.log_metric("anomaly_f1", anomaly_f1)

        anomaly_model_info = mlflow.sklearn.log_model(
            iso_forest, artifact_path="anomaly_model",
            registered_model_name=ANOMALY_MODEL_NAME,
        )

        # --- 2. Random Forest: fault-type classification ---
        fault_mask_train = y_train != "normal"
        rf = RandomForestClassifier(n_estimators=300, random_state=42, class_weight="balanced")
        rf.fit(X_train[fault_mask_train], y_train[fault_mask_train])

        fault_mask_val = y_val != "normal"
        if fault_mask_val.sum() > 0:
            rf_preds = rf.predict(X_val[fault_mask_val])
            classifier_balanced_acc = balanced_accuracy_score(y_val[fault_mask_val], rf_preds)
        else:
            classifier_balanced_acc = float("nan")
        mlflow.log_metric("classifier_balanced_accuracy", classifier_balanced_acc)

        classifier_model_info = mlflow.sklearn.log_model(
            rf, artifact_path="classifier_model",
            registered_model_name=CLASSIFIER_MODEL_NAME,
        )

        mlflow.log_artifact(dataset_path, artifact_path="training_data_snapshot")

        result = {
            "run_id": run.info.run_id,
            "anomaly_f1": anomaly_f1,
            "classifier_balanced_accuracy": classifier_balanced_acc,
            "anomaly_model_version": anomaly_model_info.registered_model_version,
            "classifier_model_version": classifier_model_info.registered_model_version,
        }

    # Tag both new versions as "challenger" - validation/promotion will
    # decide whether they should replace the champion.
    client = mlflow.tracking.MlflowClient()
    client.set_registered_model_alias(
        ANOMALY_MODEL_NAME, CHALLENGER_ALIAS, result["anomaly_model_version"]
    )
    client.set_registered_model_alias(
        CLASSIFIER_MODEL_NAME, CHALLENGER_ALIAS, result["classifier_model_version"]
    )
    return result
