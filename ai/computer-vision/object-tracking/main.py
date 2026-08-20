"""
Object Tracking Demo — OpenCV Multi-Tracker
Supports: CSRT, KCF, MOSSE, MIL
Usage: uv run main.py [--tracker CSRT] [--source 0]
"""

import argparse
import cv2
import sys

TRACKERS = {
    "CSRT": cv2.TrackerCSRT_create,
    "KCF": cv2.TrackerKCF_create,
    "MOSSE": cv2.legacy.TrackerMOSSE_create,
    "MIL": cv2.TrackerMIL_create,
}

COLORS = [
    (0, 255, 0),
    (255, 0, 0),
    (0, 0, 255),
    (255, 255, 0),
    (0, 255, 255),
]


def parse_args():
    parser = argparse.ArgumentParser(description="Object Tracking Demo")
    parser.add_argument(
        "--tracker",
        default="CSRT",
        choices=TRACKERS.keys(),
        help="Tracker algorithm (default: CSRT)",
    )
    parser.add_argument(
        "--source",
        default="0",
        help="Video source: 0 for webcam, or path to video file (default: 0)",
    )
    return parser.parse_args()


def open_source(source: str):
    """Open webcam or video file."""
    src = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open source: {source}")
        sys.exit(1)
    return cap


def draw_tracker(frame, box, color, label, success):
    """Draw bounding box and status label."""
    if success:
        x, y, w, h = [int(v) for v in box]
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        cv2.putText(
            frame, label, (x, y - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2
        )
    else:
        cv2.putText(
            frame, f"{label}: LOST", (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2
        )


def draw_help(frame):
    lines = [
        "S - select new ROI",
        "C - clear all trackers",
        "Q / ESC - quit",
    ]
    for i, line in enumerate(lines):
        cv2.putText(
            frame, line, (10, frame.shape[0] - 15 - i * 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1
        )


def main():
    args = parse_args()
    cap = open_source(args.source)

    tracker_fn = TRACKERS[args.tracker]
    trackers = []   # list of (tracker, color, label)
    tracker_count = 0

    print(f"[INFO] Tracker: {args.tracker}")
    print("[INFO] Press S to select ROI, C to clear, Q/ESC to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[INFO] End of stream.")
            break

        # Update all trackers
        for i, (tracker, color, label) in enumerate(trackers):
            success, box = tracker.update(frame)
            draw_tracker(frame, box, color, label, success)

        # HUD
        cv2.putText(
            frame,
            f"Tracker: {args.tracker}  |  Objects: {len(trackers)}",
            (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2
        )
        draw_help(frame)

        cv2.imshow("Object Tracking", frame)

        key = cv2.waitKey(1) & 0xFF

        if key in (ord("q"), 27):  # Q or ESC
            break

        elif key == ord("s"):  # Select new ROI
            roi = cv2.selectROI(
                "Object Tracking", frame, fromCenter=False, showCrosshair=True
            )
            cv2.destroyWindow("ROI selector")
            if roi[2] > 0 and roi[3] > 0:
                tracker_count += 1
                t = tracker_fn()
                t.init(frame, roi)
                color = COLORS[tracker_count % len(COLORS)]
                label = f"Obj {tracker_count}"
                trackers.append((t, color, label))
                print(f"[INFO] Added tracker #{tracker_count} at ROI {roi}")

        elif key == ord("c"):  # Clear all
            trackers.clear()
            tracker_count = 0
            print("[INFO] Cleared all trackers.")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
