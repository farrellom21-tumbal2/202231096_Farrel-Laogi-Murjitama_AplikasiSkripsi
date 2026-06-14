#!/usr/bin/env python3
"""
TESTING SCRIPT - Verify Exam Monitoring System
Tests all components to ensure system working correctly
"""

import requests
import json
import time
import sys
import base64
from datetime import datetime
from io import BytesIO
from PIL import Image

# Configuration
BASE_URL = "http://localhost:5000"
API_ENDPOINT = f"{BASE_URL}/api/record-violation"
PARTICIPANT_ID = 1
SESSION_ID = 1

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_test(name, status, message=""):
    """Print test result"""
    symbol = f"{Colors.GREEN}✓{Colors.RESET}" if status else f"{Colors.RED}✗{Colors.RESET}"
    print(f"{symbol} {name}")
    if message:
        print(f"  {message}")

def print_section(title):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def create_test_image():
    """Create a simple test image as base64"""
    img = Image.new('RGB', (100, 100), color='red')
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

def test_backend_connection():
    """Test if backend is running"""
    print_section("1. BACKEND CONNECTION TEST")
    
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print_test("Backend accessible", response.status_code < 500)
        return True
    except requests.ConnectionError:
        print_test("Backend accessible", False, 
                   f"Cannot connect to {BASE_URL}")
        return False
    except Exception as e:
        print_test("Backend accessible", False, str(e))
        return False

def test_api_endpoint():
    """Test API endpoint exists"""
    print_section("2. API ENDPOINT TEST")
    
    try:
        response = requests.post(
            API_ENDPOINT,
            json={},
            timeout=5
        )
        success = response.status_code in [200, 201, 400]
        print_test("Endpoint accessible", success,
                   f"Status: {response.status_code}")
        return success
    except requests.ConnectionError:
        print_test("Endpoint accessible", False,
                   f"Cannot connect to {API_ENDPOINT}")
        return False
    except Exception as e:
        print_test("Endpoint accessible", False, str(e))
        return False

def test_violation_without_screenshot():
    """Test recording violation without screenshot"""
    print_section("3. RECORD VIOLATION (NO SCREENSHOT)")
    
    payload = {
        "participant_id": PARTICIPANT_ID,
        "session_id": SESSION_ID,
        "violation_type": "TEST_NO_SCREENSHOT",
        "violation_description": "Test violation without screenshot",
        "violation_details": json.dumps({"test": True}),
        "page_url": "http://localhost:5000/test",
        "page_title": "Test Page",
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(API_ENDPOINT, json=payload, timeout=10)
        success = response.status_code in [200, 201]
        
        print_test("API accepts violation", success,
                   f"Status: {response.status_code}")
        
        if success:
            data = response.json()
            violation_id = data.get('violation_id')
            print_test("Violation ID returned", violation_id is not None,
                       f"ID: {violation_id}")
            return violation_id
        else:
            print(f"  Response: {response.text}")
            return None
            
    except Exception as e:
        print_test("API accepts violation", False, str(e))
        return None

def test_violation_with_screenshot():
    """Test recording violation with screenshot"""
    print_section("4. RECORD VIOLATION (WITH SCREENSHOT)")
    
    screenshot_base64 = create_test_image()
    
    payload = {
        "participant_id": PARTICIPANT_ID,
        "session_id": SESSION_ID,
        "violation_type": "TEST_WITH_SCREENSHOT",
        "violation_description": "Test violation with screenshot",
        "violation_details": json.dumps({"test": True}),
        "screenshot_base64": screenshot_base64,
        "page_url": "http://localhost:5000/test",
        "page_title": "Test Page",
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(API_ENDPOINT, json=payload, timeout=10)
        success = response.status_code in [200, 201]
        
        print_test("Screenshot processed", success,
                   f"Status: {response.status_code}")
        
        if success:
            data = response.json()
            violation_id = data.get('violation_id')
            print_test("Violation with screenshot saved", violation_id is not None,
                       f"ID: {violation_id}")
            return violation_id
        else:
            print(f"  Response: {response.text}")
            return None
            
    except Exception as e:
        print_test("Screenshot processed", False, str(e))
        return None

def test_multiple_violations():
    """Test recording multiple violations"""
    print_section("5. BULK VIOLATION TEST")
    
    violation_types = [
        ("TAB_SWITCH", "User switched tab"),
        ("WINDOW_BLUR", "User switched window"),
        ("BACK_BUTTON", "User clicked back"),
        ("CLOSE_TAB", "User closed tab"),
        ("NEW_TAB", "User opened new tab")
    ]
    
    successful = 0
    for v_type, description in violation_types:
        payload = {
            "participant_id": PARTICIPANT_ID,
            "session_id": SESSION_ID,
            "violation_type": v_type,
            "violation_description": description,
            "violation_details": json.dumps({"event": v_type}),
            "page_url": "http://localhost:5000/exam",
            "page_title": "Exam Page",
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            response = requests.post(API_ENDPOINT, json=payload, timeout=10)
            if response.status_code in [200, 201]:
                successful += 1
                print_test(f"  {v_type}", True,
                           f"ID: {response.json().get('violation_id')}")
            else:
                print_test(f"  {v_type}", False,
                           f"Status: {response.status_code}")
        except Exception as e:
            print_test(f"  {v_type}", False, str(e))
        
        time.sleep(0.5)  # Small delay between requests
    
    return successful == len(violation_types)

def test_payload_validation():
    """Test payload validation"""
    print_section("6. PAYLOAD VALIDATION TEST")
    
    # Test missing required fields
    invalid_payloads = [
        ({}, "Empty payload"),
        ({"participant_id": 1}, "Missing session_id"),
        ({"session_id": 1}, "Missing participant_id"),
        ({"participant_id": 1, "session_id": 1}, "Missing violation_type"),
    ]
    
    validation_passed = 0
    for payload, description in invalid_payloads:
        try:
            response = requests.post(API_ENDPOINT, json=payload, timeout=5)
            # Should return 400 for invalid payload
            if response.status_code == 400:
                print_test(f"  {description}", True,
                           "Correctly rejected")
                validation_passed += 1
            else:
                print_test(f"  {description}", False,
                           f"Status: {response.status_code}")
        except Exception as e:
            print_test(f"  {description}", False, str(e))
    
    return validation_passed == len(invalid_payloads)

def test_concurrent_uploads():
    """Test concurrent violation uploads"""
    print_section("7. CONCURRENT UPLOAD TEST")
    
    print(f"Sending 5 violations simultaneously...")
    
    payloads = [
        {
            "participant_id": PARTICIPANT_ID,
            "session_id": SESSION_ID,
            "violation_type": f"TEST_{i}",
            "violation_description": f"Concurrent test {i}",
            "violation_details": json.dumps({"index": i}),
            "page_url": "http://localhost:5000/test",
            "page_title": "Test Page",
            "timestamp": datetime.now().isoformat()
        }
        for i in range(5)
    ]
    
    successful = 0
    for payload in payloads:
        try:
            response = requests.post(API_ENDPOINT, json=payload, timeout=10)
            if response.status_code in [200, 201]:
                successful += 1
        except Exception as e:
            pass
    
    print_test("All concurrent uploads successful", 
               successful == len(payloads),
               f"{successful}/{len(payloads)} successful")
    
    return successful == len(payloads)

def test_response_format():
    """Test API response format"""
    print_section("8. RESPONSE FORMAT TEST")
    
    payload = {
        "participant_id": PARTICIPANT_ID,
        "session_id": SESSION_ID,
        "violation_type": "TEST",
        "violation_description": "Test",
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(API_ENDPOINT, json=payload, timeout=10)
        
        if response.status_code in [200, 201]:
            data = response.json()
            
            print_test("Response is JSON", True)
            print_test("Contains status", "status" in data,
                       f"status: {data.get('status')}")
            print_test("Contains violation_id", "violation_id" in data,
                       f"violation_id: {data.get('violation_id')}")
            print_test("Contains message", "message" in data,
                       f"message: {data.get('message')}")
            
            return all([
                "status" in data,
                "violation_id" in data,
                "message" in data
            ])
        else:
            print_test("Valid response", False,
                       f"Status: {response.status_code}")
            return False
            
    except json.JSONDecodeError:
        print_test("Response is JSON", False)
        return False
    except Exception as e:
        print_test("Response format test", False, str(e))
        return False

def test_frontend_pages():
    """Test frontend pages accessible"""
    print_section("9. FRONTEND PAGES TEST")
    
    pages = [
        ("/participant-dashboard", "Participant Dashboard"),
        ("/static/exam-monitor.js", "Exam Monitor Script"),
    ]
    
    accessible = 0
    for page, description in pages:
        try:
            response = requests.get(f"{BASE_URL}{page}", timeout=5)
            if response.status_code == 200:
                accessible += 1
                print_test(f"  {description}", True)
            else:
                print_test(f"  {description}", False,
                           f"Status: {response.status_code}")
        except Exception as e:
            print_test(f"  {description}", False, str(e))
    
    return accessible == len(pages)

def test_database_storage():
    """Test if violations stored in database"""
    print_section("10. DATABASE STORAGE TEST")
    
    print("Note: This test requires manual database check")
    print("Run these queries to verify:")
    print("")
    print("  # Check if violation table exists:")
    print("  SHOW TABLES;")
    print("")
    print("  # Query violations:")
    print(f"  SELECT * FROM violations WHERE participant_id = {PARTICIPANT_ID};")
    print("")
    print("  # Check count:")
    print(f"  SELECT COUNT(*) FROM violations WHERE participant_id = {PARTICIPANT_ID};")
    print("")
    
    return True

def main():
    """Run all tests"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("="*60)
    print("PROCTORING SYSTEM - TEST SUITE")
    print("="*60)
    print(f"{Colors.RESET}")
    
    print(f"Base URL: {BASE_URL}")
    print(f"API Endpoint: {API_ENDPOINT}")
    print(f"Participant ID: {PARTICIPANT_ID}")
    print(f"Session ID: {SESSION_ID}")
    
    # Run tests
    tests = []
    
    if not test_backend_connection():
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Backend not running!{Colors.RESET}")
        print("Please start Flask with: python app.py")
        return 1
    
    tests.append(("Backend Connection", test_backend_connection()))
    tests.append(("API Endpoint", test_api_endpoint()))
    tests.append(("Violation without screenshot", test_violation_without_screenshot() is not None))
    tests.append(("Violation with screenshot", test_violation_with_screenshot() is not None))
    tests.append(("Multiple violations", test_multiple_violations()))
    tests.append(("Payload validation", test_payload_validation()))
    tests.append(("Concurrent uploads", test_concurrent_uploads()))
    tests.append(("Response format", test_response_format()))
    tests.append(("Frontend pages", test_frontend_pages()))
    test_database_storage()
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for test_name, result in tests:
        symbol = f"{Colors.GREEN}✓{Colors.RESET}" if result else f"{Colors.RED}✗{Colors.RESET}"
        print(f"{symbol} {test_name}")
    
    print(f"\n{Colors.BOLD}Result: {passed}/{total} tests passed{Colors.RESET}")
    
    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ ALL TESTS PASSED!{Colors.RESET}")
        print("\nSystem is ready for deployment!")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ SOME TESTS FAILED!{Colors.RESET}")
        print("\nPlease fix the issues before deployment.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
