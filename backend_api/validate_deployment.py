#!/usr/bin/env python3
"""
Simple deployment validation script for FoamAI backend API.
Tests basic functionality after deployment to EC2, including new pvserver management endpoints.

IMPORTANT: As of the latest version, pvserver management is now EXPLICIT only.
- Old routes (submit_scenario, approve_mesh, run_openfoam_command) no longer automatically start pvservers
- Use the new explicit pvserver management endpoints (/api/start_pvserver, /api/pvservers, etc.)
- This eliminates the original problem of multiple pvservers being created for the same case
"""

import requests
import time
import json
import os
import sys
import subprocess
from pathlib import Path
import shutil

# Import configuration
from config import EC2_HOST as CONFIG_EC2_HOST

# Configuration
EC2_HOST = CONFIG_EC2_HOST  # Use host from config
API_BASE_URL = f"http://{EC2_HOST}:8000/api"
PARAVIEW_HOST = EC2_HOST
PARAVIEW_PORT = 11111
CAVITY_CASE_PATH = "/home/ubuntu/cavity_tutorial"

def test_api_health():
    """Test if API server is responding"""
    print("🔍 Testing API health...")
    try:
        # Increase timeout and add retry logic
        for attempt in range(3):
            try:
                response = requests.get(f"{API_BASE_URL}/health", timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ API health check passed - {data}")
                    return True
                else:
                    print(f"❌ API health check failed: {response.status_code}")
                    return False
            except requests.exceptions.Timeout:
                print(f"⏱️  Timeout on attempt {attempt + 1}/3, retrying...")
                time.sleep(2)
                continue
            except requests.exceptions.ConnectionError as e:
                print(f"🔗 Connection error on attempt {attempt + 1}/3: {e}")
                time.sleep(2)
                continue
        
        print("❌ All connection attempts failed")
        return False
        
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        return False

def test_start_pvserver():
    """Test the new start_pvserver endpoint"""
    print(f"\n🚀 Testing start_pvserver endpoint for {CAVITY_CASE_PATH}...")
    
    pvserver_data = {
        "case_path": CAVITY_CASE_PATH
        # port is optional - let API auto-find available port
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/start_pvserver",
            json=pvserver_data,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PVServer started successfully")
            print(f"📋 Status: {data.get('status')}")
            print(f"🔗 Port: {data.get('port')}")
            print(f"📡 Connection: {data.get('connection_string')}")
            print(f"🏠 Case Path: {data.get('case_path')}")
            print(f"🔄 Reused: {data.get('reused', False)}")
            
            if data.get('reused'):
                print("ℹ️  PVServer was reused from existing instance")
            else:
                print("ℹ️  New PVServer instance created")
            
            return {
                "success": True,
                "port": data.get('port'),
                "connection_string": data.get('connection_string')
            }
        else:
            print(f"❌ Start PVServer failed: {response.status_code}")
            print(f"Response: {response.text}")
            return {"success": False}
            
    except Exception as e:
        print(f"❌ Start PVServer failed: {e}")
        return {"success": False}

def test_list_pvservers():
    """Test the new list_pvservers endpoint"""
    print("\n📋 Testing list_pvservers endpoint...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/pvservers", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PVServers listed successfully")
            print(f"📊 Total Count: {data.get('total_count', 0)}")
            print(f"🔢 Port Range: {data.get('port_range', 'Unknown')}")
            print(f"🔓 Available Ports: {data.get('available_ports', 0)}")
            
            pvservers = data.get('pvservers', [])
            if pvservers:
                print("🎨 Active PVServers:")
                for i, pvserver in enumerate(pvservers, 1):
                    print(f"  {i}. Port {pvserver.get('port')} - Case: {pvserver.get('case_path', 'Unknown')}")
                    print(f"     PID: {pvserver.get('pid')}, Connection: {pvserver.get('connection_string')}")
            else:
                print("ℹ️  No active PVServers found")
            
            return {"success": True, "pvservers": pvservers}
        else:
            print(f"❌ List PVServers failed: {response.status_code}")
            print(f"Response: {response.text}")
            return {"success": False}
            
    except Exception as e:
        print(f"❌ List PVServers failed: {e}")
        return {"success": False}

def test_stop_pvserver(port):
    """Test the new stop_pvserver endpoint"""
    print(f"\n🛑 Testing stop_pvserver endpoint for port {port}...")
    
    try:
        response = requests.delete(f"{API_BASE_URL}/pvservers/{port}", timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PVServer stopped successfully")
            print(f"📋 Status: {data.get('status')}")
            print(f"🔗 Port: {data.get('port')}")
            print(f"💬 Message: {data.get('message')}")
            return True
        else:
            print(f"❌ Stop PVServer failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Stop PVServer failed: {e}")
        return False

def test_paraview_connection(port=None):
    """Test ParaView server connection"""
    test_port = port or PARAVIEW_PORT
    print(f"\n🎨 Testing ParaView server connection to {PARAVIEW_HOST}:{test_port}...")
    
    try:
        # Simple socket connection test
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((PARAVIEW_HOST, test_port))
        sock.close()
        
        if result == 0:
            print("✅ ParaView server is accepting connections")
            return True
        else:
            print(f"❌ ParaView server connection failed (port {test_port} not open)")
            return False
            
    except Exception as e:
        print(f"❌ ParaView server connection test failed: {e}")
        return False

def test_submit_scenario():
    """Test scenario submission endpoint"""
    print("\n📤 Testing scenario submission...")
    
    # Updated to match new API structure
    scenario_data = {
        "scenario_description": "I want to test cavity flow simulation for validation",
        "mesh_complexity": "medium",
        "solver_type": "incompressible"
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/submit_scenario",
            json=scenario_data,
            timeout=30
        )
        
        if response.status_code == 200:  # Updated from 202 to 200
            data = response.json()
            task_id = data.get("task_id")
            print(f"✅ Scenario submitted successfully. Task ID: {task_id}")
            print(f"📋 Status: {data.get('status')} - {data.get('message')}")
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
            response = requests.get(f"{API_BASE_URL}/task_status/{task_id}", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                message = data.get("message", "")
                
                print(f"📋 Status: {status} - {message}")
                
                # Check for pvserver info
                if data.get("pvserver"):
                    pvserver = data["pvserver"]
                    print(f"🎨 PVServer: {pvserver.get('status')} on port {pvserver.get('port')}")
                    if pvserver.get("connection_string"):
                        print(f"🔗 Connection: {pvserver['connection_string']}")
                
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
    
    # Updated to match new API structure
    approval_data = {
        "approved": True,
        "comments": "Validation test approval"
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/approve_mesh?task_id={task_id}",  # Updated to query parameter
            json=approval_data,
            timeout=30
        )
        
        if response.status_code == 200:  # Updated from 202 to 200
            data = response.json()
            print(f"✅ Mesh approved successfully: {data.get('message')}")
            # The same task_id continues to simulation phase
            return task_id
        else:
            print(f"❌ Mesh approval failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Mesh approval failed: {e}")
        return None

def test_openfoam_command():
    """Test OpenFOAM command endpoint"""
    print("\n🌊 Testing OpenFOAM command endpoint...")
    
    command_data = {
        "command": "blockMesh",
        "case_path": CAVITY_CASE_PATH,
        "description": "Test mesh generation via API"
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/run_openfoam_command",
            json=command_data,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            task_id = data.get("task_id")
            print(f"✅ OpenFOAM command submitted successfully. Task ID: {task_id}")
            print(f"📋 Command: {data.get('command')} in {data.get('case_path')}")
            return task_id
        else:
            print(f"❌ OpenFOAM command failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ OpenFOAM command failed: {e}")
        return None

def test_pvserver_info(task_id):
    """Test PVServer info endpoint"""
    print(f"\n🎨 Testing PVServer info for {task_id}...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/pvserver_info/{task_id}", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PVServer info retrieved successfully")
            print(f"📋 Status: {data.get('status')}")
            print(f"🔗 Port: {data.get('port')}")
            print(f"📡 Connection: {data.get('connection_string')}")
            return True
        elif response.status_code == 404:
            print("ℹ️  No PVServer info available yet (task may be in early stage)")
            return True
        else:
            print(f"❌ PVServer info failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ PVServer info failed: {e}")
        return False

def test_cleanup_endpoint():
    """Test cleanup endpoint"""
    print("\n🧹 Testing cleanup endpoint...")
    
    try:
        response = requests.post(f"{API_BASE_URL}/cleanup_pvservers", timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Cleanup endpoint works")
            print(f"📋 Status: {data.get('status')}")
            print(f"🧹 Cleaned up: {len(data.get('cleaned_up', []))} servers")
            return True
        else:
            print(f"❌ Cleanup endpoint failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Cleanup endpoint failed: {e}")
        return False

def test_pvserver_management_workflow():
    """Test the new pvserver management workflow"""
    print("\n🔄 Testing PVServer Management Workflow...")
    
    # Step 1: List current pvservers
    print("\n--- Step 1: List current pvservers ---")
    list_result = test_list_pvservers()
    if not list_result["success"]:
        return False
    
    # Step 2: Start a pvserver for the cavity case
    print("\n--- Step 2: Start pvserver for cavity case ---")
    start_result = test_start_pvserver()
    if not start_result["success"]:
        return False
    
    pvserver_port = start_result["port"]
    connection_string = start_result["connection_string"]
    
    # Step 3: List pvservers again to confirm it's running
    print("\n--- Step 3: Confirm pvserver is running ---")
    list_result = test_list_pvservers()
    if not list_result["success"]:
        return False
    
    # Step 4: Test ParaView connection
    print("\n--- Step 4: Test ParaView connection ---")
    connection_success = test_paraview_connection(pvserver_port)
    
    # Step 5: Run blockMesh command (this should reuse the existing pvserver)
    print("\n--- Step 5: Run blockMesh command ---")
    mesh_task_id = test_openfoam_command()
    if not mesh_task_id:
        return False
    
    # Step 6: Wait for blockMesh completion
    print("\n--- Step 6: Wait for blockMesh completion ---")
    if not test_task_status(mesh_task_id):
        return False
    
    # Step 7: Run foamRun command (this should also reuse the existing pvserver)
    print("\n--- Step 7: Run foamRun command ---")
    solver_data = {
        "command": "foamRun",
        "case_path": CAVITY_CASE_PATH,
        "description": "Test solver run via API"
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/run_openfoam_command",
            json=solver_data,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            solver_task_id = data.get("task_id")
            print(f"✅ foamRun command submitted successfully. Task ID: {solver_task_id}")
            
            # Wait for solver completion
            print("\n--- Step 8: Wait for foamRun completion ---")
            if not test_task_status(solver_task_id):
                return False
        else:
            print(f"❌ foamRun command failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ foamRun command failed: {e}")
        return False
    
    # Step 9: Final pvserver list to show it's still running
    print("\n--- Step 9: Final pvserver status ---")
    list_result = test_list_pvservers()
    if not list_result["success"]:
        return False
    
    # Step 10: Test stopping the pvserver
    print("\n--- Step 10: Stop pvserver ---")
    if not test_stop_pvserver(pvserver_port):
        return False
    
    # Step 11: Confirm pvserver is stopped
    print("\n--- Step 11: Confirm pvserver is stopped ---")
    list_result = test_list_pvservers()
    if not list_result["success"]:
        return False
    
    print("✅ PVServer management workflow test completed successfully!")
    return True

def test_openfoam_only_workflow():
    """Test the OpenFOAM workflow without automatic pvserver management"""
    print("\n🔄 Testing OpenFOAM-only workflow (no automatic pvserver)...")
    
    # Step 1: Submit scenario
    task_id = test_submit_scenario()
    if not task_id:
        return False
    
    # Step 2: Wait for mesh generation
    if not test_task_status(task_id):
        return False
    
    # Step 3: Approve mesh
    if not test_mesh_approval(task_id):
        return False
    
    # Step 4: Wait for simulation completion
    if not test_task_status(task_id):
        return False
    
    print("✅ OpenFOAM-only workflow test passed!")
    print("ℹ️  Note: No pvserver was automatically started. Use explicit pvserver management for visualization.")
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
    print(f"🎨 ParaView Host: {PARAVIEW_HOST}")
    print(f"🏠 Cavity Case Path: {CAVITY_CASE_PATH}")
    
    # Run tests
    tests = [
        ("API Health", test_api_health),
        ("PVServer Management Workflow", test_pvserver_management_workflow),
        ("Cleanup Endpoint", test_cleanup_endpoint),
        ("OpenFOAM-Only Workflow", test_openfoam_only_workflow),
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
        
        # Start a pvserver for the cavity case so it's ready for use
        print(f"\n{'='*20} Final Setup {'='*20}")
        print("🚀 Starting pvserver for cavity case to leave it ready for use...")
        
        start_result = test_start_pvserver()
        if start_result["success"]:
            print(f"✅ PVServer is now running on port {start_result['port']}")
            print(f"🔗 Connection string: {start_result['connection_string']}")
            print(f"🏠 Case path: {CAVITY_CASE_PATH}")
            print("\n💡 Use the cleanup script to stop all pvservers when done:")
            print("   python stop_all_pvservers.py")
        else:
            print("⚠️  Could not start final pvserver, but tests passed")
        
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    exit(main()) 