#!/usr/bin/env python3
"""
Test script untuk debug /api/record-violation endpoint
Jalankan: python test_violation_api.py
"""

import requests
import json
from datetime import datetime
import sys

# Configuration
API_BASE_URL = "http://localhost:5000"
ENDPOINT = f"{API_BASE_URL}/api/record-violation"

# Test data
TEST_PARTICIPANT_ID = 1
TEST_SESSION_ID = 1

def test_without_evidence():
    """Test 1: Send violation tanpa evidence"""
    print("\n" + "="*80)
    print("TEST 1: VIOLATION WITHOUT EVIDENCE")
    print("="*80)
    
    payload = {
        "participant_id": TEST_PARTICIPANT_ID,
        "session_id": TEST_SESSION_ID,
        "violation_type": "TEST_WINDOW_BLUR",
        "description": "Test violation tanpa screenshot evidence",
        "startTime": datetime.now().isoformat() + "Z",
        "evidence": None
    }
    
    print(f"\n📤 Sending to: {ENDPOINT}")
    print(f"📋 Payload:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(
            ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"\n📨 Response Status: {response.status_code}")
        print(f"📦 Response Body:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print(f"\n✅ TEST PASSED!")
                print(f"   Activity ID: {data.get('activity_id')}")
                return True
        else:
            print(f"\n❌ TEST FAILED - Wrong status code!")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def test_with_simple_evidence():
    """Test 2: Send violation dengan simple image evidence"""
    print("\n" + "="*80)
    print("TEST 2: VIOLATION WITH SIMPLE IMAGE EVIDENCE")
    print("="*80)
    
    # Create simple base64 image (1x1 pixel PNG)
    simple_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    payload = {
        "participant_id": TEST_PARTICIPANT_ID,
        "session_id": TEST_SESSION_ID,
        "violation_type": "TEST_TAB_SWITCH",
        "description": "Test violation dengan simple evidence image",
        "startTime": datetime.now().isoformat() + "Z",
        "evidence": simple_png
    }
    
    print(f"\n📤 Sending to: {ENDPOINT}")
    print(f"📋 Payload (evidence truncated):")
    payload_display = payload.copy()
    if payload_display['evidence']:
        payload_display['evidence'] = payload_display['evidence'][:50] + "..."
    print(json.dumps(payload_display, indent=2))
    
    try:
        response = requests.post(
            ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"\n📨 Response Status: {response.status_code}")
        print(f"📦 Response Body:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                print(f"\n✅ TEST PASSED!")
                print(f"   Activity ID: {data.get('activity_id')}")
                print(f"   Evidence URL: {data.get('evidence_url')}")
                return True
        else:
            print(f"\n❌ TEST FAILED - Wrong status code!")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def test_invalid_payload():
    """Test 3: Send invalid payload"""
    print("\n" + "="*80)
    print("TEST 3: INVALID PAYLOAD (Missing required fields)")
    print("="*80)
    
    payload = {
        "participant_id": TEST_PARTICIPANT_ID,
        # Missing session_id
        "violation_type": "TEST_ERROR",
        "description": "Test with missing session_id",
        "startTime": datetime.now().isoformat() + "Z"
    }
    
    print(f"\n📤 Sending INVALID payload to: {ENDPOINT}")
    print(f"📋 Payload:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(
            ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"\n📨 Response Status: {response.status_code}")
        print(f"📦 Response Body:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 400:
            print(f"\n✅ TEST PASSED! (Correctly rejected invalid payload)")
            return True
        else:
            print(f"\n❌ TEST FAILED - Should return 400!")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def main():
    print("\n" + "🧪 TESTING /api/record-violation ENDPOINT 🧪".center(80))
    
    # Check if server is running
    print("\n📡 Checking if server is running...")
    try:
        response = requests.get(API_BASE_URL, timeout=2)
        print("✅ Server is running")
    except:
        print("❌ ERROR: Server tidak berjalan!")
        print(f"   Pastikan Flask sudah start: python app.py")
        sys.exit(1)
    
    # Run tests
    results = []
    results.append(("Test 1: Without Evidence", test_without_evidence()))
    results.append(("Test 2: With Evidence", test_with_simple_evidence()))
    results.append(("Test 3: Invalid Payload", test_invalid_payload()))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {test_name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Endpoint is working correctly!")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed. Check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
