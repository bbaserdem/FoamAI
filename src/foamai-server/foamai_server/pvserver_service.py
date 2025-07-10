import logging
from typing import Optional, Dict, List
from datetime import datetime

# Import configuration
from config import MAX_CONCURRENT_PVSERVERS, CLEANUP_THRESHOLD_HOURS

# Import our utility modules
from process_utils import PVServerError, process_manager
from port_utils import (
    port_is_available, find_available_port, PortInUseError,
    get_port_range, get_available_port_count
)
from database import (
    get_running_pvservers, get_running_pvserver_for_case,
    get_pvserver_info, count_running_pvservers,
    link_task_to_pvserver, DatabaseError, TaskNotFoundError,
    create_task, update_task_status, get_inactive_pvservers,
    set_pvserver_running, set_pvserver_error, set_pvserver_stopped
)

from process_validator import validator

logger = logging.getLogger(__name__)

class PVServerServiceError(Exception):
    """Custom exception for PVServer service-related errors"""
    pass

# --- Private Helper Functions ---

def _check_concurrency_limit():
    """Checks if the max number of pvservers has been reached, raising an error if so."""
    try:
        if count_running_pvservers() >= MAX_CONCURRENT_PVSERVERS:
            msg = f"Max concurrent pvservers limit ({MAX_CONCURRENT_PVSERVERS}) reached."
            logger.warning(msg)
            raise PVServerServiceError(msg)
    except DatabaseError as e:
        raise PVServerServiceError(f"Database error checking concurrency: {e}")

def _find_and_validate_port(port: Optional[int] = None) -> int:
    """Finds an available port or validates a specific one, raising an error if unavailable."""
    if port:
        if not port_is_available(port):
            msg = f"Specified port {port} is not available."
            logger.error(msg)
            raise PVServerServiceError(msg)
        return port
    else:
        available_port = find_available_port()
        if not available_port:
            msg = "No available ports in the configured range."
            logger.error(msg)
            raise PVServerServiceError(msg)
        return available_port

# --- Public Service Functions ---

def ensure_pvserver_for_task(task_id: str, case_path: str) -> Dict:
    """
    Ensures a pvserver is running for a given task and case. Reuses an existing
    server for the same case if available. Raises PVServerServiceError on failure.
    """
    try:
        existing = get_running_pvserver_for_case(case_path)
        if existing:
            logger.info(f"Task {task_id}: Reusing pvserver on port {existing['pvserver_port']} for case {case_path}")
            link_task_to_pvserver(task_id, existing['pvserver_port'], existing['pvserver_pid'])
            return {
                "status": "reused",
                "port": existing['pvserver_port'],
                "pid": existing['pvserver_pid'],
                "connection_string": f"localhost:{existing['pvserver_port']}",
            }

        _check_concurrency_limit()
        port = _find_and_validate_port()

        logger.info(f"Task {task_id}: Starting new pvserver on port {port} for case {case_path}")
        pid = process_manager.start_pvserver(case_path, port, task_id)
        set_pvserver_running(task_id, port, pid)
        
        return {
            "status": "started",
            "port": port,
            "pid": pid,
            "connection_string": f"localhost:{port}",
        }
    except (PVServerError, PortInUseError, DatabaseError, PVServerServiceError) as e:
        error_msg = f"Failed to ensure pvserver for task {task_id}: {e}"
        logger.error(error_msg)
        set_pvserver_error(task_id, str(e))
        raise PVServerServiceError(error_msg) from e
    except Exception as e:
        error_msg = f"Unexpected error in ensure_pvserver_for_task for {task_id}: {e}"
        logger.exception(error_msg)
        set_pvserver_error(task_id, str(e))
        raise PVServerServiceError(error_msg) from e

def start_pvserver_for_case(case_path: str, port: Optional[int] = None) -> Dict:
    """
    Starts a pvserver for a specific case, reusing if possible. This is for direct,
    non-task-related requests. Raises PVServerServiceError on failure.
    """
    try:
        existing = get_running_pvserver_for_case(case_path)
        if existing:
            logger.info(f"Reusing existing pvserver on port {existing['pvserver_port']} for case {case_path}")
            return {
                "status": "running", "port": existing['pvserver_port'], "pid": existing['pvserver_pid'],
                "connection_string": f"localhost:{existing['pvserver_port']}", "case_path": case_path,
                "message": "Reused existing server.", "reused": True
            }

        _check_concurrency_limit()
        validated_port = _find_and_validate_port(port)

        temp_task_id = f"direct_{validated_port}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        create_task(temp_task_id, "pending", f"Direct pvserver for {case_path}")
        update_task_status(temp_task_id, "running", f"Starting pvserver on port {validated_port}", case_path=case_path)
        
        pid = process_manager.start_pvserver(case_path, validated_port, temp_task_id)
        set_pvserver_running(temp_task_id, validated_port, pid)
        
        logger.info(f"Started new pvserver on port {validated_port} for case {case_path}")
        return {
            "status": "running", "port": validated_port, "pid": pid,
            "connection_string": f"localhost:{validated_port}", "case_path": case_path,
            "message": "Started new server.", "reused": False
        }
    except (PVServerError, PortInUseError, DatabaseError, PVServerServiceError) as e:
        logger.error(f"Failed to start pvserver for case {case_path}: {e}")
        raise PVServerServiceError(f"Failed to start pvserver: {e}") from e

def stop_pvserver_by_port(port: int) -> Dict:
    """
    Stops a pvserver on a specific port. Raises PVServerServiceError on failure.
    """
    # TODO: This is inefficient. Add a get_pvserver_by_port function to the DAL.
    try:
        servers = get_running_pvservers()
        target = next((s for s in servers if s.get('pvserver_port') == port), None)

        if not target:
            raise PVServerServiceError(f"No active pvserver found on port {port}")

        task_id, pid = target['task_id'], target['pvserver_pid']
        logger.info(f"Stopping pvserver on port {port} (PID: {pid}, Task: {task_id})")

        if process_manager.stop_pvserver(pid):
            set_pvserver_stopped(task_id, "Stopped via API call.")
            logger.info(f"Successfully stopped pvserver on port {port}")
            return {"status": "success", "port": port, "message": "Server stopped."}
        else:
            raise PVServerServiceError(f"Failed to stop process for server on port {port}")
            
    except (DatabaseError, PVServerError, PVServerServiceError) as e:
        logger.error(f"Error stopping pvserver on port {port}: {e}")
        raise PVServerServiceError(f"Error stopping pvserver on port {port}: {e}") from e

def list_active_pvservers() -> Dict:
    """Lists all active pvservers. Raises PVServerServiceError on failure."""
    try:
        servers = get_running_pvservers()
        formatted_servers = [
            {
                "task_id": s['task_id'], "port": s['pvserver_port'], "pid": s['pvserver_pid'],
                "case_path": s.get('case_path', 'Unknown'), "status": "running",
                "connection_string": f"localhost:{s['pvserver_port']}",
                "created_at": s.get('created_at', 'Unknown'),
            } for s in servers
        ]
        return {
            "pvservers": formatted_servers, "total_count": len(formatted_servers),
            "port_range": get_port_range(),
            "available_ports": get_available_port_count()
        }
    except (DatabaseError, Exception) as e:
        logger.exception("Failed to list active pvservers")
        raise PVServerServiceError(f"Failed to list pvservers: {e}") from e

def cleanup_inactive_pvservers() -> List[str]:
    """Cleans up pvservers inactive for longer than the configured threshold."""
    logger.info("Starting cleanup of inactive pvservers...")
    try:
        inactive = get_inactive_pvservers(CLEANUP_THRESHOLD_HOURS)
        cleaned_up = []
        for server in inactive:
            task_id, pid, port = server['task_id'], server['pvserver_pid'], server['pvserver_port']
            
            if validator.is_running(server):
                logger.info(f"Stopping inactive running pvserver: Task {task_id}, Port {port}")
                if process_manager.stop_pvserver(pid):
                    set_pvserver_stopped(task_id, "Cleaned up due to inactivity.")
                    cleaned_up.append(f"stopped_task_{task_id}")
            else:
                logger.info(f"Cleaning up dead pvserver DB entry: Task {task_id}")
                set_pvserver_stopped(task_id, "Cleaned up (process was dead).")
                cleaned_up.append(f"cleaned_dead_task_{task_id}")
        
        logger.info(f"Cleanup complete: {len(cleaned_up)} pvservers cleaned up")
        return cleaned_up
    except (DatabaseError, Exception) as e:
        logger.exception("Failed to cleanup inactive pvservers")
        raise PVServerServiceError(f"Failed to cleanup inactive pvservers: {e}") from e

def get_pvserver_info_with_validation(task_id: str) -> Optional[Dict]:
    """Gets pvserver information for a task with validation."""
    try:
        return get_pvserver_info(task_id)
    except (DatabaseError, Exception) as e:
        logger.error(f"Error getting pvserver info for task {task_id}: {e}")
        raise PVServerServiceError(f"Error getting pvserver info: {e}") from e

# --- Service Class Wrapper ---

class PVServerService:
    """Service class for PVServer operations"""
    
    def start_pvserver(self, case_path: str, port: Optional[int] = None) -> Dict:
        """Start a pvserver for a case path"""
        result = start_pvserver_for_case(case_path, port)
        return {
            "port": result["port"],
            "pid": result["pid"],
            "case_path": result["case_path"],
            "status": "running",
            "started_at": datetime.now(),
            "connection_string": result["connection_string"],
            "message": result["message"]
        }
    
    def stop_pvserver(self, port: int) -> Dict:
        """Stop a pvserver by port"""
        result = stop_pvserver_by_port(port)
        return {
            "port": port,
            "status": "stopped",
            "message": result["message"]
        }
    
    def list_pvservers(self) -> Dict:
        """List all active pvservers"""
        return list_active_pvservers()
    
    def get_pvserver_info(self, task_id: str) -> Optional[Dict]:
        """Get pvserver info for a task"""
        return get_pvserver_info_with_validation(task_id)
    
    def ensure_pvserver_for_task(self, task_id: str, case_path: str) -> Dict:
        """Ensure pvserver is running for a task"""
        return ensure_pvserver_for_task(task_id, case_path)
    
    def cleanup_inactive(self) -> List[str]:
        """Clean up inactive pvservers"""
        return cleanup_inactive_pvservers() 