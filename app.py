from flask import Flask, render_template, request, redirect, url_for, session
from functools import wraps
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
import cloudinary
import cloudinary.uploader
import cv2
import numpy as np
import base64
import threading

# Import face analyzer
from face_analyzer import analyzer_manager

# Load environment variables
load_dotenv()

# File untuk menyimpan sessions (opsional, jika database tidak connect)
SESSIONS_FILE = 'sessions.json'

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key')

# Admin credentials from .env
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'password123')
PORT = int(os.getenv('PORT', 5000))

# Database configuration from .env
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT')),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

# Cloudinary configuration from .env
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)
CLOUDINARY_FOLDER = os.getenv('CLOUDINAR_MAIN_FOLDER', 'proctoring_app/')

# Helper function untuk connect ke database
def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

# Decorator untuk check login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function untuk load sessions dari file (fallback)
def load_sessions():
    try:
        if os.path.exists(SESSIONS_FILE):
            with open(SESSIONS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return []

# Helper function untuk save sessions ke file (fallback)
def save_sessions(sessions):
    with open(SESSIONS_FILE, 'w') as f:
        json.dump(sessions, f, indent=2)

# Route: Login Page
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Validasi credentials
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session['username'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('admin_login.html', error='Username atau password salah!')
    
    return render_template('admin_login.html')

# Route: Dashboard
@app.route('/admin/dashboard')
@login_required
def dashboard():
    username = session.get('username', 'Admin')
    return render_template('admin_dashboard.html', username=username)

# Route: Admin Sessions - List & Add
@app.route('/admin/sessions', methods=['GET', 'POST'])
@login_required
def admin_sessions():
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Tambah session baru
        session_name = request.form.get('session_name')
        exam_end_code = request.form.get('exam_end_code')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        exam_url = request.form.get('exam_url')
        
        # Validasi
        if not all([session_name, exam_end_code, start_time, end_time, exam_url]):
            sessions_list = get_all_sessions(conn) if conn else []
            return render_template('admin_session.html', sessions=sessions_list, error='Semua field harus diisi!')
        
        # Insert ke database
        if conn:
            try:
                cursor = conn.cursor()
                query = """
                    INSERT INTO sessions (session_name, exam_end_code, start_time, end_time, exam_url)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (session_name, exam_end_code, start_time, end_time, exam_url))
                conn.commit()
                cursor.close()
                return redirect(url_for('admin_sessions'))
            except Error as e:
                print(f"Error inserting session: {e}")
                sessions_list = get_all_sessions(conn)
                return render_template('admin_session.html', sessions=sessions_list, error=f'Error: {str(e)}')
            finally:
                if conn.is_connected():
                    conn.close()
        
        return redirect(url_for('admin_sessions'))
    
    # GET: Tampilkan list sessions
    sessions_list = get_all_sessions(conn) if conn else []
    if conn and conn.is_connected():
        conn.close()
    
    return render_template('admin_session.html', sessions=sessions_list)

# Helper function untuk get semua sessions dari database
def get_all_sessions(conn):
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM sessions ORDER BY created_at DESC"
        cursor.execute(query)
        sessions = cursor.fetchall()
        cursor.close()
        return sessions
    except Error as e:
        print(f"Error fetching sessions: {e}")
        return []

# Route: Delete Session
@app.route('/admin/sessions/delete/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    conn = get_db_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
            query = "DELETE FROM sessions WHERE id = %s"
            cursor.execute(query, (session_id,))
            conn.commit()
            cursor.close()
        except Error as e:
            print(f"Error deleting session: {e}")
        finally:
            if conn.is_connected():
                conn.close()
    
    return redirect(url_for('admin_sessions'))

# Route: Edit Session - Show form
@app.route('/admin/sessions/edit/<int:session_id>', methods=['GET', 'POST'])
@login_required
def edit_session(session_id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Update session
        session_name = request.form.get('session_name')
        exam_end_code = request.form.get('exam_end_code')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        exam_url = request.form.get('exam_url')
        
        # Validasi
        if not all([session_name, exam_end_code, start_time, end_time, exam_url]):
            session_data = get_session_by_id(conn, session_id) if conn else None
            return render_template('edit_session.html', session=session_data, error='Semua field harus diisi!')
        
        # Update ke database
        if conn:
            try:
                cursor = conn.cursor()
                query = """
                    UPDATE sessions 
                    SET session_name = %s, exam_end_code = %s, start_time = %s, end_time = %s, exam_url = %s
                    WHERE id = %s
                """
                cursor.execute(query, (session_name, exam_end_code, start_time, end_time, exam_url, session_id))
                conn.commit()
                cursor.close()
                return redirect(url_for('admin_sessions'))
            except Error as e:
                print(f"Error updating session: {e}")
                session_data = get_session_by_id(conn, session_id)
                return render_template('edit_session.html', session=session_data, error=f'Error: {str(e)}')
            finally:
                if conn.is_connected():
                    conn.close()
    
    # GET: Tampilkan form edit
    session_data = get_session_by_id(conn, session_id) if conn else None
    if conn and conn.is_connected():
        conn.close()
    
    if not session_data:
        return redirect(url_for('admin_sessions'))
    
    return render_template('edit_session.html', session=session_data)

# Helper function untuk get session by id
def get_session_by_id(conn, session_id):
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM sessions WHERE id = %s"
        cursor.execute(query, (session_id,))
        session = cursor.fetchone()
        cursor.close()
        return session
    except Error as e:
        print(f"Error fetching session: {e}")
        return None

# ===================== PARTICIPANTS CRUD =====================

# Route: Admin Participants - List & Add
@app.route('/admin/participants', methods=['GET', 'POST'])
@login_required
def admin_participants():
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Tambah participant baru
        participant_number = request.form.get('participant_number')
        participant_name = request.form.get('participant_name')
        session_id = request.form.get('session_id')
        face_photo = request.files.get('face_photo')
        
        # Validasi
        if not all([participant_number, participant_name, session_id]):
            sessions_list = get_all_sessions(conn) if conn else []
            participants_list = get_all_participants(conn) if conn else []
            return render_template('admin_participant.html', 
                                   participants=participants_list,
                                   sessions=sessions_list,
                                   error='Nomor peserta, nama, dan sesi harus diisi!')
        
        # Upload foto ke Cloudinary jika ada
        face_photo_url = None
        if face_photo:
            try:
                upload_result = cloudinary.uploader.upload(
                    face_photo,
                    folder=CLOUDINARY_FOLDER + 'participants/',
                    resource_type='auto'
                )
                face_photo_url = upload_result['secure_url']
            except Exception as e:
                print(f"Error uploading to Cloudinary: {e}")
                sessions_list = get_all_sessions(conn) if conn else []
                participants_list = get_all_participants(conn) if conn else []
                return render_template('admin_participant.html',
                                       participants=participants_list,
                                       sessions=sessions_list,
                                       error=f'Error upload foto: {str(e)}')
        
        # Insert ke database
        if conn:
            try:
                cursor = conn.cursor()
                query = """
                    INSERT INTO participants (participant_number, participant_name, face_photo_url, session_id)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(query, (participant_number, participant_name, face_photo_url, session_id))
                conn.commit()
                cursor.close()
                return redirect(url_for('admin_participants'))
            except Error as e:
                print(f"Error inserting participant: {e}")
                sessions_list = get_all_sessions(conn)
                participants_list = get_all_participants(conn)
                return render_template('admin_participant.html',
                                       participants=participants_list,
                                       sessions=sessions_list,
                                       error=f'Error: {str(e)}')
            finally:
                if conn.is_connected():
                    conn.close()
        
        return redirect(url_for('admin_participants'))
    
    # GET: Tampilkan list participants
    participants_list = get_all_participants(conn) if conn else []
    sessions_list = get_all_sessions(conn) if conn else []
    if conn and conn.is_connected():
        conn.close()
    
    return render_template('admin_participant.html', participants=participants_list, sessions=sessions_list)

# Helper function untuk get semua participants dari database
def get_all_participants(conn):
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT p.*, s.session_name 
            FROM participants p
            LEFT JOIN sessions s ON p.session_id = s.id
            ORDER BY p.created_at DESC
        """
        cursor.execute(query)
        participants = cursor.fetchall()
        cursor.close()
        return participants
    except Error as e:
        print(f"Error fetching participants: {e}")
        return []

# Route: Edit Participant
@app.route('/admin/participants/edit/<int:participant_id>', methods=['GET', 'POST'])
@login_required
def edit_participant(participant_id):
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Update participant
        participant_number = request.form.get('participant_number')
        participant_name = request.form.get('participant_name')
        session_id = request.form.get('session_id')
        face_photo = request.files.get('face_photo')
        
        # Validasi
        if not all([participant_number, participant_name, session_id]):
            participant_data = get_participant_by_id(conn, participant_id) if conn else None
            sessions_list = get_all_sessions(conn) if conn else []
            return render_template('edit_participant.html',
                                   participant=participant_data,
                                   sessions=sessions_list,
                                   error='Semua field harus diisi!')
        
        # Upload foto baru jika ada
        face_photo_url = None
        participant_data = get_participant_by_id(conn, participant_id)
        
        if face_photo:
            try:
                upload_result = cloudinary.uploader.upload(
                    face_photo,
                    folder=CLOUDINARY_FOLDER + 'participants/',
                    resource_type='auto'
                )
                face_photo_url = upload_result['secure_url']
            except Exception as e:
                print(f"Error uploading to Cloudinary: {e}")
                sessions_list = get_all_sessions(conn) if conn else []
                return render_template('edit_participant.html',
                                       participant=participant_data,
                                       sessions=sessions_list,
                                       error=f'Error upload foto: {str(e)}')
        else:
            # Gunakan foto lama jika tidak ada foto baru
            face_photo_url = participant_data.get('face_photo_url') if participant_data else None
        
        # Update ke database
        if conn:
            try:
                cursor = conn.cursor()
                query = """
                    UPDATE participants 
                    SET participant_number = %s, participant_name = %s, session_id = %s, face_photo_url = %s
                    WHERE id = %s
                """
                cursor.execute(query, (participant_number, participant_name, session_id, face_photo_url, participant_id))
                conn.commit()
                cursor.close()
                return redirect(url_for('admin_participants'))
            except Error as e:
                print(f"Error updating participant: {e}")
                participant_data = get_participant_by_id(conn, participant_id)
                sessions_list = get_all_sessions(conn)
                return render_template('edit_participant.html',
                                       participant=participant_data,
                                       sessions=sessions_list,
                                       error=f'Error: {str(e)}')
            finally:
                if conn.is_connected():
                    conn.close()
    
    # GET: Tampilkan form edit
    participant_data = get_participant_by_id(conn, participant_id) if conn else None
    sessions_list = get_all_sessions(conn) if conn else []
    if conn and conn.is_connected():
        conn.close()
    
    if not participant_data:
        return redirect(url_for('admin_participants'))
    
    return render_template('edit_participant.html', participant=participant_data, sessions=sessions_list)

# Helper function untuk get participant by id
def get_participant_by_id(conn, participant_id):
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM participants WHERE id = %s"
        cursor.execute(query, (participant_id,))
        participant = cursor.fetchone()
        cursor.close()
        return participant
    except Error as e:
        print(f"Error fetching participant: {e}")
        return None

# Route: Delete Participant
@app.route('/admin/participants/delete/<int:participant_id>', methods=['POST'])
@login_required
def delete_participant(participant_id):
    conn = get_db_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
            query = "DELETE FROM participants WHERE id = %s"
            cursor.execute(query, (participant_id,))
            conn.commit()
            cursor.close()
        except Error as e:
            print(f"Error deleting participant: {e}")
        finally:
            if conn.is_connected():
                conn.close()
    
    return redirect(url_for('admin_participants'))

# Route: Logout Admin
@app.route('/admin/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Route: Logout Participant
@app.route('/participant/logout')
def participant_logout():
    session.clear()
    return redirect(url_for('participant_login'))

# Route: Redirect root ke login peserta (default)
@app.route('/')
def index():
    return redirect(url_for('participant_login'))

# ===================== PARTICIPANT LOGIN & DASHBOARD =====================

# Route: Participant Login
@app.route('/login', methods=['GET', 'POST'])
def participant_login():
    if request.method == 'POST':
        participant_number = request.form.get('participant_number')
        
        # Validasi nomor peserta
        if not participant_number:
            return render_template('login.html', error='Nomor peserta harus diisi!')
        
        # Cari peserta di database
        conn = get_db_connection()
        participant = None
        
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM participants WHERE participant_number = %s"
                cursor.execute(query, (participant_number,))
                participant = cursor.fetchone()
                cursor.close()
            except Error as e:
                print(f"Error finding participant: {e}")
                return render_template('login.html', error='Error mencari peserta!')
            finally:
                if conn.is_connected():
                    conn.close()
        
        # Validasi peserta ditemukan
        if participant:
            session['participant_logged_in'] = True
            session['participant_id'] = participant['id']
            session['participant_number'] = participant_number
            session['participant_name'] = participant['participant_name']
            return redirect(url_for('participant_dashboard'))
        else:
            return render_template('login.html', error='Nomor peserta tidak ditemukan!')
    
    return render_template('login.html')

# Helper function untuk check exam status
def get_exam_status(start_time, end_time):
    from datetime import datetime
    now = datetime.now()
    
    if now < start_time:
        return 'Belum Dimulai'
    elif now > end_time:
        return 'Selesai'
    else:
        return 'Sedang Berlangsung'

# Route: Participant Dashboard
@app.route('/participant/dashboard')
def participant_dashboard():
    if 'participant_logged_in' not in session:
        return redirect(url_for('participant_login'))
    
    participant_id = session.get('participant_id')
    participant_name = session.get('participant_name')
    participant_number = session.get('participant_number')
    
    # Get participant data lengkap dari database
    conn = get_db_connection()
    participant_data = None
    session_data = None
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get participant data
            query = """
                SELECT p.*, s.session_name, s.start_time, s.end_time, s.exam_url
                FROM participants p
                LEFT JOIN sessions s ON p.session_id = s.id
                WHERE p.id = %s
            """
            cursor.execute(query, (participant_id,))
            participant_data = cursor.fetchone()
            cursor.close()
        except Error as e:
            print(f"Error fetching participant data: {e}")
        finally:
            if conn.is_connected():
                conn.close()
    
    # Hitung status ujian jika ada session data
    exam_status = None
    if participant_data and participant_data.get('start_time'):
        exam_status = get_exam_status(participant_data['start_time'], participant_data['end_time'])
    
    return render_template('participant_dashboard-NEW.html', 
                          participant=participant_data,
                          exam_status=exam_status)

# ===================== EXAM ACTIVITY LOGGING =====================

# Helper function untuk log exam activity
def log_exam_activity(participant_id, session_id, activity_type, description, extra_data=None):
    """Log exam activity untuk full lifecycle tracking"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        extra_json = json.dumps(extra_data) if extra_data else None
        
        query = """
            INSERT INTO exam_activity_log 
            (participant_id, session_id, activity_type, description, extra_data)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (participant_id, session_id, activity_type, description, extra_json))
        conn.commit()
        cursor.close()
        return True
    except Error as e:
        print(f"Error logging exam activity: {e}")
        return False
    finally:
        if conn.is_connected():
            conn.close()

# Route: Log exam start
@app.route('/api/exam-start', methods=['POST'])
def exam_start():
    """Log ketika peserta mulai akses ujian"""
    try:
        data = request.get_json()
        participant_id = data.get('participant_id')
        session_id = data.get('session_id')
        
        if not participant_id or not session_id:
            return {'status': 'error', 'message': 'Missing required fields'}, 400
        
        # Log exam start
        log_exam_activity(
            participant_id, 
            session_id, 
            'EXAM_START', 
            'Peserta mulai mengakses ujian',
            {'start_time': datetime.now().isoformat()}
        )
        
        return {'status': 'success', 'message': 'Exam started'}, 200
    except Exception as e:
        print(f"Error: {e}")
        return {'status': 'error', 'message': str(e)}, 500

# Route: Verify exam end code dan finalize exam
@app.route('/api/end-exam', methods=['POST'])
def end_exam():
    """Verify exam_end_code dan mark exam as ended"""
    try:
        data = request.get_json()
        participant_id = data.get('participant_id')
        session_id = data.get('session_id')
        exam_end_code = data.get('exam_end_code')
        
        if not all([participant_id, session_id, exam_end_code]):
            return {'status': 'error', 'message': 'Missing required fields'}, 400
        
        conn = get_db_connection()
        if not conn:
            return {'status': 'error', 'message': 'Database connection failed'}, 500
        
        try:
            cursor = conn.cursor(dictionary=True)
            
            # Get session dan verify exam_end_code
            session_query = "SELECT exam_end_code FROM sessions WHERE id = %s"
            cursor.execute(session_query, (session_id,))
            session = cursor.fetchone()
            
            if not session:
                cursor.close()
                return {'status': 'error', 'message': 'Sesi tidak ditemukan'}, 404
            
            # Verify code
            if session['exam_end_code'] != exam_end_code:
                # Log failed attempt
                log_exam_activity(
                    participant_id,
                    session_id,
                    'EXAM_END_FAILED',
                    f'Percobaan input kode akhir gagal (kode: {exam_end_code})'
                )
                cursor.close()
                return {'status': 'error', 'message': 'Kode akhir ujian salah!'}, 400
            
            # Code is valid - finalize exam
            # Get exam start time from activity log
            # FIXED: Use activity_timestamp instead of created_at
            activity_query = """
                SELECT MIN(activity_timestamp) as exam_start_time 
                FROM exam_activity_log 
                WHERE participant_id = %s AND activity_type IN ('EXAM_START')
            """
            try:
                cursor.execute(activity_query, (participant_id,))
                activity_result = cursor.fetchone()
                exam_start_time = activity_result['exam_start_time'] if activity_result and activity_result['exam_start_time'] else None
            except Error as e:
                print(f"[WARN] Error getting exam start time from activity log: {e}")
                print(f"[WARN] Using current time as fallback")
                exam_start_time = None
            
            # Log exam end
            exam_end_time = datetime.now()
            log_exam_activity(
                participant_id,
                session_id,
                'EXAM_END',
                'Peserta berhasil menyelesaikan ujian dengan kode yang benar',
                {'end_time': exam_end_time.isoformat()}
            )
            
            # Calculate exam duration in seconds
            if exam_start_time:
                exam_duration = int((exam_end_time - exam_start_time).total_seconds())
            else:
                exam_duration = 0
            
            # Finalize results (hitung keputusan)
            violations_query = "SELECT COUNT(*) as total, COALESCE(SUM(duration_seconds), 0) as total_duration FROM violations WHERE participant_id = %s"
            cursor.execute(violations_query, (participant_id,))
            violation_stats = cursor.fetchone()
            
            total_violations = violation_stats['total']
            total_violation_time = violation_stats['total_duration']
            final_decision = calculate_exam_decision(total_violations, total_violation_time)
            
            # Insert/Update final_results WITH exam duration
            check_result_query = "SELECT id FROM final_results WHERE participant_id = %s"
            cursor.execute(check_result_query, (participant_id,))
            existing_result = cursor.fetchone()
            
            if existing_result:
                update_result_query = """
                    UPDATE final_results 
                    SET total_violations = %s, total_violation_time = %s, final_decision = %s, 
                        exam_start_time = %s, exam_end_time = %s, exam_duration_seconds = %s, decided_at = NOW()
                    WHERE participant_id = %s
                """
                cursor.execute(update_result_query, (total_violations, total_violation_time, final_decision, exam_start_time, exam_end_time, exam_duration, participant_id))
            else:
                insert_result_query = """
                    INSERT INTO final_results 
                    (participant_id, total_violations, total_violation_time, final_decision, exam_start_time, exam_end_time, exam_duration_seconds)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_result_query, (participant_id, total_violations, total_violation_time, final_decision, exam_start_time, exam_end_time, exam_duration))
            
            conn.commit()
            cursor.close()
            
            return {
                'status': 'success',
                'message': 'Ujian selesai dan hasil telah difinalisasi',
                'total_violations': total_violations,
                'total_violation_time': total_violation_time,
                'final_decision': final_decision,
                'exam_start_time': exam_start_time.isoformat() if exam_start_time else None,
                'exam_end_time': exam_end_time.isoformat() if exam_end_time else None,
                'duration_seconds': exam_duration
            }, 200
            
        except Error as e:
            print(f"Error ending exam: {e}")
            return {'status': 'error', 'message': str(e)}, 500
        finally:
            if conn.is_connected():
                conn.close()
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {'status': 'error', 'message': str(e)}, 500

# Route: Get exam activity log
@app.route('/api/exam-log/<int:participant_id>')
def get_exam_log(participant_id):
    """Get full exam activity log untuk participant"""
    conn = get_db_connection()
    
    if not conn:
        return {'status': 'error', 'message': 'Database connection failed'}, 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT * FROM exam_activity_log 
            WHERE participant_id = %s 
            ORDER BY activity_timestamp ASC
        """
        cursor.execute(query, (participant_id,))
        activities = cursor.fetchall()
        
        cursor.close()
        
        return {
            'status': 'success',
            'activities': activities
        }, 200
        
    except Error as e:
        print(f"Error fetching exam log: {e}")
        return {'status': 'error', 'message': str(e)}, 500
    finally:
        if conn.is_connected():
            conn.close()

# Route: Log violation untuk activity tracking
@app.route('/api/log-violation', methods=['POST'])
def log_violation_activity():
    """Log violation ke exam_activity_log untuk tracking"""
    try:
        data = request.get_json()
        participant_id = data.get('participant_id')
        session_id = data.get('session_id')
        violation_id = data.get('violation_id')
        violation_type = data.get('violation_type')
        
        log_exam_activity(
            participant_id,
            session_id,
            'VIOLATION_DETECTED',
            f'{violation_type} terdeteksi',
            {'violation_id': violation_id, 'type': violation_type}
        )
        
        return {'status': 'success'}, 200
    except Exception as e:
        print(f"Error logging violation: {e}")
        return {'status': 'error'}, 500

# Helper function untuk convert ISO datetime string ke MySQL format
def convert_iso_to_mysql_datetime(iso_string):
    """Convert ISO 8601 format (2026-01-24T18:01:10.077Z) to MySQL DATETIME format"""
    try:
        from datetime import datetime
        # Parse ISO format
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        # Return MySQL format (YYYY-MM-DD HH:MM:SS)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"Error converting datetime: {e}")
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Route: Record violation realtime (USING VIOLATIONS TABLE)
@app.route('/api/record-violation', methods=['POST'])
def record_violation():
    """Record a single violation in realtime when it's detected - saves to violations table"""
    print("\n" + "="*80)
    print("[POST] RECORD-VIOLATION ENDPOINT CALLED")
    print("="*80)
    
    try:
        data = request.get_json()
        print(f"[DATA] Received data keys: {list(data.keys()) if data else 'None'}")
        
        participant_id = data.get('participant_id')
        session_id = data.get('session_id')
        violation_type = data.get('violation_type', 'UNKNOWN')
        description = data.get('description', '')
        start_time_iso = data.get('startTime')
        evidence = data.get('evidence')  # Base64 encoded screenshot
        
        print(f"[OK] Participant ID: {participant_id}")
        print(f"[OK] Session ID: {session_id}")
        print(f"[OK] Violation Type: {violation_type}")
        print(f"[OK] Description: {description[:50]}..." if description else "[OK] Description: (empty)")
        print(f"[OK] Start Time ISO: {start_time_iso}")
        print(f"[OK] Evidence: {('YES - ' + str(len(evidence)) + ' bytes') if evidence else 'NO'}")
        
        # Validasi field required
        if not participant_id or not start_time_iso:
            print(f"[ERROR] VALIDATION FAILED: Missing required fields (participant_id or startTime)")
            return {'status': 'error', 'message': 'Missing required fields: participant_id, startTime'}, 400
        
        print(f"\n[OK] Validation passed")
        
        conn = get_db_connection()
        if not conn:
            print(f"[ERROR] DATABASE CONNECTION FAILED")
            return {'status': 'error', 'message': 'Database connection failed'}, 500
        
        print(f"[OK] Database connected")
        
        try:
            cursor = conn.cursor()
            
            # Convert ISO datetime to MySQL format
            start_time = convert_iso_to_mysql_datetime(start_time_iso)
            end_time = start_time  # Start with same time, will be updated when violation ends
            duration_seconds = 0
            
            print(f"[OK] Start time converted: {start_time}")
            
            # Upload screenshot evidence to Cloudinary if available
            evidence_url = None
            if evidence and (evidence.startswith('data:image') or evidence.startswith('data:')):
                try:
                    print(f"\n[IMG] UPLOADING EVIDENCE SCREENSHOT")
                    print(f"   Violation Type: {violation_type}")
                    print(f"   Evidence Size: {len(evidence)/1024:.2f} KB")
                    
                    # Upload screenshot to Cloudinary
                    upload_result = cloudinary.uploader.upload(
                        evidence,
                        folder=CLOUDINARY_FOLDER + 'violations/evidence/',
                        resource_type='auto',
                        quality='auto',
                        fetch_format='auto'
                    )
                    evidence_url = upload_result['secure_url']
                    print(f"[OK] Evidence uploaded successfully!")
                    print(f"   URL: {evidence_url[:80]}...")
                    
                except Exception as e:
                    print(f"[WARN] Error uploading violation evidence: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue even if evidence upload fails
            else:
                print(f"[WARN] No evidence screenshot provided for violation ({violation_type})")
            
            # Insert into violations table (PRIMARY TABLE)
            print(f"\n[DB] INSERTING INTO VIOLATIONS TABLE")
            print(f"   Participant ID: {participant_id}")
            print(f"   Violation Type: {violation_type}")
            print(f"   Description: {description[:50]}...")
            print(f"   Start Time: {start_time}")
            
            insert_violation_query = """
                INSERT INTO violations 
                (participant_id, violation_type, description, start_time, end_time, duration_seconds)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_violation_query, 
                          (participant_id, violation_type, description, start_time, end_time, duration_seconds))
            
            violation_id = cursor.lastrowid
            print(f"[OK] Violation record inserted!")
            print(f"   Violation ID: {violation_id}")
            
            # If evidence was uploaded, save to violation_evidence table
            if evidence_url:
                try:
                    print(f"\n[DB] INSERTING INTO VIOLATION_EVIDENCE TABLE")
                    print(f"   Violation ID: {violation_id}")
                    print(f"   Image URL: {evidence_url[:80]}...")
                    
                    insert_evidence_query = """
                        INSERT INTO violation_evidence 
                        (violation_id, image_url)
                        VALUES (%s, %s)
                    """
                    cursor.execute(insert_evidence_query, (violation_id, evidence_url))
                    print(f"[OK] Evidence record inserted!")
                except Exception as e:
                    print(f"[WARN] Error saving evidence record: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue anyway
            
            conn.commit()
            cursor.close()
            
            print(f"\n[OK] TRANSACTION COMMITTED SUCCESSFULLY")
            print(f"="*80 + "\n")
            
            return {
                'status': 'success',
                'message': f'Violation recorded: {violation_type}',
                'violation_id': violation_id,
                'type': violation_type,
                'evidence_url': evidence_url
            }, 200
            
        except Error as e:
            print(f"[ERROR] DATABASE ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {'status': 'error', 'message': str(e)}, 500
        finally:
            if conn.is_connected():
                conn.close()
    
    except Exception as e:
        print(f"[ERROR] UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        print(f"="*80 + "\n")
        return {'status': 'error', 'message': str(e)}, 500


# Route: Upload violations dan finalize results (DEPRECATED - kept for backward compatibility)
@app.route('/api/upload-violations', methods=['POST'])
def upload_violations():
    try:
        data = request.get_json()
        participant_id = data.get('participant_id')
        violations_data = data.get('violations', [])
        
        if not participant_id:
            return {'status': 'error', 'message': 'Participant ID required'}, 400
        
        conn = get_db_connection()
        if not conn:
            return {'status': 'error', 'message': 'Database connection failed'}, 500
        
        try:
            cursor = conn.cursor()
            
            # Get all violations for this participant dari database (tidak dari client)
            violations_query = "SELECT * FROM violations WHERE participant_id = %s"
            cursor.execute(violations_query, (participant_id,))
            db_violations = cursor.fetchall()
            
            # Calculate final results from database violations
            total_violations = len(db_violations)
            total_violation_time = sum(v[7] for v in db_violations if v[7])  # duration_seconds adalah index 7
            
            # Determine final decision based on violations
            final_decision = calculate_exam_decision(total_violations, total_violation_time)
            
            # Check if final_results already exists (update) or create new
            check_result_query = "SELECT id FROM final_results WHERE participant_id = %s"
            cursor.execute(check_result_query, (participant_id,))
            existing_result = cursor.fetchone()
            
            if existing_result:
                # Update existing result
                update_result_query = """
                    UPDATE final_results 
                    SET total_violations = %s, total_violation_time = %s, final_decision = %s, decided_at = NOW()
                    WHERE participant_id = %s
                """
                cursor.execute(update_result_query, 
                              (total_violations, total_violation_time, final_decision, participant_id))
            else:
                # Create new result
                insert_result_query = """
                    INSERT INTO final_results 
                    (participant_id, total_violations, total_violation_time, final_decision)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(insert_result_query, 
                              (participant_id, total_violations, total_violation_time, final_decision))
            
            conn.commit()
            cursor.close()
            
            return {
                'status': 'success',
                'message': f'Exam results finalized',
                'total_violations': total_violations,
                'total_violation_time': total_violation_time,
                'final_decision': final_decision
            }, 200
            
        except Error as e:
            print(f"Error finalizing exam results: {e}")
            return {'status': 'error', 'message': str(e)}, 500
        finally:
            if conn.is_connected():
                conn.close()
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {'status': 'error', 'message': str(e)}, 500

# Helper function untuk calculate exam decision
def calculate_exam_decision(total_violations, total_violation_time):
    """
    Calculate final exam decision based on violations
    """
    # Decision rules:
    # JUJUR: 0 violations atau violation time < 60 seconds
    # CURANG: 2+ violations atau violation time >= 60 seconds
    
    if total_violations == 0:
        return 'JUJUR'
    elif total_violations == 1 and total_violation_time < 30:
        return 'JUJUR'  # Minor violation (less than 30 seconds)
    elif total_violations >= 2 or total_violation_time >= 60:
        return 'CURANG'
    else:
        return 'JUJUR'

# Route: Get participant exam result
@app.route('/api/exam-result/<int:participant_id>')
def get_exam_result(participant_id):
    conn = get_db_connection()
    
    if not conn:
        return {'status': 'error', 'message': 'Database connection failed'}, 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get final result
        result_query = "SELECT * FROM final_results WHERE participant_id = %s"
        cursor.execute(result_query, (participant_id,))
        final_result = cursor.fetchone()
        
        # Get violations
        violations_query = "SELECT * FROM violations WHERE participant_id = %s ORDER BY start_time ASC"
        cursor.execute(violations_query, (participant_id,))
        violations = cursor.fetchall()
        
        cursor.close()
        
        return {
            'status': 'success',
            'result': final_result,
            'violations': violations
        }, 200
        
    except Error as e:
        print(f"Error fetching exam result: {e}")
        return {'status': 'error', 'message': str(e)}, 500
    finally:
        if conn.is_connected():
            conn.close()

# ===================== ADMIN VIOLATIONS & RESULTS =====================

# Route: Admin Violations List
@app.route('/admin/violations')
@login_required
def admin_violations():
    conn = get_db_connection()
    
    if not conn:
        return render_template('admin_results.html', violations=[], participants={}, error='Koneksi database gagal')
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get all violations with participant info
        violations_query = """
            SELECT v.*, p.participant_number, p.participant_name, p.face_photo_url
            FROM violations v
            JOIN participants p ON v.participant_id = p.id
            ORDER BY v.start_time DESC
        """
        cursor.execute(violations_query)
        violations = cursor.fetchall()
        
        # Get all participants with final results INCLUDING exam duration
        participants_query = """
            SELECT p.*, s.session_name, 
                   COALESCE(fr.total_violations, 0) as total_violations,
                   COALESCE(fr.total_violation_time, 0) as total_violation_time,
                   COALESCE(fr.exam_duration_seconds, 0) as exam_duration_seconds,
                   fr.exam_start_time,
                   fr.exam_end_time,
                   COALESCE(fr.final_decision, 'PENDING') as final_decision
            FROM participants p
            LEFT JOIN sessions s ON p.session_id = s.id
            LEFT JOIN final_results fr ON p.id = fr.participant_id
            ORDER BY p.created_at DESC
        """
        cursor.execute(participants_query)
        participants = cursor.fetchall()
        
        cursor.close()
        
        return render_template('admin_results.html', violations=violations, participants=participants)
        
    except Error as e:
        print(f"Error fetching violations: {e}")
        return render_template('admin_results.html', violations=[], participants={}, error=f'Error: {str(e)}')
    finally:
        if conn.is_connected():
            conn.close()

# Route: Get violations by participant (API)
@app.route('/api/violations/<int:participant_id>')
@login_required
def get_violations_by_participant(participant_id):
    conn = get_db_connection()
    
    if not conn:
        return {'status': 'error', 'message': 'Database connection failed'}, 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get participant info
        participant_query = "SELECT * FROM participants WHERE id = %s"
        cursor.execute(participant_query, (participant_id,))
        participant = cursor.fetchone()
        
        # Get violations
        violations_query = "SELECT * FROM violations WHERE participant_id = %s ORDER BY start_time ASC"
        cursor.execute(violations_query, (participant_id,))
        violations = cursor.fetchall()
        
        # Get evidence
        evidence_query = """
            SELECT ve.*, v.violation_type, v.description
            FROM violation_evidence ve
            JOIN violations v ON ve.violation_id = v.id
            WHERE v.participant_id = %s
            ORDER BY ve.captured_at ASC
        """
        cursor.execute(evidence_query, (participant_id,))
        evidence = cursor.fetchall()
        
        # Get final result
        result_query = "SELECT * FROM final_results WHERE participant_id = %s"
        cursor.execute(result_query, (participant_id,))
        final_result = cursor.fetchone()
        
        cursor.close()
        
        return {
            'status': 'success',
            'participant': participant,
            'violations': violations,
            'evidence': evidence,
            'final_result': final_result
        }, 200
        
    except Error as e:
        print(f"Error fetching violations: {e}")
        return {'status': 'error', 'message': str(e)}, 500
    finally:
        if conn.is_connected():
            conn.close()

# Route: Proctored Exam Wrapper Page
@app.route('/proctored-exam')
def proctored_exam():
    """
    ✅ Proctored exam di normal browser tab
    Halaman ini dibuka sebagai tab biasa (bukan custom window khusus)
    Dengan UI monitoring lengkap: header bar + timer + violation counter + webcam preview
    Exam content dimuat di iframe dengan postMessage monitoring
    """
    exam_url = request.args.get('exam_url')
    participant_id = request.args.get('participant_id')
    session_id = request.args.get('session_id')
    
    if not all([exam_url, participant_id, session_id]):
        return 'Error: Missing exam parameters', 400
    
    # ✅ GET NOTIFICATION TIMING FROM .ENV
    notification_freeze_duration = int(os.getenv('NOTIFICATION_FREEZE_DURATION', 2000))
    notification_interval = int(os.getenv('NOTIFICATION_INTERVAL', 3000))
    
    print(f"[EXAM] Opening proctored exam in normal browser tab (participant {participant_id})")
    print(f"[EXAM] Notification config: freeze={notification_freeze_duration}ms, interval={notification_interval}ms")
    
    return render_template('proctored-exam-NEW.html', 
                          exam_url=exam_url,
                          participant_id=participant_id,
                          session_id=session_id,
                          notification_freeze_duration=notification_freeze_duration,
                          notification_interval=notification_interval)

# Route: Test Exam (for development/testing)
@app.route('/test-exam')
def test_exam():
    """Serve test exam page for testing monitoring system"""
    return render_template('test-exam.html')

# Route: Test Violation Debug Page
@app.route('/test-violation-debug')
def test_violation_debug():
    """Debug page untuk test violation uploads"""
    return render_template('test-violation-debug.html')

# ===================== FACE ANALYSIS & WEBCAM =====================

# Route: Initialize webcam analysis for participant
@app.route('/api/webcam-init', methods=['POST'])
def webcam_init():
    """Initialize webcam analysis when exam starts"""
    try:
        data = request.get_json()
        participant_id = data.get('participant_id')
        session_id = data.get('session_id')
        
        if not all([participant_id, session_id]):
            return {'status': 'error', 'message': 'Missing required fields'}, 400
        
        # ✅ Get participant face photo URL from database
        conn = get_db_connection()
        if not conn:
            print(f'[WEBCAM-INIT] ❌ Database connection failed')
            return {'status': 'error', 'message': 'Database connection failed'}, 500
        
        try:
            cursor = conn.cursor(dictionary=True)
            query = "SELECT face_photo_url FROM participants WHERE id = %s"
            cursor.execute(query, (participant_id,))
            participant = cursor.fetchone()
            cursor.close()
            
            if not participant or not participant.get('face_photo_url'):
                print(f'[WEBCAM-INIT] ❌ Participant face photo not found')
                return {'status': 'error', 'message': 'Participant face photo not found'}, 404
            
            face_photo_url = participant['face_photo_url']
            
            print(f'[WEBCAM-INIT] 📸 Face photo URL: {face_photo_url}')
            
            # ✅ Create analyzer for this participant
            print(f'[WEBCAM-INIT] 🔧 Creating analyzer for participant {participant_id}...')
            analyzer_manager.create_analyzer(participant_id, session_id, face_photo_url)
            
            # ✅ Return config from server
            violation_duration = int(os.getenv('VIOLATION_DURATION', '6'))  # In seconds
            violation_threshold_ms = int(os.getenv('VIOLATION_THRESHOLD_MS', '6000'))  # In milliseconds
            
            print(f'[WEBCAM-INIT] ✅ Analyzer initialized successfully')
            print(f'[WEBCAM-INIT]    Violation threshold: {violation_threshold_ms}ms ({violation_duration}s)')
            
            return {
                'status': 'success',
                'message': 'Webcam analyzer initialized',
                'config': {
                    'violation_duration': violation_duration,
                    'violation_threshold_ms': violation_threshold_ms,
                    'frame_rate': 10
                }
            }, 200
            
        except Error as e:
            print(f'[WEBCAM-INIT] ❌ Database error: {e}')
            return {'status': 'error', 'message': f'Database error: {str(e)}'}, 500
        finally:
            if conn.is_connected():
                conn.close()
        
    except Exception as e:
        print(f'[WEBCAM-INIT] ❌ Error: {e}')
        import traceback
        traceback.print_exc()
        return {'status': 'error', 'message': str(e)}, 500

# Route: Process video frame from webcam
@app.route('/api/process-frame', methods=['POST'])
def process_frame():
    """Process single frame from webcam and return analysis with bounding boxes"""
    try:
        data = request.get_json()
        participant_id = data.get('participant_id')
        frame_base64 = data.get('frame')
        
        if not all([participant_id, frame_base64]):
            return {'status': 'error', 'message': 'Missing required fields'}, 400
        
        # Decode frame
        try:
            # Remove data:image/jpeg;base64, prefix if present
            if ',' in frame_base64:
                frame_base64 = frame_base64.split(',')[1]
            
            frame_bytes = base64.b64decode(frame_base64)
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                return {'status': 'error', 'message': 'Invalid frame'}, 400
        except Exception as e:
            print(f"[WEBCAM] Frame decode error: {e}")
            return {'status': 'error', 'message': 'Frame decode failed'}, 400
        
        # Process frame (non-blocking)
        try:
            analysis_result = analyzer_manager.process_frame(participant_id, frame)
            
            if analysis_result is None:
                return {'status': 'success', 'analysis': None, 'violations': []}, 200
            
            violations = analysis_result.get('violations', [])
            face_status = analysis_result.get('face_status', 'unknown')
            yolo_class = analysis_result.get('yolo_class', 'unknown')
            gaze_state = analysis_result.get('gaze_state', 'normal')
            
            # ✅ BUILD RESPONSE
            response = {
                'status': 'success',
                'analysis': {
                    'face_status': face_status,
                    'yolo_class': yolo_class,
                    'yolo_conf': analysis_result.get('yolo_conf', 0),
                    'yolo_bbox': analysis_result.get('yolo_bbox'),
                    'face_similarity': analysis_result.get('face_similarity', -1),
                    'face_bbox': analysis_result.get('face_bbox'),
                    'gaze_state': gaze_state,
                    'violations': violations
                },
                'violations': violations
            }
            
            return response, 200
            
        except Exception as e:
            return {
                'status': 'success',
                'message': 'Frame processed',
                'analysis': None,
                'violations': []
            }, 200
    
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

# Route: Cleanup webcam analysis when exam ends
@app.route('/api/webcam-cleanup', methods=['POST'])
def webcam_cleanup():
    """Cleanup webcam analysis when exam ends"""
    try:
        data = request.get_json()
        participant_id = data.get('participant_id')
        
        if not participant_id:
            return {'status': 'error', 'message': 'Missing participant_id'}, 400
        
        analyzer_manager.remove_analyzer(participant_id)
        
        return {
            'status': 'success',
            'message': 'Cleanup done'
        }, 200
    
    except Exception as e:
        print(f"[WEBCAM] Cleanup error: {e}")
        return {'status': 'error', 'message': str(e)}, 500

if __name__ == '__main__':
    app.run(debug=True, host=os.getenv('SERVER_HOST', 'localhost'), port=PORT)