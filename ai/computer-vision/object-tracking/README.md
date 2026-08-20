# Object Tracking Demo

Real-time multi-object tracking using OpenCV's built-in tracker algorithms.  
Select any region of interest (ROI) with your mouse — track multiple objects simultaneously.

## Algorithms

| Tracker | Speed | Accuracy | Notes |
|---------|-------|----------|-------|
| **CSRT** | Medium | ★★★★★ | Best accuracy, handles scale changes — default choice |
| **KCF** | Fast | ★★★★☆ | Good balance of speed and accuracy |
| **MOSSE** | Very fast | ★★★☆☆ | Minimal CPU, good for fast motion |
| **MIL** | Slow | ★★★☆☆ | Robust to partial occlusion |

## Quick Start

```bash
# Webcam (default)
uv run main.py

# With specific tracker
uv run main.py --tracker KCF

# From video file
uv run main.py --source path/to/video.mp4
```

## Controls

| Key | Action |
|-----|--------|
| `S` | Select new ROI (draw a box with mouse) |
| `C` | Clear all trackers |
| `Q` / `ESC` | Quit |

You can track multiple objects — press `S` repeatedly to add more.

## How It Works

```
Frame → Tracker.update(frame) → bounding box (x, y, w, h) + success flag
                ↑
         Tracker.init(frame, roi)  ← called once on ROI selection
```

**CSRT** (Channel and Spatial Reliability Tracking) uses spatial reliability maps to focus  
on parts of the object that are reliably distinguishable from the background.  
It updates its internal model every frame — no re-detection step needed.

## Requirements

- Python 3.10+
- `opencv-contrib-python` — includes legacy and extra tracker modules
- Webcam or video file

> **macOS camera permissions**: System Settings → Privacy & Security → Camera → Terminal ✓
