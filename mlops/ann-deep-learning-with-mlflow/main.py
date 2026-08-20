import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from hyperopt import STATUS_OK, Trials, fmin, hp, tpe
import mlflow
from mlflow.models import infer_signature
import tensorflow as tf
from tensorflow import keras

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["OMP_NUM_THREADS"] = "1"

# Optionally suppress warnings and logs from TensorFlow and Alembic:
# import warnings
# warnings.filterwarnings("ignore")
# import logging
# logging.getLogger("alembic").setLevel(logging.WARNING)


# ── 1. DATA ──
def load_data():
    data = pd.read_csv(
        "https://raw.githubusercontent.com/mlflow/mlflow/master/tests/datasets/winequality-white.csv",
        sep=";",
    )
    return data


def prepare_splits(data):
    # Split into train (75%) and test (25%)
    train, test = train_test_split(data, test_size=0.25, random_state=42)

    train_x = train.drop(["quality"], axis=1).values
    train_y = train[["quality"]].values.ravel()
    test_x  = test.drop(["quality"], axis=1).values
    test_y  = test[["quality"]].values.ravel()

    # Further split train into train (80%) and validation (20%)
    train_x, valid_x, train_y, valid_y = train_test_split(
        train_x, train_y, test_size=0.20, random_state=42
    )

    # Infer the model signature from training data
    signature = infer_signature(train_x, train_y)

    return train_x, valid_x, test_x, train_y, valid_y, test_y, signature


# ── 2. MODEL ───

def train_model(params, epochs, train_x, train_y, valid_x, valid_y, test_x, test_y, signature):
    # Compute mean and variance per feature for input normalization
    mean = np.mean(train_x, axis=0)
    var  = np.var(train_x, axis=0)

    # Build a simple ANN: Normalize → Dense(64, ReLU) → Dense(1)
    model = keras.Sequential([
        keras.Input([train_x.shape[1]]),
        keras.layers.Normalization(mean=mean, variance=var),
        keras.layers.Dense(64, activation="relu"),
        keras.layers.Dense(1),
    ])

    # Compile with SGD optimizer and MSE loss
    model.compile(
        optimizer=keras.optimizers.SGD(
            learning_rate=params["lr"],
            momentum=params["momentum"],
        ),
        loss="mean_squared_error",
        metrics=[keras.metrics.RootMeanSquaredError()],
    )

    # Train and log in a nested MLflow run
    with mlflow.start_run(nested=True):
        model.fit(
            train_x, train_y,
            validation_data=(valid_x, valid_y),
            epochs=epochs,
            batch_size=64,
            verbose=2,
        )

        # Evaluate on validation set
        eval_result = model.evaluate(valid_x, valid_y, batch_size=64, verbose=0)
        eval_rmse   = eval_result[1]

        # Log hyperparameters and evaluation metric
        mlflow.log_params(params)
        mlflow.log_metric("eval_rmse", eval_rmse)

    return {"loss": eval_rmse, "status": STATUS_OK, "model": model}


# ── 3. HYPEROPT OBJECTIVE ──

def build_objective(train_x, train_y, valid_x, valid_y, test_x, test_y, signature):
    """Returns the objective function for Hyperopt to minimize."""
    def objective(params):
        print(f"Start trial | params={params}")
        result = train_model(
            params,
            epochs=3,
            train_x=train_x,
            train_y=train_y,
            valid_x=valid_x,
            valid_y=valid_y,
            test_x=test_x,
            test_y=test_y,
            signature=signature,
        )
        print("End trial")
        return result
    return objective


# ── 4. MAIN ──
def main():
    # Load and split data
    data = load_data()
    train_x, valid_x, test_x, train_y, valid_y, test_y, signature = prepare_splits(data)

    # Define hyperparameter search space
    space = {
        "lr":       hp.loguniform("lr",       np.log(1e-5), np.log(1e-1)),
        "momentum": hp.uniform("momentum", 0.0, 1.0),
    }

    objective = build_objective(train_x, train_y, valid_x, valid_y, test_x, test_y, signature)

    # Run hyperparameter search with MLflow tracking
    mlflow.set_experiment("wine-quality")

    with mlflow.start_run():
        trials = Trials()
        best = fmin(
            fn=objective,
            space=space,
            algo=tpe.suggest,
            max_evals=4,
            trials=trials,
        )

        # Select the best run by lowest loss
        best_run = sorted(trials.results, key=lambda x: x["loss"])[0]

        # Log best parameters and metric to parent run
        mlflow.log_params(best)
        mlflow.log_metric("eval_rmse", best_run["loss"])

        # Log the best model as an artifact
        mlflow.tensorflow.log_model(best_run["model"], name="model", signature=signature)

        print(f"\nBest parameters : {best}")
        print(f"Best eval RMSE  : {best_run['loss']:.4f}")

        # Register model in MLflow Model Registry
        run_id = mlflow.active_run().info.run_id
        model_uri = f"runs:/{run_id}/model"
        mlflow.register_model(model_uri, "wine-quality")
        print(f"Model registered | URI: {model_uri}")


if __name__ == "__main__":
    main()
