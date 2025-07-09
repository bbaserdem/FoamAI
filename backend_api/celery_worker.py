import subprocess
import os
from pathlib import Path
from datetime import datetime
from celery import Celery
from celery.signals import worker_ready

# Import our pvserver management functions
from pvserver_manager import (
    ensure_pvserver_for_task, 
    cleanup_inactive_pvservers,
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

@worker_ready.connect
def setup_worker_signal_handlers(**kwargs):
    """Set up signal handlers when worker starts"""
    print("🚀 Celery worker starting up - setting up signal handlers...")
    setup_signal_handlers()
    
    # Print summary of active processes
    summary = get_active_pvserver_summary()
    print(f"📊 Worker startup summary: {summary}")

# update_task_status function now imported from database.py (DAL)

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

def start_pvserver_for_task(task_id, case_path):
    """
    Start or reuse a pvserver for the given task and case.
    Uses the robust process management from pvserver_manager.
    Returns pvserver info.
    """
    try:
        print(f"🎨 Starting pvserver for task {task_id} in case {case_path}")
        pvserver_info = ensure_pvserver_for_task(task_id, case_path)
        
        if pvserver_info["status"] == "running":
            if pvserver_info.get("reused"):
                print(f"✅ Reusing existing pvserver on port {pvserver_info['port']}")
            else:
                print(f"✅ Started new pvserver on port {pvserver_info['port']}")
        else:
            print(f"❌ Failed to start pvserver: {pvserver_info.get('error_message')}")
        
        return pvserver_info
    except Exception as e:
        print(f"❌ Error starting pvserver for task {task_id}: {e}")
        return {"status": "error", "error_message": str(e)}

@celery_app.task
def generate_mesh_task(task_id):
    """Task for generating the mesh with robust pvserver management."""
    case_path = '/home/ubuntu/cavity_tutorial'
    update_task_status(task_id, 'in_progress', 'Generating mesh...', case_path=case_path)
    
    try:
        print(f"🔧 Starting mesh generation for task {task_id}")
        
        # Run blockMesh on the cavity case
        result = subprocess.run(
            ['blockMesh'], 
            cwd=case_path, 
            capture_output=True, 
            text=True,
            check=True
        )
        
        print(f"✅ Mesh generation completed for task {task_id}")
        
        # Ensure .foam file exists after mesh generation
        foam_file_path = ensure_foam_file(case_path)
        
        # Start pvserver for visualization with robust process management
        pvserver_info = start_pvserver_for_task(task_id, case_path)
        
        # Update status with success message
        if pvserver_info["status"] == "running":
            reused_msg = " (reusing existing)" if pvserver_info.get("reused") else ""
            message = f"Mesh generated. PVServer ready on port {pvserver_info['port']}{reused_msg}. Please approve."
            print(f"🎉 {message}")
        else:
            message = f"Mesh generated. PVServer error: {pvserver_info.get('error_message', 'Unknown error')}. Please approve."
            print(f"⚠️  {message}")
        
        update_task_status(task_id, 'waiting_approval', message, foam_file_path, case_path)
        
        return {
            "status": "SUCCESS", 
            "message": "Mesh generated successfully", 
            "output": result.stdout, 
            "foam_file": foam_file_path,
            "pvserver": pvserver_info
        }
        
    except subprocess.CalledProcessError as e:
        error_msg = f'Mesh generation failed: {e.stderr}'
        print(f"❌ {error_msg}")
        update_task_status(task_id, 'error', error_msg, case_path=case_path)
        return {"status": "FAILURE", "message": "Mesh generation failed", "error": e.stderr}
    except Exception as e:
        error_msg = f'Unexpected error during mesh generation: {str(e)}'
        print(f"❌ {error_msg}")
        update_task_status(task_id, 'error', error_msg, case_path=case_path)
        return {"status": "FAILURE", "message": "Mesh generation failed", "error": str(e)}

@celery_app.task
def run_solver_task(task_id, case_path):
    """Task for running the OpenFOAM solver with robust pvserver management."""
    update_task_status(task_id, 'in_progress', 'Simulation running...', case_path=case_path)
    
    try:
        print(f"🌊 Starting simulation for task {task_id}")
        
        # Run the full cavity simulation using foamRun
        result = subprocess.run(
            ['foamRun'], 
            cwd=case_path, 
            capture_output=True, 
            text=True,
            check=True
        )
        
        print(f"✅ Simulation completed for task {task_id}")
        
        # Ensure .foam file exists after simulation
        foam_file_path = ensure_foam_file(case_path)
        
        # Start or reuse pvserver for visualization
        pvserver_info = start_pvserver_for_task(task_id, case_path)
        
        # Update status with completion message
        if pvserver_info["status"] == "running":
            reused_msg = " (reusing existing)" if pvserver_info.get("reused") else ""
            message = f"Simulation complete. Results ready on PVServer port {pvserver_info['port']}{reused_msg}."
            print(f"🎉 {message}")
        else:
            message = f"Simulation complete. PVServer error: {pvserver_info.get('error_message', 'Unknown error')}."
            print(f"⚠️  {message}")
        
        update_task_status(task_id, 'completed', message, foam_file_path, case_path)
        
        return {
            "status": "SUCCESS", 
            "message": "Simulation completed successfully", 
            "output": result.stdout, 
            "foam_file": foam_file_path,
            "pvserver": pvserver_info
        }
        
    except subprocess.CalledProcessError as e:
        error_msg = f'Simulation failed: {e.stderr}'
        print(f"❌ {error_msg}")
        update_task_status(task_id, 'error', error_msg, case_path=case_path)
        return {"status": "FAILURE", "message": "Simulation failed", "error": e.stderr}
    except Exception as e:
        error_msg = f'Unexpected error during simulation: {str(e)}'
        print(f"❌ {error_msg}")
        update_task_status(task_id, 'error', error_msg, case_path=case_path)
        return {"status": "FAILURE", "message": "Simulation failed", "error": str(e)}

@celery_app.task
def run_openfoam_command_task(task_id, case_path, command, description="Running OpenFOAM command"):
    """
    Generic task for running any OpenFOAM command with automatic .foam file creation
    and robust pvserver management.
    """
    update_task_status(task_id, 'in_progress', description, case_path=case_path)
    
    try:
        print(f"🔧 Starting OpenFOAM command for task {task_id}: {command}")
        
        # Handle both string and list commands
        if isinstance(command, str):
            cmd = command.split()
        else:
            cmd = command
            
        # Run the OpenFOAM command
        result = subprocess.run(
            cmd,
            cwd=case_path, 
            capture_output=True, 
            text=True,
            check=True
        )
        
        print(f"✅ OpenFOAM command completed for task {task_id}")
        
        # Always ensure .foam file exists after any OpenFOAM operation
        foam_file_path = ensure_foam_file(case_path)
        
        # Start or reuse pvserver for visualization
        pvserver_info = start_pvserver_for_task(task_id, case_path)
        
        # Update status with completion message
        if pvserver_info["status"] == "running":
            reused_msg = " (reusing existing)" if pvserver_info.get("reused") else ""
            message = f"{description} completed. Results ready on PVServer port {pvserver_info['port']}{reused_msg}."
            print(f"🎉 {message}")
        else:
            message = f"{description} completed. PVServer error: {pvserver_info.get('error_message', 'Unknown error')}."
            print(f"⚠️  {message}")
        
        update_task_status(task_id, 'completed', message, foam_file_path, case_path)
        
        return {
            "status": "SUCCESS", 
            "message": f"{description} completed successfully", 
            "output": result.stdout,
            "foam_file": foam_file_path,
            "command": " ".join(cmd),
            "pvserver": pvserver_info
        }
        
    except subprocess.CalledProcessError as e:
        error_msg = f'{description} failed: {e.stderr}'
        print(f"❌ {error_msg}")
        update_task_status(task_id, 'error', error_msg, case_path=case_path)
        return {"status": "FAILURE", "message": f"{description} failed", "error": e.stderr, "command": " ".join(cmd)}
    except Exception as e:
        error_msg = f'Unexpected error during {description}: {str(e)}'
        print(f"❌ {error_msg}")
        update_task_status(task_id, 'error', error_msg, case_path=case_path)
        return {"status": "FAILURE", "message": f"{description} failed", "error": str(e), "command": " ".join(cmd)}

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
