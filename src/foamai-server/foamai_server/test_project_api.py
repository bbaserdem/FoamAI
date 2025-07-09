"""
Integration Test Script for Project API Endpoints

This script tests the /api/projects routes of the FoamAI API.
It is intended to be run from the command line while the FastAPI server is running.

Setup and Execution Steps:
1.  Ensure you have the 'requests' library installed:
    pip install requests

2.  Open two terminal windows in the 'backend_api' directory.

3.  In the first terminal, set the FOAM_RUN environment variable to the
    temporary test directory that this script uses. Then, start the API server:

    export FOAM_RUN=$(pwd)/test_foam_run
    uvicorn main:app --reload

4.  In the second terminal, run this script:

    python test_project_api.py

The script will print the results of each test case and automatically clean up
the 'test_foam_run' directory it creates.
"""
import requests
import os
import shutil
from pathlib import Path
import time

# --- Configuration ---
API_BASE_URL = "http://127.0.0.1:8000"
TEST_DIR_NAME = "test_foam_run"
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

def setup_test_environment():
    """Creates the temporary test directory for FOAM_RUN."""
    print("--- Setting up test environment ---")
    test_path = Path(TEST_DIR_NAME)
    if test_path.exists():
        shutil.rmtree(test_path)
    test_path.mkdir()
    print(f"Created temporary directory: {test_path.resolve()}")
    print("-----------------------------------")

def cleanup_test_environment():
    """Removes the temporary test directory."""
    print("\n--- Cleaning up test environment ---")
    test_path = Path(TEST_DIR_NAME)
    if test_path.exists():
        shutil.rmtree(test_path)
        print(f"Removed temporary directory: {test_path.resolve()}")
    print("------------------------------------")

def check_server_health():
    """Checks if the API server is reachable before running tests."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/health")
        response.raise_for_status()
        print("API server is running and healthy.")
        return True
    except requests.exceptions.RequestException as e:
        print("="*60)
        print("API server is not reachable.")
        print(f"Error: {e}")
        print("Please ensure the FastAPI server is running before executing this script.")
        print_instructions()
        print("="*60)
        return False

def print_instructions():
    print("\nTo run the server:")
    print("  export FOAM_RUN=$(pwd)/test_foam_run")
    print("  uvicorn main:app --reload")

def test_list_projects_empty():
    print_test_header("List Projects (Initially Empty)")
    response = requests.get(f"{API_BASE_URL}/api/projects")
    
    if not print_status("Request returned status 200 OK", response.status_code == 200):
        return False
        
    data = response.json()
    return print_status("Response contains an empty list of projects", data['projects'] == [] and data['count'] == 0)

def test_create_project_success():
    print_test_header("Create Project (Success Case)")
    project_name = "my-first-project"
    response = requests.post(f"{API_BASE_URL}/api/projects", json={"project_name": project_name})

    if not print_status("Request returned status 201 Created", response.status_code == 201):
        print(f"    Response body: {response.text}")
        return False
        
    if not print_status("Directory was created on the filesystem", (Path(TEST_DIR_NAME) / project_name).is_dir()):
        return False

    return True

def test_create_project_conflict():
    print_test_header("Create Project (Conflict/Exists Case)")
    project_name = "my-first-project" # Same name as before
    response = requests.post(f"{API_BASE_URL}/api/projects", json={"project_name": project_name})
    
    return print_status("Request returned status 409 Conflict", response.status_code == 409)

def test_create_project_invalid_name():
    print_test_header("Create Project (Invalid Name Case)")
    project_name = "invalid/name"
    response = requests.post(f"{API_BASE_URL}/api/projects", json={"project_name": project_name})
    
    return print_status("Request returned status 400 Bad Request", response.status_code == 400)

def test_list_projects_with_content():
    print_test_header("List Projects (With Content)")
    # First, create another project to have multiple items
    requests.post(f"{API_BASE_URL}/api/projects", json={"project_name": "project.2"})
    
    response = requests.get(f"{API_BASE_URL}/api/projects")
    
    if not print_status("Request returned status 200 OK", response.status_code == 200):
        return False
        
    data = response.json()
    expected_projects = ["my-first-project", "project.2"]
    
    # Sort both lists to ensure comparison is order-independent
    return print_status(f"Response contains the correct projects: {sorted(expected_projects)}", sorted(data['projects']) == sorted(expected_projects) and data['count'] == 2)


def run_all_tests():
    """Runs all test cases in sequence and reports the final result."""
    if not check_server_health():
        return

    setup_test_environment()
    
    results = {
        "list_empty": test_list_projects_empty(),
        "create_success": test_create_project_success(),
        "create_conflict": test_create_project_conflict(),
        "create_invalid": test_create_project_invalid_name(),
        "list_content": test_list_projects_with_content(),
    }
    
    cleanup_test_environment()
    
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  - {test_name.replace('_', ' ').title()}: {status}")
        if not result:
            all_passed = False
            
    print("-" * 60)
    if all_passed:
        print("🎉 All tests passed successfully! 🎉")
    else:
        print("🔥 Some tests failed. Please review the output above. 🔥")
    print("="*60)


if __name__ == "__main__":
    run_all_tests() 