import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, random_split
import json

# --- Data ---
X = np.load("keypoints/dataset_aug.npy")       # (33, 90, 225)
y = np.load("keypoints/labels_aug.npy")        # (33,)
with open("keypoints/labels.json") as f:
    labels = json.load(f)

X_t = torch.tensor(X, dtype=torch.float32)
y_t = torch.tensor(y, dtype=torch.long)

dataset = TensorDataset(X_t, y_t)

train_size = int(0.8 * len(dataset))
val_size   = len(dataset) - train_size
train_ds, val_ds = random_split(dataset, [train_size, val_size],
                                generator=torch.Generator().manual_seed(42))

train_loader = DataLoader(train_ds, batch_size=8, shuffle=True)
val_loader   = DataLoader(val_ds,   batch_size=8)

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

model     = SignCNN()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
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
for epoch in range(200):
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

torch.save(model.state_dict(), "keypoints/model_cnn.pt")
print("\nModel saved: keypoints/model_cnn.pt")
print("Classes:", labels)
