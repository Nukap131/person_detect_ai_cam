import cv2
from ultralytics import YOLO
from picamera2 import Picamera2

# Load YOLOv8 person‑friendly model
model = YOLO("yolov8n.pt")  # eller yolov8s.pt for mere præcis

# Start Pi AI Camera (bruger PiCamera2‑driveren)
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (1280, 720)})
picam2.configure(config)
picam2.start()

print("Tryk q for at stoppe...")

while True:
    # Hent frame fra AI Camera
    frame = picam2.capture_array()

    # Kør YOLO‑inferens
    results = model.predict(frame, verbose=False, imgsz=640)

    # Tegn bokse og labels (kun personer COCO‑class 0)
    annotated_frame = results[0].plot()

    # Vis billedet
    cv2.imshow("Person Detection - Pi AI Camera", annotated_frame)

    # Afslut med 'q'
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

picam2.stop()
cv2.destroyAllWindows()
