import os

FEATURE_STORE_DSN = os.environ.get(
    "FEATURE_STORE_DSN",
    "dbname=feature_store user=postgres password=postgres host=postgres port=5432",
)

FEATURE_STORE_SQLALCHEMY_URI = os.environ.get(
    "FEATURE_STORE_SQLALCHEMY_URI",
    "postgresql+psycopg2://postgres:postgres@postgres:5432/feature_store",
)

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")

FEATURE_COLUMNS = [
    "t_mean", "t_std", "t_rms", "t_kurtosis", "t_skewness",
    "t_peak_to_peak", "t_crest_factor", "t_shape_factor",
    "f_dominant_freq", "f_spectral_centroid", "f_spectral_energy", "f_spectral_entropy",
    "env_amp_bpfo", "env_amp_bpfi", "env_amp_bsf", "env_amp_ftf",
]

DATASET_SNAPSHOT_PATH = "/opt/airflow/data/features_dataset.csv"

ANOMALY_MODEL_NAME = "bearing_anomaly_detector"
CLASSIFIER_MODEL_NAME = "bearing_fault_classifier"

# Champion alias in the MLflow Model Registry - serving-api always loads
# `models:/<name>@champion`, so "promoting" a model is just flipping this alias.
CHAMPION_ALIAS = "champion"
CHALLENGER_ALIAS = "challenger"

DRIFT_EXPERIMENT = "drift-monitoring"
TRAINING_EXPERIMENT = "bearing-fault-training"

# Minimum metric improvement required for a challenger to replace the
# champion (avoids unnecessary promotions on statistical noise)
PROMOTION_MIN_IMPROVEMENT = 0.0
