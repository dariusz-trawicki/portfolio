"""Synthetic housing-price dataset. The `drift` knob simulates a market shift."""
import numpy as np
import pandas as pd

from .config import TRAIN_PATH

FEATURES = ["area_m2", "rooms", "age_years", "distance_center_km", "floor", "has_balcony"]
TARGET = "price_kpln"


def make_dataset(n: int, seed: int = 0, drift: float = 0.0) -> pd.DataFrame:
    """Generate `n` rows. drift=0 -> baseline distribution, drift=1 -> strong shift.

    Data drift:    larger, newer flats closer to the city centre.
    Concept drift: higher price per m2 and a stronger city-centre premium, so a model
                   trained on the old market is wrong even for familiar feature values.
    """
    rng = np.random.default_rng(seed)
    area = np.clip(rng.normal(60 + 25 * drift, 20, n), 20, 250)
    rooms = np.clip(np.round(area / 22 + rng.normal(0, 0.6, n)), 1, 8)
    age = rng.uniform(0, 80, n) * (1 - 0.5 * drift)
    dist = rng.gamma(2.0, 3.0 - 1.5 * drift, n)
    floor = rng.integers(1, 16, n)
    balcony = rng.binomial(1, 0.55, n)

    center_premium = 0.8 + 0.7 * drift
    price_per_sqm = (
        10.0
        * (1 + center_premium * np.exp(-dist / 4))
        * (1 - 0.004 * age)
        * (1 + 0.03 * balcony)
        * (1 + 0.01 * floor)
        * (1 + 0.30 * drift)
    )
    price = area * price_per_sqm * rng.lognormal(0, 0.05, n)

    df = pd.DataFrame(
        {
            "area_m2": area,
            "rooms": rooms,
            "age_years": age,
            "distance_center_km": dist,
            "floor": floor,
            "has_balcony": balcony,
            TARGET: price,
        }
    )
    df[FEATURES] = df[FEATURES].astype("float64")
    return df.round(3)


def ensure_baseline() -> None:
    """Create the baseline training set if it does not exist yet."""
    if not TRAIN_PATH.exists():
        TRAIN_PATH.parent.mkdir(parents=True, exist_ok=True)
        make_dataset(6000, seed=1, drift=0.0).to_csv(TRAIN_PATH, index=False)
