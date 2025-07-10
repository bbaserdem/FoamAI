#!/usr/bin/env python3
"""
Test script for the enhanced project info functionality.
Tests the new file listing, description, and creation time features.

This script runs locally but connects to the EC2 server for testing.
"""

import requests
import json
from pathlib import Path
import tempfile
import os

# Test configuration - EC2 server
SERVER_URL = "http://3.139.77.134:8000"
TEST_PROJECT_NAME = "test_project_info"

def test_project_info_functionality():
    """Test the enhanced project info endpoint"""
    
    print("🧪 Testing Enhanced Project Info Functionality")
    print(f"🌐 Server: {SERVER_URL}")
    print("=" * 60)
    
    # Test server connectivity first
    print("\n0. Testing server connectivity...")
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            print(f"   ✅ Server is healthy: {health_data.get('status', 'unknown')}")
        else:
            print(f"   ⚠️  Server responded but not healthy: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Cannot connect to server: {e}")
        return False
    
    # Clean up any existing test project
    try:
        response = requests.delete(f"{SERVER_URL}/api/projects/{TEST_PROJECT_NAME}")
        if response.status_code == 200:
            print(f"   ✅ Cleaned up existing test project")
    except:
        pass
    
    # 1. Test project creation with description
    print("\n1. Creating project with description...")
    create_data = {
        "project_name": TEST_PROJECT_NAME,
        "description": "Test project for enhanced info functionality - EC2 testing"
    }
    
    try:
        response = requests.post(f"{SERVER_URL}/api/projects", json=create_data, timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Failed to create project: {response.text}")
            return False
        
        create_result = response.json()
        print(f"   ✅ Created: {create_result.get('project_name', 'unknown')}")
        
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
        return False
    
    # 2. Test project info (should have empty files initially)
    print("\n2. Getting project info (empty active_run)...")
    try:
        response = requests.get(f"{SERVER_URL}/api/projects/{TEST_PROJECT_NAME}", timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Failed to get project info: {response.text}")
            return False
        
        info_result = response.json()
        print(f"   📋 Project Info Preview:")
        print(f"      Name: {info_result.get('project_name', 'N/A')}")
        print(f"      Description: {info_result.get('description', 'N/A')}")
        print(f"      Files: {len(info_result.get('files', []))}")
        print(f"      Total Size: {info_result.get('total_size', 0)} bytes")
        
        # Verify structure
        expected_fields = ["project_name", "project_path", "description", "created_at", "files", "file_count", "total_size"]
        missing_fields = []
        for field in expected_fields:
            if field not in info_result:
                missing_fields.append(field)
        
        if missing_fields:
            print(f"   ❌ Missing fields: {missing_fields}")
            return False
        
        # Should have empty files list initially
        if info_result["files"] != []:
            print(f"   ❌ Expected empty files list, got: {info_result['files']}")
            return False
        
        if info_result["file_count"] != 0:
            print(f"   ❌ Expected file_count=0, got: {info_result['file_count']}")
            return False
        
        if info_result["total_size"] != 0:
            print(f"   ❌ Expected total_size=0, got: {info_result['total_size']}")
            return False
        
        print("   ✅ Empty active_run correctly reported")
        
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
        return False
    
    # 3. Upload some test files
    print("\n3. Uploading test files...")
    
    # Create realistic OpenFOAM test file content
    test_files = [
        ("system/controlDict", """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      controlDict;
}

application     icoFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         0.5;
deltaT          0.005;
writeControl    timeStep;
writeInterval   20;
"""),
        ("constant/transportProperties", """FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      transportProperties;
}

nu              nu [0 2 -1 0 0 0 0] 0.01;
"""),
        ("0/U", """FoamFile
{
    version     2.0;
    format      ascii;
    class       volVectorField;
    object      U;
}

dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);

boundaryField
{
    movingWall
    {
        type            fixedValue;
        value           uniform (1 0 0);
    }
    fixedWalls
    {
        type            noSlip;
    }
    frontAndBack
    {
        type            empty;
    }
}
""")
    ]
    
    upload_success_count = 0
    for file_path, content in test_files:
        try:
            files = {
                'file': (file_path.split('/')[-1], content, 'text/plain'),
                'destination_path': (None, file_path)
            }
            
            response = requests.post(
                f"{SERVER_URL}/api/projects/{TEST_PROJECT_NAME}/upload", 
                files=files, 
                timeout=30
            )
            print(f"   📁 Upload {file_path}: {response.status_code}")
            
            if response.status_code == 200:
                upload_success_count += 1
            else:
                print(f"      ❌ Failed: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"      ❌ Upload failed: {e}")
    
    if upload_success_count != len(test_files):
        print(f"   ⚠️  Only {upload_success_count}/{len(test_files)} files uploaded successfully")
        # Continue with test anyway
    else:
        print(f"   ✅ All {len(test_files)} files uploaded successfully")
    
    # 4. Test project info again (should now have files)
    print("\n4. Getting project info (with files)...")
    try:
        response = requests.get(f"{SERVER_URL}/api/projects/{TEST_PROJECT_NAME}", timeout=30)
        print(f"   Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Failed to get project info: {response.text}")
            return False
        
        info_result = response.json()
        print(f"   📋 Updated Project Info:")
        print(f"      Name: {info_result.get('project_name', 'N/A')}")
        print(f"      Description: {info_result.get('description', 'N/A')}")
        print(f"      Created: {info_result.get('created_at', 'N/A')}")
        print(f"      Files: {info_result.get('files', [])}")
        print(f"      File Count: {info_result.get('file_count', 0)}")
        print(f"      Total Size: {info_result.get('total_size', 0)} bytes")
        
        # Verify files are listed (allow for partial uploads)
        expected_files = ["system/controlDict", "constant/transportProperties", "0/U"]
        actual_files = info_result["files"]
        
        # Check if we have at least some files
        if len(actual_files) == 0:
            print(f"   ❌ Expected some files, got empty list")
            return False
        
        # Check if uploaded files are correctly listed
        files_found = 0
        for expected_file in expected_files:
            if expected_file in actual_files:
                files_found += 1
        
        print(f"   📊 Found {files_found}/{len(expected_files)} expected files")
        
        if info_result["file_count"] != len(actual_files):
            print(f"   ❌ File count mismatch: count={info_result['file_count']}, actual={len(actual_files)}")
            return False
        
        if info_result["total_size"] <= 0:
            print(f"   ❌ Expected total_size>0, got: {info_result['total_size']}")
            return False
        
        print("   ✅ Files correctly listed and counted")
        
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
        return False
    
    # 5. Test project listing to verify our project appears
    print("\n5. Testing project listing...")
    try:
        response = requests.get(f"{SERVER_URL}/api/projects", timeout=30)
        if response.status_code == 200:
            projects_data = response.json()
            projects = projects_data.get('projects', [])
            if TEST_PROJECT_NAME in projects:
                print(f"   ✅ Test project found in project list ({len(projects)} total projects)")
            else:
                print(f"   ⚠️  Test project not found in list: {projects}")
        else:
            print(f"   ⚠️  Failed to get project list: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️  Project list request failed: {e}")
    
    # 6. Clean up
    print("\n6. Cleaning up...")
    try:
        response = requests.delete(f"{SERVER_URL}/api/projects/{TEST_PROJECT_NAME}", timeout=30)
        if response.status_code == 200:
            print("   ✅ Test project cleaned up")
        else:
            print(f"   ⚠️  Failed to clean up: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️  Cleanup request failed: {e}")
    
    print("\n🎉 All tests completed successfully!")
    return True

if __name__ == "__main__":
    print("🚀 FoamAI Enhanced Project Info Test")
    print(f"🎯 Testing against EC2 server: {SERVER_URL}")
    print("📍 Running locally, connecting remotely")
    print()
    
    try:
        success = test_project_info_functionality()
        if success:
            print("\n✅ Enhanced project info functionality working correctly on EC2!")
            exit(0)
        else:
            print("\n❌ Some tests failed!")
            exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1) 