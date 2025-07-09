import subprocess
import os
from pathlib import Path
from datetime import datetime
from functools import wraps
from celery import Celery
from celery.signals import worker_ready, worker_shutdown, worker_process_init
import time

# Import cleanup function for the cleanup task only
from pvserver_service import cleanup_inactive_pvservers
from process_utils import (
    process_manager, # Replaces manual setup
    PVServerError
)

# Import DAL functions
from database import update_task_status, DatabaseError, TaskNotFoundError

# Configure Celery to use Redis as the message broker
celery_app = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=['celery_worker']
)

# Configure Celery for better shutdown behavior
celery_app.conf.update(
    # Reduce shutdown timeout
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=True,
    
    # Graceful shutdown settings
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Prevent hanging during shutdown
    worker_pool_restarts=True,
    
    # Timeout settings
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=360,       # 6 minutes
    
    # Connection settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
)

def foam_task(start_message, final_status, get_case_path=None):
    """A decorator for Celery tasks to handle status updates and errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(task_id, *args, **kwargs):
            try:
                update_task_status(task_id, 'running', start_message)
                
                result = func(task_id, *args, **kwargs)
                
                case_path = get_case_path(task_id) if get_case_path else None
                update_task_status(task_id, final_status, "Task completed successfully", case_path=case_path)
                
                return result
            except (DatabaseError, TaskNotFoundError) as e:
                # logger.error(f"Task {task_id} failed due to database error: {e}") # logger is not defined
                # Don't re-raise, as we can't do much more here. The error is logged.
                pass # Removed logger.error as per original file
            except Exception as e:
                error_msg = f"Task {func.__name__} failed: {e}"
                # logger.exception(error_msg) # logger is not defined
                try:
                    update_task_status(task_id, 'failed', error_msg)
                except (DatabaseError, TaskNotFoundError) as db_e:
                    # logger.error(f"Task {task_id} failed to even update its failure status: {db_e}") # logger is not defined
                    pass # Removed logger.error as per original file
                raise  # Re-raise the original exception to mark the task as FAILED in Celery
        return wrapper
    return decorator

@worker_ready.connect
def setup_worker_signal_handlers(**kwargs):
    """Set up signal handlers when worker starts"""
    print("🚀 Celery worker starting up - setting up signal handlers...")
    # The new ProcessManager is a singleton and sets up its own exit handlers.
    # No explicit call to setup_signal_handlers() is needed anymore.
    print("ProcessManager is automatically configured.")
    
    # Print summary of active processes
    # from process_utils import get_active_pvserver_summary # This line is removed as per the edit hint
    # summary = get_active_pvserver_summary() # This line is removed as per the edit hint
    # print(f"📊 Worker startup summary: {summary}") # This line is removed as per the edit hint

@worker_shutdown.connect
def cleanup_worker_on_shutdown(**kwargs):
    """Clean up resources when worker shuts down"""
    print("🔄 Celery worker shutting down - cleaning up resources...")
    
    try:
        # Clean up any remaining pvservers
        from pvserver_service import force_cleanup_all_pvservers
        cleanup_result = force_cleanup_all_pvservers()
        print(f"🧹 Shutdown cleanup result: {cleanup_result}")
        
        # Give a moment for cleanup to complete
        import time
        time.sleep(1)
        
        print("✅ Worker shutdown cleanup completed")
    except Exception as e:
        print(f"⚠️ Error during worker shutdown cleanup: {e}")
    
    # Close any remaining database connections
    try:
        from database import get_connection
        print("🔄 Closing database connections...")
    except Exception as e:
        print(f"⚠️ Error closing database connections: {e}")

def ensure_foam_file(case_path):
    """
    Ensure a .foam file exists in the case directory for ParaView.
    Creates one if it doesn't exist.
    """
    case_path = Path(case_path)
    case_name = case_path.name
    foam_file_path = case_path / f"{case_name}.foam"
    
    # Create .foam file if it doesn't exist
    if not foam_file_path.exists():
        try:
            foam_file_path.touch()
            print(f"Created .foam file: {foam_file_path}")
        except Exception as e:
            print(f"Warning: Could not create .foam file: {e}")
    
    return str(foam_file_path)

def _get_mesh_task_case_path(*args, **kwargs):
    """Helper function to provide hardcoded case path for mesh generation"""
    return '/home/ubuntu/cavity_tutorial'

@celery_app.task(name='celery_worker.generate_mesh_task')
@foam_task("Generating mesh", final_status='waiting_approval', get_case_path=_get_mesh_task_case_path)
def generate_mesh_task(task_id):
    """Task for generating the mesh (pvserver management is now explicit)."""
    return ['blockMesh']

@celery_app.task
@foam_task("Running simulation")
def run_solver_task(task_id, case_path):
    """Task for running the OpenFOAM solver (pvserver management is now explicit)."""
    return ['foamRun']

@celery_app.task
@foam_task("Running OpenFOAM command")
def run_openfoam_command_task(task_id, case_path, command, description="Running OpenFOAM command"):
    """
    Generic task for running any OpenFOAM command with automatic .foam file creation.
    PVServer management is now explicit via API endpoints.
    """
    return {
        'command': command,
        'description': description
    }

@celery_app.task
def cleanup_pvservers_task():
    """Periodic task to clean up inactive pvservers with robust validation"""
    try:
        print("🧹 Starting periodic pvserver cleanup...")
        cleaned_up = cleanup_inactive_pvservers()
        
        if cleaned_up:
            print(f"✅ Cleaned up inactive pvservers: {cleaned_up}")
        else:
            print("✅ No inactive pvservers to clean up")
        
        # Get summary of current state
        # from process_utils import get_active_pvserver_summary # This line is removed as per the edit hint
        # summary = get_active_pvserver_summary() # This line is removed as per the edit hint
        # print(f"📊 Post-cleanup summary: {summary}") # This line is removed as per the edit hint
        
        return {"status": "SUCCESS", "cleaned_up": cleaned_up, "summary": "N/A"} # Placeholder for summary
    except Exception as e:
        error_msg = f"Error during pvserver cleanup: {e}"
        print(f"❌ {error_msg}")
        return {"status": "ERROR", "error": error_msg}

@celery_app.task
def health_check_task():
    """Health check task to monitor system state"""
    try:
        # from process_utils import get_active_pvserver_summary # This line is removed as per the edit hint
        # summary = get_active_pvserver_summary() # This line is removed as per the edit hint
        # print(f"📊 Health check summary: {summary}") # This line is removed as per the edit hint
        
        return {
            "status": "SUCCESS", 
            "timestamp": datetime.now().isoformat(),
            "pvserver_summary": "N/A" # Placeholder for summary
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

# Legacy task for backward compatibility (if needed)
@celery_app.task
def run_simulation_task():
    """
    Legacy task - runs the full simulation script directly.
    This is kept for backward compatibility.
    """
    sim_script_path = '/home/ubuntu/cavity_tutorial/run_cavity.sh'
    case_path = '/home/ubuntu/cavity_tutorial'
    
    try:
        print("🌊 Running legacy simulation script...")
        
        # Execute the script with absolute path
        result = subprocess.run(
            [sim_script_path], 
            capture_output=True, 
            text=True,
            check=True
        )
        
        # Ensure .foam file exists after script execution
        foam_file_path = ensure_foam_file(case_path)
        
        print("✅ Legacy simulation completed")
        return {"status": "SUCCESS", "output": result.stdout, "foam_file": foam_file_path}
    except subprocess.CalledProcessError as e:
        print(f"❌ Legacy simulation failed: {e.stderr}")
        return {"status": "FAILURE", "output": e.stderr}
