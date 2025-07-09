from typing import Optional, Dict, List
from datetime import datetime, timedelta

# Import configuration
from config import MAX_CONCURRENT_PVSERVERS, CLEANUP_THRESHOLD_HOURS

# Import our utility modules
from process_utils import (
    validate_pvserver_pid, start_pvserver, stop_pvserver, 
    get_active_pvserver_summary, setup_signal_handlers,
    PVServerError
)
from port_utils import (
    port_is_available, find_available_port, PortInUseError,
    get_port_range, get_available_port_count
)
from database import (
    # Original DAL functions
    get_running_pvservers, count_running_pvservers, get_running_pvserver_for_case,
    update_pvserver_status, cleanup_stale_pvserver_entry, get_pvserver_info,
    get_inactive_pvservers, link_task_to_pvserver, DatabaseError,
    create_task, update_task_status,
    # Enhanced DAL functions with validation
    get_running_pvservers_validated, get_running_pvserver_for_case_validated,
    get_pvserver_info_validated, count_running_pvservers_validated,
    cleanup_stale_pvserver_entries
)

# Import ProcessValidator for specific validation needs
from process_validator import validator

class PVServerServiceError(Exception):
    """Custom exception for PVServer service-related errors"""
    pass

def cleanup_stale_database_entries():
    """Clean up database entries for dead processes (lazy cleanup)"""
    print("🧹 Performing lazy cleanup of stale database entries...")
    
    try:
        # Use the enhanced DAL function for automatic cleanup
        cleaned_up = cleanup_stale_pvserver_entries()
        
        if cleaned_up:
            print(f"✅ Cleaned up {len(cleaned_up)} stale database entries")
        else:
            print("✅ No stale entries found")
        
        return cleaned_up
    
    except DatabaseError as e:
        print(f"❌ Database error during cleanup: {e}")
        return []

def count_running_pvservers_with_validation() -> int:
    """Count currently running pvservers (with validation)"""
    try:
        # Use the enhanced DAL function which automatically validates
        return count_running_pvservers_validated()
    except DatabaseError as e:
        print(f"❌ Database error counting pvservers: {e}")
        return 0

def get_running_pvserver_for_case_with_validation(case_path: str) -> Optional[Dict]:
    """Get running pvserver info for a specific case directory (with validation)"""
    try:
        # Use the enhanced DAL function which automatically validates and cleans up
        result = get_running_pvserver_for_case_validated(case_path)
        
        if result:
            print(f"✅ Found validated pvserver for case {case_path}")
        else:
            print(f"🔄 No running pvserver found for case {case_path}")
        
        return result
    
    except DatabaseError as e:
        print(f"❌ Database error getting pvserver for case {case_path}: {e}")
        return None

def link_task_to_existing_pvserver(task_id: str, existing_pvserver: Dict):
    """Link a task to an existing pvserver for the same case"""
    link_task_to_pvserver(
        task_id, 
        existing_pvserver['pvserver_port'], 
        existing_pvserver['pvserver_pid']
    )

def ensure_pvserver_for_task(task_id: str, case_path: str) -> Dict:
    """
    Ensure a pvserver is running for the given task and case.
    Uses lazy cleanup and validation for robustness.
    Returns pvserver info or error details.
    
    Args:
        task_id: The task ID requiring a pvserver
        case_path: Path to the OpenFOAM case directory
        
    Returns:
        Dict: Status and details of the pvserver operation
    """
    try:
        # 1. Check if case already has running pvserver (with validation)
        existing = get_running_pvserver_for_case_with_validation(case_path)
        if existing:
            # Process is validated in get_running_pvserver_for_case_with_validation
            link_task_to_existing_pvserver(task_id, existing)
            return {
                "status": "running",
                "port": existing['pvserver_port'],
                "pid": existing['pvserver_pid'],
                "connection_string": f"localhost:{existing['pvserver_port']}",
                "reused": True
            }
        
        # 2. Check concurrent limit (with cleanup)
        if count_running_pvservers_with_validation() >= MAX_CONCURRENT_PVSERVERS:
            error_msg = f"Max {MAX_CONCURRENT_PVSERVERS} concurrent pvservers reached"
            update_pvserver_status(task_id, 'error', error_message=error_msg)
            return {"status": "error", "error_message": error_msg}
        
        # 3. Find available port
        port = find_available_port()
        if not port:
            error_msg = "All ports in configured range are in use"
            update_pvserver_status(task_id, 'error', error_message=error_msg)
            return {"status": "error", "error_message": error_msg}
        
        # 4. Check port availability one more time (race condition protection)
        if not port_is_available(port):
            raise PortInUseError(f"Port {port} is not available")
        
        # 5. Start new pvserver with process group management
        pid = start_pvserver(case_path, port, task_id)
        update_pvserver_status(task_id, 'running', port, pid)
        
        return {
            "status": "running",
            "port": port,
            "pid": pid,
            "connection_string": f"localhost:{port}",
            "reused": False
        }
        
    except (PVServerError, PortInUseError) as e:
        error_msg = str(e)
        update_pvserver_status(task_id, 'error', error_message=error_msg)
        return {"status": "error", "error_message": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        update_pvserver_status(task_id, 'error', error_message=error_msg)
        return {"status": "error", "error_message": error_msg}

def cleanup_inactive_pvservers() -> List[str]:
    """Clean up pvservers that have been inactive for too long"""
    try:
        # Find pvservers older than threshold using DAL
        inactive_servers = get_inactive_pvservers(CLEANUP_THRESHOLD_HOURS)
        
        cleaned_up = []
        for server in inactive_servers:
            task_id = server['task_id']
            pid = server['pvserver_pid'] 
            port = server['pvserver_port']
            
            # Use validator to check if process is running
            if validator.validate_single_record(server):
                # Process is running, try to stop it
                if stop_pvserver(pid):
                    update_pvserver_status(task_id, 'stopped')
                    cleaned_up.append(f"task_{task_id}_port_{port}")
                    print(f"✅ Stopped inactive pvserver: Task {task_id}, PID {pid}, Port {port}")
                else:
                    print(f"❌ Failed to stop pvserver: Task {task_id}, PID {pid}")
            else:
                # Process already dead, just update database
                update_pvserver_status(task_id, 'stopped', 
                                     error_message="Process died (detected during cleanup)")
                cleaned_up.append(f"task_{task_id}_port_{port}_dead")
                print(f"🔄 Cleaned up dead pvserver: Task {task_id}, PID {pid}, Port {port}")
        
        if cleaned_up:
            print(f"✅ Cleaned up {len(cleaned_up)} inactive pvservers")
        else:
            print("✅ No inactive pvservers to clean up")
        
        return cleaned_up
    
    except DatabaseError as e:
        print(f"❌ Database error during cleanup: {e}")
        return []

def get_pvserver_info_with_validation(task_id: str) -> Optional[Dict]:
    """Get pvserver information for a task with process validation"""
    try:
        # Use the enhanced DAL function which automatically validates and updates status
        return get_pvserver_info_validated(task_id)
    
    except DatabaseError as e:
        print(f"❌ Database error getting pvserver info for task {task_id}: {e}")
        return None

def get_service_status() -> Dict:
    """Get comprehensive service status information"""
    try:
        # Get process tracking info
        process_summary = get_active_pvserver_summary()
        
        # Get port availability
        port_range = get_port_range()
        available_ports = get_available_port_count()
        
        # Get database counts
        running_count = count_running_pvservers()
        
        return {
            "process_tracking": process_summary,
            "port_management": {
                "range": port_range,
                "available_ports": available_ports,
                "total_ports": port_range[1] - port_range[0] + 1
            },
            "database_status": {
                "running_pvservers": running_count,
                "max_concurrent": MAX_CONCURRENT_PVSERVERS,
                "cleanup_threshold_hours": CLEANUP_THRESHOLD_HOURS
            },
            "service_health": {
                "can_start_new": available_ports > 0 and running_count < MAX_CONCURRENT_PVSERVERS,
                "ports_exhausted": available_ports == 0,
                "concurrent_limit_reached": running_count >= MAX_CONCURRENT_PVSERVERS
            }
        }
    
    except Exception as e:
        return {
            "error": f"Failed to get service status: {str(e)}",
            "service_health": {
                "can_start_new": False,
                "ports_exhausted": True,
                "concurrent_limit_reached": True
            }
        }

def force_cleanup_all_pvservers() -> Dict:
    """Force cleanup of all tracked pvservers (emergency function)"""
    try:
        # Get all running pvservers from database
        running_servers = get_running_pvservers()
        
        stopped_count = 0
        cleaned_count = 0
        errors = []
        
        for server in running_servers:
            task_id = server['task_id']
            pid = server['pvserver_pid']
            port = server['pvserver_port']
            
            try:
                # Use validator to check if process is running
                if validator.validate_single_record(server):
                    # Process is running, try to stop it
                    if stop_pvserver(pid):
                        stopped_count += 1
                    else:
                        errors.append(f"Failed to stop PID {pid}")
                
                # Update database regardless
                update_pvserver_status(task_id, 'stopped', 
                                     error_message="Forced cleanup")
                cleaned_count += 1
                
            except Exception as e:
                errors.append(f"Error processing task {task_id}: {str(e)}")
        
        return {
            "status": "completed",
            "processes_stopped": stopped_count,
            "database_entries_cleaned": cleaned_count,
            "errors": errors,
            "total_processed": len(running_servers)
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": f"Failed to force cleanup: {str(e)}"
        }

# Direct PVServer Management Functions (for API endpoints)

def start_pvserver_for_case(case_path: str, port: int = None) -> Dict:
    """
    Start a pvserver for a specific case, optionally on a specific port
    
    Args:
        case_path: Path to the OpenFOAM case directory
        port: Optional specific port to use, auto-finds if None
        
    Returns:
        Dict: Status and details of the pvserver operation
    """
    try:
        # 1. Check if case already has a running pvserver
        existing = get_running_pvserver_for_case_with_validation(case_path)
        if existing:
            return {
                "status": "running",
                "port": existing['pvserver_port'],
                "pid": existing['pvserver_pid'],
                "connection_string": f"localhost:{existing['pvserver_port']}",
                "case_path": case_path,
                "message": f"PVServer already running for case {case_path}",
                "reused": True
            }
        
        # 2. Check concurrent limit
        if count_running_pvservers_with_validation() >= MAX_CONCURRENT_PVSERVERS:
            return {
                "status": "error",
                "case_path": case_path,
                "message": f"Max {MAX_CONCURRENT_PVSERVERS} concurrent pvservers reached",
                "error_message": f"Max {MAX_CONCURRENT_PVSERVERS} concurrent pvservers reached"
            }
        
        # 3. Get port (either specified or auto-find)
        if port:
            if not port_is_available(port):
                return {
                    "status": "error",
                    "case_path": case_path,
                    "message": f"Port {port} is not available",
                    "error_message": f"Port {port} is not available"
                }
        else:
            port = find_available_port()
            if not port:
                return {
                    "status": "error",
                    "case_path": case_path,
                    "message": "All ports in configured range are in use",
                    "error_message": "All ports in configured range are in use"
                }
        
        # 4. Create a temporary task ID for this direct pvserver start
        temp_task_id = f"direct_pvserver_{port}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 5. Create the task with case_path
        create_task(temp_task_id, "pending", f"Direct pvserver start for {case_path}")
        update_task_status(temp_task_id, "pending", f"Starting pvserver on port {port}", case_path=case_path)
        
        # 6. Start the pvserver
        pid = start_pvserver(case_path, port, temp_task_id)
        update_pvserver_status(temp_task_id, 'running', port, pid)
        
        return {
            "status": "running",
            "port": port,
            "pid": pid,
            "connection_string": f"localhost:{port}",
            "case_path": case_path,
            "message": f"PVServer started successfully on port {port}",
            "reused": False
        }
        
    except (PVServerError, PortInUseError) as e:
        return {
            "status": "error",
            "case_path": case_path,
            "message": str(e),
            "error_message": str(e)
        }
    except Exception as e:
        return {
            "status": "error",
            "case_path": case_path,
            "message": f"Unexpected error: {str(e)}",
            "error_message": f"Unexpected error: {str(e)}"
        }

def list_active_pvservers() -> Dict:
    """
    List all active pvservers with their details
    
    Returns:
        Dict: List of active pvservers and summary information
    """
    try:
        # Get all validated running pvservers (automatically cleans up stale entries)
        running_servers = get_running_pvservers_validated()
        
        # Format the data
        pvservers = []
        for server in running_servers:
            pvservers.append({
                "task_id": server['task_id'],
                "port": server['pvserver_port'],
                "pid": server['pvserver_pid'],
                "case_path": server.get('case_path', 'Unknown'),
                "connection_string": f"localhost:{server['pvserver_port']}",
                "created_at": server.get('created_at', 'Unknown'),
                "status": "running"
            })
        
        # Get port information
        port_range = get_port_range()
        available_ports = get_available_port_count()
        
        return {
            "pvservers": pvservers,
            "total_count": len(pvservers),
            "port_range": port_range,
            "available_ports": available_ports
        }
        
    except Exception as e:
        return {
            "pvservers": [],
            "total_count": 0,
            "port_range": get_port_range(),
            "available_ports": 0,
            "error": f"Failed to list pvservers: {str(e)}"
        }

def stop_pvserver_by_port(port: int) -> Dict:
    """
    Stop a pvserver running on a specific port
    
    Args:
        port: Port number of the pvserver to stop
        
    Returns:
        Dict: Status and details of the stop operation
    """
    try:
        # Find the pvserver running on this port
        running_servers = get_running_pvservers()
        target_server = None
        
        for server in running_servers:
            if server['pvserver_port'] == port:
                target_server = server
                break
        
        if not target_server:
            return {
                "status": "error",
                "port": port,
                "message": f"No pvserver found running on port {port}",
                "error_message": f"No pvserver found running on port {port}"
            }
        
        task_id = target_server['task_id']
        pid = target_server['pvserver_pid']
        
        # Use validator to check if process is actually running
        if not validator.validate_single_record(target_server):
            # Process is dead, just clean up database
            update_pvserver_status(task_id, 'stopped', 
                                 error_message="Process was already dead")
            return {
                "status": "success",
                "port": port,
                "message": f"PVServer on port {port} was already stopped (cleaned up database entry)"
            }
        
        # Stop the process
        if stop_pvserver(pid):
            update_pvserver_status(task_id, 'stopped')
            return {
                "status": "success",
                "port": port,
                "message": f"PVServer on port {port} stopped successfully"
            }
        else:
            return {
                "status": "error",
                "port": port,
                "message": f"Failed to stop PVServer on port {port}",
                "error_message": f"Failed to stop PVServer on port {port}"
            }
            
    except Exception as e:
        return {
            "status": "error",
            "port": port,
            "message": f"Unexpected error stopping pvserver: {str(e)}",
            "error_message": f"Unexpected error stopping pvserver: {str(e)}"
        }

# Legacy compatibility - these functions maintain the same interface as the original pvserver_manager
def process_is_running(pid: int) -> bool:
    """Check if a process with given PID is still running"""
    return validate_pvserver_pid(pid) 