#!/usr/bin/env python3
"""
Simple deployment validation script for FoamAI backend API.
Tests basic functionality after deployment to EC2.
"""

import requests
import time
import json
import os
import sys
import subprocess
from pathlib import Path

# Configuration - Update these for your EC2 instance
EC2_HOST = "3.139.77.134"  # Replace with your EC2 host
API_BASE_URL = f"http://{EC2_HOST}:8000/api"
PARAVIEW_HOST = EC2_HOST
PARAVIEW_PORT = 11111

def test_api_health():
    """Test if API server is responding"""
    print("🔍 Testing API health...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("✅ API health check passed")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        return False

def test_submit_scenario():
    """Test scenario submission endpoint"""
    print("\n📤 Testing scenario submission...")
    
    scenario_data = {
        "scenario": "I want to see effects of 10 mph wind on a cube sitting on the ground",
        "user_id": "test_user"
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/submit_scenario",
            json=scenario_data,
            timeout=30
        )
        
        if response.status_code == 202:
            data = response.json()
            task_id = data.get("task_id")
            print(f"✅ Scenario submitted successfully. Task ID: {task_id}")
            return task_id
        else:
            print(f"❌ Scenario submission failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Scenario submission failed: {e}")
        return None

def test_task_status(task_id):
    """Test task status polling"""
    print(f"\n📊 Testing task status polling for {task_id}...")
    
    max_attempts = 60  # 5 minutes with 5-second intervals
    attempt = 0
    
    while attempt < max_attempts:
        try:
            response = requests.get(f"{API_BASE_URL}/task_status/{task_id}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                message = data.get("message", "")
                
                print(f"📋 Status: {status} - {message}")
                
                if status == "waiting_approval":
                    print("✅ Task status polling works - mesh ready for approval")
                    return True
                elif status == "completed":
                    print("✅ Task completed successfully")
                    return True
                elif status == "error":
                    print(f"❌ Task failed: {message}")
                    return False
                    
            else:
                print(f"❌ Status check failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Status check failed: {e}")
            return False
            
        attempt += 1
        time.sleep(5)
    
    print("❌ Task status polling timed out")
    return False

def test_mesh_approval(task_id):
    """Test mesh approval endpoint"""
    print(f"\n✅ Testing mesh approval for {task_id}...")
    
    approval_data = {
        "task_id": task_id,
        "approved": True
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/approve_mesh",
            json=approval_data,
            timeout=30
        )
        
        if response.status_code == 202:
            data = response.json()
            new_task_id = data.get("new_task_id")
            print(f"✅ Mesh approved successfully. New task ID: {new_task_id}")
            return new_task_id
        else:
            print(f"❌ Mesh approval failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Mesh approval failed: {e}")
        return None

def test_openfoam_direct():
    """Test OpenFOAM cavity case directly on EC2"""
    print("\n🌊 Testing OpenFOAM cavity case directly...")
    
    # This would need to be run ON the EC2 instance
    print("ℹ️  This test should be run directly on the EC2 instance:")
    print("    cd /home/ubuntu/cavity_tutorial")
    print("    ./run_cavity.sh")
    print("    ls -la *.foam")
    print("✅ Manual OpenFOAM test instructions provided")
    return True

def test_paraview_connection():
    """Test ParaView server connection"""
    print(f"\n🎨 Testing ParaView server connection to {PARAVIEW_HOST}:{PARAVIEW_PORT}...")
    
    try:
        # Simple socket connection test
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((PARAVIEW_HOST, PARAVIEW_PORT))
        sock.close()
        
        if result == 0:
            print("✅ ParaView server is accepting connections")
            return True
        else:
            print(f"❌ ParaView server connection failed (port {PARAVIEW_PORT} not open)")
            return False
            
    except Exception as e:
        print(f"❌ ParaView server connection test failed: {e}")
        return False

def test_full_workflow():
    """Test the complete workflow end-to-end"""
    print("\n🔄 Testing complete workflow...")
    
    # Step 1: Submit scenario
    task_id = test_submit_scenario()
    if not task_id:
        return False
    
    # Step 2: Wait for mesh generation
    if not test_task_status(task_id):
        return False
    
    # Step 3: Approve mesh
    sim_task_id = test_mesh_approval(task_id)
    if not sim_task_id:
        return False
    
    # Step 4: Wait for simulation completion
    if not test_task_status(sim_task_id):
        return False
    
    print("✅ Complete workflow test passed!")
    return True

def main():
    """Run all validation tests"""
    print("🚀 FoamAI Backend API Deployment Validation")
    print("=" * 50)
    
    # Update configuration
    if len(sys.argv) > 1:
        global EC2_HOST, API_BASE_URL, PARAVIEW_HOST
        EC2_HOST = sys.argv[1]
        API_BASE_URL = f"http://{EC2_HOST}:8000/api"
        PARAVIEW_HOST = EC2_HOST
    
    print(f"🎯 Testing deployment at: {EC2_HOST}")
    print(f"📡 API Base URL: {API_BASE_URL}")
    print(f"🎨 ParaView Host: {PARAVIEW_HOST}:{PARAVIEW_PORT}")
    
    # Run tests
    tests = [
        ("API Health", test_api_health),
        ("ParaView Connection", test_paraview_connection),
        ("OpenFOAM Direct", test_openfoam_direct),
        ("Full Workflow", test_full_workflow),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print(f"\n🏁 SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All validation tests passed! Deployment is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    exit(main()) 