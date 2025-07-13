"""
Integration Test Script for Project API Endpoints (Remote EC2 Testing)

This script tests the /api/projects routes of the FoamAI API running on an EC2 instance.
It reads the EC2_HOST from backend_api/.env or config.py and tests the remote API.

Setup and Execution Steps:
1.  Ensure you have the 'requests' library installed:
    pip install requests

2.  Set the EC2_HOST environment variable in backend_api/.env file:
    EC2_HOST=your-ec2-instance-ip-or-hostname

3.  Ensure your EC2 instance is running the FoamAI API server on port 8000

4.  Run this script from the backend_api directory:
    python test_project_api.py

The script will test the remote API and verify project creation on the EC2 instance.
"""
import requests
import os
import sys
from pathlib import Path
import time

# Import EC2_HOST from config.py
sys.path.insert(0, '.')
from config import EC2_HOST

# --- Configuration ---
API_BASE_URL = f"http://{EC2_HOST}:8000"
# ---

def print_test_header(name):
    """Prints a formatted header for each test case."""
    print("\n" + "="*60)
    print(f"  🧪 EXECUTING TEST: {name}")
    print("="*60)

def print_status(message, success):
    """Prints a formatted success or failure message."""
    if success:
        print(f"  ✅ SUCCESS: {message}")
    else:
        print(f"  ❌ FAILED: {message}")
    return success

def print_configuration():
    """Prints the current test configuration."""
    print("--- Test Configuration ---")
    print(f"EC2_HOST: {EC2_HOST}")
    print(f"API_BASE_URL: {API_BASE_URL}")
    print("-------------------------")

def check_server_health():
    """Checks if the API server is reachable before running tests."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/health", timeout=10)
        response.raise_for_status()
        print("✅ API server is running and healthy on EC2 instance.")
        return True
    except requests.exceptions.RequestException as e:
        print("="*60)
        print("❌ API server is not reachable on EC2 instance.")
        print(f"Error: {e}")
        print("Please ensure:")
        print("1. Your EC2 instance is running")
        print("2. The FastAPI server is running on port 8000")
        print("3. Security groups allow inbound traffic on port 8000")
        print("4. EC2_HOST is correctly set in .env file or environment")
        print("="*60)
        return False

def verify_project_creation_remotely(project_name):
    """
    Verify project creation by making an API call to list projects.
    Since we can't directly access the EC2 filesystem, we use the API to verify.
    """
    try:
        response = requests.get(f"{API_BASE_URL}/api/projects", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return project_name in data.get('projects', [])
        return False
    except requests.exceptions.RequestException:
        return False

def test_list_projects_empty():
    print_test_header("List Projects (Initially Empty)")
    try:
        response = requests.get(f"{API_BASE_URL}/api/projects", timeout=10)
        
        if not print_status("Request returned status 200 OK", response.status_code == 200):
            return False
            
        data = response.json()
        return print_status("Response contains project list", 'projects' in data and 'count' in data)
    except requests.exceptions.RequestException as e:
        print_status(f"Request failed: {e}", False)
        return False

def test_create_project_success():
    print_test_header("Create Project (Success Case)")
    project_name = "remote-test-project"
    
    try:
        response = requests.post(f"{API_BASE_URL}/api/projects", 
                               json={"project_name": project_name}, 
                               timeout=10)

        if not print_status("Request returned status 201 Created", response.status_code == 201):
            print(f"    Response body: {response.text}")
            return False
            
        # Verify project was created by checking if it appears in the project list
        if not print_status("Project appears in remote project list", 
                          verify_project_creation_remotely(project_name)):
            return False

        return True
    except requests.exceptions.RequestException as e:
        print_status(f"Request failed: {e}", False)
        return False

def test_create_project_conflict():
    print_test_header("Create Project (Conflict/Exists Case)")
    project_name = "remote-test-project"  # Same name as before
    
    try:
        response = requests.post(f"{API_BASE_URL}/api/projects", 
                               json={"project_name": project_name}, 
                               timeout=10)
        
        return print_status("Request returned status 409 Conflict", response.status_code == 409)
    except requests.exceptions.RequestException as e:
        print_status(f"Request failed: {e}", False)
        return False

def test_create_project_invalid_name():
    print_test_header("Create Project (Invalid Name Case)")
    project_name = "invalid/name"
    
    try:
        response = requests.post(f"{API_BASE_URL}/api/projects", 
                               json={"project_name": project_name}, 
                               timeout=10)
        
        return print_status("Request returned status 400 Bad Request", response.status_code == 400)
    except requests.exceptions.RequestException as e:
        print_status(f"Request failed: {e}", False)
        return False

def test_list_projects_with_content():
    print_test_header("List Projects (With Content)")
    
    # First, create another project to have multiple items
    try:
        requests.post(f"{API_BASE_URL}/api/projects", 
                     json={"project_name": "remote-project-2"}, 
                     timeout=10)
        
        response = requests.get(f"{API_BASE_URL}/api/projects", timeout=10)
        
        if not print_status("Request returned status 200 OK", response.status_code == 200):
            return False
            
        data = response.json()
        expected_projects = ["remote-test-project", "remote-project-2"]
        
        # Check if both projects exist in the response
        projects_found = all(project in data.get('projects', []) for project in expected_projects)
        return print_status(f"Response contains the expected projects", 
                          projects_found and data.get('count', 0) >= 2)
    except requests.exceptions.RequestException as e:
        print_status(f"Request failed: {e}", False)
        return False

def test_cleanup_projects():
    print_test_header("Cleanup Test Projects")
    
    # Note: This is a cleanup step, not a real test
    # In a real scenario, you might want to implement a DELETE endpoint
    # or manually clean up the projects on the EC2 instance
    
    print("  ℹ️  NOTE: Test projects created on EC2 instance:")
    print("     - remote-test-project")
    print("     - remote-project-2")
    print("  ℹ️  These should be manually cleaned up from the EC2 instance")
    print("     or implement a DELETE endpoint for automated cleanup.")
    
    return True

def run_all_tests():
    """Runs all test cases in sequence and reports the final result."""
    print_configuration()
    
    if not check_server_health():
        return

    results = {
        "list_empty": test_list_projects_empty(),
        "create_success": test_create_project_success(),
        "create_conflict": test_create_project_conflict(),
        "create_invalid": test_create_project_invalid_name(),
        "list_content": test_list_projects_with_content(),
        "cleanup_note": test_cleanup_projects(),
    }
    
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for test_name, result in results.items():
        if test_name == "cleanup_note":
            continue  # Skip cleanup note in pass/fail summary
            
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  - {test_name.replace('_', ' ').title()}: {status}")
        if not result:
            all_passed = False
            
    print("-" * 60)
    if all_passed:
        print("🎉 All tests passed successfully! 🎉")
        print(f"🌐 Remote API testing on {EC2_HOST} completed successfully!")
    else:
        print("🔥 Some tests failed. Please review the output above. 🔥")
    print("="*60)


if __name__ == "__main__":
    run_all_tests() 