#!/usr/bin/env python3
"""
Local test for zombie process handling that doesn't require OpenFOAM case directory
"""

import os
import signal
import time
import subprocess
import sqlite3
from datetime import datetime

from pvserver_manager import (
    setup_signal_handlers,
    get_active_pvserver_summary,
    validate_pvserver_pid,
    cleanup_stale_database_entries,
    _active_pvservers
)

def test_signal_handlers():
    """Test signal handler setup"""
    print("🧪 Testing signal handler setup...")
    
    # Setup signal handlers
    setup_signal_handlers()
    
    # Check if signal handler is registered
    current_handler = signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    signal.signal(signal.SIGCHLD, current_handler)  # Restore
    
    success = current_handler != signal.SIG_DFL
    print(f"✅ Signal handler setup: {'PASSED' if success else 'FAILED'}")
    return success

def test_process_validation():
    """Test process validation functions"""
    print("🧪 Testing process validation...")
    
    # Test invalid PID
    result1 = validate_pvserver_pid(99999)
    
    # Test current process PID (should fail because it's not pvserver)
    result2 = validate_pvserver_pid(os.getpid())
    
    # Test with None
    result3 = validate_pvserver_pid(None)
    
    success = not result1 and not result2 and not result3
    print(f"✅ Process validation: {'PASSED' if success else 'FAILED'}")
    return success

def test_database_cleanup():
    """Test database cleanup functionality"""
    print("🧪 Testing database cleanup...")
    
    try:
        # Create a fake stale entry
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        
        fake_task_id = 'test_cleanup_001'
        fake_pid = 99999
        fake_port = 11115
        
        cursor.execute("""
            INSERT INTO tasks (task_id, status, message, case_path, created_at, 
                              pvserver_status, pvserver_pid, pvserver_port, pvserver_started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fake_task_id, "completed", "Test cleanup task", 
              "/tmp/test", datetime.now(), "running", fake_pid, fake_port, datetime.now()))
        
        conn.commit()
        conn.close()
        
        # Run cleanup
        cleaned_up = cleanup_stale_database_entries()
        
        success = len(cleaned_up) > 0
        print(f"✅ Database cleanup: {'PASSED' if success else 'FAILED'}")
        return success
        
    except Exception as e:
        print(f"❌ Database cleanup failed: {e}")
        return False

def test_tracking_system():
    """Test the internal tracking system"""
    print("🧪 Testing tracking system...")
    
    # Test summary generation
    summary = get_active_pvserver_summary()
    
    expected_keys = ['tracked_processes', 'signal_handler_setup', 'processes']
    has_all_keys = all(key in summary for key in expected_keys)
    
    success = has_all_keys and isinstance(summary['tracked_processes'], int)
    print(f"✅ Tracking system: {'PASSED' if success else 'FAILED'}")
    return success

def test_zombie_scenario_simulation():
    """Simulate a zombie process scenario"""
    print("🧪 Testing zombie scenario simulation...")
    
    # This test simulates what happens when a process dies but database still shows it as running
    # We'll manually add a process to the tracking and then test cleanup
    
    global _active_pvservers
    
    # Add a fake process to tracking
    fake_pid = 99998
    _active_pvservers[fake_pid] = {
        'task_id': 'test_zombie_001',
        'port': 11114,
        'case_path': '/tmp/test',
        'started': datetime.now()
    }
    
    # Get summary before cleanup
    summary_before = get_active_pvserver_summary()
    
    # The process doesn't actually exist, so validation should fail
    is_valid = validate_pvserver_pid(fake_pid)
    
    # Remove the fake process (simulating cleanup)
    if fake_pid in _active_pvservers:
        del _active_pvservers[fake_pid]
    
    # Get summary after cleanup
    summary_after = get_active_pvserver_summary()
    
    success = not is_valid and summary_before['tracked_processes'] > summary_after['tracked_processes']
    print(f"✅ Zombie scenario simulation: {'PASSED' if success else 'FAILED'}")
    return success

def run_local_tests():
    """Run all local tests"""
    print("🧪 Running local zombie process handling tests...")
    print("=" * 50)
    
    tests = [
        ("Signal Handlers", test_signal_handlers),
        ("Process Validation", test_process_validation),
        ("Database Cleanup", test_database_cleanup),
        ("Tracking System", test_tracking_system),
        ("Zombie Scenario", test_zombie_scenario_simulation)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("🏁 Local Test Results:")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📊 Overall: {passed}/{len(results)} tests passed")
    
    # Final summary
    summary = get_active_pvserver_summary()
    print(f"\n📊 Final system state: {summary}")
    
    return passed == len(results)

if __name__ == "__main__":
    success = run_local_tests()
    exit(0 if success else 1) 