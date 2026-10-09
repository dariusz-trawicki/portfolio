import json

import pytest
from fastapi.testclient import TestClient

from mlops_demo.serve import create_app

from conftest import VALID_CUSTOMER


@pytest.fixture()
def log_path(tmp_path):
    return tmp_path / "pred.jsonl"


@pytest.fixture()
def client(artifacts, log_path):
    with TestClient(create_app(artifacts, log_path)) as c:  # `with` runs the lifespan (model loading)
        yield c


def test_health_and_model_info(client):
    assert client.get("/health").json() == {"status": "ok", "model_version": "v0001"}
    info = client.get("/model-info").json()
    assert info["version"] == "v0001" and "roc_auc" in info["metrics"]["test"]
    assert info["data"]["fingerprint"]


def test_predict_returns_valid_prediction_and_logs_it(client, log_path):
    r = client.post("/predict", json=VALID_CUSTOMER)
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["churn_probability"] <= 1
    assert body["model_version"] == "v0001"
    assert body["churn_predicted"] == (body["churn_probability"] >= body["threshold"])

    lines = log_path.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["request_id"] == body["request_id"] and entry["features"]["contract"] == "month_to_month"


def test_predict_is_deterministic(client):
    a = client.post("/predict", json=VALID_CUSTOMER).json()["churn_probability"]
    b = client.post("/predict", json=VALID_CUSTOMER).json()["churn_probability"]
    assert a == b


def test_risky_customer_scores_higher_than_loyal_one(client):
    risky = client.post("/predict", json=VALID_CUSTOMER).json()["churn_probability"]
    loyal = client.post("/predict", json={**VALID_CUSTOMER, "tenure_months": 60, "contract": "two_year",
                                          "support_calls_90d": 0, "monthly_charges": 60.0,
                                          "payment_method": "card"}).json()["churn_probability"]
    assert risky > loyal


@pytest.mark.parametrize("patch", [
    {"tenure_months": -1}, {"monthly_charges": 10_000}, {"is_senior": 2},
    {"tenure_months": "abc"}, {"unexpected_field": 1},
])
def test_invalid_input_is_rejected_with_422(client, patch):
    assert client.post("/predict", json={**VALID_CUSTOMER, **patch}).status_code == 422


def test_missing_field_is_rejected(client):
    payload = {k: v for k, v in VALID_CUSTOMER.items() if k != "contract"}
    assert client.post("/predict", json=payload).status_code == 422


def test_unknown_category_is_served_but_flagged(client):
    r = client.post("/predict", json={**VALID_CUSTOMER, "internet_service": "satellite"})
    assert r.status_code == 200
    assert r.json()["unknown_categories"] == ["internet_service"]


def test_batch(client, log_path):
    r = client.post("/predict/batch", json={"customers": [VALID_CUSTOMER] * 3})
    assert r.status_code == 200 and len(r.json()["predictions"]) == 3
    assert len(log_path.read_text().splitlines()) == 3
    assert client.post("/predict/batch", json={"customers": []}).status_code == 422


def test_service_reports_503_without_production_model(tmp_path):
    with TestClient(create_app(tmp_path, tmp_path / "log.jsonl")) as c:
        assert c.get("/health").status_code == 503
        assert c.post("/predict", json=VALID_CUSTOMER).status_code == 503
