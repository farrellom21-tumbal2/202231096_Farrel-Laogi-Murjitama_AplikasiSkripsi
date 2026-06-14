"""
STABLE PROCTORING ENGINE - Face Analysis Module (Importable)
Features:
- Face mismatch detection (stable cosine similarity)
- Head movement analysis (stable with smart caching)
- YOLO pose classification
- Gaze tracking
- Multi-participant support via class instantiation

Key: Smart caching algorithm ensures stable analysis
"""
import cv2
import numpy as np
import time
import os
import gc
import urllib.request
import tempfile
import traceback
from ultralytics import YOLO
from insightface.app import FaceAnalysis
from gaze_tracking import GazeTracking
from dotenv import load_dotenv

load_dotenv()

# ================= CONFIG =================
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8_final.pt")
CONF_THRES = float(os.getenv("CONF_THRES", 0.5))
FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", 640))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", 480))
YOLO_INTERVAL = int(os.getenv("YOLO_INTERVAL", 2))
FACE_INTERVAL = int(os.getenv("FACE_INTERVAL", 10))
GAZE_INTERVAL = int(os.getenv("GAZE_INTERVAL", 3))
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", 0.45))

YOLO_CLASSES = {
    0: "face_normal",
    1: "face_not_forward",
    2: "multi_face",
    3: "foreign_object"
}

# Optimize OpenCV
cv2.setUseOptimized(True)
cv2.ocl.setUseOpenCL(True)

# Global model instances (loaded once)
_yolo = None
_face_app = None
_gaze = None

def _initialize_global_models():
    """Initialize global models on first use"""
    global _yolo, _face_app, _gaze
    
    if _yolo is None:
        try:
            _yolo = YOLO(YOLO_MODEL)
            _yolo.fuse()
        except Exception as e:
            print(f"[ANALYZER] ❌ YOLO load failed: {e}")
            _yolo = None
    
    if _face_app is None:
        try:
            _face_app = FaceAnalysis(
                name="buffalo_l",
                providers=["CUDAExecutionProvider"]
            )
            _face_app.prepare(ctx_id=0, det_size=(640, 640))
        except Exception as e:
            print(f"[ANALYZER] ❌ InsightFace load failed: {e}")
            _face_app = None
    
    if _gaze is None:
        try:
            _gaze = GazeTracking()
        except Exception as e:
            print(f"[ANALYZER] ❌ GazeTracking load failed: {e}")
            _gaze = None

# Initialize on import
_initialize_global_models()

def cosine_sim(a, b):
    """Calculate cosine similarity between two embeddings"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def download_ref_face(face_photo_url):
    """Download reference face image from URL or local path"""
    try:
        if face_photo_url.startswith("http"):
            # Download from URL dengan retry logic
            print(f"[ANALYZER] 📥 Downloading reference face from URL...")
            print(f"[ANALYZER]    URL: {face_photo_url}")
            
            tmp_file = None
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    # Create temp file
                    tmp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
                    tmp_path = tmp_file.name
                    tmp_file.close()  # ✅ Close handle sebelum download
                    
                    print(f"[ANALYZER] 📝 Attempt {retry_count + 1}/{max_retries}: Downloading...")
                    
                    # Download file
                    urllib.request.urlretrieve(face_photo_url, tmp_path)
                    
                    print(f"[ANALYZER] ✅ Download successful")
                    print(f"[ANALYZER] 📖 Reading image from disk...")
                    
                    # ✅ IMPORTANT: Load image
                    ref_img = cv2.imread(tmp_path)
                    
                    if ref_img is not None:
                        print(f"[ANALYZER] ✅ Image loaded: shape={ref_img.shape}")
                        
                        # ✅ Try to delete temp file (Windows safe way)
                        try:
                            # Force close any handles
                            import gc
                            gc.collect()  # Garbage collect to release handles
                            
                            # Now try to delete
                            if os.path.exists(tmp_path):
                                os.unlink(tmp_path)
                                print(f"[ANALYZER] 🗑️ Temp file deleted")
                        except Exception as del_e:
                            print(f"[ANALYZER] ⚠️ Warning: Could not delete temp file: {del_e}")
                            # Don't fail if we can't delete temp file
                        
                        return ref_img
                    else:
                        print(f"[ANALYZER] ⚠️ cv2.imread() returned None - invalid image")
                        raise Exception("Image loading failed - cv2.imread returned None")
                
                except Exception as attempt_e:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"[ANALYZER] ⚠️ Download attempt {retry_count} failed: {attempt_e}")
                        print(f"[ANALYZER] 🔄 Retrying in 2 seconds...")
                        time.sleep(2)
                    else:
                        raise attempt_e
            
            # Should not reach here
            return None
            
        else:
            # ✅ Local file - direct read
            print(f"[ANALYZER] 📖 Reading local face photo: {face_photo_url}")
            
            if not os.path.exists(face_photo_url):
                print(f"[ANALYZER] ❌ Local file not found: {face_photo_url}")
                return None
            
            ref_img = cv2.imread(face_photo_url)
            
            if ref_img is None:
                print(f"[ANALYZER] ❌ Failed to read local image: {face_photo_url}")
                return None
            
            print(f"[ANALYZER] ✅ Local image loaded: shape={ref_img.shape}")
            return ref_img
            
    except Exception as e:
        print(f"[ANALYZER] ❌ Error downloading reference face: {e}")
        traceback.print_exc()
        return None

def get_ref_embedding(face_photo_url):
    """Get reference face embedding from URL or local path - with robust error handling"""
    print(f"\n[ANALYZER] ╔════════════════════════════════════════════════════════╗")
    print(f"[ANALYZER] ║ INITIALIZING FACE RECOGNITION (face_mismatch detection) ║")
    print(f"[ANALYZER] ╚════════════════════════════════════════════════════════╝")
    
    try:
        if _face_app is None:
            print("[ANALYZER] ❌ FATAL: InsightFace not available")
            print("[ANALYZER]    → face_mismatch detection DISABLED")
            return None
        
        print(f"[ANALYZER] Step 1: Downloading reference face image...")
        ref_img = download_ref_face(face_photo_url)
        
        if ref_img is None:
            print(f"[ANALYZER] ❌ STEP 1 FAILED: Could not load reference image")
            print(f"[ANALYZER]    → Possible causes:")
            print(f"[ANALYZER]      1. URL invalid or timeout (try again later)")
            print(f"[ANALYZER]      2. Image file corrupted")
            print(f"[ANALYZER]      3. Temp folder permission issues")
            print(f"[ANALYZER]    → face_mismatch detection DISABLED")
            return None
        
        if ref_img.size == 0:
            print(f"[ANALYZER] ❌ STEP 1 FAILED: Image is empty (0 bytes)")
            print(f"[ANALYZER]    → face_mismatch detection DISABLED")
            return None
        
        print(f"[ANALYZER] ✅ STEP 1 OK: Image loaded ({ref_img.shape[0]}x{ref_img.shape[1]} pixels)")
        
        # ===================== STEP 2: EXTRACT FACE =====================
        print(f"\n[ANALYZER] Step 2: Extracting face from reference image...")
        print(f"[ANALYZER]    Using InsightFace model (buffalo_l)...")
        
        faces = _face_app.get(ref_img)
        print(f"[ANALYZER]    Detected {len(faces)} face(s)")
        
        if len(faces) == 0:
            print(f"[ANALYZER] ❌ STEP 2 FAILED: NO FACE DETECTED in reference photo!")
            print(f"[ANALYZER]    → Possible causes:")
            print(f"[ANALYZER]      1. Image quality too low (try better photo)")
            print(f"[ANALYZER]      2. Face too small or obscured")
            print(f"[ANALYZER]      3. Multiple faces or wrong person")
            print(f"[ANALYZER]      4. Extreme lighting conditions")
            print(f"[ANALYZER]    → Recommendation: Use clear face photo, good lighting, facing camera")
            print(f"[ANALYZER]    → face_mismatch detection DISABLED")
            return None
        
        if len(faces) > 1:
            print(f"[ANALYZER] ⚠️  WARNING: Multiple faces detected ({len(faces)})")
            print(f"[ANALYZER]    → Using first face for reference")
        
        print(f"[ANALYZER] ✅ STEP 2 OK: Face detected")
        
        # ===================== STEP 3: EXTRACT EMBEDDING =====================
        print(f"\n[ANALYZER] Step 3: Extracting face embedding...")
        
        embedding = faces[0].embedding
        
        if embedding is None or embedding.size == 0:
            print(f"[ANALYZER] ❌ STEP 3 FAILED: Embedding extraction failed")
            print(f"[ANALYZER]    → face_mismatch detection DISABLED")
            return None
        
        # Validate embedding
        norm = np.linalg.norm(embedding)
        if norm == 0:
            print(f"[ANALYZER] ❌ STEP 3 FAILED: Invalid embedding (zero norm)")
            print(f"[ANALYZER]    → face_mismatch detection DISABLED")
            return None
        
        print(f"[ANALYZER] ✅ STEP 3 OK: Embedding extracted")
        
        # ===================== STEP 4: VALIDATION =====================
        # (Silent validation - logs will clutter terminal)
        
        # ===================== SUCCESS =====================
        print(f"[ANALYZER] ✅ Face recognition initialized (similarity threshold: {SIM_THRESHOLD})")
        
        return embedding
        
    except Exception as e:
        print(f"\n[ANALYZER] ❌ FATAL ERROR in get_ref_embedding(): {e}")
        traceback.print_exc()
        print(f"[ANALYZER] face_mismatch detection DISABLED")
        return None


# ============ STABLE ANALYZER CLASS ============

class StableParticipantAnalyzer:
    """
    Stable real-time analyzer for single participant
    Features:
    - Smart caching algorithm (KUNCI STABILITAS)
    - Face mismatch detection with cosine similarity
    - Head movement analysis
    - Gaze tracking
    - Multi-violation tracking
    """
    
    def __init__(self, participant_id, face_photo_url):
        """Initialize analyzer for a participant"""
        self.participant_id = participant_id
        self.face_photo_url = face_photo_url
        
        # Get reference embedding
        self.ref_embedding = get_ref_embedding(face_photo_url)
        
        # Frame counter for interval-based analysis
        self.frame_count = 0
        
        # ============ SMART CACHE (KUNCI STABILITAS) ============
        self.cached_yolo = None              # (label, conf, bbox)
        self.cached_face = None              # (bbox, similarity)
        self.cached_gaze = None              # string
        
        # ✅ REPORT STATUS OF FACE RECOGNITION INITIALIZATION
        if self.ref_embedding is not None:
            print(f"[ANALYZER] P{participant_id}: face_mismatch detection READY")
        else:
            print(f"[ANALYZER] P{participant_id}: face_mismatch detection DISABLED")
    
    def analyze_frame(self, frame):
        """
        Analyze single frame with smart caching
        - YOLO analysis every 2 frames
        - Face recognition every 10 frames
        - Gaze tracking every 3 frames
        - Render with cached data on EVERY frame (smooth tracking)
        
        Returns:
        {
            'yolo_label': str,
            'yolo_conf': float,
            'yolo_bbox': tuple,
            'face_similarity': float,
            'face_bbox': tuple,
            'gaze_state': str,
            'violations': list,
            'face_status': str,  # 'face_authenticated' or 'face_mismatch'
            'frame_count': int,
            'boxes': list  # For rendering (max 2 boxes)
        }
        """
        self.frame_count += 1
        violations = []
        
        result = {
            'yolo_label': 'face_normal',
            'yolo_conf': 0,
            'yolo_bbox': None,
            'face_similarity': -1,
            'face_bbox': None,
            'face_status': 'unknown',
            'gaze_state': None,
            'violations': [],
            'frame_count': self.frame_count,
            'boxes': []
        }
        
        # ================= YOLO ANALYSIS (Every 2 frames) =================
        if self.frame_count % YOLO_INTERVAL == 0 and _yolo:
            try:
                yolo_res = _yolo(
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
                    self.cached_yolo = (label, conf, bbox)
                    violations.append(label)
                else:
                    # ✅ NO FACE DETECTED IN THIS FRAME - CRITICAL VIOLATION
                    # When camera is black/blocked, no face should be detected
                    self.cached_yolo = None
                    violations.append('no_face')
            except Exception as e:
                print(f"[ANALYZER] YOLO error: {e}")
                self.cached_yolo = None
                violations.append('no_face')
        
        # ================= FACE ANALYSIS (Every 10 frames) =================
        if self.frame_count % FACE_INTERVAL == 0 and _face_app and self.ref_embedding is not None:
            try:
                faces = _face_app.get(frame)
                print(f"[ANALYZER] 🔍 FACE ANALYSIS (frame {self.frame_count}): Detected {len(faces)} face(s)")
                
                if len(faces) == 1:
                    face = faces[0]
                    sim = cosine_sim(face.embedding, self.ref_embedding)
                    bbox = tuple(map(int, face.bbox))
                    self.cached_face = (bbox, sim)
                    
                    # ✅ DETAILED FACE MATCHING LOGGING
                    print(f"[ANALYZER] 🔗 Face matching: similarity={sim:.6f} (threshold={SIM_THRESHOLD})")
                    print(f"[ANALYZER]    - Frame embedding L2-norm: {np.linalg.norm(face.embedding):.6f}")
                    print(f"[ANALYZER]    - Reference embedding L2-norm: {np.linalg.norm(self.ref_embedding):.6f}")
                    
                    if sim < SIM_THRESHOLD:
                        # ❌ DIFFERENT PERSON - FACE MISMATCH
                        violations.append("face_mismatch")
                        print(f"[ANALYZER] 🚨🚨 FACE MISMATCH DETECTED! PID={self.participant_id}")
                        print(f"[ANALYZER]    ❌ Similarity={sim:.6f} < Threshold={SIM_THRESHOLD}")
                        print(f"[ANALYZER]    ❌ VERDICT: Different person (IMPOSTOR) - VIOLATION TRIGGERED")
                    else:
                        # ✅ SAME PERSON - FACE AUTHENTICATED
                        print(f"[ANALYZER] ✅✅ FACE AUTHENTICATED! PID={self.participant_id}")
                        print(f"[ANALYZER]    ✅ Similarity={sim:.6f} >= Threshold={SIM_THRESHOLD}")
                        print(f"[ANALYZER]    ✅ VERDICT: Same person - FACE_NORMAL status")
                else:
                    self.cached_face = None
                    if len(faces) == 0:
                        violations.append("no_face_detected")
                        print(f"[ANALYZER] ⚠️ No face detected in frame (PID={self.participant_id})")
                    else:
                        violations.append("multi_face")
                        print(f"[ANALYZER] ⚠️ Multiple faces detected ({len(faces)}) (PID={self.participant_id})")
            except Exception as e:
                print(f"[ANALYZER] ❌ Face analysis error: {e}")
                traceback.print_exc()
                self.cached_face = None
        
        # ================= GAZE ANALYSIS (Every 3 frames) =================
        if self.frame_count % GAZE_INTERVAL == 0 and _gaze:
            try:
                _gaze.refresh(frame)
                if _gaze.is_left() or _gaze.is_right():
                    self.cached_gaze = "eye_looking_away"
                elif _gaze.is_blinking():
                    self.cached_gaze = "blinking"
                else:
                    self.cached_gaze = None
            except Exception as e:
                print(f"[ANALYZER] Gaze tracking error: {e}")
                self.cached_gaze = None
        
        # ================= RENDER WITH CACHED DATA (Every frame) =================
        boxes = []
        
        # YOLO box
        if self.cached_yolo:
            label, conf, (x1, y1, x2, y2) = self.cached_yolo
            if label != "face_normal":
                violations.append(label)
            
            result['yolo_label'] = label
            result['yolo_conf'] = conf
            result['yolo_bbox'] = (x1, y1, x2, y2)
            
            boxes.append({
                'type': 'yolo',
                'label': label,
                'bbox': (x1, y1, x2, y2),
                'color': (255, 0, 0),
                'priority': 2
            })
        
        # Face box
        if self.cached_face:
            (x1, y1, x2, y2), sim = self.cached_face
            result['face_similarity'] = float(sim)
            result['face_bbox'] = (x1, y1, x2, y2)
            
            if sim < SIM_THRESHOLD:
                violations.append("face_mismatch")
                result['face_status'] = 'face_mismatch'
                color = (0, 0, 255)  # Red
            else:
                result['face_status'] = 'face_authenticated'
                color = (0, 255, 0)  # Green
            
            boxes.append({
                'type': 'face',
                'label': f"Match {sim:.4f}",
                'bbox': (x1, y1, x2, y2),
                'color': color,
                'priority': 3
            })
        
        # Gaze box
        if self.cached_gaze:
            violations.append(self.cached_gaze)
            result['gaze_state'] = self.cached_gaze
        
        # ✅ PRIORITY-BASED VIOLATION RANKING (only return 1 primary violation)
        # Priority order: face_mismatch > no_face > face_not_forward > multi_face > eyes_looking_away > blinking
        all_violations = list(set(violations))
        
        # Determine primary violation (highest priority)
        primary_violation = None
        priority_order = ['face_mismatch', 'no_face', 'face_not_forward', 'multi_face', 'eyes_looking_away', 'blinking', 'no_face_detected']
        
        for violation_type in priority_order:
            if violation_type in all_violations:
                primary_violation = violation_type
                break
        
        # Only return primary violation (1 per frame), not array
        result['violations'] = [primary_violation] if primary_violation else []
        
        # Log which violation is primary
        if primary_violation:
            print(f"[ANALYZER] 🔴 PRIMARY VIOLATION: {primary_violation} (out of {all_violations})")
        else:
            print(f"[ANALYZER] ✅ NO VIOLATIONS")
        
        return result


# ============ CONVENIENCE FUNCTION ============

def analyze_frame_simple(frame, participant_id, face_photo_url, analyzer_dict):
    """
    Convenience function for simple frame analysis
    Uses a dictionary to cache analyzers
    
    Usage:
    analyzers = {}
    result = analyze_frame_simple(frame, 1, "participant.png", analyzers)
    """
    if participant_id not in analyzer_dict:
        analyzer_dict[participant_id] = StableParticipantAnalyzer(participant_id, face_photo_url)
    
    analyzer = analyzer_dict[participant_id]
    return analyzer.analyze_frame(frame)


# Engine ready for import