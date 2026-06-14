#!/usr/bin/env python
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT')),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor(dictionary=True)
cursor.execute('SELECT id, session_name, exam_url FROM sessions LIMIT 2')
results = cursor.fetchall()
for result in results:
    print(f"Session ID: {result['id']}")
    print(f"Session Name: {result['session_name']}")
    print(f"Exam URL: {result['exam_url']}")
    print()
cursor.close()
conn.close()
