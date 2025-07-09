#!/usr/bin/env python3
"""
PVServer Cleanup Utility
Handles various cleanup scenarios for pvserver processes and database records
"""

import argparse
import sys
from pvserver_manager import cleanup_dead_pvservers, cleanup_inactive_pvservers, force_cleanup_port, count_running_pvservers
import subprocess

def cleanup_all():
    """Clean up both dead and inactive pvservers"""
    print("🧹 Starting comprehensive pvserver cleanup...")
    
    print("\n1️⃣ Cleaning up dead pvservers...")
    dead_cleaned = cleanup_dead_pvservers()
    if dead_cleaned:
        print(f"✅ Cleaned up {len(dead_cleaned)} dead pvservers:")
        for item in dead_cleaned:
            print(f"   - {item}")
    else:
        print("✅ No dead pvservers found")
    
    print("\n2️⃣ Cleaning up inactive pvservers...")
    inactive_cleaned = cleanup_inactive_pvservers()
    if inactive_cleaned:
        print(f"✅ Cleaned up {len(inactive_cleaned)} inactive pvservers:")
        for item in inactive_cleaned:
            print(f"   - {item}")
    else:
        print("✅ No inactive pvservers found")
    
    total = len(dead_cleaned) + len(inactive_cleaned)
    print(f"\n🎉 Cleanup complete! Total cleaned: {total}")

def cleanup_dead_only():
    """Clean up only dead pvservers"""
    print("🧹 Cleaning up dead pvservers...")
    
    dead_cleaned = cleanup_dead_pvservers()
    if dead_cleaned:
        print(f"✅ Cleaned up {len(dead_cleaned)} dead pvservers:")
        for item in dead_cleaned:
            print(f"   - {item}")
    else:
        print("✅ No dead pvservers found")

def force_cleanup_all_ports():
    """Force cleanup all pvserver ports (11111-11116)"""
    print("🧹 Force cleaning up all pvserver ports...")
    
    cleaned_ports = []
    for port in range(11111, 11117):
        print(f"\n🔍 Checking port {port}...")
        if force_cleanup_port(port):
            cleaned_ports.append(port)
    
    if cleaned_ports:
        print(f"\n✅ Force cleaned ports: {cleaned_ports}")
    else:
        print("\n✅ No ports needed cleaning")

def nuclear_cleanup():
    """Nuclear option: kill all pvserver processes and reset database"""
    print("💥 NUCLEAR CLEANUP: This will kill ALL pvserver processes!")
    
    # Confirm with user
    response = input("Are you sure? Type 'YES' to continue: ")
    if response != 'YES':
        print("❌ Cancelled")
        return
    
    print("\n1️⃣ Killing all pvserver processes...")
    try:
        result = subprocess.run(['pkill', '-f', 'pvserver'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Killed all pvserver processes")
        else:
            print("ℹ️  No pvserver processes to kill")
    except Exception as e:
        print(f"❌ Error killing processes: {e}")
    
    print("\n2️⃣ Resetting database pvserver status...")
    try:
        import sqlite3
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE tasks SET pvserver_status = "stopped" WHERE pvserver_status = "running"')
        updated_rows = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"✅ Reset {updated_rows} database records")
    except Exception as e:
        print(f"❌ Error updating database: {e}")
    
    print("\n💥 Nuclear cleanup complete!")

def show_status():
    """Show current pvserver status"""
    print("📊 Current PVServer Status")
    print("=" * 40)
    
    # Count running pvservers in database
    running_count = count_running_pvservers()
    print(f"Database running pvservers: {running_count}")
    
    # Check actual system processes
    try:
        result = subprocess.run(['pgrep', '-f', 'pvserver'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
            print(f"System running pvservers: {len(pids)} (PIDs: {pids})")
        else:
            print("System running pvservers: 0")
    except Exception as e:
        print(f"Error checking system processes: {e}")
    
    # Check port status
    print(f"\nPort status (11111-11116):")
    for port in range(11111, 11117):
        try:
            result = subprocess.run(['ss', '-tuln'], capture_output=True, text=True)
            if result.returncode == 0 and f':{port} ' in result.stdout:
                print(f"  Port {port}: ✅ listening")
            else:
                print(f"  Port {port}: ❌ not listening")
        except:
            print(f"  Port {port}: ❓ unknown")

def main():
    parser = argparse.ArgumentParser(description='PVServer Cleanup Utility')
    parser.add_argument('action', choices=['all', 'dead', 'force-ports', 'nuclear', 'status'], 
                       help='Cleanup action to perform')
    parser.add_argument('--port', type=int, help='Specific port to force cleanup (11111-11116)')
    
    args = parser.parse_args()
    
    print("🚀 PVServer Cleanup Utility")
    print("=" * 40)
    
    if args.action == 'all':
        cleanup_all()
    elif args.action == 'dead':
        cleanup_dead_only()
    elif args.action == 'force-ports':
        if args.port:
            if 11111 <= args.port <= 11116:
                print(f"🧹 Force cleaning port {args.port}...")
                cleaned = force_cleanup_port(args.port)
                if cleaned:
                    print(f"✅ Port {args.port} cleaned")
                else:
                    print(f"✅ Port {args.port} was already clean")
            else:
                print("❌ Port must be in range 11111-11116")
        else:
            force_cleanup_all_ports()
    elif args.action == 'nuclear':
        nuclear_cleanup()
    elif args.action == 'status':
        show_status()

if __name__ == "__main__":
    main() 