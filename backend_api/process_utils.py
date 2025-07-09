import subprocess
import os
import psutil
import atexit
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

from process_validator import validate_pvserver_pid


class ProcessError(Exception):
    """Custom exception for process-related errors"""
    pass

class PVServerError(ProcessError):
    """Custom exception for PVServer-related errors"""
    pass


class ProcessManager:
    """Manages the lifecycle of pvserver subprocesses."""
    
    def __init__(self):
        self._active_pvservers: Dict[int, Dict] = {}
        self._lock = threading.Lock()
        self._shutdown_in_progress = False
        self._setup_exit_handler()

    def _setup_exit_handler(self):
        """Set up a handler to clean up processes on exit."""
        atexit.register(self.cleanup_on_exit)

    def cleanup_on_exit(self):
        """Stop all tracked pvserver processes on application exit."""
        with self._lock:
            if self._shutdown_in_progress:
                return
            self._shutdown_in_progress = True
        
        print("🔄 Process shutdown initiated, cleaning up all tracked pvservers...")
        
        # Create a copy of pids to avoid modification during iteration
        pids = list(self._active_pvservers.keys())
        if pids:
            print(f"Found {len(pids)} pvservers to stop.")
        
        for pid in pids:
            try:
                self.stop_pvserver(pid, is_shutdown=True)
            except Exception as e:
                print(f"⚠️ Error stopping pvserver {pid} during shutdown: {e}")

    def start_pvserver(self, case_path: str, port: int, task_id: str) -> int:
        """
        Start a pvserver process and track it.
        
        Returns:
            int: PID of the started process.
        Raises:
            PVServerError: If the process fails to start.
        """
        if self._shutdown_in_progress:
            raise PVServerError("Cannot start new pvserver, shutdown is in progress.")

        case_dir = Path(case_path)
        if not case_dir.is_dir():
            raise PVServerError(f"Case directory does not exist: {case_path}")

        cmd = ['pvserver', f'--server-port={port}', '--disable-xdisplay-test']
        
        try:
            # Start process, ensuring it can be cleaned up properly
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(case_dir)
            )
            
            # Give it a moment to start and check if it died immediately
            time.sleep(1) # Short delay to allow process to initialize or fail
            process.poll()
            if process.returncode is not None:
                _, stderr = process.communicate()
                raise PVServerError(f"PVServer failed to start. Stderr: {stderr.decode('utf-8', 'ignore')}")

            with self._lock:
                self._active_pvservers[process.pid] = {
                    'task_id': task_id,
                    'port': port,
                    'case_path': str(case_path),
                    'started': datetime.now()
                }
            
            print(f"✅ Started and now tracking pvserver PID {process.pid} on port {port}")
            return process.pid

        except FileNotFoundError:
            raise PVServerError("'pvserver' command not found. Is ParaView installed and in the system's PATH?")
        except Exception as e:
            raise PVServerError(f"An unexpected error occurred while starting pvserver: {e}")

    def stop_pvserver(self, pid: int, is_shutdown: bool = False) -> bool:
        """
        Stop a pvserver process by its PID.
        
        Args:
            pid: Process ID to stop.
            is_shutdown: Flag to indicate if this is part of a graceful shutdown.
            
        Returns:
            bool: True if process was stopped successfully, False otherwise.
        """
        if not is_shutdown:
            with self._lock:
                if pid not in self._active_pvservers:
                    print(f"⚠️ PID {pid} not tracked by ProcessManager. Skipping stop.")
                    return False

        try:
            if not psutil.pid_exists(pid):
                print(f"🔄 pvserver PID {pid} was already stopped.")
                return True
                
            process = psutil.Process(pid)
            print(f"Stopping pvserver PID {pid}...")
            process.terminate()
            
            try:
                process.wait(timeout=5)
                print(f"✅ Successfully terminated pvserver PID {pid}")
            except psutil.TimeoutExpired:
                print(f"⚠️ pvserver PID {pid} did not terminate gracefully. Killing.")
                process.kill()
                print(f"✅ Killed pvserver PID {pid}")
            
            return True
        except psutil.NoSuchProcess:
            print(f"🔄 pvserver PID {pid} was already stopped (NoSuchProcess).")
            return True # It's already stopped, so the goal is achieved.
        except (psutil.AccessDenied, Exception) as e:
            print(f"❌ Error stopping pvserver PID {pid}: {e}")
            return False
        finally:
            with self._lock:
                if pid in self._active_pvservers:
                    del self._active_pvservers[pid]
                    if not is_shutdown:
                        print(f"Untracked pvserver PID {pid}")

    def get_active_pvserver_summary(self) -> Dict:
        """Get a summary of currently tracked pvservers."""
        with self._lock:
            return {
                "tracked_pids": list(self._active_pvservers.keys()),
                "count": len(self._active_pvservers)
            }

    def get_tracked_pvservers(self) -> Dict:
        """Get the full dictionary of tracked pvservers."""
        with self._lock:
            # Return a copy to prevent mutation
            return self._active_pvservers.copy()


# Singleton instance of the ProcessManager
process_manager = ProcessManager() 