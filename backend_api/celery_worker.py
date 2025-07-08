import subprocess
import sqlite3
import os
from pathlib import Path
from celery import Celery

# Configure Celery to use Redis as the message broker
celery_app = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

DATABASE_PATH = 'tasks.db'

def update_task_status(task_id, status, message, file_path=None):
    """Helper function to update task status in the database."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    if file_path:
        cursor.execute(
            "UPDATE tasks SET status = ?, message = ?, file_path = ? WHERE task_id = ?",
            (status, message, file_path, task_id)
        )
    else:
        cursor.execute(
            "UPDATE tasks SET status = ?, message = ? WHERE task_id = ?",
            (status, message, task_id)
        )
    conn.commit()
    conn.close()

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

@celery_app.task
def generate_mesh_task(task_id):
    """Task for generating the mesh."""
    update_task_status(task_id, 'in_progress', 'Generating mesh...')
    
    # Use the cavity tutorial directory
    case_path = '/home/ubuntu/cavity_tutorial'
    
    try:
        # Run blockMesh on the cavity case
        result = subprocess.run(
            ['blockMesh'], 
            cwd=case_path, 
            capture_output=True, 
            text=True,
            check=True
        )
        
        # Ensure .foam file exists after mesh generation
        foam_file_path = ensure_foam_file(case_path)
        
        update_task_status(task_id, 'waiting_approval', 'Mesh generated. Please approve.', foam_file_path)
        
        return {"status": "SUCCESS", "message": "Mesh generated successfully", "output": result.stdout, "foam_file": foam_file_path}
        
    except subprocess.CalledProcessError as e:
        update_task_status(task_id, 'error', f'Mesh generation failed: {e.stderr}')
        return {"status": "FAILURE", "message": "Mesh generation failed", "error": e.stderr}

@celery_app.task
def run_solver_task(task_id, case_path):
    """Task for running the OpenFOAM solver."""
    update_task_status(task_id, 'in_progress', 'Simulation running...')
    
    try:
        # Run the full cavity simulation using foamRun
        result = subprocess.run(
            ['foamRun'], 
            cwd=case_path, 
            capture_output=True, 
            text=True,
            check=True
        )
        
        # Ensure .foam file exists after simulation
        foam_file_path = ensure_foam_file(case_path)
        
        update_task_status(task_id, 'completed', 'Simulation finished successfully.', foam_file_path)
        
        return {"status": "SUCCESS", "message": "Simulation completed successfully", "output": result.stdout, "foam_file": foam_file_path}
        
    except subprocess.CalledProcessError as e:
        update_task_status(task_id, 'error', f'Simulation failed: {e.stderr}')
        return {"status": "FAILURE", "message": "Simulation failed", "error": e.stderr}

@celery_app.task
def run_openfoam_command_task(task_id, case_path, command, description="Running OpenFOAM command"):
    """
    Generic task for running any OpenFOAM command with automatic .foam file creation.
    
    Args:
        task_id: Unique task identifier
        case_path: Path to the OpenFOAM case directory
        command: OpenFOAM command to run (string or list)
        description: Description of what the command does
    """
    update_task_status(task_id, 'in_progress', description)
    
    try:
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
        
        # Always ensure .foam file exists after any OpenFOAM operation
        foam_file_path = ensure_foam_file(case_path)
        
        update_task_status(task_id, 'completed', f'{description} completed successfully.', foam_file_path)
        
        return {
            "status": "SUCCESS", 
            "message": f"{description} completed successfully", 
            "output": result.stdout,
            "foam_file": foam_file_path,
            "command": " ".join(cmd)
        }
        
    except subprocess.CalledProcessError as e:
        update_task_status(task_id, 'error', f'{description} failed: {e.stderr}')
        return {"status": "FAILURE", "message": f"{description} failed", "error": e.stderr, "command": " ".join(cmd)}

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
        # Execute the script with absolute path
        result = subprocess.run(
            [sim_script_path], 
            capture_output=True, 
            text=True,
            check=True
        )
        
        # Ensure .foam file exists after script execution
        foam_file_path = ensure_foam_file(case_path)
        
        return {"status": "SUCCESS", "output": result.stdout, "foam_file": foam_file_path}
    except subprocess.CalledProcessError as e:
        return {"status": "FAILURE", "output": e.stderr}
