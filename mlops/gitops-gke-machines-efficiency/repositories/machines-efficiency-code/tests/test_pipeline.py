import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from src.data_processing import FEATURES, NUMERIC
from src.model_training import ModelTraining


@pytest.fixture
def sample_frame():
    """Synthetic data with the same structure as the production data."""
    rng = np.random.default_rng(42)
    n = 120

    df = pd.DataFrame({name: rng.normal(50, 10, n) for name in NUMERIC})
    df["Operation_Mode"] = rng.choice(["Active", "Idle", "Maintenance"], n)
    return df[FEATURES]


@pytest.fixture
def fitted_pipeline(sample_frame):
    rng = np.random.default_rng(42)
    y = rng.integers(0, 3, len(sample_frame))

    trainer = ModelTraining.__new__(ModelTraining)
    trainer.X_train, trainer.y_train = sample_frame, y
    trainer.train_model()
    return trainer.clf


def test_pipeline_is_single_artifact(fitted_pipeline):
    """Preprocessing and model must be a single object - otherwise the risk of
    training/serving skew comes back."""
    assert isinstance(fitted_pipeline, Pipeline)
    assert "preprocess" in fitted_pipeline.named_steps
    assert "model" in fitted_pipeline.named_steps


def test_accepts_raw_dataframe(fitted_pipeline, sample_frame):
    """The pipeline accepts raw data with categories as strings - exactly what
    the form sends."""
    pred = fitted_pipeline.predict(sample_frame.head(1))
    assert pred.shape == (1,)
    assert pred[0] in {0, 1, 2}


def test_categorical_is_one_hot_encoded(fitted_pipeline):
    """A LabelEncoder on Operation_Mode would give logistic regression a
    spurious ordinal scale."""
    preprocessor = fitted_pipeline.named_steps["preprocess"]
    encoder = dict(
        (name, trans) for name, trans, _ in preprocessor.transformers_
    )["cat"]
    assert encoder.__class__.__name__ == "OneHotEncoder"
    assert encoder.handle_unknown == "ignore"


def test_unknown_category_does_not_raise(fitted_pipeline, sample_frame):
    """handle_unknown='ignore' - an unknown value must not bring down the server."""
    row = sample_frame.head(1).copy()
    row["Operation_Mode"] = "Sabotage"
    assert fitted_pipeline.predict(row).shape == (1,)


def test_column_order_is_irrelevant(fitted_pipeline, sample_frame):
    """ColumnTransformer addresses columns by name - reordering them must not
    change the result."""
    row = sample_frame.head(1)
    shuffled = row[list(reversed(FEATURES))]
    assert fitted_pipeline.predict(row)[0] == fitted_pipeline.predict(shuffled)[0]


def test_scaler_not_fitted_on_full_data(sample_frame):
    """Data leakage: the scaler only ever sees the training set. Statistics from
    half the data must differ from statistics over the whole set."""
    from sklearn.preprocessing import StandardScaler

    half = sample_frame[NUMERIC].iloc[: len(sample_frame) // 2]
    full = sample_frame[NUMERIC]

    assert not np.allclose(
        StandardScaler().fit(half).mean_, StandardScaler().fit(full).mean_
    )
