import subprocess
import sqlite3
import socket
import os
import psutil
import signal
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List

DATABASE_PATH = 'tasks.db'

# Configuration
PVSERVER_PORT_RANGE = (11111, 11116)  # 6 ports: 11111-11116
MAX_CONCURRENT_PVSERVERS = 6
CLEANUP_THRESHOLD_HOURS = 4

# Global tracking for signal handler
_active_pvservers = {}
_signal_handler_setup = False
_cleanup_lock = threading.Lock()

class PVServerError(Exception):
    """Custom exception for PVServer-related errors"""
    pass

class PortInUseError(PVServerError):
    """Exception raised when a port is already in use"""
    pass

def setup_signal_handlers():
    """Set up signal handlers for automatic zombie process cleanup"""
    global _signal_handler_setup
    
    if _signal_handler_setup:
        return
    
    def reap_children(signum, frame):
        """Signal handler to reap zombie children"""
        with _cleanup_lock:
            while True:
                try:
                    pid, status = os.waitpid(-1, os.WNOHANG)
                    if pid == 0:  # No more children to reap
                        break
                    
                    print(f"🧹 Reaped child process {pid} with status {status}")
                    
                    # Update our tracking
                    if pid in _active_pvservers:
                        pvserver_info = _active_pvservers[pid]
                        print(f"🔄 Updating database for reaped pvserver {pid} on port {pvserver_info.get('port')}")
                        
                        # Update database status
                        try:
                            update_pvserver_status(
                                pvserver_info['task_id'], 
                                'stopped', 
                                error_message=f"Process terminated with status {status}"
                            )
                        except Exception as e:
                            print(f"❌ Error updating database for reaped process {pid}: {e}")
                        
                        del _active_pvservers[pid]
                        
                except OSError:
                    # No more children or other error
                    break
    
    # Set up the signal handler
    signal.signal(signal.SIGCHLD, reap_children)
    _signal_handler_setup = True
    print("✅ Signal handlers set up for zombie process cleanup")

def validate_pvserver_pid(pid: int, expected_port: int = None) -> bool:
    """
    Validate that a PID is actually a running pvserver process
    Optionally check if it's using the expected port
    """
    if not pid:
        return False
    
    try:
        if not psutil.pid_exists(pid):
            return False
        
        process = psutil.Process(pid)
        
        # Check if it's actually a pvserver process
        if process.name() != 'pvserver':
            return False
        
        # If we have an expected port, validate it
        if expected_port:
            cmdline = process.cmdline()
            found_port = None
            
            for arg in cmdline:
                if f'--server-port={expected_port}' in str(arg):
                    found_port = expected_port
                    break
                elif str(arg) == '--server-port' and cmdline.index(arg) + 1 < len(cmdline):
                    try:
                        found_port = int(cmdline[cmdline.index(arg) + 1])
                    except ValueError:
                        pass
                    break
            
            if found_port != expected_port:
                return False
        
        return True
        
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False

def port_is_available(port: int) -> bool:
    """Check if a port is available for use"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except socket.error:
        return False

def find_available_port() -> Optional[int]:
    """Find the next available port in the configured range"""
    start_port, end_port = PVSERVER_PORT_RANGE
    for port in range(start_port, end_port + 1):
        if port_is_available(port):
            return port
    return None

def cleanup_stale_database_entries():
    """Clean up database entries for dead processes (lazy cleanup)"""
    print("🧹 Performing lazy cleanup of stale database entries...")
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all running pvserver records
    cursor.execute("""
        SELECT task_id, pvserver_pid, pvserver_port, case_path
        FROM tasks 
        WHERE pvserver_status = 'running'
    """)
    
    running_records = cursor.fetchall()
    cleaned_up = []
    
    for record in running_records:
        task_id = record['task_id']
        pid = record['pvserver_pid']
        port = record['pvserver_port']
        
        # Validate the process is actually running
        if not validate_pvserver_pid(pid, port):
            print(f"🔄 Cleaning up stale entry: Task {task_id}, PID {pid}, Port {port}")
            
            # Update status to stopped
            cursor.execute("""
                UPDATE tasks 
                SET pvserver_status = 'stopped', 
                    pvserver_last_activity = ?, 
                    pvserver_error_message = 'Process died (cleaned up by lazy cleanup)'
                WHERE task_id = ?
            """, (datetime.now(), task_id))
            
            cleaned_up.append(f"task_{task_id}_port_{port}")
    
    conn.commit()
    conn.close()
    
    if cleaned_up:
        print(f"✅ Cleaned up {len(cleaned_up)} stale database entries")
    else:
        print("✅ No stale entries found")
    
    return cleaned_up

def count_running_pvservers() -> int:
    """Count currently running pvservers (with validation)"""
    # First clean up stale entries
    cleanup_stale_database_entries()
    
    # Then count what's actually running
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM tasks WHERE pvserver_status = 'running'"
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_running_pvserver_for_case(case_path: str) -> Optional[Dict]:
    """Get running pvserver info for a specific case directory (with validation)"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT task_id, pvserver_port, pvserver_pid, pvserver_started_at 
        FROM tasks 
        WHERE case_path = ? AND pvserver_status = 'running'
        ORDER BY pvserver_started_at DESC
        LIMIT 1
    """, (case_path,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        # Validate the process is actually running
        if validate_pvserver_pid(result['pvserver_pid'], result['pvserver_port']):
            return dict(result)
        else:
            # Process is dead, clean it up
            print(f"🔄 Found dead pvserver for case {case_path}, cleaning up...")
            update_pvserver_status(result['task_id'], 'stopped', 
                                 error_message="Process died (detected during case lookup)")
    
    return None

def process_is_running(pid: int) -> bool:
    """Check if a process with given PID is still running"""
    return validate_pvserver_pid(pid)

def start_pvserver(case_path: str, port: int, task_id: str) -> int:
    """
    Start a pvserver process for the given case and port using process groups
    Returns the PID of the started process
    """
    global _active_pvservers
    
    # Ensure signal handlers are set up
    setup_signal_handlers()
    
    if not port_is_available(port):
        raise PortInUseError(f"Port {port} is not available")
    
    # Ensure case directory exists
    case_path = Path(case_path)
    if not case_path.exists():
        raise PVServerError(f"Case directory does not exist: {case_path}")
    
    # Start pvserver process (without --data parameter as it's not supported in this version)
    cmd = [
        'pvserver',
        f'--server-port={port}',
        '--disable-xdisplay-test'
    ]
    
    try:
        # Start process in its own process group for better management
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(case_path),  # Start in the case directory
            preexec_fn=os.setpgrp  # Create new process group
        )
        
        # Give it a moment to start
        time.sleep(1)
        
        # Check if process is still running
        if process.poll() is None:
            # Add to our tracking
            _active_pvservers[process.pid] = {
                'task_id': task_id,
                'port': port,
                'case_path': str(case_path),
                'started': datetime.now()
            }
            
            print(f"✅ Started pvserver PID {process.pid} on port {port}")
            return process.pid
        else:
            # Process died immediately, get error
            stdout, stderr = process.communicate()
            raise PVServerError(f"PVServer failed to start: {stderr.decode()}")
            
    except FileNotFoundError:
        raise PVServerError("pvserver command not found. Is ParaView installed?")
    except Exception as e:
        raise PVServerError(f"Failed to start pvserver: {str(e)}")

def stop_pvserver(pid: int) -> bool:
    """Stop a pvserver process by PID"""
    global _active_pvservers
    
    try:
        if validate_pvserver_pid(pid):
            process = psutil.Process(pid)
            
            # Try graceful termination first
            process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                # Force kill if it doesn't shut down gracefully
                process.kill()
                process.wait(timeout=5)
            
            # Remove from our tracking
            if pid in _active_pvservers:
                del _active_pvservers[pid]
            
            return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
        # Remove from tracking even if we can't kill it (might already be dead)
        if pid in _active_pvservers:
            del _active_pvservers[pid]
    
    return False

def update_pvserver_status(task_id: str, status: str, port: int = None, pid: int = None, error_message: str = None):
    """Update pvserver status in database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    now = datetime.now()
    
    if status == 'running':
        cursor.execute("""
            UPDATE tasks 
            SET pvserver_status = ?, pvserver_port = ?, pvserver_pid = ?, 
                pvserver_started_at = ?, pvserver_last_activity = ?, pvserver_error_message = NULL
            WHERE task_id = ?
        """, (status, port, pid, now, now, task_id))
    elif status == 'error':
        cursor.execute("""
            UPDATE tasks 
            SET pvserver_status = ?, pvserver_error_message = ?, pvserver_last_activity = ?
            WHERE task_id = ?
        """, (status, error_message, now, task_id))
    else:  # stopped
        cursor.execute("""
            UPDATE tasks 
            SET pvserver_status = ?, pvserver_last_activity = ?
            WHERE task_id = ?
        """, (status, now, task_id))
    
    conn.commit()
    conn.close()

def link_task_to_existing_pvserver(task_id: str, existing_pvserver: Dict):
    """Link a task to an existing pvserver for the same case"""
    update_pvserver_status(
        task_id, 
        'running', 
        existing_pvserver['pvserver_port'], 
        existing_pvserver['pvserver_pid']
    )

def ensure_pvserver_for_task(task_id: str, case_path: str) -> Dict:
    """
    Ensure a pvserver is running for the given task and case.
    Uses lazy cleanup and validation for robustness.
    Returns pvserver info or error details.
    """
    try:
        # 1. Check if case already has running pvserver (with validation)
        existing = get_running_pvserver_for_case(case_path)
        if existing:
            # Process is validated in get_running_pvserver_for_case
            link_task_to_existing_pvserver(task_id, existing)
            return {
                "status": "running",
                "port": existing['pvserver_port'],
                "pid": existing['pvserver_pid'],
                "connection_string": f"localhost:{existing['pvserver_port']}",
                "reused": True
            }
        
        # 2. Check concurrent limit (with cleanup)
        if count_running_pvservers() >= MAX_CONCURRENT_PVSERVERS:
            error_msg = f"Max {MAX_CONCURRENT_PVSERVERS} concurrent pvservers reached"
            update_pvserver_status(task_id, 'error', error_message=error_msg)
            return {"status": "error", "error_message": error_msg}
        
        # 3. Find available port
        port = find_available_port()
        if not port:
            error_msg = "All ports in configured range are in use"
            update_pvserver_status(task_id, 'error', error_message=error_msg)
            return {"status": "error", "error_message": error_msg}
        
        # 4. Start new pvserver with process group management
        pid = start_pvserver(case_path, port, task_id)
        update_pvserver_status(task_id, 'running', port, pid)
        
        return {
            "status": "running",
            "port": port,
            "pid": pid,
            "connection_string": f"localhost:{port}",
            "reused": False
        }
        
    except PVServerError as e:
        error_msg = str(e)
        update_pvserver_status(task_id, 'error', error_message=error_msg)
        return {"status": "error", "error_message": error_msg}

def cleanup_inactive_pvservers() -> List[str]:
    """Clean up pvservers that have been inactive for too long"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Find pvservers older than threshold
    cutoff_time = datetime.now() - timedelta(hours=CLEANUP_THRESHOLD_HOURS)
    cursor.execute("""
        SELECT task_id, pvserver_pid, pvserver_port
        FROM tasks 
        WHERE pvserver_status = 'running' 
        AND pvserver_started_at < ?
    """, (cutoff_time,))
    
    inactive_servers = cursor.fetchall()
    conn.close()
    
    cleaned_up = []
    for server in inactive_servers:
        # Validate the process is actually running before trying to stop it
        if validate_pvserver_pid(server['pvserver_pid'], server['pvserver_port']):
            if stop_pvserver(server['pvserver_pid']):
                update_pvserver_status(server['task_id'], 'stopped')
                cleaned_up.append(f"task_{server['task_id']}_port_{server['pvserver_port']}")
        else:
            # Process already dead, just update database
            update_pvserver_status(server['task_id'], 'stopped', 
                                 error_message="Process died (detected during cleanup)")
            cleaned_up.append(f"task_{server['task_id']}_port_{server['pvserver_port']}_dead")
    
    return cleaned_up

def get_pvserver_info(task_id: str) -> Optional[Dict]:
    """Get pvserver information for a task"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT pvserver_port, pvserver_pid, pvserver_status, 
               pvserver_started_at, pvserver_error_message
        FROM tasks 
        WHERE task_id = ?
    """, (task_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        data = dict(result)
        
        # If status is running, validate the process
        if data['pvserver_status'] == 'running' and data['pvserver_pid']:
            if not validate_pvserver_pid(data['pvserver_pid'], data['pvserver_port']):
                # Process is dead, update status
                update_pvserver_status(task_id, 'stopped', 
                                     error_message="Process died (detected during info lookup)")
                data['pvserver_status'] = 'stopped'
                data['pvserver_error_message'] = "Process died (detected during info lookup)"
        
        if data['pvserver_status'] == 'running':
            data['connection_string'] = f"localhost:{data['pvserver_port']}"
        
        return data
    
    return None

def get_active_pvserver_summary() -> Dict:
    """Get summary of currently active pvservers"""
    global _active_pvservers
    
    return {
        'tracked_processes': len(_active_pvservers),
        'signal_handler_setup': _signal_handler_setup,
        'processes': dict(_active_pvservers)
    } 