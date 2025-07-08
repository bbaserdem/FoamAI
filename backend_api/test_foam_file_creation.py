#!/usr/bin/env python3
"""
Test script for automatic .foam file creation functionality.
This script tests the new API endpoint that automatically creates .foam files.
"""

import requests
import time
import sys

def test_foam_file_creation(api_base_url):
    """Test the automatic .foam file creation after OpenFOAM commands"""
    
    print("🧪 Testing automatic .foam file creation...")
    
    # Test 1: Run blockMesh command
    print("\n1. Testing blockMesh command...")
    
    blockMesh_data = {
        "command": "blockMesh",
        "case_path": "/home/ubuntu/cavity_tutorial",
        "description": "Testing blockMesh with automatic .foam file creation"
    }
    
    try:
        response = requests.post(f"{api_base_url}/run_openfoam_command", json=blockMesh_data, timeout=30)
        
        if response.status_code == 202:
            data = response.json()
            task_id = data["task_id"]
            print(f"✅ blockMesh command submitted. Task ID: {task_id}")
            
            # Poll for completion
            max_attempts = 60
            for attempt in range(max_attempts):
                status_response = requests.get(f"{api_base_url}/task_status/{task_id}", timeout=10)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"📋 Status: {status_data['status']} - {status_data['message']}")
                    
                    if status_data["status"] == "completed":
                        print("✅ blockMesh completed successfully!")
                        print(f"📁 File path: {status_data.get('file_path', 'Not specified')}")
                        break
                    elif status_data["status"] == "error":
                        print(f"❌ blockMesh failed: {status_data['message']}")
                        return False
                
                time.sleep(2)
            else:
                print("❌ blockMesh command timed out")
                return False
                
        else:
            print(f"❌ Failed to submit blockMesh command: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing blockMesh: {e}")
        return False
    
    # Test 2: Test arbitrary OpenFOAM command (checkMesh)
    print("\n2. Testing checkMesh command...")
    
    checkMesh_data = {
        "command": "checkMesh",
        "case_path": "/home/ubuntu/cavity_tutorial",
        "description": "Testing checkMesh with automatic .foam file creation"
    }
    
    try:
        response = requests.post(f"{api_base_url}/run_openfoam_command", json=checkMesh_data, timeout=30)
        
        if response.status_code == 202:
            data = response.json()
            task_id = data["task_id"]
            print(f"✅ checkMesh command submitted. Task ID: {task_id}")
            
            # Poll for completion
            for attempt in range(30):  # Shorter timeout for checkMesh
                status_response = requests.get(f"{api_base_url}/task_status/{task_id}", timeout=10)
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"📋 Status: {status_data['status']} - {status_data['message']}")
                    
                    if status_data["status"] == "completed":
                        print("✅ checkMesh completed successfully!")
                        print(f"📁 File path: {status_data.get('file_path', 'Not specified')}")
                        break
                    elif status_data["status"] == "error":
                        print(f"❌ checkMesh failed: {status_data['message']}")
                        return False
                
                time.sleep(2)
            else:
                print("❌ checkMesh command timed out")
                return False
                
        else:
            print(f"❌ Failed to submit checkMesh command: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing checkMesh: {e}")
        return False
    
    print("\n✅ All .foam file creation tests passed!")
    return True

def main():
    """Main test function"""
    if len(sys.argv) < 2:
        print("Usage: python3 test_foam_file_creation.py <ec2_host>")
        print("Example: python3 test_foam_file_creation.py your-ec2-host.amazonaws.com")
        sys.exit(1)
    
    ec2_host = sys.argv[1]
    api_base_url = f"http://{ec2_host}:8000/api"
    
    print("🧪 FoamAI .foam File Creation Test")
    print("=" * 50)
    print(f"🎯 Testing API at: {api_base_url}")
    
    # Test API health first
    try:
        response = requests.get(f"{api_base_url}/health", timeout=10)
        if response.status_code == 200:
            print("✅ API is healthy")
        else:
            print("❌ API health check failed")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        sys.exit(1)
    
    # Run the foam file creation tests
    if test_foam_file_creation(api_base_url):
        print("\n🎉 All tests passed! .foam files are being created automatically.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main() 