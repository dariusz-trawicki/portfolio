import pytest

from mlops_demo.data import DataValidationError, fingerprint, generate_customers, validate


def test_generator_is_reproducible():
    a, b = generate_customers(500, seed=1), generate_customers(500, seed=1)
    assert a.equals(b)
    assert not a.equals(generate_customers(500, seed=2))


def test_generated_data_passes_validation():
    validate(generate_customers(2000, seed=3))


def test_drift_shifts_distribution():
    base, drifted = generate_customers(5000, seed=4, drift=0.0), generate_customers(5000, seed=4, drift=0.9)
    assert drifted["monthly_charges"].mean() > base["monthly_charges"].mean() + 5
    assert drifted["tenure_months"].mean() < base["tenure_months"].mean()


@pytest.mark.parametrize("mutate, expected", [
    (lambda d: d.drop(columns=["contract"]), "missing columns"),
    (lambda d: d.assign(tenure_months=d["tenure_months"].where(d.index != 0)), "missing values"),
    (lambda d: d.assign(monthly_charges=d["monthly_charges"].where(d.index != 0, -5.0)), "outside"),
    (lambda d: d.assign(contract=d["contract"].where(d.index != 0, "lifetime")), "unknown categories"),
    (lambda d: d.assign(churn=0), "churn rate"),
])
def test_validation_catches_bad_data(mutate, expected):
    with pytest.raises(DataValidationError, match=expected):
        validate(mutate(generate_customers(1000, seed=5)))


def test_fingerprint_changes_with_data():
    df = generate_customers(300, seed=6)
    changed = df.copy()
    changed.loc[0, "monthly_charges"] += 1
    assert fingerprint(df) == fingerprint(df.copy())
    assert fingerprint(df) != fingerprint(changed)
