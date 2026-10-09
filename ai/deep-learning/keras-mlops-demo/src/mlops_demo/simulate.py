"""Traffic simulator: sends requests to the API (via TestClient, no network server needed).

    python -m mlops_demo.simulate --n 1500 --drift 0.0 --reset   # "normal" traffic
    python -m mlops_demo.simulate --n 1500 --drift 0.8 --reset   # traffic after the world changed

Because the data is synthetic we know the true labels and can show right away how
drift affects quality. In real life labels arrive with a delay.
"""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path

# Library-level notice from Starlette about its test client; irrelevant to this project.
warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`")

from fastapi.testclient import TestClient  # noqa: E402
from sklearn.metrics import roc_auc_score

from .config import ARTIFACTS_DIR, FEATURES, TARGET
from .data import generate_customers
from .serve import create_app


def simulate(artifacts: Path, log_path: Path, n: int, drift: float, seed: int, chunk: int = 100) -> dict:
    df = generate_customers(n, seed=seed, drift=drift)
    probs: list[float] = []
    with TestClient(create_app(artifacts, log_path)) as client:
        for i in range(0, n, chunk):
            part = df[FEATURES].iloc[i:i + chunk].to_dict("records")
            resp = client.post("/predict/batch", json={"customers": part})
            resp.raise_for_status()
            probs += [p["churn_probability"] for p in resp.json()["predictions"]]
    return {"n": n, "drift": drift, "auc": float(roc_auc_score(df[TARGET], probs)),
            "churn_rate": float(df[TARGET].mean()), "mean_prob": float(sum(probs) / len(probs))}


def main() -> None:
    parser = argparse.ArgumentParser(description="Production traffic simulator")
    parser.add_argument("--artifacts", default=str(ARTIFACTS_DIR))
    parser.add_argument("--n", type=int, default=1500)
    parser.add_argument("--drift", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=777, help="different from the training seed: these are NEW customers")
    parser.add_argument("--reset", action="store_true", help="clear the prediction log before simulating")
    args = parser.parse_args()

    artifacts = Path(args.artifacts)
    log_path = artifacts / "prediction_log.jsonl"
    if args.reset and log_path.exists():
        log_path.unlink()
    r = simulate(artifacts, log_path, args.n, args.drift, args.seed)
    print(f"sent {r['n']} requests (drift={r['drift']}): AUC {r['auc']:.4f} | "
          f"observed churn {r['churn_rate']:.1%} vs mean predicted {r['mean_prob']:.1%}")


if __name__ == "__main__":
    main()
