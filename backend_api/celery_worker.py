import subprocess
import sqlite3
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
        
        update_task_status(task_id, 'waiting_approval', 'Mesh generated. Please approve.')
        
        return {"status": "SUCCESS", "message": "Mesh generated successfully", "output": result.stdout}
        
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
        
        # Create .foam file for ParaView
        foam_file_path = f"{case_path}/cavity.foam"
        with open(foam_file_path, 'w') as f:
            f.write("")  # Create empty .foam file
        
        update_task_status(task_id, 'completed', 'Simulation finished successfully.', foam_file_path)
        
        return {"status": "SUCCESS", "message": "Simulation completed successfully", "output": result.stdout}
        
    except subprocess.CalledProcessError as e:
        update_task_status(task_id, 'error', f'Simulation failed: {e.stderr}')
        return {"status": "FAILURE", "message": "Simulation failed", "error": e.stderr}

# Legacy task for backward compatibility (if needed)
@celery_app.task
def run_simulation_task():
    """
    Legacy task - runs the full simulation script directly.
    This is kept for backward compatibility.
    """
    sim_script_path = '/home/ubuntu/cavity_tutorial/run_cavity.sh'
    try:
        # Execute the script with absolute path
        result = subprocess.run(
            [sim_script_path], 
            capture_output=True, 
            text=True,
            check=True
        )
        return {"status": "SUCCESS", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"status": "FAILURE", "output": e.stderr}
