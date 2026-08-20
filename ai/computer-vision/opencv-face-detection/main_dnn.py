import cv2
import numpy as np

# Load model DNN (SSD + ResNet)
net = cv2.dnn.readNetFromCaffe(
    "model/deploy.prototxt",
    "model/res10_300x300_ssd_iter_140000.caffemodel"
)

frame = cv2.imread("photos/photo_01.jpg")
h, w = frame.shape[:2]

# Preprocessing
blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300),
                              (104.0, 177.0, 123.0))
net.setInput(blob)
detections = net.forward()

for i in range(detections.shape[2]):
    confidence = detections[0, 0, i, 2]
    if confidence > 0.5:
        box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
        x1, y1, x2, y2 = box.astype(int)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, f"{confidence:.2f}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

print(f"Detected {i} face(s)")
cv2.imshow("Faces DNN", frame)
cv2.waitKey(0)
cv2.destroyAllWindows()
