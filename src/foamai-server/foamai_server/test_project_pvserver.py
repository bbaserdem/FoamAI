#!/usr/bin/env python3
"""
Test script for project-based PVServer functionality
Tests the new project-based pvserver endpoints
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime

# Configuration
try:
    from config import EC2_HOST, API_PORT
    BASE_URL = f"http://{EC2_HOST}:{API_PORT}"
except ImportError:
    BASE_URL = "http://localhost:8000"

print(f"Testing against: {BASE_URL}")

def test_health_check():
    """Test health check endpoint"""
    print("\n=== Testing Health Check ===")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        print(f"Health check status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Server status: {data.get('status')}")
            print(f"Database connected: {data.get('database_connected')}")
            print(f"Running task pvservers: {data.get('running_pvservers')}")
            print(f"Running project pvservers: {data.get('running_project_pvservers')}")
        else:
            print(f"Health check failed: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check error: {e}")
        return False

def test_create_project():
    """Test creating a project"""
    print("\n=== Testing Project Creation ===")
    project_name = f"test_pvserver_project_{int(time.time())}"
    
    try:
        data = {
            "project_name": project_name,
            "description": "Test project for pvserver functionality"
        }
        response = requests.post(f"{BASE_URL}/api/projects", json=data, timeout=30)
        print(f"Create project status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Project created: {result.get('project_name')}")
            print(f"Project path: {result.get('project_path')}")
            return project_name
        else:
            print(f"Project creation failed: {response.text}")
            return None
    except Exception as e:
        print(f"Project creation error: {e}")
        return None

def test_project_pvserver_info(project_name):
    """Test getting project pvserver info"""
    print(f"\n=== Testing Project PVServer Info for {project_name} ===")
    try:
        response = requests.get(f"{BASE_URL}/api/projects/{project_name}/pvserver/info", timeout=10)
        print(f"PVServer info status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"PVServer status: {data.get('status')}")
            print(f"Port: {data.get('port')}")
            print(f"PID: {data.get('pid')}")
            print(f"Case path: {data.get('case_path')}")
            print(f"Connection string: {data.get('connection_string')}")
            return data
        else:
            print(f"PVServer info failed: {response.text}")
            return None
    except Exception as e:
        print(f"PVServer info error: {e}")
        return None

def test_start_project_pvserver(project_name):
    """Test starting a project pvserver"""
    print(f"\n=== Testing Start Project PVServer for {project_name} ===")
    try:
        # Empty request body since we use active_run automatically
        response = requests.post(f"{BASE_URL}/api/projects/{project_name}/pvserver/start", json={}, timeout=60)
        print(f"Start PVServer status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"PVServer started successfully!")
            print(f"Port: {data.get('port')}")
            print(f"PID: {data.get('pid')}")
            print(f"Status: {data.get('status')}")
            print(f"Case path: {data.get('case_path')}")
            print(f"Connection string: {data.get('connection_string')}")
            print(f"Started at: {data.get('started_at')}")
            return data
        else:
            print(f"Start PVServer failed: {response.text}")
            return None
    except Exception as e:
        print(f"Start PVServer error: {e}")
        return None

def test_stop_project_pvserver(project_name):
    """Test stopping a project pvserver"""
    print(f"\n=== Testing Stop Project PVServer for {project_name} ===")
    try:
        response = requests.delete(f"{BASE_URL}/api/projects/{project_name}/pvserver/stop", timeout=30)
        print(f"Stop PVServer status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"PVServer stopped successfully!")
            print(f"Project: {data.get('project_name')}")
            print(f"Status: {data.get('status')}")
            print(f"Message: {data.get('message')}")
            print(f"Stopped at: {data.get('stopped_at')}")
            return True
        else:
            print(f"Stop PVServer failed: {response.text}")
            return False
    except Exception as e:
        print(f"Stop PVServer error: {e}")
        return False

def test_list_all_pvservers():
    """Test listing all pvservers"""
    print("\n=== Testing List All PVServers ===")
    try:
        response = requests.get(f"{BASE_URL}/api/pvservers", timeout=10)
        print(f"List PVServers status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total PVServers: {data.get('total_count')}")
            print(f"Running PVServers: {data.get('running_count')}")
            print(f"Task-based PVServers: {len(data.get('task_pvservers', []))}")
            print(f"Project-based PVServers: {len(data.get('project_pvservers', []))}")
            
            # Show project pvservers
            project_pvservers = data.get('project_pvservers', [])
            if project_pvservers:
                print("\nProject PVServers:")
                for pv in project_pvservers:
                    print(f"  - Project: {pv.get('project_name')}")
                    print(f"    Port: {pv.get('port')}")
                    print(f"    Status: {pv.get('status')}")
                    print(f"    Started: {pv.get('started_at')}")
            
            return data
        else:
            print(f"List PVServers failed: {response.text}")
            return None
    except Exception as e:
        print(f"List PVServers error: {e}")
        return None

def test_system_stats():
    """Test system statistics"""
    print("\n=== Testing System Statistics ===")
    try:
        response = requests.get(f"{BASE_URL}/api/system/stats", timeout=10)
        print(f"System stats status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total tasks: {data.get('total_tasks')}")
            print(f"Running task pvservers: {data.get('running_task_pvservers')}")
            print(f"Total project pvservers: {data.get('total_project_pvservers')}")
            print(f"Running project pvservers: {data.get('running_project_pvservers')}")
            print(f"Timestamp: {data.get('timestamp')}")
            return data
        else:
            print(f"System stats failed: {response.text}")
            return None
    except Exception as e:
        print(f"System stats error: {e}")
        return None

def test_duplicate_start_prevention(project_name):
    """Test that starting a second pvserver for the same project fails"""
    print(f"\n=== Testing Duplicate Start Prevention for {project_name} ===")
    try:
        response = requests.post(f"{BASE_URL}/api/projects/{project_name}/pvserver/start", json={}, timeout=30)
        print(f"Duplicate start status: {response.status_code}")
        
        if response.status_code == 400:
            print("✓ Correctly prevented duplicate pvserver start")
            print(f"Error message: {response.json().get('detail')}")
            return True
        else:
            print(f"✗ Unexpected response: {response.text}")
            return False
    except Exception as e:
        print(f"Duplicate start test error: {e}")
        return False

def cleanup_project(project_name):
    """Clean up test project"""
    print(f"\n=== Cleaning up project {project_name} ===")
    try:
        response = requests.delete(f"{BASE_URL}/api/projects/{project_name}", timeout=30)
        print(f"Delete project status: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ Project deleted successfully")
            return True
        else:
            print(f"✗ Project deletion failed: {response.text}")
            return False
    except Exception as e:
        print(f"Project cleanup error: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 60)
    print("PROJECT-BASED PVSERVER FUNCTIONALITY TEST")
    print("=" * 60)
    
    # Test health check first
    if not test_health_check():
        print("❌ Health check failed - aborting tests")
        return
    
    # Create test project
    project_name = test_create_project()
    if not project_name:
        print("❌ Failed to create test project - aborting tests")
        return
    
    try:
        # Test project pvserver info (should show no pvserver initially)
        test_project_pvserver_info(project_name)
        
        # Test starting project pvserver
        pvserver_data = test_start_project_pvserver(project_name)
        if not pvserver_data:
            print("❌ Failed to start project pvserver")
            return
        
        # Test getting pvserver info after start
        test_project_pvserver_info(project_name)
        
        # Test duplicate start prevention
        test_duplicate_start_prevention(project_name)
        
        # Test listing all pvservers
        test_list_all_pvservers()
        
        # Test system stats
        test_system_stats()
        
        # Wait a bit to let pvserver fully start
        print("\n⏳ Waiting 3 seconds for pvserver to fully initialize...")
        time.sleep(3)
        
        # Test stopping project pvserver
        test_stop_project_pvserver(project_name)
        
        # Test getting pvserver info after stop
        test_project_pvserver_info(project_name)
        
        print("\n✅ All project-based pvserver tests completed!")
        
    finally:
        # Clean up
        cleanup_project(project_name)

if __name__ == "__main__":
    main() 