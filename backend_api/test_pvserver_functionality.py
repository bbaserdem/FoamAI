#!/usr/bin/env python3
"""
Test script for PVServer functionality
Tests the new pvserver management features including:
- Database operations
- Port management
- Process management
- API integration
"""

import sqlite3
import subprocess
import os
import time
import requests
from pathlib import Path
from datetime import datetime

DATABASE_PATH = 'tasks.db'
API_BASE_URL = 'http://3.139.77.134:8000'  # Update this to your EC2 IP

def test_database_schema():
    """Test that the database schema includes all pvserver columns"""
    print("🧪 Testing database schema...")
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Get table info
    cursor.execute("PRAGMA table_info(tasks)")
    columns = cursor.fetchall()
    
    required_columns = [
        'case_path', 'pvserver_port', 'pvserver_pid', 'pvserver_status',
        'pvserver_started_at', 'pvserver_last_activity', 'pvserver_error_message'
    ]
    
    column_names = [col[1] for col in columns]
    
    for col in required_columns:
        if col in column_names:
            print(f"  ✅ Column '{col}' exists")
        else:
            print(f"  ❌ Column '{col}' missing")
    
    conn.close()
    print("✅ Database schema test completed\n")

def test_port_management():
    """Test port management functions"""
    print("🧪 Testing port management...")
    
    try:
        from pvserver_manager import port_is_available, find_available_port, PVSERVER_PORT_RANGE
        
        # Test port availability check
        available_port = find_available_port()
        if available_port:
            print(f"  ✅ Found available port: {available_port}")
            
            # Test that the port is indeed available
            if port_is_available(available_port):
                print(f"  ✅ Port {available_port} is available")
            else:
                print(f"  ❌ Port {available_port} reported as available but is not")
        else:
            print(f"  ⚠️  No available ports in range {PVSERVER_PORT_RANGE}")
        
        # Test port range
        start_port, end_port = PVSERVER_PORT_RANGE
        print(f"  ✅ Port range: {start_port}-{end_port}")
        
    except ImportError as e:
        print(f"  ❌ Error importing pvserver_manager: {e}")
    
    print("✅ Port management test completed\n")

def test_pvserver_functions():
    """Test pvserver management functions"""
    print("🧪 Testing pvserver management functions...")
    
    try:
        from pvserver_manager import (
            count_running_pvservers, 
            get_running_pvserver_for_case,
            update_pvserver_status,
            get_pvserver_info,
            find_available_port
        )
        
        # Test counting running pvservers
        count = count_running_pvservers()
        print(f"  ✅ Currently running pvservers: {count}")
        
        # Test updating pvserver status
        test_task_id = "test_task_123"
        test_case_path = "/home/ubuntu/cavity_tutorial"
        test_port = find_available_port()
        
        if test_port:
            update_pvserver_status(test_task_id, 'running', test_port, 12345)
            print(f"  ✅ Updated pvserver status for test task")
            
            # Test getting pvserver info
            info = get_pvserver_info(test_task_id)
            if info:
                print(f"  ✅ Retrieved pvserver info: port={info.get('pvserver_port')}, status={info.get('pvserver_status')}")
            else:
                print(f"  ❌ Failed to retrieve pvserver info")
            
            # Test getting running pvserver for case
            running_server = get_running_pvserver_for_case(test_case_path)
            if running_server:
                print(f"  ✅ Found running pvserver for case: {running_server}")
            else:
                print(f"  ℹ️  No running pvserver found for case (expected)")
            
            # Clean up test data
            update_pvserver_status(test_task_id, 'stopped')
            print(f"  ✅ Cleaned up test pvserver status")
        
    except ImportError as e:
        print(f"  ❌ Error importing pvserver_manager: {e}")
    except Exception as e:
        print(f"  ❌ Error in pvserver functions: {e}")
    
    print("✅ PVServer functions test completed\n")

def test_api_endpoints():
    """Test API endpoints with pvserver functionality"""
    print("🧪 Testing API endpoints...")
    
    try:
        # Test health endpoint
        response = requests.get(f"{API_BASE_URL}/api/health")
        if response.status_code == 200:
            print("  ✅ Health endpoint working")
        else:
            print(f"  ❌ Health endpoint failed: {response.status_code}")
            return
        
        # Test submit scenario
        scenario_data = {
            "scenario_description": "Test cavity flow",
            "mesh_complexity": "medium",
            "solver_type": "incompressible"
        }
        
        response = requests.post(f"{API_BASE_URL}/api/submit_scenario", json=scenario_data)
        if response.status_code == 200:
            data = response.json()
            task_id = data.get('task_id')
            print(f"  ✅ Submit scenario endpoint working, task_id: {task_id}")
            
            # Test task status endpoint
            time.sleep(2)  # Give task time to start
            response = requests.get(f"{API_BASE_URL}/api/task_status/{task_id}")
            if response.status_code == 200:
                status_data = response.json()
                print(f"  ✅ Task status endpoint working, status: {status_data.get('status')}")
                
                # Check if pvserver info is included
                if 'pvserver' in status_data:
                    print(f"  ✅ PVServer info included in response")
                else:
                    print(f"  ℹ️  PVServer info not yet available (task may be early stage)")
            else:
                print(f"  ❌ Task status endpoint failed: {response.status_code}")
        else:
            print(f"  ❌ Submit scenario endpoint failed: {response.status_code}")
        
        # Test OpenFOAM command endpoint
        command_data = {
            "command": "blockMesh",
            "case_path": "/home/ubuntu/cavity_tutorial",
            "description": "Test mesh generation"
        }
        
        response = requests.post(f"{API_BASE_URL}/api/run_openfoam_command", json=command_data)
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ OpenFOAM command endpoint working, task_id: {data.get('task_id')}")
        else:
            print(f"  ❌ OpenFOAM command endpoint failed: {response.status_code}")
        
        # Test cleanup endpoint
        response = requests.post(f"{API_BASE_URL}/api/cleanup_pvservers")
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Cleanup endpoint working, cleaned: {len(data.get('cleaned_up', []))}")
        else:
            print(f"  ❌ Cleanup endpoint failed: {response.status_code}")
        
    except requests.exceptions.ConnectionError:
        print("  ❌ Could not connect to API server. Make sure server is running.")
    except Exception as e:
        print(f"  ❌ API test error: {e}")
    
    print("✅ API endpoints test completed\n")

def test_celery_integration():
    """Test Celery integration with pvserver management"""
    print("🧪 Testing Celery integration...")
    
    try:
        # Check if Celery is available
        result = subprocess.run(['celery', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("  ✅ Celery is available")
        else:
            print("  ❌ Celery not available")
            return
        
        # Test importing Celery tasks
        from celery_worker import generate_mesh_task, run_solver_task, run_openfoam_command_task, cleanup_pvservers_task
        print("  ✅ Celery tasks imported successfully")
        
        # Test that tasks are registered
        from celery_worker import celery_app
        registered_tasks = list(celery_app.tasks.keys())
        expected_tasks = [
            'celery_worker.generate_mesh_task',
            'celery_worker.run_solver_task', 
            'celery_worker.run_openfoam_command_task',
            'celery_worker.cleanup_pvservers_task'
        ]
        
        for task in expected_tasks:
            if task in registered_tasks:
                print(f"  ✅ Task {task} registered")
            else:
                print(f"  ❌ Task {task} not registered")
        
    except ImportError as e:
        print(f"  ❌ Error importing Celery tasks: {e}")
    except Exception as e:
        print(f"  ❌ Celery integration error: {e}")
    
    print("✅ Celery integration test completed\n")

def main():
    """Run all tests"""
    print("🚀 FoamAI PVServer Functionality Tests")
    print("=" * 50)
    
    test_database_schema()
    test_port_management()
    test_pvserver_functions()
    test_celery_integration()
    test_api_endpoints()
    
    print("🎉 All tests completed!")
    print("\nNext steps:")
    print("1. Start the API server: uvicorn main:app --host 0.0.0.0 --port 8000")
    print("2. Start Celery worker: celery -A celery_worker worker --loglevel=info")
    print("3. Run validation script: python validate_deployment.py")

if __name__ == "__main__":
    main() 