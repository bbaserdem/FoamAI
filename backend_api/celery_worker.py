import subprocess
import os
from pathlib import Path
from datetime import datetime
from functools import wraps
from celery import Celery
from celery.signals import worker_ready

# Import cleanup function for the cleanup task only
from pvserver_service import cleanup_inactive_pvservers
from process_utils import (
    setup_signal_handlers,
    get_active_pvserver_summary
)

# Import DAL functions
from database import update_task_status, DatabaseError

# Configure Celery to use Redis as the message broker
celery_app = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

def foam_task(description_template, final_status='completed', get_case_path=None):
    """
    A decorator to create a standardized OpenFOAM Celery task.
    
    Args:
        description_template: Template for progress description (can use format placeholders)
        final_status: Final status to set on success ('completed' or 'waiting_approval')
        get_case_path: Function to extract case_path from task arguments (optional)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(task_id, *args, **kwargs):
            # Extract case_path using the provided function or from arguments
            if get_case_path:
                case_path = get_case_path(*args, **kwargs)
            else:
                # Default: assume first argument is case_path
                case_path = args[0] if args else kwargs.get('case_path')
            
            # Generate command and description from the decorated function
            command_info = func(task_id, *args, **kwargs)
            
            # Handle different return types from the decorated function
            if isinstance(command_info, dict):
                command = command_info['command']
                description = command_info.get('description', description_template.format(*args, **kwargs))
            else:
                command = command_info
                description = description_template.format(*args, **kwargs)
            
            # Update task status to in_progress
            update_task_status(task_id, 'in_progress', description, case_path=case_path)
            
            try:
                # Handle both string and list commands
                if isinstance(command, str):
                    cmd = command.split()
                else:
                    cmd = command
                
                print(f"🔧 Starting {description} for task {task_id}: {cmd}")
                
                # Run the command
                result = subprocess.run(
                    cmd,
                    cwd=case_path, 
                    capture_output=True, 
                    text=True,
                    check=True
                )
                
                print(f"✅ {description} completed for task {task_id}")
                
                # Ensure .foam file exists after operation
                foam_file_path = ensure_foam_file(case_path)
                
                # Generate success message
                success_message = f"{description} completed successfully. Use /api/start_pvserver to start visualization."
                if final_status == 'waiting_approval':
                    success_message += " Please approve."
                
                print(f"🎉 {success_message}")
                
                # Update status to final state
                update_task_status(task_id, final_status, success_message, foam_file_path, case_path)
                
                # Return standardized success response
                return {
                    "status": "SUCCESS", 
                    "message": f"{description} completed successfully", 
                    "output": result.stdout,
                    "foam_file": foam_file_path,
                    "command": " ".join(cmd) if isinstance(cmd, list) else cmd
                }
                
            except subprocess.CalledProcessError as e:
                error_msg = f'{description} failed: {e.stderr}'
                print(f"❌ {error_msg}")
                update_task_status(task_id, 'error', error_msg, case_path=case_path)
                return {
                    "status": "FAILURE", 
                    "message": f"{description} failed", 
                    "error": e.stderr,
                    "command": " ".join(cmd) if isinstance(cmd, list) else cmd
                }
            except Exception as e:
                error_msg = f'Unexpected error during {description}: {str(e)}'
                print(f"❌ {error_msg}")
                update_task_status(task_id, 'error', error_msg, case_path=case_path)
                return {
                    "status": "FAILURE", 
                    "message": f"{description} failed", 
                    "error": str(e),
                    "command": " ".join(cmd) if isinstance(cmd, list) else cmd
                }
        return wrapper
    return decorator

@worker_ready.connect
def setup_worker_signal_handlers(**kwargs):
    """Set up signal handlers when worker starts"""
    print("🚀 Celery worker starting up - setting up signal handlers...")
    setup_signal_handlers()
    
    # Print summary of active processes
    summary = get_active_pvserver_summary()
    print(f"📊 Worker startup summary: {summary}")

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

@celery_app.task
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
        summary = get_active_pvserver_summary()
        print(f"📊 Post-cleanup summary: {summary}")
        
        return {"status": "SUCCESS", "cleaned_up": cleaned_up, "summary": summary}
    except Exception as e:
        error_msg = f"Error during pvserver cleanup: {e}"
        print(f"❌ {error_msg}")
        return {"status": "ERROR", "error": error_msg}

@celery_app.task
def health_check_task():
    """Health check task to monitor system state"""
    try:
        summary = get_active_pvserver_summary()
        print(f"📊 Health check summary: {summary}")
        
        return {
            "status": "SUCCESS", 
            "timestamp": datetime.now().isoformat(),
            "pvserver_summary": summary
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
