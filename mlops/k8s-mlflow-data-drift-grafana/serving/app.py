"""
Model serving API with Prometheus metrics
"""
import os
import pickle
import json
import time
from datetime import datetime
from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import numpy as np

# Configuration
MODEL_PATH = os.getenv("MODEL_PATH", "/models/latest")
RELOAD_INTERVAL = int(os.getenv("MODEL_RELOAD_INTERVAL", "60"))  # seconds

# Prometheus metrics
prediction_counter = Counter(
    'model_predictions_total',
    'Total predictions made',
    ['model_version', 'predicted_class']
)

prediction_duration = Histogram(
    'model_prediction_duration_seconds',
    'Time spent processing prediction',
    ['model_version']
)

model_accuracy_gauge = Gauge(
    'model_accuracy',
    'Current model accuracy',
    ['model_version']
)

model_info = Gauge(
    'model_info',
    'Model information',
    ['version', 'model_type', 'timestamp']
)

last_reload_time = Gauge(
    'model_last_reload_timestamp',
    'Timestamp of last model reload'
)

# Application
app = FastAPI(title="Iris Model Serving API", version="1.0.0")

# Global variables for the model
current_model = None
current_metadata = None
last_model_check = 0

class PredictionRequest(BaseModel):
    """Prediction request"""
    features: List[List[float]]

    class Config:
        schema_extra = {
            "example": {
                "features": [[5.1, 3.5, 1.4, 0.2]]
            }
        }

class PredictionResponse(BaseModel):
    """Prediction response"""
    predictions: List[str]
    probabilities: List[List[float]]
    model_version: str
    timestamp: str

def load_model():
    """Load model from disk"""
    global current_model, current_metadata

    try:
        print(f"Loading model from {MODEL_PATH}...")

        # Load model
        model_file = f"{MODEL_PATH}/model.pkl"
        with open(model_file, 'rb') as f:
            current_model = pickle.load(f)

        # Load metadata
        metadata_file = f"{MODEL_PATH}/metadata.json"
        with open(metadata_file, 'r') as f:
            current_metadata = json.load(f)

        # Update metrics
        version = current_metadata.get('version', 'unknown')
        accuracy = current_metadata.get('metrics', {}).get('accuracy', 0)
        model_type = current_metadata.get('model_type', 'unknown')

        model_accuracy_gauge.labels(model_version=version).set(accuracy)
        model_info.labels(
            version=version,
            model_type=model_type,
            timestamp=current_metadata.get('timestamp', '')
        ).set(1)

        last_reload_time.set(time.time())

        print(f"Model loaded: {version}")
        print(f"Accuracy: {accuracy:.4f}")

    except Exception as e:
        print(f"Model loading error: {e}")
        raise

def check_and_reload_model():
    """Check if the model has changed and reload if needed"""
    global last_model_check

    current_time = time.time()

    # Check only every RELOAD_INTERVAL seconds
    if current_time - last_model_check < RELOAD_INTERVAL:
        return

    last_model_check = current_time

    try:
        metadata_file = f"{MODEL_PATH}/metadata.json"
        with open(metadata_file, 'r') as f:
            new_metadata = json.load(f)

        # Check if version has changed
        if current_metadata is None or new_metadata['version'] != current_metadata['version']:
            print(f"New model version detected: {new_metadata['version']}")
            load_model()
    except Exception as e:
        print(f"Model check error: {e}")

@app.on_event("startup")
async def startup_event():
    """Load model on startup"""
    load_model()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "iris-model-serving",
        "model_version": current_metadata.get('version', 'unknown') if current_metadata else 'not_loaded'
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    if current_model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    return {
        "status": "healthy",
        "model_loaded": True,
        "model_version": current_metadata['version'],
        "model_accuracy": current_metadata['metrics']['accuracy'],
        "timestamp": datetime.now().isoformat()
    }

@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """Prediction endpoint"""

    # Check if model is loaded
    if current_model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    # Check for new model version
    check_and_reload_model()

    try:
        # Timing
        start_time = time.time()

        # Convert to numpy array
        X = np.array(request.features)

        # Prediction
        predictions_idx = current_model.predict(X)
        probabilities = current_model.predict_proba(X).tolist()

        # Convert class indices to class names
        target_names = current_metadata['target_names']
        predictions = [target_names[idx] for idx in predictions_idx]

        # Metrics
        duration = time.time() - start_time
        version = current_metadata['version']

        prediction_duration.labels(model_version=version).observe(duration)
        for pred in predictions:
            prediction_counter.labels(
                model_version=version,
                predicted_class=pred
            ).inc()

        return PredictionResponse(
            predictions=predictions,
            probabilities=probabilities,
            model_version=version,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

@app.get("/model/info")
async def model_info_endpoint():
    """Information about the current model"""
    if current_metadata is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    return current_metadata

@app.post("/model/reload")
async def reload_model():
    """Manual model reload"""
    try:
        load_model()
        return {
            "status": "success",
            "message": "Model reloaded",
            "version": current_metadata['version']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reload failed: {str(e)}")

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
