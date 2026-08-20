import argparse
import os
import sys
import time
import numpy as np
import cv2

import torch
import torch.nn as nn
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

# ── constants ────────────────────────────────────────────────────────────────
LATENT_DIM   = 100
IMG_SIZE     = 28
CHANNELS     = 1
BATCH_SIZE   = 128
LR           = 0.0002
BETAS        = (0.5, 0.999)   # Adam betas — standard for GAN
GRID_ROWS    = 4
GRID_COLS    = 8              # 32 sample images in window
WEIGHTS_DIR  = "weights"
G_PATH       = os.path.join(WEIGHTS_DIR, "generator.pt")
D_PATH       = os.path.join(WEIGHTS_DIR, "discriminator.pt")

# ── models ───────────────────────────────────────────────────────────────────

class Generator(nn.Module):
    """Maps random noise → fake image."""
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(LATENT_DIM, 256),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(256, momentum=0.8),

            nn.Linear(256, 512),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(512, momentum=0.8),

            nn.Linear(512, 1024),
            nn.LeakyReLU(0.2),
            nn.BatchNorm1d(1024, momentum=0.8),

            nn.Linear(1024, IMG_SIZE * IMG_SIZE * CHANNELS),
            nn.Tanh(),   # output in [-1, 1]
        )

    def forward(self, z):
        img = self.net(z)
        return img.view(-1, CHANNELS, IMG_SIZE, IMG_SIZE)


class Discriminator(nn.Module):
    """Classifies image as real (1) or fake (0)."""
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(IMG_SIZE * IMG_SIZE * CHANNELS, 512),
            nn.LeakyReLU(0.2),

            nn.Linear(512, 256),
            nn.LeakyReLU(0.2),

            nn.Linear(256, 1),
            nn.Sigmoid(),
        )

    def forward(self, img):
        flat = img.view(img.size(0), -1)
        return self.net(flat)


# ── helpers ──────────────────────────────────────────────────────────────────

def get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def make_grid_image(G, device, fixed_noise):
    """Generate a grid of sample images for display."""
    G.eval()
    with torch.no_grad():
        fake = G(fixed_noise).cpu().numpy()  # (N, 1, 28, 28)
    G.train()

    # Denormalize [-1,1] → [0,255]
    fake = ((fake + 1) / 2 * 255).astype(np.uint8)

    rows = []
    for r in range(GRID_ROWS):
        cols = []
        for c in range(GRID_COLS):
            idx = r * GRID_COLS + c
            img = fake[idx, 0]             # (28, 28)
            img = cv2.resize(img, (84, 84), interpolation=cv2.INTER_NEAREST)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            cols.append(img_bgr)
        rows.append(np.hstack(cols))
    grid = np.vstack(rows)
    return grid  # (GRID_ROWS*84, GRID_COLS*84, 3)


def draw_hud(grid, epoch, total_epochs, d_loss, g_loss, elapsed):
    h, w = grid.shape[:2]
    hud_h = 56
    hud = np.zeros((hud_h, w, 3), dtype=np.uint8)

    texts = [
        f"Epoch: {epoch}/{total_epochs}",
        f"D loss: {d_loss:.4f}",
        f"G loss: {g_loss:.4f}",
        f"Time: {elapsed:.0f}s",
        "Q/ESC — quit   S — save weights",
    ]
    x = 12
    for i, t in enumerate(texts):
        cv2.putText(hud, t, (x, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                    (200, 200, 200), 1)
        x += 210 if i < 4 else 0

    return np.vstack([hud, grid])


def save_weights(G, D):
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    torch.save(G.state_dict(), G_PATH)
    torch.save(D.state_dict(), D_PATH)
    print(f"[INFO] Weights saved → {WEIGHTS_DIR}/")


def load_weights(G, D, device):
    if os.path.exists(G_PATH) and os.path.exists(D_PATH):
        G.load_state_dict(torch.load(G_PATH, map_location=device))
        D.load_state_dict(torch.load(D_PATH, map_location=device))
        print("[INFO] Weights loaded.")
        return True
    print("[WARN] No saved weights found.")
    return False


# ── training loop ─────────────────────────────────────────────────────────────

def train(args):
    device = get_device()
    print(f"[INFO] Device: {device}")

    # Data
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.5], [0.5]),   # → [-1, 1]
    ])
    dataset = datasets.MNIST("data", train=True, download=True, transform=transform)
    loader  = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)

    # Models
    G = Generator().to(device)
    D = Discriminator().to(device)

    if args.load:
        load_weights(G, D, device)

    opt_G = torch.optim.Adam(G.parameters(), lr=LR, betas=BETAS)
    opt_D = torch.optim.Adam(D.parameters(), lr=LR, betas=BETAS)
    criterion = nn.BCELoss()

    # Fixed noise for consistent visualization
    fixed_noise = torch.randn(GRID_ROWS * GRID_COLS, LATENT_DIM, device=device)

    cv2.namedWindow("GAN — MNIST", cv2.WINDOW_NORMAL)

    d_loss_val, g_loss_val = 0.0, 0.0
    start = time.time()

    print(f"[INFO] Training for {args.epochs} epochs. Press Q/ESC to stop.")

    for epoch in range(1, args.epochs + 1):
        for batch_idx, (real_imgs, _) in enumerate(loader):
            real_imgs = real_imgs.to(device)
            bs = real_imgs.size(0)

            real_labels = torch.ones(bs, 1, device=device)
            fake_labels = torch.zeros(bs, 1, device=device)

            # ── Train Discriminator ──────────────────────────────────────
            opt_D.zero_grad()
            d_real = criterion(D(real_imgs), real_labels)

            z = torch.randn(bs, LATENT_DIM, device=device)
            fake_imgs = G(z).detach()   # detach: don't update G here
            d_fake = criterion(D(fake_imgs), fake_labels)

            d_loss = (d_real + d_fake) / 2
            d_loss.backward()
            opt_D.step()

            # ── Train Generator ──────────────────────────────────────────
            opt_G.zero_grad()
            z = torch.randn(bs, LATENT_DIM, device=device)
            fake_imgs = G(z)
            # Generator wants D to classify its output as REAL
            g_loss = criterion(D(fake_imgs), real_labels)
            g_loss.backward()
            opt_G.step()

            d_loss_val = d_loss.item()
            g_loss_val = g_loss.item()

        # ── Update window every epoch ────────────────────────────────────
        grid  = make_grid_image(G, device, fixed_noise)
        frame = draw_hud(grid, epoch, args.epochs, d_loss_val, g_loss_val,
                         time.time() - start)
        cv2.imshow("GAN — MNIST", frame)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            print("[INFO] Interrupted by user.")
            break
        elif key == ord("s"):
            save_weights(G, D)

        print(f"Epoch {epoch:3d}/{args.epochs}  "
              f"D: {d_loss_val:.4f}  G: {g_loss_val:.4f}  "
              f"({time.time()-start:.0f}s)")

    save_weights(G, D)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# ── generate only (--load) ───────────────────────────────────────────────────

def generate_only(args):
    device = get_device()
    G = Generator().to(device)
    D = Discriminator().to(device)
    if not load_weights(G, D, device):
        print("[ERROR] Run without --load first to train the model.")
        sys.exit(1)

    fixed_noise = torch.randn(GRID_ROWS * GRID_COLS, LATENT_DIM, device=device)
    cv2.namedWindow("GAN — Generate", cv2.WINDOW_NORMAL)

    print("[INFO] Showing generated images. Press SPACE to regenerate, Q/ESC to quit.")
    while True:
        grid  = make_grid_image(G, device, fixed_noise)
        frame = draw_hud(grid, epoch="–", total_epochs="–",
                         d_loss=0, g_loss=0, elapsed=0)
        cv2.imshow("GAN — Generate", frame)
        key = cv2.waitKey(0) & 0xFF
        if key in (ord("q"), 27):
            break
        elif key == ord(" "):
            fixed_noise = torch.randn(GRID_ROWS * GRID_COLS, LATENT_DIM, device=device)

    cv2.destroyAllWindows()


# ── entry point ───────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="GAN MNIST Demo")
    p.add_argument("--epochs", type=int, default=30,
                   help="Number of training epochs (default: 30)")
    p.add_argument("--load", action="store_true",
                   help="Load saved weights and generate only (skip training)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.load:
        generate_only(args)
    else:
        train(args)
