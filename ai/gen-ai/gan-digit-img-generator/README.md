# GAN Demo — MNIST Handwritten Digits

Example of a **Generative Adversarial Network** (GAN) demonstration – a network that learns to generate handwritten digits (0-9) from the MNIST dataset (60,000 grayscale digit images, 28x28 pixels).

## Quick Start

```bash
# Train for 30 epochs (default) — shows live window
uv run main.py

# Train longer for better results
uv run main.py --epochs 100

# Load saved weights and generate only (no training)
uv run main.py --load
```

## Controls

| Key | Action |
|-----|--------|
| `S` | Save weights to `weights/` |
| `Q` / `ESC` | Stop training and quit |
| `SPACE` | (generate-only mode) new random batch |

## What You'll See

A grid of **32 generated digit images** (4 rows × 8 columns) that updates every epoch.

- **Epoch 1–5**: blurry noise, barely recognizable shapes
- **Epoch 10–20**: digits start to appear
- **Epoch 30+**: fairly clean handwritten-style digits

HUD shows: current epoch, Discriminator loss, Generator loss, elapsed time.

## Architecture

```
TRAINING INPUT
  Real images (MNIST)  ──────────────────────────┐
                                                  ▼
  Noise z ~ N(0,1)  ──► Generator ──► Fake imgs ──► Discriminator ──► real / fake
  (100,)               (28×28)                        (binary)
```

### Generator
```
z (100,) → Linear(256) → BN → LeakyReLU
         → Linear(512) → BN → LeakyReLU
         → Linear(1024) → BN → LeakyReLU
         → Linear(784) → Tanh → reshape (1, 28, 28)
```

### Discriminator
```
img (784,) → Linear(512) → LeakyReLU
           → Linear(256) → LeakyReLU
           → Linear(1)   → Sigmoid → P(real)
```

### Loss (Binary Cross-Entropy)

```
D loss = BCE(D(real), 1) + BCE(D(G(z)), 0)   # D wants real=1, fake=0
G loss = BCE(D(G(z)), 1)                      # G wants D to think fake=1
```

The two networks compete — D gets better at spotting fakes,  
G gets better at creating convincing images. **Equilibrium** = good generation.

### Why LeakyReLU?

Standard ReLU kills gradients for negative values ("dying ReLU").  
LeakyReLU lets a small gradient through (`0.2x` for negatives) — critical for stable GAN training.

### Why Tanh on Generator output?

MNIST pixels normalized to `[-1, 1]` — Tanh matches that range exactly.  
Using Sigmoid here would cause training instability.

## Saved Weights

After training, weights are saved to:
```
weights/
  generator.pt
  discriminator.pt
```

Load them anytime with `uv run main.py --load` — no retraining needed.

## GAN vs Diffusion Models

| | GAN | Diffusion (e.g. Stable Diffusion) |
|---|---|---|
| Training | Two competing networks | Single network, noise prediction |
| Speed | Fast inference | Slow (many denoising steps) |
| Quality | Good, can have mode collapse | State-of-the-art |
| Control | Harder to control | Easy (CFG, ControlNet) |
| Year | 2014 (Goodfellow) | 2020+ |

## Requirements

- Python 3.10+
- `torch` + `torchvision` — MNIST download + training
- `opencv-python` — live display window
- Apple Silicon: uses MPS automatically (`torch.backends.mps`)
- MNIST dataset downloaded automatically to `data/` on first run (~11MB)
