import json
import pickle

import numpy as np
import pytest

from app import app

MODEL_PATH = "model/iris_model.pkl"
METADATA_PATH = "model/metadata.json"

with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)


# ── known samples from the dataset (class is deterministic for these values) ──

SAMPLES = [
    ([5.1, 3.5, 1.4, 0.2], 0, "Iris setosa"),
    ([6.0, 2.7, 5.1, 1.6], 1, "Iris versicolor"),
    ([6.3, 2.9, 5.6, 1.8], 2, "Iris virginica"),
]


@pytest.mark.parametrize("features, expected_class, expected_name", SAMPLES)
def test_model_predicts_correct_species(features, expected_class, expected_name):
    prediction = model.predict([features])
    assert int(prediction[0]) == expected_class, (
        f"Expected {expected_name} (class {expected_class}), got class {prediction[0]}"
    )


def test_model_accuracy_above_threshold():
    with open(METADATA_PATH) as f:
        metadata = json.load(f)
    accuracy = metadata["accuracy"]
    assert accuracy >= 0.90, f"Model accuracy {accuracy:.4f} is below the 0.90 threshold"


def test_prediction_output_type():
    features = [5.1, 3.5, 1.4, 0.2]
    prediction = model.predict([features])
    assert isinstance(prediction[0], (int, np.integer))


@pytest.mark.parametrize("features, _, expected_name", SAMPLES)
def test_flask_returns_species_name(features, _, expected_name):
    form_data = {
        "sepal_length": features[0],
        "sepal_width":  features[1],
        "petal_length": features[2],
        "petal_width":  features[3],
    }
    with app.test_client() as client:
        response = client.post("/predict", data=form_data)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert expected_name in body, f"Expected '{expected_name}' in response"


def test_flask_rejects_missing_field():
    with app.test_client() as client:
        response = client.post("/predict", data={"sepal_length": 5.1})
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Missing field" in body or "Invalid" in body or "error" in body.lower()


def test_flask_rejects_out_of_range_value():
    form_data = {
        "sepal_length": 99.0,
        "sepal_width":  3.5,
        "petal_length": 1.4,
        "petal_width":  0.2,
    }
    with app.test_client() as client:
        response = client.post("/predict", data=form_data)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "sepal_length" in body


def test_health_endpoint():
    with app.test_client() as client:
        response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert "model_accuracy" in data
