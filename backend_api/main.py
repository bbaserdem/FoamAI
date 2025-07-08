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
    feedback: str | None = None

class MeshRejectionRequest(BaseModel):
    task_id: str
    approved: bool
    feedback: str | None = None

# Health check endpoint
@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "FoamAI API is running"}

# Version endpoint
@app.get("/api/version")
def get_version():
    """Get API version"""
    return {"version": "1.0.0", "name": "FoamAI Backend API"}

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "FoamAI Backend API Server is running"}

@app.post("/api/submit_scenario")
def submit_scenario(request: ScenarioRequest):
    """Submit a simulation scenario"""
    task_id = str(uuid.uuid4())
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (task_id, status, message) VALUES (?, ?, ?)",
        (task_id, "submitted", f"Understood: {request.scenario[:50]}... Generating mesh...")
    )
    conn.commit()
    conn.close()

    # Start mesh generation task
    generate_mesh_task.delay(task_id)
    
    return JSONResponse(
        status_code=202, 
        content={
            "status": "success",
            "task_id": task_id,
            "message": f"Understood: {request.scenario[:50]}... Generating mesh...",
            "estimated_time": 30
        }
    )

@app.get("/api/task_status/{task_id}")
def get_task_status(task_id: str):
    """Check task status"""
    conn = sqlite3.connect(DATABASE_PATH)
    # Return rows as dictionaries
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = dict(result)
    
    # Map database status to API response format
    response = {
        "task_id": task_data["task_id"],
        "status": task_data["status"],
        "message": task_data["message"],
        "progress": 65 if task_data["status"] == "in_progress" else 100 if task_data["status"] == "completed" else 0,
        "file_path": task_data.get("file_path")
    }
    
    return response

@app.post("/api/approve_mesh")
def approve_mesh(request: MeshApprovalRequest):
    """Approve mesh and start simulation"""
    if request.approved:
        new_task_id = str(uuid.uuid4())
        case_path = "/home/ubuntu/cavity_tutorial"  # Use absolute path
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (task_id, status, message, file_path) VALUES (?, ?, ?, ?)",
            (new_task_id, "submitted", "Mesh approved. Starting simulation...", case_path)
        )
        conn.commit()
        conn.close()

        # Start simulation task
        run_solver_task.delay(new_task_id, case_path)
        
        return JSONResponse(
            status_code=202, 
            content={
                "status": "success",
                "message": "Mesh approved. Starting simulation...",
                "new_task_id": new_task_id
            }
        )
    else:
        # Handle rejection by updating the original mesh task
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET status = ?, message = ? WHERE task_id = ?", 
            ("rejected", f"Mesh rejected by user. {request.feedback or ''}", request.task_id)
        )
        conn.commit()
        conn.close()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "rejected", 
                "message": f"Mesh rejected by user. {request.feedback or ''}"
            }
        )

@app.post("/api/reject_mesh")
def reject_mesh(request: MeshRejectionRequest):
    """Reject mesh with feedback"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tasks SET status = ?, message = ? WHERE task_id = ?", 
        ("rejected", f"Mesh rejected by user. {request.feedback or ''}", request.task_id)
    )
    conn.commit()
    conn.close()
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "rejected", 
            "message": f"Mesh rejected by user. {request.feedback or ''}"
        }
    )

@app.get("/api/results/{task_id}")
def get_results(task_id: str):
    """Get simulation results"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = dict(result)
    
    if task_data["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")
    
    # For cavity case, return standard results
    case_path = task_data.get("file_path", "/home/ubuntu/cavity_tutorial")
    
    return {
        "status": "completed",
        "task_id": task_id,
        "file_path": f"{case_path}/cavity.foam",
        "file_type": "openfoam",
        "time_steps": [0, 0.1, 0.2, 0.3, 0.4, 0.5],
        "available_fields": ["p", "U", "k", "epsilon", "nut"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
