from fastapi import FastAPI
from fastapi.responses import JSONResponse
# Import the task from your celery_worker.py file
from celery_worker import run_simulation_task

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "OpenFOAM API Server is running"}

@app.post("/submit_scenario")
def submit_scenario():
    """
    This endpoint is now asynchronous. 
    It adds the simulation task to the queue and returns immediately.
    """
    # .delay() is how you send a task to the Celery queue
    task = run_simulation_task.delay()

    # Return a JSON response with the task ID
    return JSONResponse(
        status_code=202, # HTTP 202 Accepted
        content={"task_id": task.id, "status": "submitted"}
    )

# Note: You would also add the /task_status/{task_id} endpoint here
# to allow the client to check on the job's progress.
