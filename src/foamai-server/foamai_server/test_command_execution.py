#!/usr/bin/env python3
"""
Test script for command execution functionality.
Tests the new /api/projects/{project_name}/run_command endpoint.
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://3.139.77.134:8000"
PROJECT_NAME = "test_command_project"

def make_request(method: str, endpoint: str, data: Dict[Any, Any] = None, files: Dict[str, Any] = None) -> Dict[Any, Any]:
    """Make HTTP request with error handling"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            if files:
                response = requests.post(url, files=files, timeout=30)
            else:
                response = requests.post(url, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        print(f"{method} {endpoint}")
        print(f"Status: {response.status_code}")
        
        if response.headers.get('content-type', '').startswith('application/json'):
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            return result
        else:
            print(f"Response: {response.text}")
            return {"status_code": response.status_code, "text": response.text}
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return {"error": str(e)}

def test_command_execution():
    """Test the complete command execution workflow"""
    print("=" * 60)
    print("TESTING COMMAND EXECUTION FUNCTIONALITY")
    print("=" * 60)
    
    # 1. Create test project
    print("\n1. Creating test project...")
    result = make_request("POST", "/api/projects", {
        "project_name": PROJECT_NAME,
        "description": "Test project for command execution"
    })
    
    if result.get("created"):
        print("✓ Project created successfully")
    else:
        print("⚠ Project might already exist, continuing...")
    
    # 2. Upload a simple blockMeshDict file
    print("\n2. Creating and uploading blockMeshDict...")
    
    # Create a simple blockMeshDict content
    block_mesh_dict = """/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  8
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

convertToMeters 0.1;

vertices
(
    (0 0 0)
    (1 0 0)
    (1 1 0)
    (0 1 0)
    (0 0 0.1)
    (1 0 0.1)
    (1 1 0.1)
    (0 1 0.1)
);

blocks
(
    hex (0 1 2 3 4 5 6 7) (20 20 1) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
    movingWall
    {
        type wall;
        faces
        (
            (3 7 6 2)
        );
    }
    fixedWalls
    {
        type wall;
        faces
        (
            (0 4 7 3)
            (2 6 5 1)
            (1 5 4 0)
        );
    }
    frontAndBack
    {
        type empty;
        faces
        (
            (0 3 2 1)
            (4 5 6 7)
        );
    }
);

mergePatchPairs
(
);

// ************************************************************************* //
"""
    
    # Create system directory structure
    system_dir_content = """/*--------------------------------*- C++ -*----------------------------------*\\
  =========                 |
  \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\\\    /   O peration     | Website:  https://openfoam.org
    \\\\  /    A nd           | Version:  8
     \\\\/     M anipulation  |
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      controlDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

application     icoFoam;

startFrom       startTime;

startTime       0;

stopAt          endTime;

endTime         0.5;

deltaT          0.005;

writeControl    timeStep;

writeInterval   20;

purgeWrite      0;

writeFormat     ascii;

writePrecision  6;

writeCompression off;

timeFormat      general;

timePrecision   6;

runTimeModifiable true;

// ************************************************************************* //
"""
    
    # Upload blockMeshDict
    files = {
        'file': ('blockMeshDict', block_mesh_dict, 'text/plain')
    }
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/upload", files=files)
    
    if result.get("filename") == "blockMeshDict":
        print("✓ blockMeshDict uploaded successfully")
    else:
        print("✗ Failed to upload blockMeshDict")
        return
    
    # Upload controlDict
    files = {
        'file': ('controlDict', system_dir_content, 'text/plain')
    }
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/upload", files=files)
    
    if result.get("filename") == "controlDict":
        print("✓ controlDict uploaded successfully")
    else:
        print("✗ Failed to upload controlDict")
        return
    
    # 3. Test blockMesh command
    print("\n3. Testing blockMesh command...")
    
    # First, let's try a simple command to test the endpoint
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/run_command", {
        "command": "ls",
        "args": ["-la"],
        "working_directory": "active_run"
    })
    
    if result.get("success"):
        print("✓ Basic command execution works")
        print(f"  Directory contents:\n{result.get('stdout', '')}")
    else:
        print("✗ Basic command execution failed")
        print(f"  Error: {result.get('stderr', '')}")
    
    # Create system directory and move files
    print("\n4. Setting up OpenFOAM case structure...")
    
    # Create system directory
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/run_command", {
        "command": "mkdir",
        "args": ["-p", "system"],
        "working_directory": "active_run"
    })
    
    # Move blockMeshDict to system directory
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/run_command", {
        "command": "mv",
        "args": ["blockMeshDict", "system/blockMeshDict"],
        "working_directory": "active_run"
    })
    
    # Move controlDict to system directory
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/run_command", {
        "command": "mv",
        "args": ["controlDict", "system/controlDict"],
        "working_directory": "active_run"
    })
    
    # Verify structure
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/run_command", {
        "command": "find",
        "args": [".", "-type", "f"],
        "working_directory": "active_run"
    })
    
    if result.get("success"):
        print("✓ Case structure created")
        print(f"  Files found:\n{result.get('stdout', '')}")
    
    # 5. Test blockMesh command
    print("\n5. Testing blockMesh command...")
    
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/run_command", {
        "command": "blockMesh",
        "args": ["-case", "."],
        "working_directory": "active_run",
        "timeout": 60
    })
    
    if result.get("success"):
        print("✓ blockMesh executed successfully")
        print(f"  Execution time: {result.get('execution_time', 0)} seconds")
        print(f"  Output preview: {result.get('stdout', '')[:200]}...")
    else:
        print("✗ blockMesh execution failed")
        print(f"  Exit code: {result.get('exit_code', 'unknown')}")
        print(f"  Error: {result.get('stderr', '')}")
    
    # 6. Test checkMesh command
    print("\n6. Testing checkMesh command...")
    
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/run_command", {
        "command": "checkMesh",
        "args": ["-case", "."],
        "working_directory": "active_run",
        "timeout": 30
    })
    
    if result.get("success"):
        print("✓ checkMesh executed successfully")
        print(f"  Execution time: {result.get('execution_time', 0)} seconds")
        print(f"  Output preview: {result.get('stdout', '')[:200]}...")
    else:
        print("✗ checkMesh execution failed")
        print(f"  Exit code: {result.get('exit_code', 'unknown')}")
        print(f"  Error: {result.get('stderr', '')}")
    
    # 7. Test command with timeout
    print("\n7. Testing command timeout...")
    
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/run_command", {
        "command": "sleep",
        "args": ["10"],
        "working_directory": "active_run",
        "timeout": 5
    })
    
    if not result.get("success") and "timed out" in result.get("error", "").lower():
        print("✓ Command timeout works correctly")
    else:
        print("⚠ Command timeout test inconclusive")
    
    # 8. Test invalid command
    print("\n8. Testing invalid command handling...")
    
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/run_command", {
        "command": "nonexistent_command",
        "args": [],
        "working_directory": "active_run"
    })
    
    if not result.get("success"):
        print("✓ Invalid command handled correctly")
        print(f"  Error: {result.get('error', result.get('stderr', ''))}")
    else:
        print("⚠ Invalid command test inconclusive")
    
    # 9. List final project contents
    print("\n9. Final project contents...")
    
    result = make_request("POST", f"/api/projects/{PROJECT_NAME}/run_command", {
        "command": "find",
        "args": [".", "-type", "f", "-exec", "ls", "-la", "{}", ";"],
        "working_directory": "active_run"
    })
    
    if result.get("success"):
        print("✓ Final project structure:")
        print(f"{result.get('stdout', '')}")
    
    print("\n" + "=" * 60)
    print("COMMAND EXECUTION TESTS COMPLETED")
    print("=" * 60)

if __name__ == "__main__":
    test_command_execution() 