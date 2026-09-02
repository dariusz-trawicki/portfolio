import logging
import os

import joblib
import pandas as pd
from flask import Flask, render_template, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL_DIR = os.getenv("MODEL_DIR", "artifacts/models")

DEFAULTS = {
    "Operation_Mode": "Active",
    "Temperature_C": 75.0,
    "Vibration_Hz": 2.5,
    "Power_Consumption_kW": 30.0,
    "Network_Latency_ms": 20.0,
    "Packet_Loss_%": 1.0,
    "Quality_Control_Defect_Rate_%": 2.5,
    "Production_Speed_units_per_hr": 500.0,
    "Predictive_Maintenance_Score": 0.6,
    "Error_Rate_%": 1.5,
    "Year": 2025,
    "Month": 6,
    "Day": 15,
    "Hour": 14,
}


app = Flask(__name__)

model = joblib.load(os.path.join(MODEL_DIR, "model.pkl"))
label_encoder = joblib.load(os.path.join(MODEL_DIR, "label_encoder.pkl"))

CATEGORICAL = {
    "Operation_Mode": ["Active", "Idle", "Maintenance"],
}

NUMERIC = [
    "Temperature_C", "Vibration_Hz", "Power_Consumption_kW",
    "Network_Latency_ms", "Packet_Loss_%", "Quality_Control_Defect_Rate_%",
    "Production_Speed_units_per_hr", "Predictive_Maintenance_Score",
    "Error_Rate_%", "Year", "Month", "Day", "Hour",
]

FEATURES = list(CATEGORICAL) + NUMERIC

# --------------------------------------------------------------------------
# Prometheus metrics.
#
# Run gunicorn with a single worker. Each worker process keeps its own
# registry, so /metrics would answer from whichever process handled the
# request - counters appear to jump backwards and rate() returns garbage.
# Scale with Deployment replicas instead; Prometheus scrapes each pod.
# --------------------------------------------------------------------------
PREDICTIONS = Counter(
    "predictions_total",
    "Predictions served, by predicted class",
    ["predicted_class"],
)

LATENCY = Histogram(
    "prediction_latency_seconds",
    "Model inference time",
)

# Split by reason: invalid_input is a user typo, internal is a real failure.
# Without the label the error graph mixes two unrelated signals.
ERRORS = Counter(
    "prediction_errors_total",
    "Failed predictions",
    ["reason"],
)

# Data drift proxy - when the input distribution moves away from the training
# data, the histogram shape shifts. Limited to three features on purpose:
# every feature would be 13 series x bucket count for little added insight.
INPUTS = Histogram(
    "prediction_input_value",
    "Distribution of selected input features",
    ["feature"],
    buckets=(0, 10, 25, 50, 75, 100, 250, 500, 1000),
)

DRIFT_FEATURES = ("Temperature_C", "Vibration_Hz", "Power_Consumption_kW")

# Gauge fixed at 1 - the labels carry the payload. Lets every other metric be
# tied back to the exact build that produced it.
MODEL_INFO = Gauge(
    "model_info",
    "Deployed model build metadata",
    ["version", "git_sha"],
)
MODEL_INFO.labels(
    version=os.getenv("MODEL_VERSION", "unknown"),
    git_sha=os.getenv("GIT_SHA", "unknown"),
).set(1)


@app.get("/health")
def health():
    return {"status": "ok"}, 200


@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/", methods=["GET", "POST"])
def index():
    prediction = None
    error = None

    if request.method == "POST":
        try:
            row = {}
            for name, allowed in CATEGORICAL.items():
                value = request.form[name]
                if value not in allowed:
                    raise ValueError(f"{name}: unexpected value")
                row[name] = value
            for name in NUMERIC:
                row[name] = float(request.form[name])

            X = pd.DataFrame([row], columns=FEATURES)
            with LATENCY.time():
                pred = model.predict(X)[0]
            prediction = label_encoder.inverse_transform([pred])[0]

            PREDICTIONS.labels(predicted_class=prediction).inc()
            for name in DRIFT_FEATURES:
                INPUTS.labels(feature=name).observe(row[name])

        except (KeyError, ValueError) as exc:
            ERRORS.labels(reason="invalid_input").inc()
            logger.warning("Invalid input data: %s", exc)
            error = "Invalid input data - please check all fields."
        except Exception:
            ERRORS.labels(reason="internal").inc()
            logger.exception("Prediction error")
            error = "An error occurred during prediction."

    return render_template(
        "index.html",
        prediction=prediction,
        error=error,
        numeric=NUMERIC,
        categorical=CATEGORICAL,
        defaults=DEFAULTS,
        submitted=request.form,
    )


if __name__ == "__main__":
    # Local development only - gunicorn binds 0.0.0.0 in the container.
    # 0.0.0.0 here too, so `docker run -p 5000:5000` works without gunicorn.
    app.run(debug=False, host="0.0.0.0", port=5000)
