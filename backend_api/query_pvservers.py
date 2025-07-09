#!/usr/bin/env python3
"""
Query running pvserver processes script
Shows all running pvserver processes and compares with database records
"""

import subprocess
import sqlite3
import psutil
import re
from datetime import datetime
from typing import List, Dict, Optional

DATABASE_PATH = 'tasks.db'

def get_system_pvservers_simple() -> List[Dict]:
    """Simple method to get pvserver processes using basic commands"""
    system_processes = []
    
    try:
        # Use pgrep to find pvserver processes
        result = subprocess.run(['pgrep', '-f', 'pvserver'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
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
                            
                            system_processes.append({
                                'pid': int(pid.strip()),
                                'port': port,
                                'cmdline': cmdline,
                                'create_time': None,
                                'status': 'running'
                            })
                    except:
                        continue
    except Exception as e:
        print(f"❌ Error with simple process scanning: {e}")
    
    return system_processes

def get_system_pvservers() -> List[Dict]:
    """Get all running pvserver processes from the system"""
    print("🔍 Scanning system for running pvserver processes...")
    
    system_processes = []
    
    try:
        # Method 1: Using psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                # Check if we have valid process info
                if not proc.info or not proc.info.get('name'):
                    continue
                
                # Check if cmdline is available and not None
                cmdline = proc.info.get('cmdline')
                if not cmdline:
                    continue
                
                # Check if this is a pvserver process
                if proc.info['name'] == 'pvserver' or (cmdline and len(cmdline) > 0 and 'pvserver' in cmdline[0]):
                    # Extract port from command line
                    port = None
                    for arg in cmdline:
                        if '--server-port=' in str(arg):
                            port = int(str(arg).split('=')[1])
                            break
                        elif str(arg) == '--server-port' and cmdline.index(arg) + 1 < len(cmdline):
                            port = int(cmdline[cmdline.index(arg) + 1])
                            break
                    
                    # Get creation time safely
                    create_time = None
                    if proc.info.get('create_time'):
                        create_time = datetime.fromtimestamp(proc.info['create_time'])
                    
                    system_processes.append({
                        'pid': proc.info['pid'],
                        'port': port,
                        'cmdline': ' '.join(str(arg) for arg in cmdline),
                        'create_time': create_time,
                        'status': 'running'
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception as e:
                # Skip processes that cause other errors
                continue
                
    except Exception as e:
        print(f"❌ Error scanning processes with psutil: {e}")
        print("🔄 Falling back to simple process scanning...")
        return get_system_pvservers_simple()
    
    # Method 2: Using ps command as backup
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if result.returncode == 0:
            ps_processes = []
            for line in result.stdout.split('\n'):
                if 'pvserver' in line and not line.strip().startswith('grep'):
                    parts = line.split()
                    if len(parts) >= 11:
                        pid = int(parts[1])
                        # Skip if we already found this PID with psutil
                        if any(p['pid'] == pid for p in system_processes):
                            continue
                        
                        # Extract port from command line
                        port = None
                        cmdline = ' '.join(parts[10:])
                        port_match = re.search(r'--server-port[=\s](\d+)', cmdline)
                        if port_match:
                            port = int(port_match.group(1))
                        
                        ps_processes.append({
                            'pid': pid,
                            'port': port,
                            'cmdline': cmdline,
                            'create_time': None,
                            'status': 'running'
                        })
            
            system_processes.extend(ps_processes)
    except Exception as e:
        print(f"⚠️  Error scanning processes with ps: {e}")
    
    print(f"✅ Found {len(system_processes)} running pvserver processes")
    return system_processes

def get_database_pvservers() -> List[Dict]:
    """Get pvserver records from database"""
    print("🔍 Querying database for pvserver records...")
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT task_id, case_path, pvserver_port, pvserver_pid, pvserver_status, 
                   pvserver_started_at, pvserver_last_activity, pvserver_error_message
            FROM tasks 
            WHERE pvserver_status IS NOT NULL
            ORDER BY pvserver_started_at DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        db_records = []
        for row in rows:
            db_records.append({
                'task_id': row['task_id'],
                'case_path': row['case_path'],
                'port': row['pvserver_port'],
                'pid': row['pvserver_pid'],
                'status': row['pvserver_status'],
                'started_at': row['pvserver_started_at'],
                'last_activity': row['pvserver_last_activity'],
                'error_message': row['pvserver_error_message']
            })
        
        print(f"✅ Found {len(db_records)} pvserver records in database")
        return db_records
        
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        return []

def check_port_status(port: int) -> str:
    """Check if a port is listening"""
    try:
        result = subprocess.run(['ss', '-tuln'], capture_output=True, text=True)
        if result.returncode == 0:
            if f':{port} ' in result.stdout:
                return "listening"
        
        # Fallback to netstat
        result = subprocess.run(['netstat', '-tuln'], capture_output=True, text=True)
        if result.returncode == 0:
            if f':{port} ' in result.stdout:
                return "listening"
        
        return "not listening"
    except:
        return "unknown"

def analyze_pvservers():
    """Analyze and compare system processes with database records"""
    print("🔍 Analyzing pvserver processes...")
    
    system_processes = get_system_pvservers()
    db_records = get_database_pvservers()
    
    print(f"\n{'='*60}")
    print("📊 SYSTEM PROCESSES")
    print(f"{'='*60}")
    
    if not system_processes:
        print("❌ No running pvserver processes found in system")
    else:
        for i, proc in enumerate(system_processes, 1):
            print(f"\n🔸 Process {i}:")
            print(f"   PID: {proc['pid']}")
            print(f"   Port: {proc['port']}")
            print(f"   Status: {proc['status']}")
            if proc['create_time']:
                print(f"   Started: {proc['create_time']}")
            if proc['port']:
                port_status = check_port_status(proc['port'])
                print(f"   Port Status: {port_status}")
            print(f"   Command: {proc['cmdline']}")
    
    print(f"\n{'='*60}")
    print("🗄️  DATABASE RECORDS")
    print(f"{'='*60}")
    
    if not db_records:
        print("❌ No pvserver records found in database")
    else:
        for i, record in enumerate(db_records, 1):
            print(f"\n🔸 Record {i}:")
            print(f"   Task ID: {record['task_id']}")
            print(f"   PID: {record['pid']}")
            print(f"   Port: {record['port']}")
            print(f"   Status: {record['status']}")
            print(f"   Case Path: {record['case_path']}")
            if record['started_at']:
                print(f"   Started: {record['started_at']}")
            if record['last_activity']:
                print(f"   Last Activity: {record['last_activity']}")
            if record['error_message']:
                print(f"   Error: {record['error_message']}")
    
    print(f"\n{'='*60}")
    print("🔍 ANALYSIS")
    print(f"{'='*60}")
    
    # Find running processes in DB that are marked as running
    running_db = [r for r in db_records if r['status'] == 'running']
    system_pids = [p['pid'] for p in system_processes]
    
    print(f"\n📊 Summary:")
    print(f"   System Processes: {len(system_processes)}")
    print(f"   Database Records: {len(db_records)}")
    print(f"   DB Running Records: {len(running_db)}")
    
    # Check for discrepancies
    orphaned_processes = []
    zombie_records = []
    
    for proc in system_processes:
        matching_db = None
        for db_rec in running_db:
            if db_rec['pid'] == proc['pid']:
                matching_db = db_rec
                break
        
        if not matching_db:
            orphaned_processes.append(proc)
    
    for db_rec in running_db:
        if db_rec['pid'] not in system_pids:
            zombie_records.append(db_rec)
    
    if orphaned_processes:
        print(f"\n⚠️  Orphaned Processes (running but not in DB):")
        for proc in orphaned_processes:
            print(f"   PID {proc['pid']} on port {proc['port']}")
    
    if zombie_records:
        print(f"\n👻 Zombie Records (in DB but not running):")
        for record in zombie_records:
            print(f"   Task {record['task_id']} - PID {record['pid']} on port {record['port']}")
    
    if not orphaned_processes and not zombie_records:
        print(f"\n✅ All processes are properly tracked in database")
    
    # Port conflicts
    ports_in_use = {}
    for proc in system_processes:
        if proc['port']:
            if proc['port'] in ports_in_use:
                ports_in_use[proc['port']].append(proc)
            else:
                ports_in_use[proc['port']] = [proc]
    
    conflicts = {port: procs for port, procs in ports_in_use.items() if len(procs) > 1}
    if conflicts:
        print(f"\n⚠️  Port Conflicts:")
        for port, procs in conflicts.items():
            print(f"   Port {port}: {len(procs)} processes")
            for proc in procs:
                print(f"     PID {proc['pid']}")

def cleanup_suggestions():
    """Provide cleanup suggestions"""
    print(f"\n{'='*60}")
    print("🧹 CLEANUP SUGGESTIONS")
    print(f"{'='*60}")
    
    system_processes = get_system_pvservers()
    db_records = get_database_pvservers()
    
    running_db = [r for r in db_records if r['status'] == 'running']
    system_pids = [p['pid'] for p in system_processes]
    
    # Find zombie records
    zombie_records = [r for r in running_db if r['pid'] not in system_pids]
    
    if zombie_records:
        print(f"\n🛠️  To fix zombie records, run:")
        print(f"   python -c \"")
        print(f"   import sqlite3")
        print(f"   conn = sqlite3.connect('{DATABASE_PATH}')")
        print(f"   cursor = conn.cursor()")
        for record in zombie_records:
            print(f"   cursor.execute('UPDATE tasks SET pvserver_status = \\'stopped\\' WHERE task_id = \\'{record['task_id']}\\')")
        print(f"   conn.commit()")
        print(f"   conn.close()\"")
    
    # Find orphaned processes
    orphaned_processes = []
    for proc in system_processes:
        if not any(r['pid'] == proc['pid'] for r in running_db):
            orphaned_processes.append(proc)
    
    if orphaned_processes:
        print(f"\n🛠️  To kill orphaned processes, run:")
        for proc in orphaned_processes:
            print(f"   kill {proc['pid']}  # Port {proc['port']}")
    
    if not zombie_records and not orphaned_processes:
        print(f"\n✅ No cleanup needed - all processes are properly tracked!")

def main():
    """Main function"""
    print("🚀 PVServer Process Query Script")
    print("=" * 60)
    
    try:
        analyze_pvservers()
        cleanup_suggestions()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 