import pytest

from mlops_demo.config import GateConfig, TrainConfig
from mlops_demo.train import run_training

# Tests train a tiny model on little data, so the gate is more lenient than in production.
LENIENT_GATE = GateConfig(min_auc=0.6, min_lift_over_baseline=-0.1, min_slice_auc=0.4, max_p95_latency_ms=5000)

VALID_CUSTOMER = {
    "tenure_months": 3, "monthly_charges": 95.5, "support_calls_90d": 4, "is_senior": 0,
    "contract": "month_to_month", "payment_method": "e_check", "internet_service": "fiber",
}


@pytest.fixture(scope="session")
def artifacts(tmp_path_factory):
    """Once per session: train a small model through the REAL pipeline (without MLflow) and promote it."""
    path = tmp_path_factory.mktemp("artifacts")
    # High learning rate so the tiny model learns something within a few seconds.
    cfg = TrainConfig(n_rows=4000, max_epochs=12, patience=4, hidden=(16, 8), lr=1e-2)
    result = run_training(cfg, path, tracking_uri=None, promote=True, gate_cfg=LENIENT_GATE)
    assert result["promoted"], result["checks"]
    return path
