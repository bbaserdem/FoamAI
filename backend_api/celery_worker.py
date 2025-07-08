import subprocess
from celery import Celery

# Configure Celery to use Redis as the message broker
celery_app = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

@celery_app.task
def run_simulation_task():
    """
    A Celery task to execute the OpenFOAM simulation script.
    This runs in the background, handled by a Celery worker.
    """
    sim_script_path = './run_cavity.sh'
    try:
        # Execute the script. We're assuming it's in the same directory.
        # In a real app, you'd use absolute paths.
        result = subprocess.run(
            [sim_script_path], 
            capture_output=True, 
            text=True,
            check=True # This will raise an exception if the script fails
        )
        return {"status": "SUCCESS", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        # If the script fails, return the error
        return {"status": "FAILURE", "output": e.stderr}
