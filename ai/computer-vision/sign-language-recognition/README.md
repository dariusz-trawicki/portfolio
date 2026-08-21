# Sign Language Recognition — Demo

Polish Sign Language (PJM) recognition proof-of-concept.

## What it does

Extracts body and hand keypoints from video using MediaPipe, trains a 1D CNN
classifier to recognize PJM signs.

## Pipeline

```
video (.mp4) → keypoints extraction → tensor (N, 90, 225) → 1D CNN → sign label
```

## Project structure

```
.
├── azure/
│   ├── terraform/                    # IaC (Resource Group, Storage, ML Workspace)
│   ├── conda.yml                     # Python environment definition
│   ├── job.yml                       # Azure ML Job configuration
│   └── train_classifier_azure.py     # training script adapted for Azure ML
│
├── data/videos/                      # source videos
│   ├── 01_czesc.mp4
│   ├── 02_dzien_dobry.mp4
│   └── 03_dobry_wieczor.mp4
│
├── keypoints/                        # extracted data
│   ├── dataset.npy                   # tensor (N, 90, 225)
│   ├── dataset_aug.npy               # augmented tensor (33, 90, 225)
│   ├── labels.json                   # class names
│   ├── labels_aug.npy                # numeric labels for augmented dataset
│   └── model_cnn.pt                  # trained model weights
│
├── .amlignore                        # excludes terraform/ from Azure ML upload
├── extract_keypoints.py              # keypoint extraction script
├── augment.py                        # data augmentation script
├── train_classifier_local.py         # model training script
└── README.md
```

## Feature vector (225 float32 per frame)

```
pose   33 × (x, y, z) =  99
left   21 × (x, y, z) =  63
right  21 × (x, y, z) =  63
──────────────────────────────
total                    225
```

Each frame of video is converted into a flat array of 225 numbers:

- `Pose` — 33 body landmarks (shoulders, elbows, hips, etc.) × 3 coordinates (x, y, z) = 99 values
- `Left hand` — 21 hand landmarks × 3 = 63 values
- `Right hand` — 21 hand landmarks × 3 = 63 values

All detected by `MediaPipe`. Coordinates are normalized — x=0.0 is the left edge of the frame, x=1.0 is the right edge, same for y. This makes the vector independent of video resolution.

If a hand is not visible in a frame (e.g. only one hand used in the gesture), those 63 values are filled with zeros.

One gesture recording = 90 frames × 225 floats.


## Setup

Requires Python 3.10+, [uv](https://github.com/astral-sh/uv).

## Usage

**1. Extract keypoints**
```bash
uv run extract_keypoints.py --input data/videos/ --output keypoints/
```

With live preview:
```bash
uv run extract_keypoints.py --input data/videos/ --output keypoints/ --visualize
```

Save annotated video:
```bash
uv run extract_keypoints.py --input data/videos/ --output keypoints/ --save_video
```

**2. Augment data**

Generates 10 augmented samples per class → tensor (33, 90, 225).
```bash
uv run augment.py
```

---

### Option 1 — local

**3. Train model**
```bash
uv run train_classifier_local.py
# Epoch  20 | loss: 0.0437 | train: 1.00 | val: 1.00
# ...
# Epoch 200 | loss: 0.0001 | train: 1.00 | val: 1.00
```

---

### Option 2 — Azure ML

**3. Prepare Azure environment**
```bash
cd azure/terraform
terraform init
terraform plan
terraform apply
# Outputs:
# resource_group  = "rg-pjm-ml"
# storage_account = "dartitpjmmlstorage"
# workspace_name  = "pjm-workspace-6"
```

**4. Upload data to Blob Storage**
```bash
cd ../..
az storage blob upload-batch \
  --account-name dartitpjmmlstorage \
  --destination keypoints \
  --source keypoints/
```

**5. Create job**
```bash
cd azure
az ml job create \
  --file job.yml \
  --resource-group rg-pjm-ml \
  --workspace-name pjm-workspace-6
# ...
#   "name": "<job-name>",
# ...
```

**6. Monitor job**
```bash
az ml job show \
  --name <job-name> \
  --resource-group rg-pjm-ml \
  --workspace-name pjm-workspace-6 \
  --query status

az ml job stream \
  --name <job-name> \
  --resource-group rg-pjm-ml \
  --workspace-name pjm-workspace-6
```

Or open in browser:
```bash
open "https://ml.azure.com/runs/<job-name>?wsid=/subscriptions/b81de34a-705b-4253-a664-6bed9ca398bb/resourcegroups/rg-pjm-ml/workspaces/pjm-workspace-6"
```

Navigate to: **Default Directory → pjm-workspace-6 → Jobs → sign-language-recognition → pjm-cnn-train**

Wait for status **Running**, then check the **Metrics** tab for training results.

---

## Model

1D CNN trained on keypoint sequences:

```
Conv1d(225→128) → ReLU → Dropout(0.3)
Conv1d(128→64)  → ReLU
AdaptiveAvgPool1d(1)
Linear(64→num_classes)
```

## Current results

| Video | Frames | Left hand | Right hand |
|---|---|---|---|
| 01_czesc | 75 | 4% | 46% |
| 02_dzien_dobry | 150 | 56% | 34% |
| 03_dobry_wieczor | 100 | 71% | 35% |

Training accuracy: 1.00 (3 classes, memorization expected at this dataset size).

## Limitations

- 3 classes only — not enough for real generalization
- Single recording per class — no true train/val split possible
- Augmented validation is not independent from training data

## Environment

- macOS arm64 (Apple Silicon M1 Max)
- Python 3.11 via uv
- MediaPipe 0.10.x
- PyTorch 2.x

## About PJM

Polish Sign Language (Polski Język Migowy) is an autonomous visual-spatial
language, not a signed version of Polish. It has its own grammar, spatial
syntax, and simultaneous morphology with no written form.

## Data

Source videos are from YouTube:
- https://www.youtube.com/watch?v=kAPkLzE4gpI
