from picamera2 import Picamera2
from picamera2.devices import IMX500
from datetime import datetime
from collections import defaultdict
import sqlite3
import time
import math

print("FABLAB PERSON TÆLLER v6.0 - IMX500 AI CAMERA")

# ----------------------
# Database
# ----------------------

DB_FILE = "fablab_people.db"

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    track_id INTEGER,
    direction TEXT,
    total INTEGER
)
""")

conn.commit()

# ----------------------
# Kamera + IMX500
# ----------------------

picam2 = Picamera2()
imx500 = IMX500(picam2)

config = picam2.create_preview_configuration(
    main={"size": (640, 480)}
)

picam2.configure(config)
picam2.start()

time.sleep(2)

frame_width = 640
frame_height = 480

line_x = frame_width // 2

print(f"Kamera OK | Linje x={line_x}")
print("-" * 50)

# ----------------------
# Counters
# ----------------------

total_crossings = 0
current_inside = 0

cross_history = defaultdict(list)
last_cross_time = {}

cooldown_seconds = 1.5

# ----------------------
# Tracker
# ----------------------

tracks = {}
next_track_id = 1
max_distance = 100

def distance(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)

# ----------------------
# Main loop
# ----------------------

try:

    while True:

        metadata = picam2.capture_metadata()
        detections = imx500.get_detections(metadata)

        current_centers = []

        # Debug detections (kan slås fra senere)
        # print(detections)

        for det in detections:

            # Person klasse (kan være 0 eller 1 afhængigt af model)
            if det["category"] not in [0,1]:
                continue

            x, y, w, h = det["bbox"]

            cx = int(x + w/2)
            cy = int(y + h/2)

            current_centers.append((cx, cy))

        # ----------------------
        # Tracking
        # ----------------------

        updated_tracks = {}
        used_centers = set()

        for track_id, old_center in tracks.items():

            closest_center = None
            closest_dist = 9999

            for center in current_centers:

                if center in used_centers:
                    continue

                d = distance(center, old_center)

                if d < closest_dist and d < max_distance:
                    closest_dist = d
                    closest_center = center

            if closest_center:

                updated_tracks[track_id] = closest_center
                used_centers.add(closest_center)

        # nye tracks

        for center in current_centers:

            if center not in used_centers:

                updated_tracks[next_track_id] = center
                next_track_id += 1

        tracks = updated_tracks

        # ----------------------
        # Line crossing detection
        # ----------------------

        for track_id, center in tracks.items():

            cx = center[0]

            cross_history[track_id].append(cx)

            if len(cross_history[track_id]) > 10:
                cross_history[track_id].pop(0)

            if len(cross_history[track_id]) < 2:
                continue

            prev_cx = cross_history[track_id][-2]

            now = datetime.now()

            last_time = last_cross_time.get(track_id)

            too_soon = last_time and (now - last_time).total_seconds() < cooldown_seconds

            # IND (højre → venstre)

            if prev_cx > line_x and cx <= line_x and not too_soon:

                direction = "←"
                last_cross_time[track_id] = now

                total_crossings += 1
                current_inside += 1

                timestamp = now.strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute(
                    "INSERT INTO people VALUES (NULL, ?, ?, ?, ?)",
                    (timestamp, track_id, direction, total_crossings)
                )

                conn.commit()

                print(f"IND! {timestamp} | ID{track_id} | Total: {total_crossings} | I rummet: {current_inside}")

            # UD (venstre → højre)

            elif prev_cx < line_x and cx >= line_x and not too_soon:

                direction = "→"
                last_cross_time[track_id] = now

                current_inside = max(current_inside - 1, 0)

                timestamp = now.strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute(
                    "INSERT INTO people VALUES (NULL, ?, ?, ?, ?)",
                    (timestamp, track_id, direction, total_crossings)
                )

                conn.commit()

                print(f"UD! {timestamp} | ID{track_id} | Total: {total_crossings} | I rummet: {current_inside}")

        time.sleep(0.03)

# ----------------------
# Stop
# ----------------------

except KeyboardInterrupt:

    print("\nStoppet manuelt")

finally:

    picam2.stop()
    conn.close()

    print(f"FÆRDIG! Total personer: {total_crossings}")
