import numpy as np
import json
from pathlib import Path

# --- Parameters ---
AUGMENTATIONS_PER_SAMPLE = 10
OUTPUT_DIR = Path("keypoints")
NOISE_STD = 0.005          # Gaussian noise
SCALE_RANGE = (0.9, 1.1)   # scaling ±10%
TEMPO_RANGE = (0.8, 1.2)   # tempo change ±20%

rng = np.random.default_rng(42)

# --- Load data ---
X = np.load(OUTPUT_DIR / "dataset.npy")        # (3, 90, 225)
with open(OUTPUT_DIR / "labels.json") as f:
    labels = json.load(f)

N, T, F = X.shape  # 3, 90, 225


# --- Transforms ---
def add_noise(seq):
    return seq + rng.normal(0, NOISE_STD, seq.shape)


def scale(seq):
    factor = rng.uniform(*SCALE_RANGE)
    return seq * factor


def change_tempo(seq):
    factor = rng.uniform(*TEMPO_RANGE)
    original_len = seq.shape[0]
    new_len = max(1, int(original_len * factor))
    indices = np.linspace(0, original_len - 1, new_len)
    resampled = np.array([
        seq[int(i)] * (1 - (i % 1)) + seq[min(int(i) + 1, original_len - 1)] * (i % 1)
        for i in indices
    ])
    # resample back to 90 frames
    indices_back = np.linspace(0, new_len - 1, original_len)
    result = np.array([
        resampled[int(i)] * (1 - (i % 1)) + resampled[min(int(i) + 1, new_len - 1)] * (i % 1)
        for i in indices_back
    ])
    return result


def flip_horizontal(seq):
    # mirror: x → 1 - x, every 3rd value (x, y, z) — flip x
    flipped = seq.copy()
    flipped[:, 0::3] = 1.0 - flipped[:, 0::3]
    return flipped


TRANSFORMS = [add_noise, scale, change_tempo, flip_horizontal]


# --- Augmentation ---
X_aug = [X]          # original samples are always kept
y_aug = list(range(N))

for class_idx in range(N):
    original = X[class_idx]  # (90, 225)
    for i in range(AUGMENTATIONS_PER_SAMPLE):
        sample = original.copy()
        # randomly apply 1-3 transforms
        chosen = rng.choice(TRANSFORMS, size=rng.integers(1, 4), replace=False)
        for transform in chosen:
            sample = transform(sample)
        X_aug.append(sample[np.newaxis])
        y_aug.append(class_idx)

X_aug = np.concatenate(X_aug, axis=0)  # (33, 90, 225)
y_aug = np.array(y_aug)

# --- Save ---
np.save(OUTPUT_DIR / "dataset_aug.npy", X_aug)
np.save(OUTPUT_DIR / "labels_aug.npy", y_aug)

print(f"Original samples:  {N}")
print(f"After augmentation: {len(X_aug)}")
print(f"Tensor shape:      {X_aug.shape}")
print(f"Class distribution: {np.bincount(y_aug)}")
print(f"Saved: {OUTPUT_DIR}/dataset_aug.npy")
print(f"Saved: {OUTPUT_DIR}/labels_aug.npy")
