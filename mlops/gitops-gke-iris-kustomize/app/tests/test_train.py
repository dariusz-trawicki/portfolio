import json

from iris.train import train


def test_train_produces_artifacts_and_reasonable_accuracy(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_URI", f"file://{tmp_path}")

    result = train(epochs=100, model_version="test-version")
    assert result["metrics"]["accuracy"] > 0.8

    artifact_dir = tmp_path / "test-version"
    assert (artifact_dir / "model.pt").exists()
    assert (artifact_dir / "preprocessor.json").exists()

    metrics = json.loads((artifact_dir / "metrics.json").read_text())
    assert metrics["accuracy"] > 0.8
