"""Iris model training.

Run as a standalone job (locally, as a Kubernetes Job, or a
Vertex AI Custom Job) — never as part of the CI that builds the API image.
Saves model.pt, preprocessor.json and metrics.json under ARTIFACT_URI/{version}/.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.datasets import load_iris
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from torch import nn

from iris.features import Preprocessor
from iris.model import IrisNet
from iris.storage import upload_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("train")

SEED = 42


def train(
    epochs: int = 200,
    lr: float = 0.01,
    hidden_dim: int = 16,
    model_version: str | None = None,
) -> dict:
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    data = load_iris()
    x_train, x_test, y_train, y_test = train_test_split(
        data.data, data.target, test_size=0.2, random_state=SEED, stratify=data.target
    )

    preprocessor = Preprocessor.fit(x_train)
    x_train_t = torch.tensor(preprocessor.transform(x_train), dtype=torch.float32)
    y_train_t = torch.tensor(y_train, dtype=torch.long)
    x_test_t = torch.tensor(preprocessor.transform(x_test), dtype=torch.float32)

    model = IrisNet(input_dim=4, hidden_dim=hidden_dim, num_classes=3)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()

    model.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        loss = loss_fn(model(x_train_t), y_train_t)
        loss.backward()
        optimizer.step()
        if epoch % 50 == 0:
            log.info("epoch %d, loss %.4f", epoch, loss.item())

    model.eval()
    with torch.inference_mode():
        preds = torch.argmax(model(x_test_t), dim=1).numpy()

    metrics = {
        "accuracy": accuracy_score(y_test, preds),
        "f1_macro": f1_score(y_test, preds, average="macro"),
        "n_train": len(y_train),
        "n_test": len(y_test),
        "trained_at": int(time.time()),
    }
    log.info("metrics: %s", metrics)

    version = model_version or str(int(time.time()))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        torch.save(
            {
                "state_dict": model.state_dict(),
                "input_dim": 4,
                "hidden_dim": hidden_dim,
                "num_classes": 3,
                "model_version": version,
            },
            tmp_path / "model.pt",
        )
        preprocessor.save(tmp_path / "preprocessor.json")
        (tmp_path / "metrics.json").write_text(json.dumps(metrics, indent=2))

        artifact_uri = os.environ["ARTIFACT_URI"].rstrip("/") + f"/{version}/"
        upload_dir(tmp_path, artifact_uri)
        log.info("artifacts saved to %s", artifact_uri)

    return {"version": version, "artifact_uri": artifact_uri, "metrics": metrics}


if __name__ == "__main__":
    train()
