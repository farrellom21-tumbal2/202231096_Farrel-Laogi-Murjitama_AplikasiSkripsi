# realtime_proctoring_stable_highfps.py
import cv2
import numpy as np
import time
import os
import urllib.request
from ultralytics import YOLO
from insightface.app import FaceAnalysis
from gaze_tracking import GazeTracking

# ================= CONFIG =================
YOLO_MODEL = os.getenv("YOLO_MODEL_PATH", "yolov8_final.pt")
REF_FACE = "peserta.png" #atau dapat juga URL gambar
CONF_THRES = os.getenv("YOLO_CONF_THRESHOLD", 0.5)
CAM_ID = 0

FRAME_WIDTH = os.getenv("FRAME_WIDTH", 640)
FRAME_HEIGHT = os.getenv("FRAME_HEIGHT", 480)

YOLO_INTERVAL = os.getenv("YOLO_INTERVAL", 2)
FACE_INTERVAL = os.getenv("FACE_INTERVAL", 10)
GAZE_INTERVAL = os.getenv("GAZE_INTERVAL", 3)

SIM_THRESHOLD = os.getenv("SIM_THRESHOLD", 0.45)

YOLO_CLASSES = {
    0: "face_normal",
    1: "face_not_forward",
    2: "multi_face",
    3: "foreign_object"
}
# =========================================

cv2.setUseOptimized(True)
cv2.ocl.setUseOpenCL(True)

# ---------- Load Models ----------
yolo = YOLO(YOLO_MODEL)
yolo.fuse()

face_app = FaceAnalysis(
    name="buffalo_l",
    providers=["CUDAExecutionProvider"]
)
face_app.prepare(ctx_id=0, det_size=(640, 640))

gaze = GazeTracking()

# ---------- Load Reference Face ----------
if REF_FACE.startswith("http"):
    tmp = "tmp_ref.png"
    urllib.request.urlretrieve(REF_FACE, tmp)
    ref_img = cv2.imread(tmp)
    os.remove(tmp)
else:
    ref_img = cv2.imread(REF_FACE)

ref_face = face_app.get(ref_img)[0]
ref_emb = ref_face.embedding

def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# ---------- Camera ----------
cap = cv2.VideoCapture(CAM_ID, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
cap.set(cv2.CAP_PROP_FPS, 60)

print("[INFO] Proctoring Started (Stable + High FPS)")

# ================= CACHE (INI KUNCI STABILITAS) =================
frame_count = 0

cached_yolo = None              # (label, conf, bbox)
cached_face = None              # (bbox, similarity)
cached_gaze = None              # string
cached_violations = []

fps_time = time.time()

# ===============================================================

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1
    violations = []

    # ================= YOLO (ANALYSIS ONLY) =================
    if frame_count % YOLO_INTERVAL == 0:
        yolo_res = yolo(
            frame,
            conf=CONF_THRES,
            device=0,
            half=True,
            imgsz=640,
            verbose=False
        )[0]

        if yolo_res.boxes:
            best = max(yolo_res.boxes, key=lambda b: float(b.conf[0]))
            cls_id = int(best.cls[0])
            label = YOLO_CLASSES[cls_id]
            bbox = tuple(map(int, best.xyxy[0]))
            conf = float(best.conf[0])
            cached_yolo = (label, conf, bbox)
        else:
            cached_yolo = None

    # ================= FACE (ANALYSIS ONLY) =================
    if frame_count % FACE_INTERVAL == 0:
        faces = face_app.get(frame)

        if len(faces) == 1:
            face = faces[0]
            sim = cosine_sim(face.embedding, ref_emb)
            bbox = tuple(map(int, face.bbox))
            cached_face = (bbox, sim)
        else:
            cached_face = None
            if len(faces) == 0:
                violations.append("no_face")
            else:
                violations.append("multi_face")

    # ================= GAZE (ANALYSIS ONLY) =================
    if frame_count % GAZE_INTERVAL == 0:
        gaze.refresh(frame)
        if gaze.is_left() or gaze.is_right():
            cached_gaze = "eye_looking_away"
        elif gaze.is_blinking():
            cached_gaze = "blinking"
        else:
            cached_gaze = None

    # ================= RENDER (SETIAP FRAME) =================

    # YOLO render
    if cached_yolo:
        label, conf, (x1, y1, x2, y2) = cached_yolo
        if label != "face_normal":
            violations.append(label)

        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.putText(frame, label, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

    # Face render
    if cached_face:
        (x1, y1, x2, y2), sim = cached_face
        if sim < SIM_THRESHOLD:
            violations.append("face_mismatch")

        color = (255, 0, 0) if sim >= SIM_THRESHOLD else (0, 0, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"Match {sim:.2f}", (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Gaze render
    if cached_gaze:
        violations.append(cached_gaze)

    # ================= FINAL STATUS =================
    status = "NORMAL" if not violations else "VIOLATION"
    color = (255, 0, 0) if status == "NORMAL" else (0, 0, 255)

    fps = 1.0 / (time.time() - fps_time)
    fps_time = time.time()

    cv2.putText(frame, status, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.3, color, 3)

    if violations:
        cv2.putText(frame, ", ".join(set(violations)), (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    cv2.putText(frame, f"FPS: {int(fps)}", (20, 120),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

    cv2.imshow("AI Proctoring System", frame)

    # ================= STATUS PROCESSING =================
    # hitung fps
    fps_list = []

    # setelah hitung fps
    fps_list.append(fps)

    if len(fps_list) == 300:  # 5 detik jika 60fps
        print("FPS avg:", sum(fps_list)/len(fps_list))
        print("FPS min:", min(fps_list))
        print("FPS max:", max(fps_list))
        fps_list.clear()

    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()