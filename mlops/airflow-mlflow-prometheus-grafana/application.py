import pickle
import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify, Response
from src.logger import get_logger
from src.feature_store import RedisFeatureStore
from sklearn.preprocessing import StandardScaler
from prometheus_client import start_http_server, Counter, generate_latest

logger = get_logger(__name__)

app = Flask(__name__, template_folder="templates")

# ─────────────────────────────────────────────
# Prometheus metrics
# ─────────────────────────────────────────────
prediction_count = Counter('prediction_count', "Number of predictions")
drift_count      = Counter('drift_count',      "Number of times data drift is detected")

# ─────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────
MODEL_PATH = "artifacts/models/random_forest_model.pkl"
with open(MODEL_PATH, 'rb') as model_file:
    model = pickle.load(model_file)
print("✅ Model loaded")

FEATURE_NAMES = ['Age', 'Fare', 'Pclass', 'Sex', 'Embarked', 'Familysize',
                 'Isalone', 'HasCabin', 'Title', 'Pclass_Fare', 'Age_Fare']

# ─────────────────────────────────────────────
# Feature Store + Scaler
# ─────────────────────────────────────────────
feature_store = RedisFeatureStore()
scaler = StandardScaler()

def fit_scaler_on_ref_data():
    entity_ids   = feature_store.get_all_entity_ids()
    all_features = feature_store.get_batch_features(entity_ids)
    df = pd.DataFrame.from_dict(all_features, orient='index')[FEATURE_NAMES]
    scaler.fit(df)
    return scaler.transform(df)

print("✅ Fitting scaler on reference data...")
historical_data = fit_scaler_on_ref_data()
print(f"✅ Reference data shape: {historical_data.shape}")

# ─────────────────────────────────────────────
# Drift Detection — Z-score
# Operates on a single sample: checks whether
# a feature value exceeds the threshold in
# standard deviations from the reference mean
# ─────────────────────────────────────────────
ref_mean = historical_data.mean(axis=0)   # mean of each feature
ref_std  = historical_data.std(axis=0)    # std of each feature

def detect_drift(new_data, threshold=3.0):
    """
    Z-score drift detection for a single sample.
    Returns (is_drift, drifted_features) — which features exceeded the threshold.
    """
    z_scores = np.abs((new_data - ref_mean) / (ref_std + 1e-8))
    drifted_features = [
        FEATURE_NAMES[i]
        for i in range(len(FEATURE_NAMES))
        if z_scores[0, i] > threshold
    ]
    is_drift = len(drifted_features) > 0
    return is_drift, drifted_features

# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.form

        Age         = float(data["Age"])
        Fare        = float(data["Fare"])
        Pclass      = int(data["Pclass"])
        Sex         = int(data["Sex"])
        Embarked    = int(data["Embarked"])
        Familysize  = int(data["Familysize"])
        Isalone     = int(data["Isalone"])
        HasCabin    = int(data["HasCabin"])
        Title       = int(data["Title"])
        Pclass_Fare = float(data["Pclass_Fare"])
        Age_Fare    = float(data["Age_Fare"])

        features = pd.DataFrame(
            [[Age, Fare, Pclass, Sex, Embarked, Familysize,
              Isalone, HasCabin, Title, Pclass_Fare, Age_Fare]],
            columns=FEATURE_NAMES
        )

        # Drift detection (z-score on scaled data)
        features_scaled = scaler.transform(features)
        is_drift, drifted_features = detect_drift(features_scaled)

        if is_drift:
            logger.warning(f"⚠️ Drift detected in features: {drifted_features}")
            print(f"⚠️ Drift detected in features: {drifted_features}")
            drift_count.inc()

        # Prediction
        prediction = model.predict(features)[0]
        prediction_count.inc()

        result     = 'Survived' if prediction == 1 else 'Did Not Survive'
        drift_info = f" (⚠️ Drift: {drifted_features})" if is_drift else ""

        return render_template('index.html',
                               prediction_text=f"Prediction: {result}{drift_info}")

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return jsonify({'error': str(e)})


@app.route('/metrics')
def metrics():
    return Response(generate_latest(), content_type='text/plain')


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == "__main__":
    start_http_server(8000)
    print("✅ Prometheus metrics server started on port 8000")
    print("✅ Flask app starting on port 5001")
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
