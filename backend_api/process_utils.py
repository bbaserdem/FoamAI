import subprocess
import os
import psutil
import signal
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
from database import update_pvserver_status, DatabaseError

# Global tracking for signal handler
_active_pvservers = {}
_signal_handler_setup = False
_cleanup_lock = threading.Lock()

class ProcessError(Exception):
    """Custom exception for process-related errors"""
    pass

class PVServerError(ProcessError):
    """Custom exception for PVServer-related errors"""
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

def process_is_running(pid: int) -> bool:
    """Check if a process with given PID is still running"""
    return validate_pvserver_pid(pid)

def start_pvserver(case_path: str, port: int, task_id: str) -> int:
    """
    Start a pvserver process for the given case and port using process groups
    Returns the PID of the started process
    
    Args:
        case_path: Path to the OpenFOAM case directory
        port: Port number to use for the pvserver
        task_id: Associated task ID for tracking
        
    Returns:
        int: PID of the started process
        
    Raises:
        PVServerError: If the process fails to start
    """
    global _active_pvservers
    
    # Ensure signal handlers are set up
    setup_signal_handlers()
    
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
    """
    Stop a pvserver process by PID
    
    Args:
        pid: Process ID to stop
        
    Returns:
        bool: True if process was stopped successfully, False otherwise
    """
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

def get_active_pvserver_summary() -> Dict:
    """Get summary of currently active pvservers"""
    global _active_pvservers
    
    return {
        'tracked_processes': len(_active_pvservers),
        'signal_handler_setup': _signal_handler_setup,
        'processes': dict(_active_pvservers)
    }

def get_tracked_pvservers() -> Dict:
    """Get the current tracked pvservers dictionary"""
    global _active_pvservers
    return dict(_active_pvservers)

def add_to_tracking(pid: int, task_id: str, port: int, case_path: str):
    """Add a pvserver to the tracking system"""
    global _active_pvservers
    _active_pvservers[pid] = {
        'task_id': task_id,
        'port': port,
        'case_path': case_path,
        'started': datetime.now()
    }

def remove_from_tracking(pid: int):
    """Remove a pvserver from the tracking system"""
    global _active_pvservers
    if pid in _active_pvservers:
        del _active_pvservers[pid]

def is_signal_handler_setup() -> bool:
    """Check if signal handlers are set up"""
    return _signal_handler_setup 