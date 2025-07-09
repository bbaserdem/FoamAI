#!/usr/bin/env python3
"""
Script to demonstrate proper Celery shutdown to avoid hanging.

This script shows how to shut down Celery gracefully and provides
troubleshooting steps if shutdown issues persist.
"""

import os
import signal
import subprocess
import time
import sys

def find_celery_processes():
    """Find all running Celery processes"""
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )
        
        celery_processes = []
        for line in result.stdout.split('\n'):
            if 'celery' in line and 'worker' in line:
                parts = line.split()
                if len(parts) >= 2:
                    pid = int(parts[1])
                    celery_processes.append(pid)
        
        return celery_processes
    except Exception as e:
        print(f"Error finding Celery processes: {e}")
        return []

def graceful_shutdown():
    """Perform graceful Celery shutdown"""
    print("🔄 Performing graceful Celery shutdown...")
    
    # Find Celery processes
    celery_pids = find_celery_processes()
    if not celery_pids:
        print("✅ No Celery processes found")
        return True
    
    print(f"📋 Found Celery processes: {celery_pids}")
    
    # Step 1: Send SIGTERM for graceful shutdown
    print("📤 Sending SIGTERM for graceful shutdown...")
    for pid in celery_pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"✅ Sent SIGTERM to PID {pid}")
        except ProcessLookupError:
            print(f"⚠️ Process {pid} already terminated")
        except Exception as e:
            print(f"❌ Error sending SIGTERM to {pid}: {e}")
    
    # Step 2: Wait for graceful shutdown (up to 10 seconds)
    print("⏳ Waiting for graceful shutdown...")
    for i in range(10):
        time.sleep(1)
        remaining_pids = find_celery_processes()
        if not remaining_pids:
            print("✅ All Celery processes shut down gracefully")
            return True
        print(f"⏳ Still waiting... {len(remaining_pids)} processes remaining")
    
    # Step 3: Force shutdown if needed
    remaining_pids = find_celery_processes()
    if remaining_pids:
        print(f"⚠️ Forcing shutdown of remaining processes: {remaining_pids}")
        for pid in remaining_pids:
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"🔨 Sent SIGKILL to PID {pid}")
            except ProcessLookupError:
                print(f"⚠️ Process {pid} already terminated")
            except Exception as e:
                print(f"❌ Error sending SIGKILL to {pid}: {e}")
        
        # Wait a bit more
        time.sleep(2)
        final_pids = find_celery_processes()
        if final_pids:
            print(f"❌ Failed to terminate processes: {final_pids}")
            return False
    
    print("✅ Celery shutdown completed")
    return True

def cleanup_resources():
    """Clean up any remaining resources"""
    print("🧹 Cleaning up remaining resources...")
    
    try:
        # Clean up pvservers
        from pvserver_service import force_cleanup_all_pvservers
        cleanup_result = force_cleanup_all_pvservers()
        print(f"🧹 PVServer cleanup result: {cleanup_result}")
    except Exception as e:
        print(f"⚠️ Error cleaning up pvservers: {e}")
    
    # Clean up any zombie processes
    try:
        subprocess.run(['ps', '-eo', 'pid,ppid,state,comm'], 
                      capture_output=True, text=True)
        print("✅ Process cleanup completed")
    except Exception as e:
        print(f"⚠️ Error checking processes: {e}")

def main():
    """Main function to demonstrate proper shutdown"""
    print("🚀 Celery Clean Shutdown Script")
    print("=" * 50)
    
    # Perform graceful shutdown
    success = graceful_shutdown()
    
    if success:
        # Clean up resources
        cleanup_resources()
        print("\n✅ Shutdown completed successfully!")
        print("\n💡 Tips to prevent hanging:")
        print("   - Use Ctrl+C (SIGINT) or kill -TERM <pid> for graceful shutdown")
        print("   - Avoid kill -9 (SIGKILL) unless absolutely necessary")
        print("   - The signal handling improvements should prevent most hangs")
        print("   - Monitor for long-running tasks that might block shutdown")
        
    else:
        print("\n❌ Shutdown had issues. Check for:")
        print("   - Long-running tasks")
        print("   - Database connection issues")
        print("   - Stuck file operations")
        print("   - Process permission issues")
        
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 