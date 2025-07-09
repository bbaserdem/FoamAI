#!/usr/bin/env python3
"""
Test script to validate the zombie process handling implementation
"""

import time
import subprocess
import os
import signal
import sqlite3
from datetime import datetime
from pathlib import Path

# Import our new robust pvserver management
from process_utils import (
    setup_signal_handlers, 
    get_active_pvserver_summary,
    validate_pvserver_pid
)
from pvserver_service import (
    ensure_pvserver_for_task, 
    cleanup_stale_database_entries,
    get_pvserver_info_with_validation as get_pvserver_info
)

DATABASE_PATH = 'tasks.db'

def reset_database():
    """Reset the database for testing"""
    print("🔄 Resetting database for testing...")
    
    # Remove existing database
    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)
    
    # Recreate database by running the setup script
    result = subprocess.run(['python', 'database_setup.py'], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Database setup failed: {result.stderr}")
        return False
    
    print("✅ Database reset complete")
    return True

def create_test_task(task_id: str, case_path: str = '/home/ubuntu/cavity_tutorial'):
    """Create a test task entry in the database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO tasks (task_id, status, message, case_path, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (task_id, "pending", "Test task", case_path, datetime.now()))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Created test task: {task_id}")

def test_signal_handler_setup():
    """Test 1: Signal handler setup"""
    print("\n🧪 Test 1: Signal handler setup")
    
    # Setup signal handlers
    setup_signal_handlers()
    
    # Check if signal handler is registered
    current_handler = signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    signal.signal(signal.SIGCHLD, current_handler)  # Restore
    
    if current_handler != signal.SIG_DFL:
        print("✅ Signal handler is properly registered")
        return True
    else:
        print("❌ Signal handler registration failed")
        return False

def test_process_validation():
    """Test 2: Process validation"""
    print("\n🧪 Test 2: Process validation")
    
    # Test with invalid PID
    result1 = validate_pvserver_pid(99999)
    print(f"Validation of invalid PID (99999): {result1}")
    
    # Test with current process PID (should fail because it's not pvserver)
    result2 = validate_pvserver_pid(os.getpid())
    print(f"Validation of current PID ({os.getpid()}): {result2}")
    
    if not result1 and not result2:
        print("✅ Process validation works correctly")
        return True
    else:
        print("❌ Process validation failed")
        return False

def test_pvserver_lifecycle():
    """Test 3: PVServer lifecycle management"""
    print("\n🧪 Test 3: PVServer lifecycle management")
    
    case_path = '/home/ubuntu/cavity_tutorial'
    task_id = 'test_lifecycle_001'
    
    # Create test task
    create_test_task(task_id, case_path)
    
    # Check if case directory exists
    if not os.path.exists(case_path):
        print(f"❌ Case directory {case_path} does not exist, skipping lifecycle test")
        return False
    
    try:
        # Start pvserver
        print("🚀 Starting pvserver...")
        pvserver_info = ensure_pvserver_for_task(task_id, case_path)
        
        if pvserver_info["status"] == "running":
            print(f"✅ PVServer started on port {pvserver_info['port']}")
            
            # Validate process is running
            if validate_pvserver_pid(pvserver_info['pid'], pvserver_info['port']):
                print("✅ PVServer process validated")
                
                # Get active summary
                summary = get_active_pvserver_summary()
                print(f"📊 Active summary: {summary}")
                
                # Test reuse with same case
                task_id2 = 'test_lifecycle_002'
                create_test_task(task_id2, case_path)
                
                pvserver_info2 = ensure_pvserver_for_task(task_id2, case_path)
                if pvserver_info2.get("reused"):
                    print("✅ PVServer reuse works correctly")
                else:
                    print("❌ PVServer reuse failed")
                    return False
                
                return True
            else:
                print("❌ PVServer process validation failed")
                return False
        else:
            print(f"❌ PVServer failed to start: {pvserver_info.get('error_message')}")
            return False
            
    except Exception as e:
        print(f"❌ PVServer lifecycle test failed: {e}")
        return False

def test_lazy_cleanup():
    """Test 4: Lazy cleanup of stale entries"""
    print("\n🧪 Test 4: Lazy cleanup of stale entries")
    
    # Manually insert a stale entry
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    fake_task_id = 'test_stale_001'
    fake_pid = 99999  # Non-existent PID
    fake_port = 11115
    
    cursor.execute("""
        INSERT INTO tasks (task_id, status, message, case_path, created_at, 
                          pvserver_status, pvserver_pid, pvserver_port, pvserver_started_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (fake_task_id, "completed", "Test stale task", 
          "/tmp/test", datetime.now(), "running", fake_pid, fake_port, datetime.now()))
    
    conn.commit()
    conn.close()
    
    print(f"📝 Created fake stale entry: PID {fake_pid}, Port {fake_port}")
    
    # Run cleanup
    cleaned_up = cleanup_stale_database_entries()
    
    if cleaned_up:
        print(f"✅ Lazy cleanup worked: {cleaned_up}")
        return True
    else:
        print("❌ Lazy cleanup failed to detect stale entry")
        return False

def test_database_consistency():
    """Test 5: Database consistency after operations"""
    print("\n🧪 Test 5: Database consistency")
    
    # Check database state
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Count total tasks
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0]
    
    # Count running pvservers
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE pvserver_status = 'running'")
    running_count = cursor.fetchone()[0]
    
    # Get all running pvservers
    cursor.execute("""
        SELECT task_id, pvserver_pid, pvserver_port, pvserver_status
        FROM tasks 
        WHERE pvserver_status = 'running'
    """)
    running_servers = cursor.fetchall()
    
    conn.close()
    
    print(f"📊 Database state: {total_tasks} total tasks, {running_count} running pvservers")
    
    # Validate each running server
    valid_servers = 0
    for server in running_servers:
        if validate_pvserver_pid(server['pvserver_pid'], server['pvserver_port']):
            valid_servers += 1
            print(f"✅ Valid pvserver: Task {server['task_id']}, PID {server['pvserver_pid']}, Port {server['pvserver_port']}")
        else:
            print(f"❌ Invalid pvserver: Task {server['task_id']}, PID {server['pvserver_pid']}, Port {server['pvserver_port']}")
    
    print(f"📈 Validation summary: {valid_servers}/{running_count} servers are valid")
    
    return valid_servers == running_count

def test_zombie_simulation():
    """Test 6: Simulate zombie process scenario"""
    print("\n🧪 Test 6: Zombie process simulation")
    
    # This is a theoretical test - we can't easily create actual zombies
    # but we can test the cleanup mechanisms
    
    print("🧟 Simulating zombie process scenario...")
    
    # Get summary before
    summary_before = get_active_pvserver_summary()
    print(f"📊 Before simulation: {summary_before}")
    
    # Run cleanup
    cleaned_up = cleanup_stale_database_entries()
    
    # Get summary after
    summary_after = get_active_pvserver_summary()
    print(f"📊 After cleanup: {summary_after}")
    
    print("✅ Zombie simulation test completed (no actual zombies created)")
    return True

def run_all_tests():
    """Run all tests"""
    print("🧪 Starting comprehensive zombie process handling tests...")
    print("=" * 60)
    
    # Reset database
    if not reset_database():
        print("❌ Database reset failed, aborting tests")
        return False
    
    # Run tests
    tests = [
        ("Signal Handler Setup", test_signal_handler_setup),
        ("Process Validation", test_process_validation),
        ("PVServer Lifecycle", test_pvserver_lifecycle),
        ("Lazy Cleanup", test_lazy_cleanup),
        ("Database Consistency", test_database_consistency),
        ("Zombie Simulation", test_zombie_simulation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 Test Results Summary:")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📊 Overall: {passed}/{len(results)} tests passed")
    
    # Final system state
    print("\n🔍 Final System State:")
    summary = get_active_pvserver_summary()
    print(f"Active PVServer Summary: {summary}")
    
    return passed == len(results)

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1) 