import numpy as np
import pytest

from mlops_demo.data import generate_customers
from mlops_demo.drift import build_reference, compare, psi, status


def test_psi_is_zero_for_identical_and_large_for_shifted():
    same = np.array([0.25, 0.25, 0.25, 0.25])
    assert psi(same, same) == pytest.approx(0.0, abs=1e-9)
    assert psi(same, [0.7, 0.1, 0.1, 0.1]) > 0.25


@pytest.mark.parametrize("value, expected", [(0.05, "ok"), (0.15, "warn"), (0.30, "alert")])
def test_status_thresholds(value, expected):
    assert status(value) == expected


@pytest.fixture(scope="module")
def reference():
    return build_reference(generate_customers(10_000, seed=1))


def test_reference_distinguishes_kinds(reference):
    kinds = {name: spec["kind"] for name, spec in reference["features"].items()}
    assert kinds["monthly_charges"] == "continuous"
    assert kinds["contract"] == "discrete"
    assert kinds["is_senior"] == "discrete"


def test_no_alert_for_fresh_sample_from_same_distribution(reference):
    report = compare(reference, generate_customers(2000, seed=99))
    assert not report["alert"]
    assert report["max_psi"] < 0.1


def test_alert_for_drifted_sample(reference):
    report = compare(reference, generate_customers(2000, seed=99, drift=0.8))
    assert report["alert"]
    assert report["features"]["monthly_charges"]["status"] == "alert"


def test_small_sample_never_alerts(reference):
    """With 100 rows PSI is mostly noise, so nobody should be paged at night."""
    report = compare(reference, generate_customers(100, seed=99, drift=0.8), min_samples=500)
    assert not report["enough_data"]
    assert not report["alert"]


def test_unseen_category_goes_to_other_bucket(reference):
    df = generate_customers(1000, seed=5).assign(contract="lifetime")
    assert compare(reference, df)["features"]["contract"]["status"] == "alert"
