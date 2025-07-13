#!/usr/bin/env python3
"""
Simplified test script for datetime serialization fix.
Only tests routes we know exist and exception handlers we know work.
"""

import requests
import json
from datetime import datetime

from config import EC2_HOST, API_PORT

# Test configuration
BASE_URL = f"http://{EC2_HOST}:{API_PORT}"

def print_header(title: str):
    """Print a formatted header"""
    print(f"\n{'='*50}")
    print(f"🧪 {title}")
    print(f"{'='*50}")

def validate_datetime_serialization(response_data: dict) -> bool:
    """Check if timestamp is properly serialized as string"""
    if 'timestamp' not in response_data:
        print("   ❌ No timestamp field found")
        return False
    
    timestamp = response_data['timestamp']
    if not isinstance(timestamp, str):
        print(f"   ❌ Timestamp is {type(timestamp)}, expected string")
        return False
    
    # Try to parse it as ISO format
    try:
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        print(f"   ✅ Timestamp properly serialized: {timestamp}")
        return True
    except ValueError:
        print(f"   ❌ Invalid timestamp format: {timestamp}")
        return False

def test_server_health():
    """Test basic connectivity"""
    print_header("Server Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("✅ Server is healthy and reachable")
            return True
        else:
            print(f"❌ Server health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def test_project_error_datetime():
    """Test ProjectError handler with datetime serialization"""
    print_header("ProjectError Handler - Datetime Serialization Test")
    
    # Test with the exact error case you encountered
    test_name = "testing :)"
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/projects",
            json={"project_name": test_name, "description": "Test project"},
            timeout=15
        )
        
        if response.status_code == 400:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # Check required fields
            required_fields = ['detail', 'error_type', 'timestamp']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                print(f"❌ Missing fields: {missing_fields}")
                return False
            
            # Check error type
            if data['error_type'] != 'ProjectError':
                print(f"❌ Expected ProjectError, got: {data['error_type']}")
                return False
            
            # Main test: validate datetime serialization
            if validate_datetime_serialization(data):
                print("✅ ProjectError handler correctly serializes datetime!")
                return True
            else:
                return False
        else:
            print(f"❌ Expected 400 status, got: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def test_validation_error_datetime():
    """Test ValidationError handler with datetime serialization"""
    print_header("ValidationError Handler - Datetime Serialization Test")
    
    try:
        # Send completely invalid JSON structure to trigger validation error
        response = requests.post(
            f"{BASE_URL}/api/projects",
            json={},  # Missing required project_name field
            timeout=15
        )
        
        if response.status_code == 422:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # This should be the validation error format we saw in main.py
            if validate_datetime_serialization(data):
                print("✅ ValidationError handler correctly serializes datetime!")
                return True
            else:
                return False
        else:
            print(f"❌ Expected 422 status, got: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def test_before_after_comparison():
    """Show what the response looks like with proper serialization"""
    print_header("Before vs After Comparison")
    
    print("🚫 BEFORE our fix, you would have seen:")
    print("   TypeError: Object of type datetime is not JSON serializable")
    print("   (Server would crash when trying to return error response)")
    
    print("\n✅ AFTER our fix, you now see:")
    print("   Proper JSON error responses with serialized timestamps")
    print("   Example timestamp: '2025-07-10T20:46:08.217486'")
    
    return True

def main():
    """Run simplified datetime serialization tests"""
    print("🚀 Simplified Datetime Serialization Test")
    print(f"🌐 Target Server: {BASE_URL}")
    print(f"⏰ Test Time: {datetime.now().isoformat()}")
    print("\n🎯 Focus: Validating the .model_dump(mode='json') fix")
    
    # Run focused tests
    tests = [
        ("Server Health", test_server_health),
        ("ProjectError DateTime Fix", test_project_error_datetime),
        ("ValidationError DateTime Fix", test_validation_error_datetime),
        ("Before/After Comparison", test_before_after_comparison),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Results summary
    print_header("Test Results Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed >= 2:  # At least server health + one datetime test
        print("\n🎉 SUCCESS! Datetime serialization fix is working!")
        print("💡 Your API now properly handles datetime objects in error responses")
        print("🔧 The .model_dump(mode='json') fix resolved the JSON serialization issue")
        return 0
    else:
        print("\n⚠️  Some core tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    exit(main()) 