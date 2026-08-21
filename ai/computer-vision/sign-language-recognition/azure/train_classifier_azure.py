import argparse
import json

import mlflow
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, random_split

# --- Args ---
parser = argparse.ArgumentParser()
parser.add_argument("--data_dir",   type=str, default="keypoints")
parser.add_argument("--epochs",     type=int, default=200)
parser.add_argument("--batch_size", type=int, default=8)
parser.add_argument("--lr",         type=float, default=1e-3)
args = parser.parse_args()

# --- Data ---
X = np.load(f"{args.data_dir}/dataset_aug.npy")   # (33, 90, 225)
y = np.load(f"{args.data_dir}/labels_aug.npy")    # (33,)
with open(f"{args.data_dir}/labels.json") as f:
    labels = json.load(f)

num_classes = len(labels)

X_t = torch.tensor(X, dtype=torch.float32)
y_t = torch.tensor(y, dtype=torch.long)

dataset    = TensorDataset(X_t, y_t)
train_size = int(0.8 * len(dataset))
val_size   = len(dataset) - train_size
train_ds, val_ds = random_split(
    dataset, [train_size, val_size],
    generator=torch.Generator().manual_seed(42)
)

train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
val_loader   = DataLoader(val_ds,   batch_size=args.batch_size)

# --- Model ---
class SignCNN(nn.Module):
    def __init__(self, in_features=225, num_classes=3):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(in_features, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Conv1d(128, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.clf = nn.Linear(64, num_classes)

    def forward(self, x):
        x = x.permute(0, 2, 1)
        x = self.net(x).squeeze(-1)
        return self.clf(x)

model     = SignCNN(num_classes=num_classes)
optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
criterion = nn.CrossEntropyLoss()

# --- Evaluation ---
def evaluate(loader):
    model.eval()
    correct = total = 0
    with torch.no_grad():
        for xb, yb in loader:
            pred = model(xb).argmax(1)
            correct += (pred == yb).sum().item()
            total   += len(yb)
    return correct / total

# --- Training ---
mlflow.start_run()
mlflow.log_params({
    "epochs":     args.epochs,
    "batch_size": args.batch_size,
    "lr":         args.lr,
    "num_classes": num_classes,
})

for epoch in range(args.epochs):
    model.train()
    for xb, yb in train_loader:
        loss = criterion(model(xb), yb)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    if (epoch + 1) % 20 == 0:
        train_acc = evaluate(train_loader)
        val_acc   = evaluate(val_loader)
        print(f"Epoch {epoch+1:3d} | loss: {loss.item():.4f} | "
              f"train: {train_acc:.2f} | val: {val_acc:.2f}")
        mlflow.log_metrics({
            "loss":      loss.item(),
            "train_acc": train_acc,
            "val_acc":   val_acc,
        }, step=epoch + 1)

mlflow.end_run()

# --- Save ---
import os
os.makedirs("outputs", exist_ok=True)
torch.save(model.state_dict(), "outputs/model_cnn.pt")
print("\nModel saved: outputs/model_cnn.pt")
print("Classes:", labels)
