"""
Serving API for the bearing fault detection system.

Fixes one of the "known simplifications" of the original demo: the
Isolation Forest and the Random Forest used to run independently. Here,
inference is a CASCADE:
  1. The Isolation Forest decides whether a sample is an anomaly.
  2. Only if it IS, the Random Forest is run to determine the fault type
     (the classifier is never invoked at all for 'normal' samples).

Models are loaded from the MLflow Model Registry under the `champion`
alias - promoting a model (Airflow -> promote.py) is just flipping that
alias, so calling `/reload-model` is enough for serving to start using the
new version without a container restart.

In addition, a background Kafka consumer (`vibration-features`) runs the
same cascade in real time on the stream produced by feature_consumer, and
publishes the results to the `predictions` topic as well as writing them to
Postgres.
"""
from __future__ import annotations
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

import mlflow
import numpy as np
import pandas as pd
import psycopg2
from fastapi import FastAPI, HTTPException
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [serving-api] %(message)s")
log = logging.getLogger(__name__)

MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
ANOMALY_MODEL_NAME = os.environ.get("ANOMALY_MODEL_NAME", "bearing_anomaly_detector")
CLASSIFIER_MODEL_NAME = os.environ.get("CLASSIFIER_MODEL_NAME", "bearing_fault_classifier")
CHAMPION_ALIAS = "champion"

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
FEATURES_TOPIC = os.environ.get("FEATURES_TOPIC", "vibration-features")
PREDICTIONS_TOPIC = os.environ.get("PREDICTIONS_TOPIC", "predictions")
PG_DSN = os.environ.get(
    "FEATURE_STORE_DSN",
    "dbname=feature_store user=postgres password=postgres host=postgres port=5432",
)

FEATURE_COLUMNS = [
    "t_mean", "t_std", "t_rms", "t_kurtosis", "t_skewness",
    "t_peak_to_peak", "t_crest_factor", "t_shape_factor",
    "f_dominant_freq", "f_spectral_centroid", "f_spectral_energy", "f_spectral_entropy",
    "env_amp_bpfo", "env_amp_bpfi", "env_amp_bsf", "env_amp_ftf",
]

_state = {"anomaly_model": None, "classifier_model": None, "loaded_at": None}
_state_lock = threading.Lock()


def load_champion_models() -> None:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    anomaly_model = mlflow.sklearn.load_model(f"models:/{ANOMALY_MODEL_NAME}@{CHAMPION_ALIAS}")
    classifier_model = mlflow.sklearn.load_model(f"models:/{CLASSIFIER_MODEL_NAME}@{CHAMPION_ALIAS}")
    with _state_lock:
        _state["anomaly_model"] = anomaly_model
        _state["classifier_model"] = classifier_model
        _state["loaded_at"] = time.time()
    log.info("Loaded champion models: %s, %s", ANOMALY_MODEL_NAME, CLASSIFIER_MODEL_NAME)


def cascade_predict(features: dict) -> dict:
    """Cascade: IsolationForest -> (conditionally) RandomForest."""
    with _state_lock:
        anomaly_model = _state["anomaly_model"]
        classifier_model = _state["classifier_model"]

    if anomaly_model is None or classifier_model is None:
        raise HTTPException(status_code=503, detail="Models not loaded yet (no champion exists in MLflow)")

    X = pd.DataFrame([features])[FEATURE_COLUMNS]
    is_anomaly = bool(anomaly_model.predict(X)[0] == -1)

    if not is_anomaly:
        return {"is_anomaly": False, "predicted_fault_type": "normal", "confidence": None}

    proba = classifier_model.predict_proba(X)[0]
    classes = classifier_model.classes_
    best_idx = int(np.argmax(proba))
    return {
        "is_anomaly": True,
        "predicted_fault_type": str(classes[best_idx]),
        "confidence": float(proba[best_idx]),
    }


def _kafka_inference_loop() -> None:
    """Background thread: consumes features from Kafka, runs the cascade,
    publishes the result and writes it to Postgres. Best-effort - errors
    don't kill serving-api."""
    consumer = None
    for attempt in range(30):
        try:
            consumer = KafkaConsumer(
                FEATURES_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="latest",
                group_id="serving-inference-group",
            )
            break
        except NoBrokersAvailable:
            time.sleep(2)
    if consumer is None:
        log.error("Could not connect to Kafka in the inference thread - streaming inference disabled")
        return

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    conn = psycopg2.connect(PG_DSN)

    log.info("Streaming inference thread started (topic=%s)", FEATURES_TOPIC)
    for message in consumer:
        payload = message.value
        try:
            with _state_lock:
                ready = _state["anomaly_model"] is not None
            if not ready:
                continue
            result = cascade_predict(payload["features"])
            result["sensor_id"] = payload["sensor_id"]
            result["timestamp"] = payload["timestamp"]
            producer.send(PREDICTIONS_TOPIC, value=result)

            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO predictions (sensor_id, is_anomaly, predicted_fault_type, confidence, model_version)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (result["sensor_id"], result["is_anomaly"], result["predicted_fault_type"],
                     result["confidence"], "champion"),
                )
            conn.commit()
        except Exception:  # noqa: BLE001
            log.exception("Error during streaming inference for a message, continuing")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        load_champion_models()
    except Exception as exc:  # noqa: BLE001
        log.warning("Champion models not available at startup (%s) - /predict will return 503 until a model is trained", exc)

    thread = threading.Thread(target=_kafka_inference_loop, daemon=True)
    thread.start()
    yield


app = FastAPI(title="Bearing Fault Detection Serving API", lifespan=lifespan)


class FeatureVector(BaseModel):
    t_mean: float
    t_std: float
    t_rms: float
    t_kurtosis: float
    t_skewness: float
    t_peak_to_peak: float
    t_crest_factor: float
    t_shape_factor: float
    f_dominant_freq: float
    f_spectral_centroid: float
    f_spectral_energy: float
    f_spectral_entropy: float
    env_amp_bpfo: float
    env_amp_bpfi: float
    env_amp_bsf: float
    env_amp_ftf: float


@app.get("/health")
def health():
    with _state_lock:
        ready = _state["anomaly_model"] is not None
        loaded_at = _state["loaded_at"]
    return {"status": "ok", "models_ready": ready, "models_loaded_at": loaded_at}


@app.post("/predict")
def predict(features: FeatureVector):
    return cascade_predict(features.model_dump())


@app.post("/reload-model")
def reload_model():
    """Called by Airflow after a champion promotion - hot-swaps the model
    without a container restart."""
    try:
        load_champion_models()
        return {"status": "reloaded", "loaded_at": _state["loaded_at"]}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Could not reload models: {exc}")
