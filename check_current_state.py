#!/usr/bin/env python3
import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

config = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT')),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

conn = mysql.connector.connect(**config)
cursor = conn.cursor(dictionary=True)

# Check violations
print("="*80)
print("CURRENT STATE OF VIOLATIONS TABLE")
print("="*80)
cursor.execute("SELECT COUNT(*) as count FROM violations WHERE participant_id = 2")
result = cursor.fetchone()
print(f"Total violations for participant 2: {result['count']}")

cursor.execute("SELECT * FROM violations WHERE participant_id = 2 ORDER BY id DESC LIMIT 10")
violations = cursor.fetchall()
for v in violations:
    print(f"  ID: {v['id']}, Type: {v['violation_type']}, Time: {v['start_time']}, Duration: {v['duration_seconds']}s")

# Check exam_activity_log
print("\n" + "="*80)
print("CHECKING EXAM_ACTIVITY_LOG TABLE")
print("="*80)
cursor.execute("SELECT COUNT(*) as count FROM exam_activity_log WHERE participant_id = 2")
result = cursor.fetchone()
print(f"Total activities for participant 2: {result['count']}")

cursor.execute("SELECT * FROM exam_activity_log WHERE participant_id = 2 ORDER BY id DESC LIMIT 10")
activities = cursor.fetchall()
for a in activities:
    print(f"  ID: {a['id']}, Type: {a['activity_type']}, Desc: {a['description'][:40]}, Time: {a['activity_timestamp']}")

# Check session info
print("\n" + "="*80)
print("SESSION INFO")
print("="*80)
cursor.execute("SELECT id, session_name, exam_end_code, start_time, end_time FROM sessions WHERE id = 2")
session = cursor.fetchone()
if session:
    print(f"Session ID: {session['id']}")
    print(f"Name: {session['session_name']}")
    print(f"End Code: {session['exam_end_code']}")
    print(f"Time: {session['start_time']} - {session['end_time']}")

cursor.close()
conn.close()

print("\n" + "="*80)
