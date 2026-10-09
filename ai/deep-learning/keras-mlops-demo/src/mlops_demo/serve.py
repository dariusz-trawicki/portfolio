"""API (FastAPI): serves the production model with input validation and a prediction log.

Usage:  uvicorn mlops_demo.serve:app --port 8000
Docs:   http://localhost:8000/docs
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .config import ARTIFACTS_DIR
from .predictor import load_production

WARMUP_RECORD = {
    "tenure_months": 1, "monthly_charges": 50.0, "support_calls_90d": 0, "is_senior": 0,
    "contract": "month_to_month", "payment_method": "card", "internet_service": "dsl",
}


class Customer(BaseModel):
    """Input contract. `extra="forbid"` rejects misspelled field names instead of silently ignoring them."""

    model_config = ConfigDict(extra="forbid")
    tenure_months: int = Field(ge=0, le=120, examples=[5])
    monthly_charges: float = Field(ge=0, le=500, examples=[89.9])
    support_calls_90d: int = Field(ge=0, le=100, examples=[3])
    is_senior: int = Field(ge=0, le=1, examples=[0])
    # Categories are plain strings: an unknown value is NOT an error. It goes to the OOV
    # bucket and is reported in the response and in the log (a signal for monitoring).
    contract: str = Field(min_length=1, max_length=40, examples=["month_to_month"])
    payment_method: str = Field(min_length=1, max_length=40, examples=["e_check"])
    internet_service: str = Field(min_length=1, max_length=40, examples=["fiber"])


class Prediction(BaseModel):
    request_id: str
    churn_probability: float
    churn_predicted: bool
    threshold: float
    model_version: str
    unknown_categories: list[str]


class BatchRequest(BaseModel):
    customers: list[Customer] = Field(min_length=1, max_length=1000)


class BatchResponse(BaseModel):
    predictions: list[Prediction]


def create_app(artifacts_dir: Path | None = None, log_path: Path | None = None) -> FastAPI:
    artifacts = Path(artifacts_dir or ARTIFACTS_DIR)
    log_file = Path(log_path or os.environ.get("PREDICTION_LOG", artifacts / "prediction_log.jsonl"))
    state: dict = {"predictor": None}
    model_lock = threading.Lock()  # the Keras backend does not guarantee thread safety
    log_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state["predictor"] = load_production(artifacts)
        if state["predictor"] is not None:  # warm-up: the first call triggers JIT compilation
            state["predictor"].predict_records([WARMUP_RECORD])
        yield

    app = FastAPI(title="Churn API", version="0.1.0", lifespan=lifespan)

    def score(customers: list[Customer]) -> list[Prediction]:
        predictor = state["predictor"]
        if predictor is None:
            raise HTTPException(503, "No production model. Run: python -m mlops_demo.train --promote")
        records = [c.model_dump() for c in customers]
        t0 = time.perf_counter()
        with model_lock:
            probs = predictor.predict_records(records)
        latency_ms = (time.perf_counter() - t0) * 1000 / len(records)

        results, lines = [], []
        for rec, prob in zip(records, probs):
            unknown = predictor.preprocessor.unknown_categories(rec)
            pred = Prediction(
                request_id=uuid.uuid4().hex, churn_probability=round(float(prob), 6),
                churn_predicted=bool(prob >= predictor.threshold), threshold=predictor.threshold,
                model_version=predictor.version, unknown_categories=unknown,
            )
            results.append(pred)
            lines.append(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "request_id": pred.request_id,
                "model_version": pred.model_version, "features": rec, "probability": pred.churn_probability,
                "unknown_categories": unknown, "latency_ms": round(latency_ms, 3),
            }))
        # The prediction log feeds monitoring. In production it would go to a queue/warehouse, not a file.
        with log_lock:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with log_file.open("a") as f:
                f.write("\n".join(lines) + "\n")
        return results

    @app.get("/health")
    def health():
        predictor = state["predictor"]
        if predictor is None:
            raise HTTPException(503, "no production model")
        return {"status": "ok", "model_version": predictor.version}

    @app.get("/model-info")
    def model_info():
        predictor = state["predictor"]
        if predictor is None:
            raise HTTPException(503, "no production model")
        m = predictor.metadata
        return {k: m[k] for k in ("version", "created_at", "threshold", "metrics", "data", "environment", "mlflow_run_id")}

    @app.post("/predict", response_model=Prediction)
    def predict(customer: Customer):
        return score([customer])[0]

    @app.post("/predict/batch", response_model=BatchResponse)
    def predict_batch(batch: BatchRequest):
        return BatchResponse(predictions=score(batch.customers))

    return app


app = create_app()
