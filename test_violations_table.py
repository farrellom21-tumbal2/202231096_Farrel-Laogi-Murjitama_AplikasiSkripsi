#!/usr/bin/env python
"""
Test script untuk verify bahwa violations terupload ke tabel VIOLATIONS
Tidak ke exam_activity_log
"""

import requests
import json
from datetime import datetime, timedelta
import base64
from PIL import Image
import io

# API endpoint
API_URL = "http://localhost:5000/api/record-violation"

# Test data - gunakan valid participant_id dan session_id
PARTICIPANT_ID = 2
SESSION_ID = 2

def create_test_image():
    """Create a simple test image and convert to base64"""
    # Create a simple image
    img = Image.new('RGB', (100, 100), color='red')
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    # Convert to data URL format (jpg)
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{img_base64}"

def test_violation_without_evidence():
    """Test 1: Record violation WITHOUT screenshot"""
    print("\n" + "="*80)
    print("TEST 1: VIOLATION WITHOUT EVIDENCE")
    print("="*80)
    
    payload = {
        "participant_id": PARTICIPANT_ID,
        "session_id": SESSION_ID,
        "violation_type": "TAB_SWITCH",
        "description": "Test: Peserta meninggalkan tab",
        "startTime": datetime.now().isoformat() + "Z",
        "evidence": None
    }
    
    print(f"\nSending payload:")
    print(json.dumps(payload, indent=2, default=str))
    
    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        print(f"\nResponse Status: {response.status_code}")
        
        data = response.json()
        print(f"Response Data:")
        print(json.dumps(data, indent=2))
        
        if response.status_code == 200 and data.get('status') == 'success':
            print("\n✅ TEST 1 PASSED - Violation inserted to violations table")
            print(f"   Violation ID: {data.get('violation_id')}")
            return True
        else:
            print("\n❌ TEST 1 FAILED")
            return False
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED - Network error: {e}")
        return False

def test_violation_with_evidence():
    """Test 2: Record violation WITH screenshot evidence"""
    print("\n" + "="*80)
    print("TEST 2: VIOLATION WITH EVIDENCE")
    print("="*80)
    
    # Create test image
    test_image = create_test_image()
    
    payload = {
        "participant_id": PARTICIPANT_ID,
        "session_id": SESSION_ID,
        "violation_type": "WINDOW_BLUR",
        "description": "Test: Peserta beralih ke window lain",
        "startTime": datetime.now().isoformat() + "Z",
        "evidence": test_image
    }
    
    print(f"\nSending payload with evidence:")
    print(f"  - Participant ID: {payload['participant_id']}")
    print(f"  - Session ID: {payload['session_id']}")
    print(f"  - Violation Type: {payload['violation_type']}")
    print(f"  - Description: {payload['description']}")
    print(f"  - Evidence Size: {len(test_image)/1024:.2f} KB")
    
    try:
        response = requests.post(API_URL, json=payload, timeout=15)
        print(f"\nResponse Status: {response.status_code}")
        
        data = response.json()
        print(f"Response Data:")
        print(json.dumps(data, indent=2))
        
        if response.status_code == 200 and data.get('status') == 'success':
            print("\n✅ TEST 2 PASSED - Violation with evidence inserted")
            print(f"   Violation ID: {data.get('violation_id')}")
            print(f"   Evidence URL: {data.get('evidence_url')}")
            return True
        else:
            print("\n❌ TEST 2 FAILED")
            return False
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED - Network error: {e}")
        return False

def test_invalid_payload():
    """Test 3: Record with missing required fields (should fail)"""
    print("\n" + "="*80)
    print("TEST 3: INVALID PAYLOAD (Missing participant_id)")
    print("="*80)
    
    payload = {
        # participant_id MISSING (required)
        "session_id": SESSION_ID,
        "violation_type": "BACK_BUTTON",
        "description": "Test invalid payload",
        "startTime": datetime.now().isoformat() + "Z"
    }
    
    print(f"\nSending invalid payload:")
    print(json.dumps(payload, indent=2, default=str))
    
    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        print(f"\nResponse Status: {response.status_code}")
        
        data = response.json()
        print(f"Response Data:")
        print(json.dumps(data, indent=2))
        
        if response.status_code == 400:
            print("\n✅ TEST 3 PASSED - Invalid payload correctly rejected")
            return True
        else:
            print("\n❌ TEST 3 FAILED - Expected 400 status code")
            return False
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED - Network error: {e}")
        return False

if __name__ == '__main__':
    print("\n")
    print("#"*80)
    print("# TESTING VIOLATIONS TABLE INSERTION")
    print("#"*80)
    print(f"\nTargeting API: {API_URL}")
    print(f"Participant ID: {PARTICIPANT_ID}")
    print(f"Session ID: {SESSION_ID}")
    
    # Run tests
    test1 = test_violation_without_evidence()
    test2 = test_violation_with_evidence()
    test3 = test_invalid_payload()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Test 1 (No Evidence): {'PASSED' if test1 else 'FAILED'}")
    print(f"Test 2 (With Evidence): {'PASSED' if test2 else 'FAILED'}")
    print(f"Test 3 (Invalid Payload): {'PASSED' if test3 else 'FAILED'}")
    
    passed = sum([test1, test2, test3])
    total = 3
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅✅✅ ALL TESTS PASSED ✅✅✅")
        print("\nViolations should now be saved to the VIOLATIONS table!")
    else:
        print("\n❌ Some tests failed")
    
    print("\n" + "="*80)
