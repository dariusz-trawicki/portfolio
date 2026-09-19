"""Shared configuration (paths, MLflow names).

Kept dependency-free on purpose: it is imported at the top of DAG files,
which the Airflow scheduler re-parses every few seconds.
"""
import os
from pathlib import Path

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")

MODEL_NAME = "housing-xgb"
CHAMPION_ALIAS = "champion"
EXPERIMENT_TRAINING = "xgb-housing-training"
EXPERIMENT_DRIFT = "xgb-housing-drift"

DATA_DIR = Path(os.getenv("DEMO_DATA_DIR", "/opt/airflow/data"))
TRAIN_PATH = DATA_DIR / "train.csv"                       # baseline training set
REFERENCE_PATH = DATA_DIR / "reference.csv"               # data the current champion was trained on
PRODUCTION_PATH = DATA_DIR / "production" / "latest.csv"  # simulated production traffic (with labels)
REPORTS_DIR = DATA_DIR / "reports"                        # JSON drift reports
