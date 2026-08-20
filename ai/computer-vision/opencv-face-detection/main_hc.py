import cv2

# Load image
frame = cv2.imread("photos/photo-01.jpg")
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

# Edge detection (Canny)
edges = cv2.Canny(gray, 50, 150)

# Face detection (Haar Cascade)
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=10)

for (x, y, w, h) in faces:
    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.putText(frame, "Face", (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

print(f"Detected {len(faces)} face(s)")

# Show windows
cv2.imshow("Original + Faces", frame)
cv2.imshow("Edges (Canny)", edges)
cv2.waitKey(0)
cv2.destroyAllWindows()
