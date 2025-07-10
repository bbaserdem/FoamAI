#!/usr/bin/env python3
"""
Test script to diagnose pvserver startup issues
"""

import subprocess
import time
import os
from pathlib import Path

def test_pvserver_startup():
    """Test starting a pvserver and see what happens"""
    
    print("=== PVSERVER STARTUP TEST ===")
    
    # Test case directory
    test_case_dir = Path("/home/ubuntu/foam_projects/test_pvserver_project_1752114145/active_run")
    
    print(f"Test case directory: {test_case_dir}")
    print(f"Directory exists: {test_case_dir.exists()}")
    print(f"Directory is dir: {test_case_dir.is_dir()}")
    
    if test_case_dir.exists():
        print("Directory contents:")
        try:
            for item in test_case_dir.iterdir():
                print(f"  {item}")
        except Exception as e:
            print(f"  Error listing directory: {e}")
    
    # Test pvserver command
    print("\n=== Testing pvserver command ===")
    
    # Check if pvserver is in PATH
    try:
        result = subprocess.run(['which', 'pvserver'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"pvserver found at: {result.stdout.strip()}")
        else:
            print("pvserver not found in PATH")
    except Exception as e:
        print(f"Error checking pvserver path: {e}")
    
    # Try to get pvserver help
    print("\n=== Testing pvserver --help ===")
    try:
        result = subprocess.run(['pvserver', '--help'], capture_output=True, text=True, timeout=10)
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout[:500]}")  # First 500 chars
        print(f"Stderr: {result.stderr[:500]}")  # First 500 chars
    except subprocess.TimeoutExpired:
        print("pvserver --help timed out")
    except FileNotFoundError:
        print("pvserver command not found")
    except Exception as e:
        print(f"Error running pvserver --help: {e}")
    
    # Try to start pvserver with our parameters
    print("\n=== Testing actual pvserver startup ===")
    
    cmd = ['pvserver', '--server-port=11111', '--disable-xdisplay-test']
    print(f"Command: {' '.join(cmd)}")
    print(f"Working directory: {test_case_dir}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(test_case_dir) if test_case_dir.exists() else None
        )
        
        print(f"Started process with PID: {process.pid}")
        
        # Check status after 1 second
        time.sleep(1)
        process.poll()
        
        if process.returncode is None:
            print("✅ Process is still running after 1 second")
            
            # Let it run for a bit more
            time.sleep(2)
            process.poll()
            
            if process.returncode is None:
                print("✅ Process is still running after 3 seconds")
                print("Terminating process...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                    print("✅ Process terminated cleanly")
                except subprocess.TimeoutExpired:
                    print("Process didn't terminate, killing...")
                    process.kill()
            else:
                print(f"❌ Process died after 3 seconds with return code: {process.returncode}")
                stdout, stderr = process.communicate()
                print(f"Stdout: {stdout.decode('utf-8', 'ignore')}")
                print(f"Stderr: {stderr.decode('utf-8', 'ignore')}")
        else:
            print(f"❌ Process died immediately with return code: {process.returncode}")
            stdout, stderr = process.communicate()
            print(f"Stdout: {stdout.decode('utf-8', 'ignore')}")
            print(f"Stderr: {stderr.decode('utf-8', 'ignore')}")
            
    except FileNotFoundError:
        print("❌ pvserver command not found")
    except Exception as e:
        print(f"❌ Error starting pvserver: {e}")

if __name__ == "__main__":
    test_pvserver_startup() 