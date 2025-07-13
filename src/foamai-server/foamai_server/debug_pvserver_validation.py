#!/usr/bin/env python3
"""
Debug script to diagnose pvserver validation issues
Run this on the EC2 server to understand why pvservers are being marked as stopped
"""

import subprocess
import sys
import os
from pathlib import Path

def check_pvserver_process():
    """Check if there are any pvserver processes running"""
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        pvserver_processes = [line for line in result.stdout.split('\n') if 'pvserver' in line.lower()]
        
        print("=== PVServer Processes ===")
        if pvserver_processes:
            for proc in pvserver_processes:
                print(f"  {proc}")
        else:
            print("  No pvserver processes found")
        
        return len(pvserver_processes)
    except Exception as e:
        print(f"Error checking processes: {e}")
        return 0

def check_port_usage():
    """Check what's using the pvserver ports"""
    try:
        result = subprocess.run(['netstat', '-tuln'], capture_output=True, text=True)
        port_lines = [line for line in result.stdout.split('\n') if ':1111' in line]
        
        print("\n=== Port Usage (11111-11116) ===")
        if port_lines:
            for line in port_lines:
                print(f"  {line}")
        else:
            print("  No processes using pvserver ports")
    except Exception as e:
        print(f"Error checking ports: {e}")

def test_process_validation():
    """Test the process validation logic"""
    try:
        # Import from current directory
        from process_validator import validator, validate_pvserver_pid
        import psutil
        
        print("\n=== Testing Process Validation ===")
        
        # Test with current python process (should be running)
        current_pid = os.getpid()
        test_record = {'pid': current_pid, 'port': 11111}
        
        # Check what the current process looks like
        try:
            current_process = psutil.Process(current_pid)
            print(f"Current process name: '{current_process.name()}'")
            print(f"Current process cmdline: {current_process.cmdline()}")
        except Exception as e:
            print(f"Error getting current process info: {e}")
        
        is_running = validator.is_running(test_record)
        print(f"Current Python process (PID {current_pid}): {'RUNNING' if is_running else 'NOT RUNNING'}")
        
        # Test the actual pvserver PIDs from database
        print("\n=== Testing Actual PVServer PIDs ===")
        from database import get_all_project_pvservers
        project_pvservers = get_all_project_pvservers()
        
        for pv in project_pvservers:
            pid = pv.get('pid')
            if pid:
                try:
                    if psutil.pid_exists(pid):
                        process = psutil.Process(pid)
                        print(f"PID {pid}: name='{process.name()}', cmdline={process.cmdline()}")
                        
                        # Test validation
                        is_valid = validate_pvserver_pid(pid, pv.get('port'))
                        print(f"  -> Validation result: {'VALID' if is_valid else 'INVALID'}")
                    else:
                        print(f"PID {pid}: DOES NOT EXIST")
                except Exception as e:
                    print(f"PID {pid}: Error - {e}")
        
        # Test with a non-existent PID
        fake_record = {'pid': 99999, 'port': 11111}
        is_running = validator.is_running(fake_record)
        print(f"Fake process (PID 99999): {'RUNNING' if is_running else 'NOT RUNNING'}")
        
        return True
    except Exception as e:
        print(f"Error testing process validation: {e}")
        return False

def check_database_state():
    """Check the current database state"""
    try:
        from database import get_all_project_pvservers, get_running_pvservers
        
        print("\n=== Database State ===")
        
        # Check project pvservers
        project_pvservers = get_all_project_pvservers()
        print(f"Project PVServers: {len(project_pvservers)}")
        for pv in project_pvservers:
            print(f"  {pv['project_name']}: status={pv['status']}, port={pv['port']}, pid={pv['pid']}")
        
        # Check task pvservers
        task_pvservers = get_running_pvservers()
        print(f"Task PVServers: {len(task_pvservers)}")
        for pv in task_pvservers:
            print(f"  {pv['task_id']}: port={pv.get('pvserver_port')}, pid={pv.get('pvserver_pid')}")
        
        return True
    except Exception as e:
        print(f"Error checking database: {e}")
        return False

def main():
    print("=" * 60)
    print("PVSERVER VALIDATION DIAGNOSTIC")
    print("=" * 60)
    
    # Check if we're in the right directory
    current_dir = Path.cwd()
    print(f"Current directory: {current_dir}")
    
    # Check for running pvserver processes
    num_processes = check_pvserver_process()
    
    # Check port usage
    check_port_usage()
    
    # Test process validation logic
    validation_works = test_process_validation()
    
    # Check database state
    db_works = check_database_state()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"PVServer processes found: {num_processes}")
    print(f"Process validation works: {validation_works}")
    print(f"Database access works: {db_works}")
    
    if num_processes == 0:
        print("\n⚠️  No pvserver processes found - this explains why they're marked as stopped")
    
    if not validation_works:
        print("\n⚠️  Process validation is failing - this could cause issues")

if __name__ == "__main__":
    main() 