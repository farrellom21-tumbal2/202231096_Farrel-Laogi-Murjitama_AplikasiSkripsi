#!/usr/bin/env python3
"""
Simple test untuk memastikan violations API bekerja dengan benar
"""
import requests
import json
from datetime import datetime

# Configuration
API_URL = 'http://localhost:5000'
PARTICIPANT_ID = 2
SESSION_ID = 2

def test_record_violation_no_evidence():
    """Test recording a violation WITHOUT screenshot"""
    print("\n" + "="*80)
    print("TEST 1: Record violation WITHOUT evidence")
    print("="*80)
    
    payload = {
        'participant_id': PARTICIPANT_ID,
        'session_id': SESSION_ID,
        'violation_type': 'TAB_SWITCH',
        'description': 'Test: Peserta beralih ke tab lain',
        'startTime': datetime.now().isoformat()
    }
    
    print(f"Sending payload:")
    print(json.dumps(payload, indent=2))
    
    response = requests.post(f'{API_URL}/api/record-violation', json=payload)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Body:")
    print(json.dumps(response.json(), indent=2))
    
    return response.status_code == 200

def test_record_violation_with_fake_evidence():
    """Test recording a violation WITH fake base64 evidence"""
    print("\n" + "="*80)
    print("TEST 2: Record violation WITH fake evidence (data URL)")
    print("="*80)
    
    # Fake image data URL (minimal valid PNG)
    fake_image = """data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="""
    
    payload = {
        'participant_id': PARTICIPANT_ID,
        'session_id': SESSION_ID,
        'violation_type': 'WINDOW_BLUR',
        'description': 'Test: Peserta beralih window dengan evidence',
        'startTime': datetime.now().isoformat(),
        'evidence': fake_image
    }
    
    print(f"Sending payload:")
    print(f"  participant_id: {payload['participant_id']}")
    print(f"  session_id: {payload['session_id']}")
    print(f"  violation_type: {payload['violation_type']}")
    print(f"  startTime: {payload['startTime']}")
    print(f"  evidence: {payload['evidence'][:80]}...")
    
    response = requests.post(f'{API_URL}/api/record-violation', json=payload)
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Body:")
    print(json.dumps(response.json(), indent=2))
    
    return response.status_code == 200

def test_database_violations():
    """Check violations table"""
    print("\n" + "="*80)
    print("TEST 3: Check violations in database")
    print("="*80)
    
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
    
    try:
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT id, participant_id, violation_type, description, start_time, duration_seconds
            FROM violations 
            WHERE participant_id = %s
            ORDER BY id DESC LIMIT 10
        """
        
        cursor.execute(query, (PARTICIPANT_ID,))
        violations = cursor.fetchall()
        
        print(f"\nFound {len(violations)} violations for participant {PARTICIPANT_ID}:")
        for v in violations:
            print(f"  ID: {v['id']}, Type: {v['violation_type']}, Time: {v['start_time']}")
        
        cursor.close()
        conn.close()
        
        return True
    except Exception as e:
        print(f"Error checking database: {e}")
        return False

if __name__ == '__main__':
    print("\n" + "="*80)
    print("SIMPLE VIOLATIONS API TEST")
    print("="*80)
    print(f"Target: {API_URL}")
    print(f"Participant ID: {PARTICIPANT_ID}")
    print(f"Session ID: {SESSION_ID}")
    
    # Test 1: No evidence
    if test_record_violation_no_evidence():
        print("✓ Test 1 PASSED")
    else:
        print("✗ Test 1 FAILED")
    
    # Test 2: With evidence
    if test_record_violation_with_fake_evidence():
        print("✓ Test 2 PASSED")
    else:
        print("✗ Test 2 FAILED")
    
    # Test 3: Check database
    if test_database_violations():
        print("✓ Test 3 PASSED")
    else:
        print("✗ Test 3 FAILED")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
