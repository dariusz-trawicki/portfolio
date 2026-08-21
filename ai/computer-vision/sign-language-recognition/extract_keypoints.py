"""
extract_keypoints.py
──────────────────────────
Keypoint extraction from PJM video files — MediaPipe 0.10.x (arm64 / Apple Silicon).

Usage:
    uv run extract_keypoints.py --input data/videos/ --output keypoints/
    uv run extract_keypoints.py --input data/videos/ --output keypoints/ --visualize
    uv run extract_keypoints.py --input data/videos/ --output keypoints/ --save_video

Output:
    keypoints/<name>.json                     metadata + per-frame stats
    keypoints/videos/<name>_keypoints.mp4     annotated video with skeleton overlay (--save_video)
    keypoints/dataset.npy                     tensor (N, T, 225) ready for training
    keypoints/labels.json                     list of class labels

Feature vector dimensions per frame (225 float32):
    pose   33 × (x, y, z)  =  99
    left   21 × (x, y, z)  =  63
    right  21 × (x, y, z)  =  63
    ──────────────────────────────
    total                     225
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import (
    PoseLandmarker, PoseLandmarkerOptions,
    HandLandmarker, HandLandmarkerOptions,
    RunningMode,
)

# ── constants ─────────────────────────────────────────────────────────────────
N_POSE  = 33
N_HAND  = 21
DEFAULT_MAX_FRAMES = 90

# Connections for skeleton visualization
POSE_CONN = [
    (11,13),(13,15),(12,14),(14,16),
    (11,12),(11,23),(12,24),(23,24),
    (0,1),(1,2),(2,3),(3,7),
    (0,4),(4,5),(5,6),(6,8),
]
HAND_CONN = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (0,9),(9,10),(10,11),(11,12),
    (0,13),(13,14),(14,15),(15,16),
    (0,17),(17,18),(18,19),(19,20),
    (5,9),(9,13),(13,17),
]


# ── model download ────────────────────────────────────────────────────────────

def download_model(url, dest):
    """Download model if not already cached locally."""
    dest = Path(dest)
    if dest.exists():
        return dest
    print(f"  Downloading {dest.name}...")
    import urllib.request
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    print(f"  OK → {dest}")
    return dest


MODELS_DIR = Path.home() / ".cache" / "mediapipe_models"

POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "pose_landmarker/pose_landmarker_lite/float16/latest/"
    "pose_landmarker_lite.task"
)
HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/"
    "hand_landmarker.task"
)


def get_models():
    pose_path = download_model(POSE_MODEL_URL, MODELS_DIR / "pose_landmarker_lite.task")
    hand_path = download_model(HAND_MODEL_URL, MODELS_DIR / "hand_landmarker.task")
    return str(pose_path), str(hand_path)


# ── landmarker initialization ─────────────────────────────────────────────────

def make_pose_landmarker(model_path):
    opts = PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path),
        running_mode=RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.4,
        min_pose_presence_confidence=0.4,
        min_tracking_confidence=0.4,
    )
    return PoseLandmarker.create_from_options(opts)


def make_hand_landmarker(model_path):
    opts = HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path),
        running_mode=RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.4,
        min_hand_presence_confidence=0.4,
        min_tracking_confidence=0.4,
    )
    return HandLandmarker.create_from_options(opts)


# ── landmark extraction ───────────────────────────────────────────────────────

def pose_to_array(pose_result):
    """Returns ndarray (33, 3) or None."""
    if not pose_result.pose_landmarks:
        return None
    lms = pose_result.pose_landmarks[0]
    return np.array([[lm.x, lm.y, lm.z] for lm in lms], dtype=np.float32)


def hands_to_arrays(hand_result):
    """Returns (left, right) as ndarray (21, 3) or None.

    MediaPipe 0.10 returns handedness as 'Left'/'Right' from the perspective
    of the person in the video (mirror correction already applied).
    """
    left = right = None
    if not hand_result.hand_landmarks:
        return left, right
    for lms, handed in zip(hand_result.hand_landmarks,
                           hand_result.handedness):
        arr = np.array([[lm.x, lm.y, lm.z] for lm in lms], dtype=np.float32)
        label = handed[0].category_name  # 'Left' or 'Right'
        if label == "Left":
            left = arr
        else:
            right = arr
    return left, right


def frame_to_vector(pose, hand_l, hand_r):
    """Concatenates pose + hands into a (225,) float32 vector. Missing = zeros."""
    p = pose.flatten()   if pose   is not None else np.zeros(N_POSE * 3, np.float32)
    l = hand_l.flatten() if hand_l is not None else np.zeros(N_HAND * 3, np.float32)
    r = hand_r.flatten() if hand_r is not None else np.zeros(N_HAND * 3, np.float32)
    return np.concatenate([p, l, r])


# ── visualization ─────────────────────────────────────────────────────────────

def draw_skeleton(frame_bgr, pose, hand_l, hand_r):
    out = frame_bgr.copy()
    H, W = out.shape[:2]

    if pose is not None:
        px = (pose[:, 0] * W).astype(int)
        py = (pose[:, 1] * H).astype(int)
        for a, b in POSE_CONN:
            cv2.line(out, (px[a], py[a]), (px[b], py[b]), (0, 229, 255), 1)
        for i in range(N_POSE):
            color = (0, 255, 100) if i in (11, 12) else \
                    (255, 235, 59) if i in (15, 16) else (200, 80, 80)
            cv2.circle(out, (px[i], py[i]), 3, color, -1)

    for hand, color in [(hand_l, (255, 140, 0)), (hand_r, (0, 140, 255))]:
        if hand is not None:
            hx = (hand[:, 0] * W).astype(int)
            hy = (hand[:, 1] * H).astype(int)
            for a, b in HAND_CONN:
                cv2.line(out, (hx[a], hy[a]), (hx[b], hy[b]), color, 1)
            for i in range(N_HAND):
                cv2.circle(out, (hx[i], hy[i]), 3, color, -1)

    return out


# ── single video processing ───────────────────────────────────────────────────

def process_video(video_path, output_dir, pose_lm, hand_lm,
                  visualize=False, save_video=False):
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    W   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # ── VideoWriter ──
    writer = None
    if save_video:
        (Path(output_dir) / "videos").mkdir(parents=True, exist_ok=True)
        out_path = Path(output_dir) / "videos" / (Path(video_path).stem + "_keypoints.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"avc1")
        writer = cv2.VideoWriter(str(out_path), fourcc, fps, (W, H))

    sequence   = []
    frame_meta = []
    pose_ok = lh_ok = rh_ok = 0
    frame_idx = 0

    while cap.isOpened():
        ret, frame_bgr = cap.read()
        if not ret:
            break

        # MediaPipe 0.10 requires mp.Image
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        ts_ms     = int(frame_idx * 1000 / fps)

        pose_result = pose_lm.detect_for_video(mp_image, ts_ms)
        hand_result = hand_lm.detect_for_video(mp_image, ts_ms)

        pose   = pose_to_array(pose_result)
        hand_l, hand_r = hands_to_arrays(hand_result)

        sequence.append(frame_to_vector(pose, hand_l, hand_r))

        if pose   is not None: pose_ok += 1
        if hand_l is not None: lh_ok   += 1
        if hand_r is not None: rh_ok   += 1

        frame_meta.append({
            "frame":      frame_idx,
            "has_pose":   pose   is not None,
            "has_left":   hand_l is not None,
            "has_right":  hand_r is not None,
        })

        if visualize or save_video:
            annotated = draw_skeleton(frame_bgr, pose, hand_l, hand_r)
            if save_video and writer:
                writer.write(annotated)
            if visualize:
                cv2.imshow("Keypoints — press q to quit", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        frame_idx += 1

    cap.release()
    if writer:
        writer.release()
    if visualize:
        cv2.destroyAllWindows()

    n     = len(frame_meta)
    stats = {"pose": pose_ok, "left_hand": lh_ok, "right_hand": rh_ok, "total": n}
    stem  = Path(video_path).stem

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    with open(Path(output_dir) / f"{stem}.json", "w") as f:
        json.dump({
            "video": str(video_path), "fps": fps,
            "width": W, "height": H,
            "n_frames": n, "vec_dim": 225,
            "stats": stats, "frames": frame_meta,
        }, f, indent=2)

    return np.array(sequence, dtype=np.float32), stats, n


# ── pad / trim ────────────────────────────────────────────────────────────────

def normalize_sequence(seq, max_frames):
    out  = np.zeros((max_frames, 225), dtype=np.float32)
    take = min(len(seq), max_frames)
    out[:take] = seq[:take]
    return out


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="PJM keypoint extraction (MediaPipe 0.10.x, arm64)"
    )
    parser.add_argument("--input",      required=True,
                        help="Folder with MP4 files or a single file path")
    parser.add_argument("--output",     default="keypoints",
                        help="Output folder (default: keypoints/)")
    parser.add_argument("--visualize",  action="store_true",
                        help="Show live preview with skeleton overlay")
    parser.add_argument("--save_video", action="store_true",
                        help="Save annotated video with skeleton to output/")
    parser.add_argument("--max_frames", type=int, default=DEFAULT_MAX_FRAMES,
                        help=f"Sequence length after pad/trim (default: {DEFAULT_MAX_FRAMES})")
    args = parser.parse_args()

    print("Downloading MediaPipe models...")
    pose_model_path, hand_model_path = get_models()
    print("OK\n")

    inp    = Path(args.input)
    videos = sorted(inp.glob("*.mp4")) if inp.is_dir() else [inp]

    if not videos:
        print(f"No MP4 files found in: {inp}")
        return

    print(f"Found {len(videos)} video(s).\n")

    all_sequences = []
    all_labels    = []

    for video_path in videos:
        print(f"-> {video_path.name}")
        # New instance per video — timestamp resets to 0
        pose_lm = make_pose_landmarker(pose_model_path)
        hand_lm = make_hand_landmarker(hand_model_path)

        seq, stats, n = process_video(
            video_path, args.output, pose_lm, hand_lm,
            args.visualize, args.save_video
        )

        pose_lm.close()
        hand_lm.close()

        seq_norm = normalize_sequence(list(seq), args.max_frames)
        all_sequences.append(seq_norm)
        all_labels.append(video_path.stem)

        pct = lambda k: f"{100*stats[k]//n if n else 0}%"
        print(f"   {n} frames | "
              f"pose: {stats['pose']} ({pct('pose')}) | "
              f"left: {stats['left_hand']} ({pct('left_hand')}) | "
              f"right: {stats['right_hand']} ({pct('right_hand')})")

    if all_sequences:
        dataset = np.stack(all_sequences)
        out_dir = Path(args.output)
        np.save(out_dir / "dataset.npy", dataset)
        with open(out_dir / "labels.json", "w") as f:
            json.dump(all_labels, f, indent=2)

        print(f"\nDataset: {out_dir}/dataset.npy")
        print(f"  shape: {dataset.shape[0]} videos "
              f"× {dataset.shape[1]} frames "
              f"× {dataset.shape[2]} features")
        print(f"  labels: {all_labels}")


if __name__ == "__main__":
    main()
