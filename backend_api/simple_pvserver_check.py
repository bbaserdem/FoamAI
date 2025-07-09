#!/usr/bin/env python3
"""
Simple pvserver process checker without psutil dependency
"""

import subprocess
import re

def check_pvserver_processes():
    """Check for running pvserver processes using basic commands"""
    print("🔍 Checking for running pvserver processes...")
    
    processes = []
    
    try:
        # Method 1: Using pgrep
        result = subprocess.run(['pgrep', '-f', 'pvserver'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"📋 Found {len(pids)} pvserver PIDs: {pids}")
            
            for pid in pids:
                if pid.strip():
                    try:
                        # Get command line for this PID
                        cmdline_result = subprocess.run(['ps', '-p', pid.strip(), '-o', 'cmd='], capture_output=True, text=True)
                        if cmdline_result.returncode == 0:
                            cmdline = cmdline_result.stdout.strip()
                            
                            # Extract port
                            port = None
                            port_match = re.search(r'--server-port[=\s](\d+)', cmdline)
                            if port_match:
                                port = int(port_match.group(1))
                            
                            processes.append({
                                'pid': int(pid.strip()),
                                'port': port,
                                'cmdline': cmdline
                            })
                            
                            print(f"  🔸 PID {pid.strip()}: Port {port}")
                            print(f"     Command: {cmdline}")
                    except Exception as e:
                        print(f"  ❌ Error getting info for PID {pid}: {e}")
        else:
            print("❌ No pvserver processes found")
            
    except Exception as e:
        print(f"❌ Error running pgrep: {e}")
    
    # Method 2: Using ps aux as fallback
    print("\n🔍 Double-checking with ps aux...")
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if result.returncode == 0:
            pvserver_lines = []
            for line in result.stdout.split('\n'):
                if 'pvserver' in line and not line.strip().startswith('grep'):
                    pvserver_lines.append(line)
            
            if pvserver_lines:
                print(f"📋 Found {len(pvserver_lines)} pvserver processes in ps aux:")
                for line in pvserver_lines:
                    print(f"  {line}")
            else:
                print("❌ No pvserver processes found in ps aux")
    except Exception as e:
        print(f"❌ Error running ps aux: {e}")
    
    return processes

def check_port_listeners():
    """Check which ports are listening"""
    print("\n🔍 Checking listening ports in range 11111-11116...")
    
    for port in range(11111, 11117):
        try:
            # Method 1: Using ss
            result = subprocess.run(['ss', '-tuln'], capture_output=True, text=True)
            if result.returncode == 0:
                if f':{port} ' in result.stdout:
                    print(f"  ✅ Port {port} is listening")
                    continue
            
            # Method 2: Using netstat
            result = subprocess.run(['netstat', '-tuln'], capture_output=True, text=True)
            if result.returncode == 0:
                if f':{port} ' in result.stdout:
                    print(f"  ✅ Port {port} is listening (netstat)")
                    continue
            
            print(f"  ❌ Port {port} is not listening")
            
        except Exception as e:
            print(f"  ❌ Error checking port {port}: {e}")

def check_database():
    """Check database for pvserver records"""
    print("\n🔍 Checking database for pvserver records...")
    
    try:
        import sqlite3
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT task_id, pvserver_port, pvserver_pid, pvserver_status 
            FROM tasks 
            WHERE pvserver_status IS NOT NULL
            ORDER BY pvserver_started_at DESC
            LIMIT 10
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        if rows:
            print(f"📋 Found {len(rows)} pvserver records in database:")
            for row in rows:
                task_id, port, pid, status = row
                print(f"  🔸 Task: {task_id[:8]}... | PID: {pid} | Port: {port} | Status: {status}")
        else:
            print("❌ No pvserver records found in database")
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")

def main():
    """Main function"""
    print("🚀 Simple PVServer Process Checker")
    print("=" * 50)
    
    processes = check_pvserver_processes()
    check_port_listeners()
    check_database()
    
    print(f"\n🏁 Summary: Found {len(processes)} running pvserver processes")

if __name__ == "__main__":
    main() 