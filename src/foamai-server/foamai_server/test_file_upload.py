#!/usr/bin/env python3
"""
Test script for the file upload endpoint.

This script demonstrates how to use the new /api/projects/{project_name}/upload endpoint
to upload files to a project on the FoamAI server.
"""

import requests
import sys
import os
from pathlib import Path

# Import EC2_HOST from config.py
sys.path.insert(0, '.')
from config import EC2_HOST

API_BASE_URL = f"http://{EC2_HOST}:8000"

def test_file_upload():
    """Test the file upload endpoint with various scenarios."""
    
    print("=" * 60)
    print("  🧪 TESTING FILE UPLOAD ENDPOINT")
    print("=" * 60)
    print(f"API URL: {API_BASE_URL}")
    print()
    
    # Test 1: Create a test project first
    print("1. Creating test project...")
    try:
        response = requests.post(f"{API_BASE_URL}/api/projects", 
                               json={"project_name": "upload-test-project"})
        if response.status_code in [200, 201, 409]:  # 200 = success, 201 = created, 409 = already exists
            print("   ✅ Test project ready")
        else:
            print(f"   ❌ Failed to create project: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Error creating project: {e}")
        return
    
    # Test 2: Upload a simple text file
    print("\n2. Uploading a simple text file...")
    try:
        # Create a test file content
        test_content = """# OpenFOAM Configuration File
# This is a test file uploaded via the API

application     icoFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         0.5;
deltaT          0.005;
writeControl    timeStep;
writeInterval   20;
"""
        
        # Prepare the multipart data
        files = {
            'file': ('controlDict', test_content.encode('utf-8'), 'text/plain')
        }
        data = {
            'destination_path': 'system/controlDict'
        }
        
        response = requests.post(f"{API_BASE_URL}/api/projects/upload-test-project/upload",
                               files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print("   ✅ File uploaded successfully!")
            print(f"      File path: {result['file_path']}")
            print(f"      File size: {result['file_size']} bytes")
            print(f"      Upload time: {result['upload_time']}")
            print(f"      Message: {result['message']}")
        else:
            print(f"   ❌ Upload failed: {response.status_code}")
            print(f"      Response: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Error uploading file: {e}")
    
    # Test 3: Upload to a nested directory
    print("\n3. Uploading to nested directory...")
    try:
        mesh_content = """# OpenFOAM blockMeshDict
# Test mesh configuration

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
"""
        
        files = {
            'file': ('blockMeshDict', mesh_content.encode('utf-8'), 'text/plain')
        }
        data = {
            'destination_path': 'system/mesh/blockMeshDict'
        }
        
        response = requests.post(f"{API_BASE_URL}/api/projects/upload-test-project/upload",
                               files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print("   ✅ Nested directory upload successful!")
            print(f"      File path: {result['file_path']}")
            print(f"      File size: {result['file_size']} bytes")
            print(f"      Upload time: {result['upload_time']}")
        else:
            print(f"   ❌ Upload failed: {response.status_code}")
            print(f"      Response: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Error uploading to nested directory: {e}")
    
    # Test 4: Test overwrite behavior
    print("\n4. Testing file overwrite...")
    try:
        updated_content = """# OpenFOAM Configuration File - UPDATED
# This file has been updated to test overwrite functionality

application     icoFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         1.0;  // Changed from 0.5 to 1.0
deltaT          0.005;
writeControl    timeStep;
writeInterval   20;

// Added a comment to show this is the updated version
"""
        
        files = {
            'file': ('controlDict', updated_content.encode('utf-8'), 'text/plain')
        }
        data = {
            'destination_path': 'system/controlDict'  # Same path as before
        }
        
        response = requests.post(f"{API_BASE_URL}/api/projects/upload-test-project/upload",
                               files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print("   ✅ File overwrite successful!")
            print(f"      File path: {result['file_path']}")
            print(f"      New file size: {result['file_size']} bytes")
            print(f"      Upload time: {result['upload_time']}")
        else:
            print(f"   ❌ Overwrite failed: {response.status_code}")
            print(f"      Response: {response.text}")
            
    except Exception as e:
        print(f"   ❌ Error testing overwrite: {e}")
    
    print("\n" + "=" * 60)
    print("  📁 TEST COMPLETE")
    print("=" * 60)
    print("Files uploaded to project 'upload-test-project':")
    print("  - active_run/system/controlDict (overwritten)")
    print("  - active_run/system/mesh/blockMeshDict (new)")
    print()
    print("You can manually verify these files exist on your EC2 instance.")
    print("=" * 60)

def show_usage():
    """Show usage examples for the file upload endpoint."""
    print("=" * 60)
    print("  📖 FILE UPLOAD ENDPOINT USAGE")
    print("=" * 60)
    print()
    print("Endpoint: POST /api/projects/{project_name}/upload")
    print("Content-Type: multipart/form-data")
    print()
    print("Form fields:")
    print("  - file: (binary file data)")
    print("  - destination_path: relative path within project's active_run directory")
    print()
    print("Example using curl:")
    print("  curl -X POST \\")
    print("    -F 'file=@my_config.txt' \\")
    print("    -F 'destination_path=system/controlDict' \\")
    print(f"    {API_BASE_URL}/api/projects/my-project/upload")
    print("    # Saves to: my-project/active_run/system/controlDict")
    print()
    print("Example using Python requests:")
    print("  files = {'file': open('config.txt', 'rb')}")
    print("  data = {'destination_path': 'system/controlDict'}")
    print("  response = requests.post(url, files=files, data=data)")
    print("  # Saves to: my-project/active_run/system/controlDict")
    print()
    print("Features:")
    print("  ✅ Creates directories automatically")
    print("  ✅ Allows file overwriting")
    print("  ✅ Supports up to 300MB files")
    print("  ✅ Works with any file type")
    print("  ✅ Returns detailed upload information")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--usage":
        show_usage()
    else:
        test_file_upload() 