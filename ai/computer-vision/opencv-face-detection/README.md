# OpenCV Face Detection Demo

A simple Computer Vision demo using OpenCV to detect faces in images.
Two approaches are included: classic Haar Cascade and DNN-based detection.

## Project Structure

```
opencv-face-detection/
├── model/
│   ├── deploy.prototxt
│   └── res10_300x300_ssd_iter_140000.caffemodel
├── photos/
│   └── photo_01.jpg
├── main_dnn.py        # DNN-based face detection (recommended)
├── main_hc.py         # Haar Cascade face detection
└── pyproject.toml
```

## Requirements

- Python 3.x
- [uv](https://astral.sh/uv) package manager

## Installation

```bash
mkdir -p model

wget -P model https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt

wget -P model https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel
```

## Usage

DNN-based detection (recommended):
```bash
uv run main_dnn.py
```

Haar Cascade detection:
```bash
uv run main_hc.py
```

## Approaches

### Haar Cascade
Classic method using a pre-trained XML classifier. Fast and lightweight
but prone to false positives on complex backgrounds or patterns.

Known limitation: patterns resembling a face (e.g. a checked tie)
can trigger false detections even at high `minNeighbors` values.

### DNN — SSD + ResNet
Deep learning approach using a pre-trained Caffe model (SSD + ResNet-10,
140 000 training iterations). More accurate and robust than Haar Cascade.


## Output

### main_hc.py
Opens two windows:
- **Original + Faces** — input image with green bounding boxes
- **Edges (Canny)** — grayscale image with detected edges

### main_dnn.py
Opens one window:
- **Faces DNN** — input image with green bounding boxes and confidence scores

Press any key to close.

## Notes

- Place images in the `photos/` folder
- Default input: `photos/photo_01.jpg`

Note: Image by <a href="https://pixabay.com/users/be4te-6101787/?utm_source=link-attribution&utm_medium=referral&utm_campaign=image&utm_content=2918531">be4te</a> from <a href="https://pixabay.com//?utm_source=link-attribution&utm_medium=referral&utm_campaign=image&utm_content=2918531">Pixabay</a>
