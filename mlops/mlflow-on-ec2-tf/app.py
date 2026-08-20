import sys
import logging
from urllib.parse import urlparse

import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNet
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

import mlflow
import mlflow.sklearn
from mlflow.models.signature import infer_signature

# --- Configuration ---
MLFLOW_SERVER_URI = "http://ec2-3-121-219-175.eu-central-1.compute.amazonaws.com:5000/"
DATA_URL = "https://raw.githubusercontent.com/mlflow/mlflow/master/tests/datasets/winequality-red.csv"
EXPERIMENT_NAME = "Wine-Quality"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def eval_metrics(actual, pred):
    rmse = float(np.sqrt(mean_squared_error(actual, pred)))
    mae = float(mean_absolute_error(actual, pred))
    r2 = float(r2_score(actual, pred))
    return rmse, mae, r2


if __name__ == "__main__":
    # Set remote tracking (and registry — for clarity in 3.x it's the same URI)
    mlflow.set_tracking_uri(MLFLOW_SERVER_URI)
    mlflow.set_registry_uri(MLFLOW_SERVER_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    # Data
    try:
        data = pd.read_csv(DATA_URL, sep=";")
    except Exception:
        logger.exception("Unable to download the data")
        sys.exit(1)

    # Reproducible split
    train, test = train_test_split(data, test_size=0.25, random_state=42)

    train_x = train.drop(columns=["quality"])
    test_x = test.drop(columns=["quality"])
    # y as Series (1D) to avoid sklearn warnings
    train_y = train["quality"]
    test_y = test["quality"]

    # Parameters from CLI (default 0.5/0.5)
    alpha = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    l1_ratio = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5

    tracking_scheme = urlparse(mlflow.get_tracking_uri()).scheme

    with mlflow.start_run(run_name=f"elasticnet_a{alpha}_l{l1_ratio}"):
        # Model
        lr = ElasticNet(alpha=alpha, l1_ratio=l1_ratio, random_state=42)
        lr.fit(train_x, train_y)

        preds = lr.predict(test_x)
        rmse, mae, r2 = eval_metrics(test_y, preds)

        print(f"Elasticnet model (alpha={alpha:.6f}, l1_ratio={l1_ratio:.6f}):")
        print(f"  RMSE: {rmse}")
        print(f"  MAE:  {mae}")
        print(f"  R2:   {r2}")

        # MLflow logs
        mlflow.log_params({"alpha": alpha, "l1_ratio": l1_ratio})
        mlflow.log_metrics({"rmse": rmse, "mae": mae, "r2": r2})

        # Signature + input_example to avoid warnings
        signature = infer_signature(train_x, lr.predict(train_x))
        input_example = train_x.iloc[:5]

        if tracking_scheme != "file":
            # Remote tracking: log + registration in Model Registry
            mlflow.sklearn.log_model(
                sk_model=lr,
                name="model",  # instead of artifact_path
                signature=signature,
                input_example=input_example,
                registered_model_name="ElasticnetWineModel",
            )
        else:
            # Local tracking: only log model
            mlflow.sklearn.log_model(
                sk_model=lr,
                name="model",
                signature=signature,
                input_example=input_example,
            )

        # Useful UI links
        run = mlflow.active_run()
        base = MLFLOW_SERVER_URI.rstrip("/")
        print(f"View run at: {base}/#/experiments/{run.info.experiment_id}/runs/{run.info.run_id}")
        print(f"View experiment at: {base}/#/experiments/{run.info.experiment_id}")
