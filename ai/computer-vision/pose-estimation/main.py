"""
Pose Estimation Demo — MediaPipe BlazePose
Detects 33 body landmarks in real time.
Usage: uv run main.py [--source 0] [--mode full|upper|lite]
"""

import argparse
import time
import cv2
import mediapipe as mp
import sys

# MediaPipe setup
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Landmark indices for angle calculations
# (see: https://developers.google.com/mediapipe/solutions/vision/pose_landmarker)
LANDMARK = mp_pose.PoseLandmark

ANGLE_JOINTS = {
    "L Elbow": (LANDMARK.LEFT_SHOULDER, LANDMARK.LEFT_ELBOW, LANDMARK.LEFT_WRIST),
    "R Elbow": (LANDMARK.RIGHT_SHOULDER, LANDMARK.RIGHT_ELBOW, LANDMARK.RIGHT_WRIST),
    "L Knee":  (LANDMARK.LEFT_HIP, LANDMARK.LEFT_KNEE, LANDMARK.LEFT_ANKLE),
    "R Knee":  (LANDMARK.RIGHT_HIP, LANDMARK.RIGHT_KNEE, LANDMARK.RIGHT_ANKLE),
}

MODEL_COMPLEXITY = {"lite": 0, "full": 1, "heavy": 2}


def parse_args():
    parser = argparse.ArgumentParser(description="Pose Estimation Demo")
    parser.add_argument(
        "--source", default="0",
        help="Video source: 0 for webcam, or path to video file (default: 0)",
    )
    parser.add_argument(
        "--model", default="full",
        choices=MODEL_COMPLEXITY.keys(),
        help="Model complexity: lite (fast), full (balanced), heavy (accurate)",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.5,
        help="Minimum detection confidence (default: 0.5)",
    )
    return parser.parse_args()


def open_source(source: str):
    src = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open source: {source}")
        sys.exit(1)
    return cap


def calculate_angle(lm_a, lm_b, lm_c) -> float:
    """
    Calculate angle at joint B, formed by points A-B-C.
    Uses 2D (x, y) coordinates from normalized landmarks.
    Returns angle in degrees [0, 180].
    """
    import math
    ax, ay = lm_a.x - lm_b.x, lm_a.y - lm_b.y
    cx, cy = lm_c.x - lm_b.x, lm_c.y - lm_b.y
    dot = ax * cx + ay * cy
    mag_a = math.sqrt(ax ** 2 + ay ** 2)
    mag_c = math.sqrt(cx ** 2 + cy ** 2)
    if mag_a * mag_c == 0:
        return 0.0
    cos_angle = max(-1.0, min(1.0, dot / (mag_a * mag_c)))
    return math.degrees(math.acos(cos_angle))


def draw_angles(frame, landmarks, h, w):
    """Overlay joint angles on frame."""
    for label, (a, b, c) in ANGLE_JOINTS.items():
        lm = landmarks.landmark
        # Only draw if all three landmarks are visible
        if all(lm[j].visibility > 0.5 for j in (a, b, c)):
            angle = calculate_angle(lm[a], lm[b], lm[c])
            bx = int(lm[b].x * w)
            by = int(lm[b].y * h)
            cv2.putText(
                frame, f"{angle:.0f}deg",
                (bx + 10, by),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2
            )


def draw_hud(frame, fps, model, n_visible):
    cv2.putText(
        frame,
        f"FPS: {fps:.1f}  |  Model: {model}  |  Landmarks: {n_visible}/33",
        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
    )
    lines = ["A - toggle angles", "Q / ESC - quit"]
    for i, line in enumerate(lines):
        cv2.putText(
            frame, line, (10, frame.shape[0] - 15 - i * 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1
        )


def main():
    args = parse_args()
    cap = open_source(args.source)
    complexity = MODEL_COMPLEXITY[args.model]

    show_angles = True
    fps = 0.0
    prev_time = time.time()

    print(f"[INFO] Model: {args.model} (complexity={complexity})")
    print("[INFO] Press A to toggle angle display, Q/ESC to quit.")

    with mp_pose.Pose(
        model_complexity=complexity,
        min_detection_confidence=args.min_confidence,
        min_tracking_confidence=args.min_confidence,
        enable_segmentation=False,
    ) as pose:

        while True:
            ret, frame = cap.read()
            if not ret:
                print("[INFO] End of stream.")
                break

            # MediaPipe expects RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            results = pose.process(rgb)
            rgb.flags.writeable = True
            frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

            h, w = frame.shape[:2]
            n_visible = 0

            if results.pose_landmarks:
                # Draw skeleton
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing_styles.get_default_pose_landmarks_style(),
                )

                n_visible = sum(
                    1 for lm in results.pose_landmarks.landmark
                    if lm.visibility > 0.5
                )

                if show_angles:
                    draw_angles(frame, results.pose_landmarks, h, w)

            # FPS
            now = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - prev_time, 1e-6))
            prev_time = now

            draw_hud(frame, fps, args.model, n_visible)
            cv2.imshow("Pose Estimation", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            elif key == ord("a"):
                show_angles = not show_angles
                print(f"[INFO] Angles: {'ON' if show_angles else 'OFF'}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
