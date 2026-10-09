import pytest

from mlops_demo import registry
from mlops_demo.config import GateConfig, TARGET
from mlops_demo.data import generate_customers
from mlops_demo.gate import passed, run_gate
from mlops_demo.predictor import Predictor

BASELINE = {"roc_auc": 0.5, "pr_auc": 0.3}


@pytest.fixture(scope="module")
def predictor(artifacts):
    return Predictor.load(registry.bundle_dir(artifacts, "v0001"))


@pytest.fixture(scope="module")
def holdout():
    df = generate_customers(2000, seed=999)
    return df, df[TARGET].to_numpy()


def _gate(predictor, holdout, cfg, champion=None, roundtrip=0.0, baseline=BASELINE):
    df, y = holdout
    return run_gate(challenger=predictor, test_df=df, y_test=y, baseline=baseline,
                    champion=champion, roundtrip_diff=roundtrip, cfg=cfg)


def test_gate_passes_for_reasonable_model(predictor, holdout):
    checks = _gate(predictor, holdout, GateConfig(min_auc=0.6, min_slice_auc=0.4, max_p95_latency_ms=5000))
    assert passed(checks), [c for c in checks if not c.passed]


def test_gate_rejects_model_below_min_auc(predictor, holdout):
    # Change ONLY min_auc so the test isolates a single check.
    checks = _gate(predictor, holdout, GateConfig(min_auc=0.99, min_slice_auc=0.0, max_p95_latency_ms=5000))
    assert not passed(checks)
    assert [c.name for c in checks if not c.passed] == ["min_auc"]


def test_gate_rejects_miscalibrated_model(predictor, holdout):
    """A limit of 0.0 is unreachable, so the calibration check must fail (and only that one)."""
    cfg = GateConfig(min_auc=0.5, min_slice_auc=0.0, max_p95_latency_ms=5000, max_calibration_gap=0.0)
    assert [c.name for c in _gate(predictor, holdout, cfg) if not c.passed] == ["calibration_in_the_large"]


def test_gate_rejects_model_worse_than_baseline(predictor, holdout):
    checks = _gate(predictor, holdout, GateConfig(min_auc=0.5, min_slice_auc=0.0, max_p95_latency_ms=5000),
                   baseline={"roc_auc": 0.99, "pr_auc": 0.9})
    assert "beats_baseline" in [c.name for c in checks if not c.passed]


def test_gate_rejects_regression_against_champion(predictor, holdout):
    """Champion identical to the challenger while we demand a 0.1 improvement, so it must fail."""
    cfg = GateConfig(min_auc=0.5, min_slice_auc=0.0, max_p95_latency_ms=5000, max_regression=-0.1)
    checks = _gate(predictor, holdout, cfg, champion=predictor)
    assert "no_regression_vs_champion" in [c.name for c in checks if not c.passed]


def test_gate_rejects_broken_serialization(predictor, holdout):
    checks = _gate(predictor, holdout, GateConfig(min_auc=0.5, min_slice_auc=0.0, max_p95_latency_ms=5000), roundtrip=0.5)
    assert "serialization_roundtrip" in [c.name for c in checks if not c.passed]


# ---------------------------------------------------------------- registry
def _fake_bundles(root, n):
    for i in range(1, n + 1):
        (registry.models_dir(root) / f"v{i:04d}").mkdir(parents=True)


def test_registry_versions_promote_and_rollback(tmp_path):
    _fake_bundles(tmp_path, 3)
    assert registry.next_version(tmp_path) == "v0004"
    assert registry.production_version(tmp_path) is None

    registry.promote(tmp_path, "v0001")
    registry.promote(tmp_path, "v0002", reason="better")
    assert registry.production_version(tmp_path) == "v0002"

    assert registry.rollback(tmp_path) == "v0001"
    assert registry.production_version(tmp_path) == "v0001"
    assert [h["version"] for h in registry.read_registry(tmp_path)["history"]] == ["v0001", "v0002", "v0001"]


def test_registry_refuses_missing_bundle_and_empty_rollback(tmp_path):
    with pytest.raises(FileNotFoundError):
        registry.promote(tmp_path, "v0009")
    _fake_bundles(tmp_path, 1)
    registry.promote(tmp_path, "v0001")
    with pytest.raises(RuntimeError):
        registry.rollback(tmp_path)  # there is no previous version
