# Wine Quality – ANN + MLflow Demo

Hyperparameter tuning of a Keras neural network on the UCI Wine Quality dataset, with experiment tracking via MLflow.

## Stack

- **TensorFlow / Keras** – ANN model
- **Hyperopt** – hyperparameter search (TPE algorithm)
- **MLflow** – experiment tracking, model registry

## Setup

```bash
pyenv local 3.10.19
python -m venv venv
source venv/bin/activate

# Install dependencies (order matters on Apple Silicon)
pip install tensorflow-macos==2.16.2 tensorflow-metal
pip install "protobuf>=5.0,<7.0" --force-reinstall
pip install mlflow numpy pandas scikit-learn hyperopt
```

## Run

```bash
# MLflow UI – open http://127.0.0.1:5000
mlflow ui

# Terminal II:
source venv/bin/activate
python main.py
```

## What it does

1. Loads the white wine quality CSV from GitHub
2. Splits data → train / validation / test
3. Runs Hyperopt over `lr` and `momentum` (4 trials)
4. Logs each trial as a nested MLflow run
5. Saves the best model to MLflow Model Registry as `wine-quality`

## Notes

- `AttributeError: 'MessageFactory'` warnings can be ignored – caused by a known `protobuf` version conflict between `tensorflow-macos 2.16` and `mlflow 3.x`
