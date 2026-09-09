"""API serving the Iris model.

/health  — liveness: the process is alive, nothing else is checked.
/ready   — readiness: model loaded into memory and ready to respond.
/predict — the actual prediction.
/metrics — exposition for Prometheus.
"""

from __future__ import annotations

import logging
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from iris.config import settings
from iris.features import CLASS_NAMES, FEATURE_NAMES
from iris.metrics import (
    FEATURE_VALUE,
    PREDICTION_CONFIDENCE,
    PREDICTION_LATENCY,
    PREDICTIONS_TOTAL,
)
from iris.model import Predictor
from iris.schemas import PredictRequest, PredictResponse
from iris.storage import download_dir

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("api")

state: dict = {"predictor": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("downloading artifacts from %s", settings.model_uri)
    try:
        artifact_dir = Path(tempfile.mkdtemp(prefix="iris-model-"))
        download_dir(settings.model_uri, artifact_dir)
        state["predictor"] = Predictor(artifact_dir)
        log.info("model ready, version=%s", state["predictor"].model_version)
    except Exception:
        log.exception("failed to load the model — /ready will stay red")
        state["predictor"] = None
    yield
    state.clear()


app = FastAPI(title="iris-api", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response):
    if state.get("predictor") is None:
        response.status_code = 503
        return {"status": "not-ready"}
    return {"status": "ready", "model_version": state["predictor"].model_version}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest):
    predictor = state.get("predictor")
    if predictor is None:
        raise HTTPException(status_code=503, detail="model is not ready yet")

    features = [getattr(request, name) for name in FEATURE_NAMES]
    for name, value in zip(FEATURE_NAMES, features):
        FEATURE_VALUE.labels(feature=name).observe(value)

    start = time.perf_counter()
    predicted_class, confidence, probs = predictor.predict(features)
    PREDICTION_LATENCY.observe(time.perf_counter() - start)
    PREDICTIONS_TOTAL.labels(predicted_class=predicted_class).inc()
    PREDICTION_CONFIDENCE.observe(confidence)

    return PredictResponse(
        predicted_class=predicted_class,
        confidence=confidence,
        probabilities=dict(zip(CLASS_NAMES, probs)),
        model_version=predictor.model_version,
    )
