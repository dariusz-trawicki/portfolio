"""Network definition and artifact-loading logic for serving."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn

from iris.features import CLASS_NAMES, Preprocessor


class IrisNet(nn.Module):
    def __init__(self, input_dim: int = 4, hidden_dim: int = 16, num_classes: int = 3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class Predictor:
    """Loads the model and preprocessor once, at process startup."""

    def __init__(self, artifact_dir: Path):
        checkpoint = torch.load(artifact_dir / "model.pt", map_location="cpu", weights_only=True)

        self.model = IrisNet(
            input_dim=checkpoint["input_dim"],
            hidden_dim=checkpoint["hidden_dim"],
            num_classes=checkpoint["num_classes"],
        )
        self.model.load_state_dict(checkpoint["state_dict"])
        self.model.eval()

        self.preprocessor = Preprocessor.load(artifact_dir / "preprocessor.json")
        self.model_version = checkpoint.get("model_version", "unknown")

    @torch.inference_mode()
    def predict(self, features: list[float]) -> tuple[str, float, list[float]]:
        x = np.array([features], dtype=np.float32)
        x = self.preprocessor.transform(x).astype(np.float32)
        logits = self.model(torch.from_numpy(x))
        probs = torch.softmax(logits, dim=1)[0]
        idx = int(torch.argmax(probs).item())
        return CLASS_NAMES[idx], float(probs[idx]), probs.tolist()
