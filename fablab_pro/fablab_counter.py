from picamera2 import Picamera2
from picamera2.devices import IMX500
from datetime import datetime
import sqlite3
import time

print("FABLAB PERSON TÆLLER - IMX500")

# ---------------- DATABASE ----------------

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

# ---------------- MODEL ----------------

MODEL = "/usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk"
imx500 = IMX500(MODEL)

# ---------------- CAMERA ----------------

picam2 = Picamera2()

config = picam2.create_preview_configuration(
 main={"size": (640,480)}
)

picam2.configure(config)
picam2.start()

time.sleep(2)

frame_width = 640

# ---------------- DOOR LINE ----------------

line_x = 320
margin = 70

LEFT = line_x - margin
RIGHT = line_x + margin

print("Camera ready")

# ---------------- COUNTERS ----------------

total_crossings = 0
current_inside = 0

zone_history = []
last_event = 0

cooldown = 1.5

# ---------------- LOOP ----------------

try:

 while True:

  metadata = picam2.capture_metadata()
  outputs = imx500.get_outputs(metadata)

  if outputs is None:
   continue

  boxes, scores, classes, num = outputs

  persons = []

  for i in range(int(num)):

   score = float(scores[i])
   cls = int(classes[i])

   if cls != 0:
    continue

   if score < 0.55:
    continue

   box = boxes[i]

   xmin = float(box[1])
   xmax = float(box[3])

   cx = int(((xmin + xmax) / 2) * frame_width)

   persons.append(cx)

  if len(persons) == 0:
   continue

  # person tættest på linjen
  cx = min(persons, key=lambda x: abs(x - line_x))

  if cx < LEFT:
   zone = "LEFT"

  elif cx > RIGHT:
   zone = "RIGHT"

  else:
   zone = "CENTER"

  if len(zone_history) == 0 or zone_history[-1] != zone:
   zone_history.append(zone)

  if len(zone_history) > 5:
   zone_history.pop(0)

  now = time.time()

  # -------- IND --------

  if zone_history[-3:] == ["RIGHT","CENTER","LEFT"]:

   if now - last_event > cooldown:

    total_crossings += 1
    current_inside += 1

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute(
     "INSERT INTO people VALUES(NULL,?,?,?,?)",
     (timestamp,0,"←",total_crossings)
    )

    conn.commit()

    print("IND | Total:", total_crossings)

    last_event = now
    zone_history = []

  # -------- UD --------

  if zone_history[-3:] == ["LEFT","CENTER","RIGHT"]:

   if now - last_event > cooldown:

    current_inside = max(current_inside - 1, 0)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute(
     "INSERT INTO people VALUES(NULL,?,?,?,?)",
     (timestamp,0,"→",total_crossings)
    )

    conn.commit()

    print("UD | Inside:", current_inside)

    last_event = now
    zone_history = []

  time.sleep(0.05)

except KeyboardInterrupt:

 print("Stopped")

finally:

 picam2.stop()
 conn.close()

