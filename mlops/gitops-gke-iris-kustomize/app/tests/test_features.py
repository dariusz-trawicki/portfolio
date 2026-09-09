import numpy as np

from iris.features import Preprocessor


def test_fit_transform_normalizes_to_zero_mean():
    x = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    prep = Preprocessor.fit(x)
    assert np.allclose(prep.transform(x).mean(axis=0), 0, atol=1e-6)


def test_save_and_load_roundtrip(tmp_path):
    x = np.array([[1.0, 2.0], [3.0, 4.0]])
    prep = Preprocessor.fit(x)
    path = tmp_path / "preprocessor.json"
    prep.save(path)
    loaded = Preprocessor.load(path)
    assert loaded.mean == prep.mean
    assert loaded.std == prep.std


def test_zero_std_does_not_divide_by_zero():
    x = np.array([[1.0, 5.0], [1.0, 7.0]])
    prep = Preprocessor.fit(x)
    assert np.isfinite(prep.transform(x)).all()
