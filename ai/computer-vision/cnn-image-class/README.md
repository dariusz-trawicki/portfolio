# CNN Image Classification (MNIST)

## Overview
Convolutional Neural Network trained from scratch on the MNIST handwritten digits dataset.
Demonstrates the core CNN pipeline: spatial feature extraction → pooling → classification.

## Problem
Given a 28×28 grayscale image of a handwritten digit, predict the correct class (0–9).

## Architecture

```
Input: (1, 28, 28)
↓
Block 1: Conv2d(1→32) + BN + ReLU × 2 → MaxPool2d(2) → (32, 14, 14)
↓
Block 2: Conv2d(32→64) + BN + ReLU × 2 → MaxPool2d(2) → (64, 7, 7)
↓
Block 3: Conv2d(64→128) + BN + ReLU → MaxPool2d(2) → (128, 3, 3)
↓
Flatten → Linear(1152→256) → ReLU → Dropout(0.5)
↓
Linear(256→10) → CrossEntropyLoss
```

| Component | Role |
|-----------|------|
| `Conv2d` | Slides a learnable filter over the image to detect local patterns |
| `BatchNorm` | Normalises activations, stabilises and speeds up training |
| `MaxPool2d(2)` | Halves spatial dimensions, reduces parameters and adds translation invariance |
| `Dropout` | Randomly zeros activations during training to prevent overfitting |

## Training Details
| Setting | Value |
|---------|-------|
| Optimizer | Adam + weight decay 1e-4 |
| Scheduler | OneCycleLR (warm-up → peak → cool-down) |
| Loss | CrossEntropyLoss |
| Augmentation | RandomCrop(28, padding=4) |
| Epochs (default) | 20 |
| Batch size | 128 |
| Device | MPS / CUDA / CPU (auto) |

## Dataset — MNIST
- 60,000 training / 10,000 test images
- 28×28 px, single channel (grayscale)
- Classes: digits 0–9
- Downloaded automatically on first run (~11 MB)

## Results
~99% test accuracy after 20 epochs on Apple Silicon MPS.

## Usage
```bash
uv run main.py              # train for 20 epochs
uv run main.py --epochs 30  # longer training
uv run main.py --lr 5e-4    # custom learning rate
```

## Live Output
- **Training window** — loss and accuracy curves (train vs val) updated after each epoch
- **Prediction grid** — 4×4 sample predictions after training; green = correct, red = incorrect
