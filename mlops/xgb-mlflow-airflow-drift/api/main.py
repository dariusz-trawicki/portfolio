"""Serving API for the model behind the `champion` alias.

Every REFRESH_SECONDS it checks whether the alias points to a new version and hot-swaps the model,
so a promotion in the registry reaches production without redeploying or restarting the API.
"""
import os
import threading
import time

import mlflow
import mlflow.pyfunc
import pandas as pd
from fastapi import FastAPI, HTTPException
from mlflow import MlflowClient
from pydantic import BaseModel, Field

MODEL_NAME = os.getenv("MODEL_NAME", "housing-xgb")
MODEL_ALIAS = os.getenv("MODEL_ALIAS", "champion")
REFRESH_SECONDS = int(os.getenv("REFRESH_SECONDS", "10"))
# NOTE: duplicated from src/mlops_demo/data.py on purpose (the API image does not ship `src`).
# In a real project, read the feature list from the model signature or share a package.
FEATURES = ["area_m2", "rooms", "age_years", "distance_center_km", "floor", "has_balcony"]

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))


class House(BaseModel):
    area_m2: float = Field(..., gt=0, examples=[55])
    rooms: float = Field(..., ge=1, examples=[2])
    age_years: float = Field(..., ge=0, examples=[15])
    distance_center_km: float = Field(..., ge=0, examples=[4.5])
    floor: float = Field(..., ge=0, examples=[3])
    has_balcony: float = Field(..., ge=0, le=1, examples=[1])


class PredictRequest(BaseModel):
    instances: list[House]


class ModelHolder:
    """Keeps the loaded model and reloads it when the `champion` alias moves to another version."""

    def __init__(self):
        self.model = None
        self.version = None
        self.checked_at = 0.0
        self.lock = threading.Lock()

    def get(self):
        # Lazy check on request: no background thread needed.
        if self.model is None or time.time() - self.checked_at > REFRESH_SECONDS:
            with self.lock:
                self.checked_at = time.time()
                try:
                    version = str(MlflowClient().get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS).version)
                    if version != self.version:
                        # Load a concrete version (not the alias) to avoid a race if the alias moves meanwhile.
                        self.model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{version}")
                        self.version = version
                        print(f"Loaded {MODEL_NAME} v{self.version}")
                except Exception as exc:  # no alias yet / MLflow unreachable -> keep serving the old model
                    print(f"Could not refresh model: {exc}")
        if self.model is None:
            raise HTTPException(503, f"No model '{MODEL_NAME}@{MODEL_ALIAS}' yet. Run the xgb_training_pipeline DAG in Airflow.")
        return self.model, self.version


holder = ModelHolder()
app = FastAPI(title="Housing price API (XGBoost + MLflow)")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/model")
def model_info():
    _, version = holder.get()
    return {"name": MODEL_NAME, "alias": MODEL_ALIAS, "version": version}


@app.post("/predict")
def predict(req: PredictRequest):
    model, version = holder.get()
    df = pd.DataFrame([i.model_dump() for i in req.instances])[FEATURES].astype("float64")
    preds = model.predict(df)
    return {"model_version": version, "predictions_kpln": [round(float(p), 1) for p in preds]}
