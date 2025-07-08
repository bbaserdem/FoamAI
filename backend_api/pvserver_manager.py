import subprocess
import sqlite3
import socket
import os
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List

DATABASE_PATH = 'tasks.db'

# Configuration
PVSERVER_PORT_RANGE = (11111, 11116)  # 6 ports: 11111-11116
MAX_CONCURRENT_PVSERVERS = 6
CLEANUP_THRESHOLD_HOURS = 4

class PVServerError(Exception):
    """Custom exception for PVServer-related errors"""
    pass

class PortInUseError(PVServerError):
    """Exception raised when a port is already in use"""
    pass

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

def count_running_pvservers() -> int:
    """Count currently running pvservers in database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM tasks WHERE pvserver_status = 'running'"
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_running_pvserver_for_case(case_path: str) -> Optional[Dict]:
    """Get running pvserver info for a specific case directory"""
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
        return dict(result)
    return None

def process_is_running(pid: int) -> bool:
    """Check if a process with given PID is still running"""
    try:
        return psutil.pid_exists(pid) and psutil.Process(pid).is_running()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False

def start_pvserver(case_path: str, port: int) -> int:
    """
    Start a pvserver process for the given case and port
    Returns the PID of the started process
    """
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
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(case_path)  # Start in the case directory
        )
        
        # Give it a moment to start
        import time
        time.sleep(1)
        
        # Check if process is still running
        if process.poll() is None:
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
    try:
        if process_is_running(pid):
            process = psutil.Process(pid)
            process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                # Force kill if it doesn't shut down gracefully
                process.kill()
                process.wait(timeout=5)
            
            return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
        pass
    
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
    Returns pvserver info or error details.
    """
    try:
        # 1. Check if case already has running pvserver
        existing = get_running_pvserver_for_case(case_path)
        if existing:
            # Verify the process is actually running
            if process_is_running(existing['pvserver_pid']):
                link_task_to_existing_pvserver(task_id, existing)
                return {
                    "status": "running",
                    "port": existing['pvserver_port'],
                    "pid": existing['pvserver_pid'],
                    "connection_string": f"localhost:{existing['pvserver_port']}",
                    "reused": True
                }
            else:
                # Process died, mark as stopped
                update_pvserver_status(task_id, 'stopped')
        
        # 2. Check concurrent limit
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
        
        # 4. Start new pvserver
        pid = start_pvserver(case_path, port)
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
        if stop_pvserver(server['pvserver_pid']):
            update_pvserver_status(server['task_id'], 'stopped')
            cleaned_up.append(f"task_{server['task_id']}_port_{server['pvserver_port']}")
    
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
        if data['pvserver_status'] == 'running':
            data['connection_string'] = f"localhost:{data['pvserver_port']}"
        return data
    
    return None 