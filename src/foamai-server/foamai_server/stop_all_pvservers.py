#!/usr/bin/env python3
"""
Script to stop all running pvservers.
This script stops all active pvservers and cleans up their database entries.
"""

import sys
import json
from pathlib import Path

# Add the backend_api directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from pvserver_service import list_active_pvservers, stop_pvserver_by_port
from database import get_database_stats

def stop_all_pvservers():
    """Stop all running pvservers"""
    print("🛑 Stopping all running pvservers...")
    
    # Step 1: List current pvservers
    print("\n--- Step 1: List current pvservers ---")
    list_result = list_active_pvservers()
    
    if not list_result or "error" in list_result:
        print("❌ Failed to list pvservers")
        return False
    
    pvservers = list_result.get("pvservers", [])
    total_count = list_result.get("total_count", 0)
    
    print(f"📊 Found {total_count} active pvservers")
    
    if total_count == 0:
        print("✅ No pvservers to stop")
        return True
    
    # Step 2: Stop each pvserver
    print("\n--- Step 2: Stop each pvserver ---")
    stopped_count = 0
    failed_count = 0
    
    for i, pvserver in enumerate(pvservers, 1):
        port = pvserver.get("port")
        case_path = pvserver.get("case_path", "Unknown")
        pid = pvserver.get("pid")
        
        print(f"\n🛑 Stopping pvserver {i}/{total_count}:")
        print(f"   Port: {port}")
        print(f"   PID: {pid}")
        print(f"   Case: {case_path}")
        
        stop_result = stop_pvserver_by_port(port)
        
        if stop_result.get("status") == "success":
            print(f"   ✅ Stopped successfully")
            stopped_count += 1
        else:
            print(f"   ❌ Failed to stop: {stop_result.get('message', 'Unknown error')}")
            failed_count += 1
    
    # Step 3: Verify all are stopped
    print("\n--- Step 3: Verify cleanup ---")
    final_result = list_active_pvservers()
    final_count = final_result.get("total_count", 0)
    
    print(f"📊 Final count: {final_count} active pvservers")
    print(f"✅ Successfully stopped: {stopped_count}")
    if failed_count > 0:
        print(f"❌ Failed to stop: {failed_count}")
    
    # Show port availability
    available_ports = final_result.get("available_ports", 0)
    port_range = final_result.get("port_range", "Unknown")
    print(f"🔓 Available ports: {available_ports}")
    print(f"🔢 Port range: {port_range}")
    
    if final_count == 0:
        print("\n🎉 All pvservers stopped successfully!")
        return True
    else:
        print(f"\n⚠️  {final_count} pvservers still running")
        return False

def show_database_stats():
    """Show database statistics"""
    print("\n--- Database Statistics ---")
    try:
        stats = get_database_stats()
        print(f"📊 Total tasks: {stats.get('total_tasks', 0)}")
        
        status_counts = stats.get('status_counts', {})
        if status_counts:
            print("📋 Task status breakdown:")
            for status, count in status_counts.items():
                print(f"   {status}: {count}")
        
        pvserver_counts = stats.get('pvserver_counts', {})
        if pvserver_counts:
            print("🎨 PVServer status breakdown:")
            for status, count in pvserver_counts.items():
                print(f"   {status}: {count}")
                
    except Exception as e:
        print(f"❌ Could not get database stats: {e}")

def main():
    """Main function"""
    print("🧹 FoamAI PVServer Cleanup Script")
    print("=" * 40)
    
    # Show initial statistics
    show_database_stats()
    
    # Stop all pvservers
    success = stop_all_pvservers()
    
    # Show final statistics
    show_database_stats()
    
    if success:
        print("\n✅ Cleanup completed successfully!")
        print("💡 All pvservers have been stopped and cleaned up.")
        return 0
    else:
        print("\n⚠️  Cleanup completed with some issues.")
        print("💡 Check the output above for details.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Cleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Cleanup failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 