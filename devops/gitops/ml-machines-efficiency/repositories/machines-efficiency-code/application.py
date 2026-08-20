import logging
import os

import joblib
import pandas as pd
from flask import Flask, render_template, request

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


@app.get("/health")
def health():
    return {"status": "ok"}, 200


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
            pred = model.predict(X)[0]
            prediction = label_encoder.inverse_transform([pred])[0]

        except (KeyError, ValueError) as exc:
            logger.warning("Invalid input data: %s", exc)
            error = "Invalid input data - please check all fields."
        except Exception:
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
    app.run(debug=False, host="127.0.0.1", port=5000)
