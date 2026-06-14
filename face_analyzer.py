"""
FACE ANALYSIS ENGINE - Using Stable Proctoring Engine
Wraps the proven stable analysis from realtime_proctoring_stable_highfps.py
for integration with app.py

✅ FITUR:
- Face mismatch detection (stable dengan cosine similarity)
- Head movement analysis (stabil dengan smart caching)
- YOLO pose classification
- Gaze tracking
- Multi-participant support via class instantiation
"""
import os
import time
import numpy as np
import cv2
import cloudinary.uploader
import mysql.connector
from datetime import datetime
from dotenv import load_dotenv
from mysql.connector import Error
import threading
import traceback

# Import stable analyzer dari realtime_proctoring_stable_highfps.py
from realtime_proctoring_stable_highfps import StableParticipantAnalyzer

load_dotenv()

# ============ CONFIG ============
VIOLATION_DURATION = int(os.getenv("VIOLATION_DURATION", 6))  # Dalam DETIK, bukan millisecond
CLOUDINARY_FOLDER = os.getenv("CLOUDINAR_MAIN_FOLDER", "proctoring_app/")

# Database config
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT')),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

print("[ANALYZER] Ready")

def get_db_connection():
    """Get MySQL connection"""
    try:
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            port=int(DB_CONFIG['port']),
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        return connection
    except Error as e:
        print(f"[ANALYZER] Database connection error: {e}")
        return None

def upload_violation_evidence(frame, violation_type, participant_id, session_id):
    """Upload violation evidence to Cloudinary"""
    try:
        if frame is None or frame.size == 0:
            return None
        
        _, buffer = cv2.imencode('.jpg', frame)
        
        result = cloudinary.uploader.upload(
            buffer.tobytes(),
            folder=CLOUDINARY_FOLDER + f'violations/{participant_id}/',
            resource_type='auto',
            quality='auto',
            public_id=f'violation_{violation_type}_{int(time.time() * 1000)}'
        )
        
        if result and result.get('secure_url'):
            return result.get('secure_url')
        return None
            
    except Exception as e:
        return None

def log_violation_to_db(participant_id, violation_type, evidence_url, duration):
    """Log violation to database"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
        
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO violations 
            (participant_id, violation_type, description, start_time, end_time, duration_seconds)
            VALUES (%s, %s, %s, NOW(), NOW(), %s)
        """
        
        cursor.execute(insert_query, (
            participant_id,
            violation_type,
            f'Face analysis violation: {violation_type}',
            int(duration)
        ))
        
        violation_id = cursor.lastrowid
        
        if evidence_url:
            evidence_query = """
                INSERT INTO violation_evidence 
                (violation_id, evidence_url, created_at)
                VALUES (%s, %s, NOW())
            """
            cursor.execute(evidence_query, (violation_id, evidence_url))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True
    except Error as e:
        return False

# ============ ANALYZER CLASS ============

class ParticipantAnalyzer:
    """Wrapper around StableParticipantAnalyzer with violation tracking and database logging"""
    
    def __init__(self, participant_id, session_id, face_photo_url):
        self.participant_id = participant_id
        self.session_id = session_id
        self.face_photo_url = face_photo_url
        
        # Use stable analyzer dari realtime_proctoring_stable_highfps.py
        self.stable_analyzer = StableParticipantAnalyzer(participant_id, face_photo_url)
        
        # Violation tracking
        self.violation_start_time = None
        self.current_violation_type = None
        self.last_logged_violations = {}
        self.violation_cooldown = 5
        
        self.cloudinary_upload_count = 0
        self.max_uploads_per_session = 3
        self.last_upload_time = 0
        self.min_upload_interval = 180
    
    def analyze_frame(self, frame):
        """Analyze frame using stable analyzer"""
        result = self.stable_analyzer.analyze_frame(frame)
        
        # Restructure result for compatibility dengan app.py
        analysis_result = {
            'yolo_class': result.get('yolo_label', 'face_normal'),
            'yolo_conf': result.get('yolo_conf', 0),
            'yolo_bbox': result.get('yolo_bbox'),
            'face_similarity': result.get('face_similarity', -1),
            'face_bbox': result.get('face_bbox'),
            'face_status': result.get('face_status', 'unknown'),
            'gaze_state': result.get('gaze_state'),
            'violations': result.get('violations', []),
            'frame_count': result.get('frame_count', 0),
            'best_boxes': result.get('boxes', [])
        }
        
        return analysis_result
    
    def process_violations(self, analysis_result, frame):
        """
        Process detected violations:
        - UI: Show ALL violations (face_mismatch, face_not_forward, multi_face, eyes_looking_away)
        - DB: Only log face_mismatch to database + Cloudinary
        """
        violations = analysis_result.get('violations', [])
        current_time = time.time()
        
        # ✅ TRACK ALL VIOLATIONS (for UI freeze logic)
        # But only log face_mismatch to database
        has_any_violation = len(violations) > 0
        
        if not has_any_violation:
            if self.violation_start_time is not None:
                duration = current_time - self.violation_start_time
                self.violation_start_time = None
                self.current_violation_type = None
            return False
        
        primary_violation = violations[0]
        
        if primary_violation != self.current_violation_type:
            self.violation_start_time = current_time
            self.current_violation_type = primary_violation
        
        if self.violation_start_time:
            duration = current_time - self.violation_start_time
            
            if primary_violation == 'face_mismatch':
                evidence_url = None
                should_upload = False
                
                upload_interval_passed = (current_time - self.last_upload_time) >= self.min_upload_interval
                uploads_remaining = self.cloudinary_upload_count < self.max_uploads_per_session
                
                if uploads_remaining and upload_interval_passed and duration >= VIOLATION_DURATION:
                    should_upload = True
                    time_until_next = self.min_upload_interval - (current_time - self.last_upload_time)
                    print(f"[ANALYZER] ⏳ Next upload in {time_until_next:.0f}s")
                
                if should_upload and frame is not None and frame.size > 0:
                    evidence_url = upload_violation_evidence(frame, 'face_mismatch', self.participant_id, self.session_id)
                    if evidence_url:
                        self.cloudinary_upload_count += 1
                        self.last_upload_time = current_time
                
                if duration >= VIOLATION_DURATION:
                    last_logged = self.last_logged_violations.get('face_mismatch', 0)
                    if current_time - last_logged >= self.violation_cooldown:
                        log_violation_to_db(
                            self.participant_id,
                            'face_mismatch',
                            evidence_url,
                            duration
                        )
                        self.last_logged_violations['face_mismatch'] = current_time
        
        return True

# ============ ANALYZER MANAGER ============

class AnalyzerManager:
    """Manages multiple participant analyzers"""
    
    def __init__(self):
        self.analyzers = {}
        self.lock = threading.Lock()
    
    def create_analyzer(self, participant_id, session_id, face_photo_url):
        """Create analyzer for new participant"""
        with self.lock:
            if participant_id not in self.analyzers:
                self.analyzers[participant_id] = ParticipantAnalyzer(participant_id, session_id, face_photo_url)
    
    def remove_analyzer(self, participant_id):
        """Remove analyzer when exam ends"""
        with self.lock:
            if participant_id in self.analyzers:
                del self.analyzers[participant_id]
    
    def process_frame(self, participant_id, frame):
        """Process single frame and return analysis result"""
        if participant_id not in self.analyzers:
            return None
        
        analyzer = self.analyzers[participant_id]
        analysis_result = analyzer.analyze_frame(frame)
        analyzer.process_violations(analysis_result, frame)
        return analysis_result
    
    def get_analyzer(self, participant_id):
        """Get analyzer instance"""
        return self.analyzers.get(participant_id)

# Global manager instance
analyzer_manager = AnalyzerManager()

print("[ANALYZER] Ready")
