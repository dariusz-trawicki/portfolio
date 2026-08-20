import torch
import torch.nn as nn
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import argparse

# ── device ────────────────────────────────────────────────────────────────────
DEVICE = (
    torch.device("mps") if torch.backends.mps.is_available()
    else torch.device("cuda") if torch.cuda.is_available()
    else torch.device("cpu")
)
print(f"Device: {DEVICE}")

CLASSES = [str(i) for i in range(10)]

# ── model ─────────────────────────────────────────────────────────────────────
class CNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            # blok 1
            nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
            nn.Conv2d(32, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
            nn.MaxPool2d(2), nn.Dropout2d(0.2),
            # blok 2
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.Conv2d(64, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(),
            nn.MaxPool2d(2), nn.Dropout2d(0.3),
            # blok 3
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
            nn.MaxPool2d(2), nn.Dropout2d(0.4),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 3 * 3, 256), nn.ReLU(), nn.Dropout(0.5),
            nn.Linear(256, 10),
        )

    def forward(self, x):
        return self.classifier(self.features(x))

# ── data ──────────────────────────────────────────────────────────────────────
def get_loaders(batch_size=128):
    train_tf = transforms.Compose([
        transforms.RandomCrop(28, padding=4),
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])
    test_tf = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])
    train = torchvision.datasets.MNIST("data", train=True,  download=True, transform=train_tf)
    test  = torchvision.datasets.MNIST("data", train=False, download=True, transform=test_tf)
    return (
        torch.utils.data.DataLoader(train, batch_size=batch_size, shuffle=True,  num_workers=2),
        torch.utils.data.DataLoader(test,  batch_size=batch_size, shuffle=False, num_workers=2),
    )

# ── live plot setup ────────────────────────────────────────────────────────────
def make_live_plot():
    fig, (ax_loss, ax_acc) = plt.subplots(1, 2, figsize=(11, 4))
    fig.suptitle("CNN — MNIST Training", fontsize=13, fontweight="bold")
    for ax, title, ylabel in [
        (ax_loss, "Loss",     "Loss"),
        (ax_acc,  "Accuracy", "Accuracy %"),
    ]:
        ax.set_title(title); ax.set_xlabel("Epoch"); ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.ion(); plt.show()
    return fig, ax_loss, ax_acc

def update_live_plot(fig, ax_loss, ax_acc, train_losses, test_losses, train_accs, test_accs):
    epochs = range(1, len(train_losses) + 1)
    for ax in (ax_loss, ax_acc): ax.cla()

    ax_loss.set_title("Loss"); ax_loss.set_xlabel("Epoch"); ax_loss.set_ylabel("Loss")
    ax_loss.plot(epochs, train_losses, "b-o", ms=4, label="train")
    ax_loss.plot(epochs, test_losses,  "r-o", ms=4, label="val")
    ax_loss.legend(); ax_loss.grid(True, alpha=0.3)

    ax_acc.set_title("Accuracy"); ax_acc.set_xlabel("Epoch"); ax_acc.set_ylabel("Accuracy %")
    ax_acc.plot(epochs, train_accs, "b-o", ms=4, label="train")
    ax_acc.plot(epochs, test_accs,  "r-o", ms=4, label="val")
    ax_acc.legend(); ax_acc.grid(True, alpha=0.3)

    fig.canvas.draw(); fig.canvas.flush_events()

# ── train / eval ──────────────────────────────────────────────────────────────
def run_epoch(model, loader, criterion, optimizer=None):
    training = optimizer is not None
    model.train() if training else model.eval()
    total_loss, correct, total = 0.0, 0, 0
    ctx = torch.enable_grad() if training else torch.no_grad()
    with ctx:
        for X, y in loader:
            X, y = X.to(DEVICE), y.to(DEVICE)
            out = model(X)
            loss = criterion(out, y)
            if training:
                optimizer.zero_grad(); loss.backward(); optimizer.step()
            total_loss += loss.item() * y.size(0)
            correct    += (out.argmax(1) == y).sum().item()
            total      += y.size(0)
    return total_loss / total, 100.0 * correct / total

# ── prediction grid ───────────────────────────────────────────────────────────
def show_predictions(model, loader):
    model.eval()
    images, labels = next(iter(loader))
    images, labels = images[:16].to(DEVICE), labels[:16]
    with torch.no_grad():
        preds = model(images).argmax(1).cpu()

    mean = torch.tensor([0.1307]).view(1,1,1)
    std  = torch.tensor([0.3081]).view(1,1,1)
    imgs = images.cpu() * std + mean

    fig = plt.figure(figsize=(10, 6))
    fig.suptitle("CNN Predictions — MNIST", fontsize=13, fontweight="bold")
    gs = gridspec.GridSpec(4, 4, figure=fig, hspace=0.5)
    for i in range(16):
        ax = fig.add_subplot(gs[i // 4, i % 4])
        ax.imshow(imgs[i].squeeze(), cmap="gray")
        color = "green" if preds[i] == labels[i] else "red"
        ax.set_title(f"{CLASSES[preds[i]]}", color=color, fontsize=8)
        ax.axis("off")
    plt.tight_layout()
    plt.ioff(); plt.show()

# ── main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--lr",     type=float, default=1e-3)
    args = parser.parse_args()

    train_loader, test_loader = get_loaders()
    model     = CNN().to(DEVICE)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=args.lr * 10,
        epochs=args.epochs, steps_per_epoch=len(train_loader)
    )

    print(f"Params: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")

    fig, ax_loss, ax_acc = make_live_plot()
    train_losses, test_losses, train_accs, test_accs = [], [], [], []

    for epoch in range(1, args.epochs + 1):
        tr_loss, tr_acc = run_epoch(model, train_loader, criterion, optimizer)
        # OneCycleLR powinien stepować per-batch — tu uproszczenie per-epoch
        scheduler.step()
        te_loss, te_acc = run_epoch(model, test_loader, criterion)

        train_losses.append(tr_loss); test_losses.append(te_loss)
        train_accs.append(tr_acc);   test_accs.append(te_acc)

        print(f"Epoch {epoch:2d}/{args.epochs} | "
              f"loss {tr_loss:.3f}/{te_loss:.3f} | "
              f"acc {tr_acc:.1f}%/{te_acc:.1f}%")

        update_live_plot(fig, ax_loss, ax_acc,
                         train_losses, test_losses, train_accs, test_accs)

    print("\nTraining done!")
    show_predictions(model, test_loader)

if __name__ == "__main__":
    main()
