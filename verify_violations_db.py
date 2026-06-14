#!/usr/bin/env python
"""
Verify that violations are saved in the violations table
"""

import mysql.connector
import os
from dotenv import load_dotenv
import json

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT')),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

def verify_violations():
    """Check violations table for newly inserted records"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        print("\n" + "="*80)
        print("VERIFYING VIOLATIONS IN DATABASE")
        print("="*80)
        
        # Get latest violations for participant 2
        query = """
            SELECT v.id, v.participant_id, v.violation_type, v.description, 
                   v.start_time, v.duration_seconds,
                   ve.image_url
            FROM violations v
            LEFT JOIN violation_evidence ve ON v.id = ve.violation_id
            WHERE v.participant_id = 2
            ORDER BY v.id DESC
            LIMIT 5
        """
        
        cursor.execute(query)
        violations = cursor.fetchall()
        
        print(f"\nLatest violations for Participant ID 2:")
        print(f"Total records: {len(violations)}\n")
        
        for i, v in enumerate(violations, 1):
            print(f"Record {i}:")
            print(f"  - Violation ID: {v['id']}")
            print(f"  - Type: {v['violation_type']}")
            print(f"  - Description: {v['description']}")
            print(f"  - Start Time: {v['start_time']}")
            print(f"  - Duration: {v['duration_seconds']} seconds")
            if v['image_url']:
                print(f"  - Evidence URL: {v['image_url'][:70]}...")
            else:
                print(f"  - Evidence URL: None")
            print()
        
        print("="*80)
        print("✅ VIOLATIONS TABLE VERIFICATION COMPLETE")
        print("="*80)
        
        cursor.close()
        conn.close()
        
        return len(violations) > 0
        
    except Exception as e:
        print(f"❌ Error verifying violations: {e}")
        return False

if __name__ == '__main__':
    verify_violations()
