import os

import pytest
from fastapi.testclient import TestClient

from iris.train import train


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    artifacts_dir = tmp_path_factory.mktemp("artifacts")
    os.environ["ARTIFACT_URI"] = f"file://{artifacts_dir}"

    result = train(epochs=50, model_version="test")
    os.environ["MODEL_URI"] = result["artifact_uri"]

    from iris.api import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/health").status_code == 200


def test_ready_after_startup(client):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_predict_returns_valid_class(client):
    resp = client.post(
        "/predict",
        json={
            "sepal_length_cm": 5.1,
            "sepal_width_cm": 3.5,
            "petal_length_cm": 1.4,
            "petal_width_cm": 0.2,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["predicted_class"] in ["setosa", "versicolor", "virginica"]
    assert 0 <= body["confidence"] <= 1


def test_predict_rejects_invalid_input(client):
    resp = client.post(
        "/predict",
        json={
            "sepal_length_cm": -1,
            "sepal_width_cm": 3,
            "petal_length_cm": 1,
            "petal_width_cm": 1,
        },
    )
    assert resp.status_code == 422


def test_metrics_endpoint_exposes_prometheus_format(client):
    resp = client.get("/metrics")
    assert b"iris_predictions_total" in resp.content
