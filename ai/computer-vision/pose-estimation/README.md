# Pose Estimation Demo

Real-time human pose estimation using **MediaPipe BlazePose**.  
Detects 33 body landmarks and computes joint angles (elbows, knees) live.

## What You'll See

- Full skeleton overlay with 33 landmarks
- Colour-coded connections (arms, legs, torso)
- Joint angles in degrees at elbows and knees
- FPS counter + visible landmark count

## Quick Start

```bash
# Webcam (default, full model)
uv run main.py

# Faster — lite model
uv run main.py --model lite

# From video file
uv run main.py --source path/to/video.mp4

# Lower detection threshold (noisier but more detections)
uv run main.py --min-confidence 0.3
```

## Controls

| Key | Action |
|-----|--------|
| `A` | Toggle joint angle display |
| `Q` / `ESC` | Quit |

## Model Options

| Flag | Complexity | Speed | Accuracy |
|------|-----------|-------|----------|
| `lite` | 0 | ★★★★★ | ★★★☆☆ |
| `full` | 1 | ★★★☆☆ | ★★★★☆ — **default** |
| `heavy` | 2 | ★★☆☆☆ | ★★★★★ |

## The 33 BlazePose Landmarks

```
         0 (nose)
    1  2  3  4  (eyes + ears)
         5 (mouth)
    11     12  (shoulders)
    13     14  (elbows)
    15     16  (wrists)
    17 19  18 20 (pinky/index fingers)
    21     22  (thumbs)
    23     24  (hips)
    25     26  (knees)
    27     28  (ankles)
    29 31  30 32 (heels + foot index)
```

Each landmark has `x`, `y`, `z` (depth) and `visibility` [0–1].

## How It Works

```
BGR frame
    │
    ▼
cv2.cvtColor → RGB          (MediaPipe expects RGB)
    │
    ▼
pose.process(rgb)
    │
    ▼
PoseLandmarks (33 × {x, y, z, visibility})
    │
    ├── draw_landmarks()     → skeleton overlay
    └── calculate_angle()    → angle at joint B given A–B–C
```

### Joint Angle Formula

```
angle = arccos( (BA · BC) / (|BA| × |BC|) )
```

Uses 2D `(x, y)` normalized coordinates. Angle is at the **middle** landmark (B).

### BlazePose vs Alternatives

| | MediaPipe BlazePose | OpenPose | MoveNet |
|---|---|---|---|
| Landmarks | 33 | 25 / 135 | 17 |
| 3D depth | ✓ | ✗ | ✗ |
| CPU real-time | ✓ | ✗ (slow) | ✓ |
| GPU needed | No | Yes (fast mode) | No |
| License | Apache 2.0 | Non-commercial | Apache 2.0 |

## Requirements

- Python 3.10+
- `mediapipe` — includes the pre-trained BlazePose model
- `opencv-python`

> **macOS camera permissions**: System Settings → Privacy & Security → Camera → Terminal ✓

> **Note**: `mediapipe` bundles its own native libs — no separate model download needed.
