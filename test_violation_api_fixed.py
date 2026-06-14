#!/usr/bin/env python3
"""
Updated test script for /api/record-violation endpoint
Now with proper session/participant validation
Run: python test_violation_api_fixed.py
"""

import requests
import json
from datetime import datetime
import sys

# Configuration
API_BASE_URL = "http://localhost:5000"
ENDPOINT = f"{API_BASE_URL}/api/record-violation"

# VALID TEST DATA (from database)
TEST_PARTICIPANT_ID = 2  # Valid participant that exists in DB
TEST_SESSION_ID = 2       # Valid session that exists in DB

def test_without_evidence():
    """Test 1: Send violation without evidence"""
    print("\n" + "="*80)
    print("[TEST 1] VIOLATION WITHOUT EVIDENCE")
    print("="*80)
    
    payload = {
        "participant_id": TEST_PARTICIPANT_ID,
        "session_id": TEST_SESSION_ID,
        "violation_type": "TEST_WINDOW_BLUR",
        "description": "Test violation without screenshot evidence",
        "startTime": datetime.now().isoformat() + "Z",
        "evidence": None
    }
    
    print(f"\n[SEND] POST {ENDPOINT}")
    print(f"[DATA] Payload:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(
            ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"\n[RESPONSE] Status: {response.status_code}")
        resp_data = response.json()
        print(f"[RESPONSE] Body:")
        print(json.dumps(resp_data, indent=2))
        
        if response.status_code == 200 and resp_data.get('status') == 'success':
            print(f"\n[OK] TEST 1 PASSED!")
            print(f"    Activity ID: {resp_data.get('activity_id')}")
            return True
        else:
            print(f"\n[ERROR] TEST 1 FAILED!")
            print(f"    Expected: status=200, response.status='success'")
            print(f"    Got: status={response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] TEST 1 FAILED: {e}")
        return False


def test_with_simple_evidence():
    """Test 2: Send violation with simple base64 image evidence"""
    print("\n" + "="*80)
    print("[TEST 2] VIOLATION WITH BASE64 IMAGE EVIDENCE")
    print("="*80)
    
    # Create simple 1x1 pixel PNG in base64
    simple_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    payload = {
        "participant_id": TEST_PARTICIPANT_ID,
        "session_id": TEST_SESSION_ID,
        "violation_type": "TEST_TAB_SWITCH",
        "description": "Test violation with screenshot evidence",
        "startTime": datetime.now().isoformat() + "Z",
        "evidence": simple_png
    }
    
    print(f"\n[SEND] POST {ENDPOINT}")
    print(f"[DATA] Payload (evidence truncated):")
    payload_display = payload.copy()
    payload_display['evidence'] = payload_display['evidence'][:50] + "..."
    print(json.dumps(payload_display, indent=2))
    
    try:
        response = requests.post(
            ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"\n[RESPONSE] Status: {response.status_code}")
        resp_data = response.json()
        print(f"[RESPONSE] Body:")
        print(json.dumps(resp_data, indent=2))
        
        if response.status_code == 200 and resp_data.get('status') == 'success':
            print(f"\n[OK] TEST 2 PASSED!")
            print(f"    Activity ID: {resp_data.get('activity_id')}")
            print(f"    Evidence URL: {resp_data.get('evidence_url')[:70]}..." if resp_data.get('evidence_url') else "    Evidence URL: None")
            return True
        else:
            print(f"\n[ERROR] TEST 2 FAILED!")
            print(f"    Expected: status=200, response.status='success'")
            print(f"    Got: status={response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] TEST 2 FAILED: {e}")
        return False


def test_invalid_payload():
    """Test 3: Send invalid payload (missing required fields)"""
    print("\n" + "="*80)
    print("[TEST 3] INVALID PAYLOAD (SHOULD BE REJECTED)")
    print("="*80)
    
    payload = {
        "participant_id": TEST_PARTICIPANT_ID,
        # Missing: session_id (REQUIRED)
        # Missing: startTime (REQUIRED)
        "violation_type": "TEST_ERROR",
        "description": "Missing required fields"
    }
    
    print(f"\n[SEND] POST {ENDPOINT}")
    print(f"[DATA] Payload (intentionally invalid):")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(
            ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"\n[RESPONSE] Status: {response.status_code}")
        resp_data = response.json()
        print(f"[RESPONSE] Body:")
        print(json.dumps(resp_data, indent=2))
        
        if response.status_code == 400:
            print(f"\n[OK] TEST 3 PASSED!")
            print(f"    Correctly rejected invalid payload with 400 status")
            return True
        else:
            print(f"\n[ERROR] TEST 3 FAILED!")
            print(f"    Expected: status=400")
            print(f"    Got: status={response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] TEST 3 FAILED: {e}")
        return False


def main():
    print("\n" + "="*80)
    print("[START] Testing /api/record-violation ENDPOINT")
    print("="*80)
    print(f"\nEndpoint: {ENDPOINT}")
    print(f"Test Participant ID: {TEST_PARTICIPANT_ID}")
    print(f"Test Session ID: {TEST_SESSION_ID}")
    
    # Check if server is running
    print("\n[CHECK] Verifying Flask server is running...")
    try:
        response = requests.get(API_BASE_URL, timeout=2)
        print("[OK] Flask server is running!")
    except:
        print("[ERROR] Flask server is NOT running!")
        print(f"[INFO] Start it with: python app.py")
        sys.exit(1)
    
    # Run tests
    print("\n" + "="*80)
    print("[TESTS] Running API endpoint tests...")
    print("="*80)
    
    results = []
    results.append(("Test 1: Without Evidence", test_without_evidence()))
    results.append(("Test 2: With Evidence", test_with_simple_evidence()))
    results.append(("Test 3: Invalid Payload", test_invalid_payload()))
    
    # Summary
    print("\n" + "="*80)
    print("[SUMMARY] TEST RESULTS")
    print("="*80)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED!")
        print("\nDatabase should now contain:")
        print("  - 2 new records in exam_activity_log")
        print("  - 1 new record in violation_evidence")
        print("  - 1 image uploaded to Cloudinary")
        sys.exit(0)
    else:
        print(f"\n[FAILURE] {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
