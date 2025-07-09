# FoamAI Backend PRD

## 1. Objective

The goal of this project is to create the backend infrastructure for FlowGen, an open-source AI agent that makes Computational Fluid Dynamics (CFD) more accessible. The backend will interpret natural language commands from a desktop client, automate the setup and execution of OpenFOAM simulations, and serve the results for visualization.

This PRD outlines the requirements for an MVP that proves the core asynchronous workflow for a single user and a single simulation template.

## 2. User Stories

**As a student**, I want to simulate airflow over a cylinder by describing the speed in plain English, so that I can quickly visualize the results for my fluid dynamics course without learning complex file syntax.

**As a junior engineer**, I want to model pressure drop in a pipe by specifying the dimensions and flow rate, so that I can get key design metrics without needing a dedicated CFD expert.

**As a hobbyist**, I want to test the effectiveness of cooling airflow on a heated block, so that I can make data-driven decisions for my electronics project.

## 3. Functional Requirements (API Specification)

The backend will be a REST API that communicates with the desktop client. It must handle long-running tasks asynchronously.

- **Protocol**: HTTP
- **Content-Type**: application/json
- **Base URL**: http://server_hostname:8000/api/

### 3.1. Submit Simulation Scenario

**Endpoint**: `POST /api/submit_scenario`

**Description**: Receives a natural language scenario from the client, creates a task, and queues the initial mesh generation job.

**Request Body**:
```json
{
  "scenario": "I want to see effects of 10 mph wind on a cube sitting on the ground",
  "user_id": "optional_user_identifier"
}
```

**Success Response (202 Accepted)**:
```json
{
  "status": "success",
  "task_id": "unique_task_identifier_123"
}
```

### 3.2. Check Task Status

**Endpoint**: `GET /api/task_status/{task_id}`

**Description**: Allows the client to poll for the status of a long-running task.

**Response**:
```json
{
  "task_id": "unique_task_identifier_123",
  "status": "waiting_approval", // "in_progress", "completed", "error"
  "message": "Mesh generated. Please approve.",
  "file_path": null // Or path to results when completed
}
```

### 3.3. Mesh Approval

**Endpoint**: `POST /api/approve_mesh`

**Description**: The client sends user validation for the generated mesh. If approved, the backend queues the simulation solver task.

**Request Body**:
```json
{
  "task_id": "mesh_task_id_123",
  "approved": true
}
```

**Success Response (202 Accepted)**:
```json
{
  "status": "success",
  "message": "Mesh approved. Starting simulation...",
  "new_task_id": "simulation_task_id_456"
}
```

## 4. Technical Architecture

- **Framework**: Python with FastAPI for the REST API
- **Asynchronous Tasks**: Celery will be used to manage background tasks (meshing, solving)
- **Message Broker**: Redis will act as the broker between FastAPI and the Celery workers
- **State Management**: A SQLite database will store the state and metadata of each task (task_id, status, message)
- **Process Management**: Long-running server processes (FastAPI, Celery) will be managed using tmux to ensure they persist after SSH sessions are closed
- **Deployment Target**: A single AWS EC2 instance

## 5. Out of Scope for MVP

**Multi-user Support**: The initial implementation will focus on a single-user workflow. The API will not manage separate sessions, ports, or authentication.

**Multiple Simulation Templates**: The MVP will be hardcoded to use a single OpenFOAM tutorial case (e.g., cavity or pitzDaily).

**Advanced LLM Logic**: The LLM's role will be limited to extracting one or two key parameters from the user's prompt. It will not be generating case files from scratch.

**PVServer Automation**: The initial /approve_mesh and final visualization steps will rely on a single, manually started pvserver instance. The API will not yet manage multiple pvserver processes.

## Appendix A: Current Code Implementation

This is the code developed so far, which serves as the foundation for this implementation.

### database_setup.py

```python
import sqlite3

# Connect to the database (this will create 'tasks.db' if it doesn't exist)
conn = sqlite3.connect('tasks.db')
cursor = conn.cursor()

# Create the tasks table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        status TEXT,
        message TEXT,
        file_path TEXT
    )
''')

conn.commit()
conn.close()

print("Database 'tasks.db' and table 'tasks' created successfully.")
```

### celery_worker.py

```python
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

def update_task_status(task_id, status, message):
    """Helper function to update task status in the database."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
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
    # For now, we'll just use blockMesh on the cavity case
    try:
        subprocess.run(['blockMesh'], cwd='./cavity', check=True)
        update_task_status(task_id, 'waiting_approval', 'Mesh generated. Please approve.')
    except subprocess.CalledProcessError:
        update_task_status(task_id, 'error', 'Mesh generation failed.')

@celery_app.task
def run_solver_task(task_id, case_path):
    """Task for running the OpenFOAM solver."""
    update_task_status(task_id, 'in_progress', 'Simulation running...')
    try:
        subprocess.run(['icoFoam'], cwd=case_path, check=True)
        update_task_status(task_id, 'completed', 'Simulation finished successfully.')
    except subprocess.CalledProcessError:
        update_task_status(task_id, 'error', 'Simulation failed.')
```

### main.py

```python
import sqlite3
import uuid
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import your Celery tasks
from celery_worker import generate_mesh_task, run_solver_task

app = FastAPI()
DATABASE_PATH = 'tasks.db'

# Pydantic models for request body validation
class ScenarioRequest(BaseModel):
    scenario: str
    user_id: str | None = None

class MeshApprovalRequest(BaseModel):
    task_id: str
    approved: bool

@app.post("/api/submit_scenario")
def submit_scenario(request: ScenarioRequest):
    task_id = str(uuid.uuid4())
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (task_id, status, message) VALUES (?, ?, ?)",
        (task_id, "submitted", "Scenario received. Queuing mesh generation.")
    )
    conn.commit()
    conn.close()

    generate_mesh_task.delay(task_id)
    
    return JSONResponse(status_code=202, content={"task_id": task_id})

@app.get("/api/task_status/{task_id}")
def get_task_status(task_id: str):
    conn = sqlite3.connect(DATABASE_PATH)
    # Return rows as dictionaries
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return dict(result)

@app.post("/api/approve_mesh")
def approve_mesh(request: MeshApprovalRequest):
    if request.approved:
        new_task_id = str(uuid.uuid4())
        case_path = os.path.expandvars("$FOAM_RUN/cavity") # Using absolute path
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (task_id, status, message, file_path) VALUES (?, ?, ?, ?)",
            (new_task_id, "submitted", "Mesh approved. Queuing simulation.", case_path)
        )
        conn.commit()
        conn.close()

        run_solver_task.delay(new_task_id, case_path)
        
        return JSONResponse(status_code=202, content={"new_task_id": new_task_id})
    else:
        # Handle rejection by updating the original mesh task
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET status = ? WHERE task_id = ?", ("rejected", request.task_id))
        conn.commit()
        conn.close()
        return {"status": "rejected", "message": "Mesh rejected by user."}
```