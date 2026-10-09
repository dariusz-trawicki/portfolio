import numpy as np

from mlops_demo import registry
from mlops_demo.config import FEATURES, TrainConfig
from mlops_demo.data import generate_customers
from mlops_demo.model import build_model
from mlops_demo.predictor import Predictor
from mlops_demo.preprocessing import Preprocessor


def test_unknown_category_maps_to_oov_bucket():
    train = generate_customers(500, seed=1)
    pre = Preprocessor.fit(train)
    row = train.head(1).assign(contract="lifetime")
    assert pre.transform(row)["contract"][0, 0] == 0                      # OOV
    assert pre.transform(train.head(1))["contract"][0, 0] >= 1            # known category
    assert pre.unknown_categories({**row.iloc[0].to_dict()}) == ["contract"]


def test_preprocessor_serialization_roundtrip():
    pre = Preprocessor.fit(generate_customers(300, seed=2))
    assert Preprocessor.from_dict(pre.to_dict()) == pre


def test_model_outputs_probabilities():
    df = generate_customers(300, seed=3)
    pre = Preprocessor.fit(df)
    inputs = pre.transform(df)
    model = build_model(pre, inputs["numeric"], TrainConfig(hidden=(8,)))
    out = np.asarray(model.predict(inputs, verbose=0))
    assert out.shape == (300, 1)
    assert ((out >= 0) & (out <= 1)).all()


def test_bundle_loads_and_predicts_deterministically(artifacts):
    predictor = Predictor.load(registry.bundle_dir(artifacts, "v0001"))
    df = generate_customers(200, seed=11)[FEATURES]
    p1, p2 = predictor.predict_df(df), predictor.predict_df(df)
    assert p1.shape == (200,)
    assert np.array_equal(p1, p2)
    assert ((p1 >= 0) & (p1 <= 1)).all()


def test_unseen_category_does_not_crash_prediction(artifacts):
    predictor = Predictor.load(registry.bundle_dir(artifacts, "v0001"))
    row = generate_customers(1, seed=12)[FEATURES].assign(internet_service="satellite")
    prob = predictor.predict_df(row)
    assert 0 <= prob[0] <= 1


def test_prediction_independent_of_batch_composition(artifacts):
    """A row's prediction must not depend on which other rows share the batch."""
    predictor = Predictor.load(registry.bundle_dir(artifacts, "v0001"))
    df = generate_customers(50, seed=13)[FEATURES]
    batch = predictor.predict_df(df)
    single = np.array([predictor.predict_df(df.iloc[[i]])[0] for i in range(5)])
    assert np.allclose(batch[:5], single, atol=1e-5)
