#!/usr/bin/env python3
"""
Debug script to test pvserver functionality on EC2
"""

import subprocess
import os
import socket
import sys
from pathlib import Path

def check_paraview_installation():
    """Check if ParaView and pvserver are available"""
    print("🔍 Checking ParaView installation...")
    
    # Check if pvserver is in PATH
    try:
        result = subprocess.run(['which', 'pvserver'], capture_output=True, text=True)
        if result.returncode == 0:
            pvserver_path = result.stdout.strip()
            print(f"✅ pvserver found at: {pvserver_path}")
        else:
            print("❌ pvserver not found in PATH")
            return False
    except Exception as e:
        print(f"❌ Error checking pvserver: {e}")
        return False
    
    # Check pvserver version
    try:
        result = subprocess.run(['pvserver', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ pvserver version: {result.stdout.strip()}")
        else:
            print(f"❌ pvserver --version failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error checking pvserver version: {e}")
        return False
    
    return True

def check_case_directory():
    """Check if the case directory exists"""
    print("\n🔍 Checking case directory...")
    
    case_path = Path('/home/ubuntu/cavity_tutorial')
    if case_path.exists():
        print(f"✅ Case directory exists: {case_path}")
        
        # List contents
        contents = list(case_path.iterdir())
        print(f"📁 Contents: {[f.name for f in contents[:10]]}")  # Show first 10 items
        
        # Check for .foam file
        foam_files = list(case_path.glob('*.foam'))
        if foam_files:
            print(f"✅ Found .foam files: {[f.name for f in foam_files]}")
        else:
            print("⚠️  No .foam files found")
        
        return True
    else:
        print(f"❌ Case directory does not exist: {case_path}")
        return False

def test_port_availability():
    """Test if port 11111 is available"""
    print("\n🔍 Testing port availability...")
    
    port = 11111
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            print(f"✅ Port {port} is available")
            return True
    except socket.error as e:
        print(f"❌ Port {port} is not available: {e}")
        return False

def test_pvserver_startup():
    """Test starting pvserver manually"""
    print("\n🔍 Testing pvserver startup...")
    
    case_path = '/home/ubuntu/cavity_tutorial'
    port = 11111
    
    # Construct command (without --data parameter as it's not supported)
    cmd = [
        'pvserver',
        f'--server-port={port}',
        '--disable-xdisplay-test'
    ]
    
    print(f"📋 Command: {' '.join(cmd)}")
    
    try:
        # Start process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=case_path
        )
        
        # Give it time to start
        import time
        time.sleep(2)
        
        # Check if it's still running
        if process.poll() is None:
            print("✅ pvserver started successfully")
            
            # Test connection
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(5)
                    s.connect(('localhost', port))
                    print(f"✅ Connection to port {port} successful")
            except Exception as e:
                print(f"❌ Connection test failed: {e}")
            
            # Stop the process
            process.terminate()
            process.wait()
            print("✅ pvserver stopped")
            
            return True
        else:
            # Process died
            stdout, stderr = process.communicate()
            print(f"❌ pvserver failed to start")
            print(f"📤 stdout: {stdout.decode()}")
            print(f"📤 stderr: {stderr.decode()}")
            return False
            
    except Exception as e:
        print(f"❌ Error starting pvserver: {e}")
        return False

def test_alternative_pvserver():
    """Test pvserver without --data parameter"""
    print("\n🔍 Testing alternative pvserver startup...")
    
    port = 11111
    
    # Try without --data parameter
    cmd = [
        'pvserver',
        f'--server-port={port}',
        '--disable-xdisplay-test'
    ]
    
    print(f"📋 Command: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        import time
        time.sleep(2)
        
        if process.poll() is None:
            print("✅ Alternative pvserver startup successful")
            process.terminate()
            process.wait()
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Alternative pvserver failed")
            print(f"📤 stdout: {stdout.decode()}")
            print(f"📤 stderr: {stderr.decode()}")
            return False
            
    except Exception as e:
        print(f"❌ Error with alternative pvserver: {e}")
        return False

def main():
    """Run all debug tests"""
    print("🚀 PVServer Debug Script")
    print("=" * 40)
    
    tests = [
        ("ParaView Installation", check_paraview_installation),
        ("Case Directory", check_case_directory),
        ("Port Availability", test_port_availability),
        ("PVServer Startup", test_pvserver_startup),
        ("Alternative PVServer", test_alternative_pvserver),
    ]
    
    passed = 0
    for test_name, test_func in tests:
        print(f"\n{'='*10} {test_name} {'='*10}")
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print(f"\n🏁 Results: {passed}/{len(tests)} tests passed")
    
    if passed < len(tests):
        print("\n💡 Suggestions:")
        if passed == 0:
            print("1. Install ParaView: sudo apt install -y paraview")
        print("2. Check if display is available: echo $DISPLAY")
        print("3. Try running pvserver manually: pvserver --server-port=11111 --disable-xdisplay-test")

if __name__ == "__main__":
    main() 