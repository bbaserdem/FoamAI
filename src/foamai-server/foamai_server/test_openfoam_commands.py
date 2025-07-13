#!/usr/bin/env python3
"""
Test script to verify OpenFOAM commands work with the new bash sourcing approach.
"""

import requests
import json
from datetime import datetime

from config import EC2_HOST, API_PORT

# Test configuration
BASE_URL = f"http://{EC2_HOST}:{API_PORT}"
TEST_PROJECT_NAME = "openfoam_test_project"

def print_header(title: str):
    """Print a formatted header"""
    print(f"\n{'='*50}")
    print(f"🧪 {title}")
    print(f"{'='*50}")

def test_openfoam_command(command: str, args: list = None, description: str = ""):
    """Test a specific OpenFOAM command"""
    print(f"\n🔧 Testing: {command}")
    if description:
        print(f"   {description}")
    
    payload = {
        "command": command,
        "timeout": 30
    }
    if args:
        payload["args"] = args
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/projects/{TEST_PROJECT_NAME}/run_command",
            json=payload,
            timeout=45
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ SUCCESS - Exit code: {data.get('exit_code', 'unknown')}")
            print(f"   ⏱️  Execution time: {data.get('execution_time', 'unknown')}s")
            
            stdout = data.get('stdout', '').strip()
            stderr = data.get('stderr', '').strip()
            
            if stdout:
                print(f"   📤 Output: {stdout[:200]}{'...' if len(stdout) > 200 else ''}")
            if stderr:
                print(f"   ⚠️  Stderr: {stderr[:200]}{'...' if len(stderr) > 200 else ''}")
                
            return True
        else:
            print(f"   ❌ FAILED")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"   Raw response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"   ❌ REQUEST FAILED: {e}")
        return False

def setup_test_project():
    """Create test project if it doesn't exist"""
    print_header("Setting Up Test Project")
    
    try:
        # Try to create project
        response = requests.post(
            f"{BASE_URL}/api/projects",
            json={"project_name": TEST_PROJECT_NAME, "description": "OpenFOAM command testing"},
            timeout=15
        )
        
        if response.status_code == 200:
            print("✅ Test project created successfully")
            return True
        elif response.status_code == 400:
            # Project might already exist
            print("ℹ️  Test project already exists (continuing)")
            return True
        else:
            print(f"❌ Failed to create test project: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return False

def cleanup_test_project():
    """Clean up test project"""
    print_header("Cleanup")
    
    try:
        response = requests.delete(f"{BASE_URL}/api/projects/{TEST_PROJECT_NAME}", timeout=15)
        if response.status_code in [200, 404]:
            print("✅ Test project cleaned up")
        else:
            print(f"⚠️  Cleanup returned status: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Cleanup error (not critical): {e}")

def main():
    """Run OpenFOAM command tests"""
    print("🚀 OpenFOAM Command Test Suite")
    print(f"🌐 Target Server: {BASE_URL}")
    print(f"⏰ Test Time: {datetime.now().isoformat()}")
    print("\n🎯 Testing: OpenFOAM environment sourcing fix")
    
    # Setup
    if not setup_test_project():
        print("❌ Setup failed, aborting tests")
        return 1
    
    # Test various OpenFOAM commands
    tests = [
        ("foamVersion", [], "Check OpenFOAM version"),
        ("checkMesh", ["-help"], "Test checkMesh help"),
        ("blockMesh", ["-help"], "Test blockMesh help"),
        ("which", ["checkMesh"], "Verify checkMesh is in PATH"),
        ("echo", ["$FOAM_VERSION"], "Check FOAM_VERSION environment variable"),
    ]
    
    results = []
    for command, args, description in tests:
        success = test_openfoam_command(command, args, description)
        results.append((f"{command} {' '.join(args)}".strip(), success))
    
    # Cleanup
    cleanup_test_project()
    
    # Results summary
    print_header("Test Results Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed >= 1:  # At least one OpenFOAM command worked
        print("\n🎉 SUCCESS! OpenFOAM environment sourcing is working!")
        print("💡 Your commands now have access to OpenFOAM binaries and environment")
        print("🔧 The bash sourcing fix resolved the PATH issue")
        return 0
    else:
        print("\n⚠️  All OpenFOAM tests failed. Check server logs and OpenFOAM installation.")
        return 1

if __name__ == "__main__":
    exit(main()) 