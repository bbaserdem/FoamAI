from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import sqlite3
import uuid
from datetime import datetime
import json

from celery_worker import celery_app, generate_mesh_task, run_solver_task, run_openfoam_command_task, cleanup_pvservers_task
from pvserver_manager import get_pvserver_info, cleanup_inactive_pvservers

app = FastAPI(title="FoamAI API", version="1.0.0")

DATABASE_PATH = 'tasks.db'

# Request models
class SubmitScenarioRequest(BaseModel):
    scenario_description: str = Field(..., description="Description of the CFD scenario")
    mesh_complexity: str = Field(default="medium", description="Mesh complexity level (low, medium, high)")
    solver_type: str = Field(default="incompressible", description="Solver type")

class ApprovalRequest(BaseModel):
    approved: bool = Field(..., description="Whether the mesh is approved")
    comments: Optional[str] = Field(None, description="Optional comments")

class OpenFOAMCommandRequest(BaseModel):
    command: str = Field(..., description="OpenFOAM command to run")
    case_path: str = Field(..., description="Path to the OpenFOAM case directory")
    description: Optional[str] = Field(None, description="Description of what the command does")

# Response models
class PVServerInfo(BaseModel):
    status: str = Field(..., description="PVServer status (running, stopped, error)")
    port: Optional[int] = Field(None, description="Port number if running")
    pid: Optional[int] = Field(None, description="Process ID if running")
    connection_string: Optional[str] = Field(None, description="Connection string for ParaView")
    reused: Optional[bool] = Field(None, description="Whether existing server was reused")
    error_message: Optional[str] = Field(None, description="Error message if failed")

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    message: str
    file_path: Optional[str] = None
    case_path: Optional[str] = None
    pvserver: Optional[PVServerInfo] = None
    created_at: Optional[str] = None

class SubmitScenarioResponse(BaseModel):
    task_id: str
    status: str
    message: str

class ResultsResponse(BaseModel):
    task_id: str
    status: str
    message: str
    file_path: Optional[str] = None
    case_path: Optional[str] = None
    output: Optional[str] = None
    pvserver: Optional[PVServerInfo] = None

def create_task_in_db(task_id: str, initial_status: str = "pending", initial_message: str = "Task created"):
    """Create a new task in the database."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO tasks (task_id, status, message, created_at)
        VALUES (?, ?, ?, ?)
    ''', (task_id, initial_status, initial_message, datetime.now()))
    
    conn.commit()
    conn.close()

def get_task_from_db(task_id: str) -> dict:
    """Get task information from the database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def format_pvserver_info(task_data: dict) -> Optional[PVServerInfo]:
    """Format pvserver information from database data."""
    if not task_data.get('pvserver_status'):
        return None
    
    pvserver_info = PVServerInfo(
        status=task_data['pvserver_status'],
        port=task_data.get('pvserver_port'),
        pid=task_data.get('pvserver_pid'),
        error_message=task_data.get('pvserver_error_message')
    )
    
    if pvserver_info.status == 'running' and pvserver_info.port:
        pvserver_info.connection_string = f"localhost:{pvserver_info.port}"
    
    return pvserver_info

@app.get("/")
async def root():
    return {"message": "FoamAI API is running"}

@app.get("/api/health")
async def health_check():
    """Check if the API is running and healthy."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/version")
async def get_version():
    """Get API version information."""
    return {"version": "1.0.0", "api_name": "FoamAI API"}

@app.post("/api/submit_scenario", response_model=SubmitScenarioResponse)
async def submit_scenario(request: SubmitScenarioRequest):
    """Submit a CFD scenario for processing."""
    try:
        task_id = str(uuid.uuid4())
        
        # Create task in database
        create_task_in_db(task_id, "pending", "Scenario submitted, starting mesh generation...")
        
        # Start mesh generation task
        generate_mesh_task.delay(task_id)
        
        return SubmitScenarioResponse(
            task_id=task_id,
            status="pending",
            message="Scenario submitted successfully. Mesh generation started."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit scenario: {str(e)}")

@app.get("/api/task_status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the status of a specific task."""
    task_data = get_task_from_db(task_id)
    
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    pvserver_info = format_pvserver_info(task_data)
    
    return TaskStatusResponse(
        task_id=task_id,
        status=task_data['status'],
        message=task_data['message'],
        file_path=task_data.get('file_path'),
        case_path=task_data.get('case_path'),
        pvserver=pvserver_info,
        created_at=task_data.get('created_at')
    )

@app.post("/api/approve_mesh")
async def approve_mesh(task_id: str, request: ApprovalRequest):
    """Approve or reject the generated mesh."""
    task_data = get_task_from_db(task_id)
    
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task_data['status'] != 'waiting_approval':
        raise HTTPException(status_code=400, detail="Task is not waiting for approval")
    
    if request.approved:
        # Start solver task
        case_path = task_data.get('case_path', '/home/ubuntu/cavity_tutorial')
        run_solver_task.delay(task_id, case_path)
        
        return {"message": "Mesh approved. Simulation started.", "task_id": task_id}
    else:
        # Update task status to rejected
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET status = ?, message = ? WHERE task_id = ?",
            ('rejected', f'Mesh rejected. Comments: {request.comments or "None"}', task_id)
        )
        conn.commit()
        conn.close()
        
        return {"message": "Mesh rejected.", "task_id": task_id}

@app.post("/api/reject_mesh")
async def reject_mesh(task_id: str, request: ApprovalRequest):
    """Reject the generated mesh (alternative endpoint)."""
    request.approved = False
    return await approve_mesh(task_id, request)

@app.get("/api/results/{task_id}", response_model=ResultsResponse)
async def get_results(task_id: str):
    """Get the results of a completed task."""
    task_data = get_task_from_db(task_id)
    
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    pvserver_info = format_pvserver_info(task_data)
    
    return ResultsResponse(
        task_id=task_id,
        status=task_data['status'],
        message=task_data['message'],
        file_path=task_data.get('file_path'),
        case_path=task_data.get('case_path'),
        output=None,  # Could be enhanced to store actual output
        pvserver=pvserver_info
    )

@app.post("/api/run_openfoam_command")
async def run_openfoam_command(request: OpenFOAMCommandRequest):
    """Run a custom OpenFOAM command."""
    try:
        task_id = str(uuid.uuid4())
        
        # Create task in database
        description = request.description or f"Running command: {request.command}"
        create_task_in_db(task_id, "pending", f"Command submitted: {request.command}")
        
        # Start the command task
        run_openfoam_command_task.delay(
            task_id, 
            request.case_path, 
            request.command, 
            description
        )
        
        return {
            "task_id": task_id,
            "status": "pending",
            "message": f"OpenFOAM command submitted: {request.command}",
            "command": request.command,
            "case_path": request.case_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run OpenFOAM command: {str(e)}")

@app.post("/api/cleanup_pvservers")
async def cleanup_pvservers():
    """Manually trigger cleanup of inactive pvservers."""
    try:
        cleaned_up = cleanup_inactive_pvservers()
        return {
            "status": "success",
            "message": f"Cleaned up {len(cleaned_up)} inactive pvservers",
            "cleaned_up": cleaned_up
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup pvservers: {str(e)}")

@app.get("/api/pvserver_info/{task_id}")
async def get_pvserver_info_endpoint(task_id: str):
    """Get detailed pvserver information for a task."""
    task_data = get_task_from_db(task_id)
    
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    pvserver_info = format_pvserver_info(task_data)
    
    if not pvserver_info:
        raise HTTPException(status_code=404, detail="No pvserver information available for this task")
    
    return pvserver_info

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {"error": "Not found", "detail": str(exc)}

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {"error": "Internal server error", "detail": str(exc)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
