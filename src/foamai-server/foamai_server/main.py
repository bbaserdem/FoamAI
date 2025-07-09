from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Tuple
import uuid
from datetime import datetime
import json

from celery_worker import celery_app, generate_mesh_task, run_solver_task, run_openfoam_command_task, cleanup_pvservers_task
from pvserver_service import (
    get_pvserver_info_with_validation, cleanup_inactive_pvservers,
    start_pvserver_for_case, list_active_pvservers, stop_pvserver_by_port
)
from project_service import (
    create_project, list_projects,
    ProjectConfigurationError, ProjectExistsError, InvalidProjectNameError, ProjectError
)
from database import (
    create_task, get_task, update_task_rejection, 
    DatabaseError, TaskNotFoundError
)

app = FastAPI(title="FoamAI API", version="1.0.0")

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

class StartPVServerRequest(BaseModel):
    case_path: str = Field(..., description="Path to the OpenFOAM case directory")
    port: Optional[int] = Field(None, description="Specific port to use (optional, auto-finds if not specified)")

class ProjectRequest(BaseModel):
    project_name: str = Field(..., description="The name for the new project. Allowed characters: alphanumeric, underscores, dashes, periods.")

# Response models
class PVServerInfo(BaseModel):
    status: str = Field(..., description="PVServer status (running, stopped, error)")
    port: Optional[int] = Field(None, description="Port number if running")
    pid: Optional[int] = Field(None, description="Process ID if running")
    connection_string: Optional[str] = Field(None, description="Connection string for ParaView")
    reused: Optional[bool] = Field(None, description="Whether existing server was reused")
    error_message: Optional[str] = Field(None, description="Error message if failed")

class PVServerStartResponse(BaseModel):
    status: str = Field(..., description="Operation status")
    port: Optional[int] = Field(None, description="Port number if successful")
    pid: Optional[int] = Field(None, description="Process ID if successful")
    connection_string: Optional[str] = Field(None, description="Connection string for ParaView")
    case_path: str = Field(..., description="Case path used")
    message: str = Field(..., description="Status message")
    error_message: Optional[str] = Field(None, description="Error message if failed")

class PVServerListResponse(BaseModel):
    pvservers: List[Dict] = Field(..., description="List of active pvservers")
    total_count: int = Field(..., description="Total number of active pvservers")
    port_range: Tuple[int, int] = Field(..., description="Available port range")
    available_ports: int = Field(..., description="Number of available ports")

class PVServerStopResponse(BaseModel):
    status: str = Field(..., description="Operation status")
    port: int = Field(..., description="Port that was stopped")
    message: str = Field(..., description="Status message")
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

class ProjectResponse(BaseModel):
    status: str = Field(..., description="Status of the project creation")
    project_name: str = Field(..., description="Name of the created project")
    path: str = Field(..., description="Full path to the new project directory")
    message: str = Field(..., description="A descriptive message")

class ProjectListResponse(BaseModel):
    projects: List[str] = Field(..., description="A list of existing project names")
    count: int = Field(..., description="The number of projects found")

# Database functions now replaced by DAL - keeping these for reference during migration
# def create_task_in_db() -> replaced by database.create_task()
# def get_task_from_db() -> replaced by database.get_task()

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

# --- Project Management Endpoints ---

@app.post("/api/projects", response_model=ProjectResponse, status_code=201)
async def create_new_project(request: ProjectRequest):
    """
    Creates a new project directory under the FOAM_RUN path.
    """
    try:
        project_path = create_project(request.project_name)
        return ProjectResponse(
            status="success",
            project_name=request.project_name,
            path=str(project_path),
            message=f"Project '{request.project_name}' created successfully."
        )
    except InvalidProjectNameError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ProjectExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ProjectConfigurationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ProjectError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects", response_model=ProjectListResponse)
async def get_project_list():
    """
    Lists all existing projects in the FOAM_RUN directory.
    """
    try:
        projects = list_projects()
        return ProjectListResponse(projects=projects, count=len(projects))
    except ProjectConfigurationError as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- CFD Task Endpoints ---

@app.post("/api/submit_scenario", response_model=SubmitScenarioResponse)
async def submit_scenario(request: SubmitScenarioRequest):
    """Submit a CFD scenario for processing."""
    try:
        task_id = str(uuid.uuid4())
        
        # Create task in database using DAL
        if not create_task(task_id, "pending", "Scenario submitted, starting mesh generation..."):
            raise HTTPException(status_code=500, detail="Failed to create task in database")
        
        # Start mesh generation task
        generate_mesh_task.delay(task_id)
        
        return SubmitScenarioResponse(
            task_id=task_id,
            status="pending",
            message="Scenario submitted successfully. Mesh generation started."
        )
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit scenario: {str(e)}")

@app.get("/api/task_status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the status of a specific task."""
    try:
        task_data = get_task(task_id)
        
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
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/approve_mesh")
async def approve_mesh(task_id: str, request: ApprovalRequest):
    """Approve or reject the generated mesh."""
    try:
        task_data = get_task(task_id)
        
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
            # Update task status to rejected using DAL
            if not update_task_rejection(task_id, request.comments):
                raise HTTPException(status_code=500, detail="Failed to update task status")
            
            return {"message": "Mesh rejected.", "task_id": task_id}
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/reject_mesh")
async def reject_mesh(task_id: str, request: ApprovalRequest):
    """Reject the generated mesh (alternative endpoint)."""
    request.approved = False
    return await approve_mesh(task_id, request)

@app.get("/api/results/{task_id}", response_model=ResultsResponse)
async def get_results(task_id: str):
    """Get the results of a completed task."""
    try:
        task_data = get_task(task_id)
        
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
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/run_openfoam_command")
async def run_openfoam_command(request: OpenFOAMCommandRequest):
    """Run a custom OpenFOAM command."""
    try:
        task_id = str(uuid.uuid4())
        
        # Create task in database using DAL
        description = request.description or f"Running command: {request.command}"
        if not create_task(task_id, "pending", f"Command submitted: {request.command}"):
            raise HTTPException(status_code=500, detail="Failed to create task in database")
        
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
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
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
    try:
        # Use the new service function with validation
        pvserver_data = get_pvserver_info_with_validation(task_id)
        
        if not pvserver_data:
            raise HTTPException(status_code=404, detail="Task not found or no pvserver information available")
        
        # Convert to PVServerInfo format
        pvserver_info = PVServerInfo(
            status=pvserver_data['pvserver_status'],
            port=pvserver_data.get('pvserver_port'),
            pid=pvserver_data.get('pvserver_pid'),
            connection_string=pvserver_data.get('connection_string'),
            error_message=pvserver_data.get('pvserver_error_message')
        )
        
        return pvserver_info
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/start_pvserver", response_model=PVServerStartResponse)
async def start_pvserver_endpoint(request: StartPVServerRequest):
    """Start a pvserver for a specific case directory."""
    try:
        result = start_pvserver_for_case(request.case_path, request.port)
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        return PVServerStartResponse(
            status=result["status"],
            port=result.get("port"),
            pid=result.get("pid"),
            connection_string=result.get("connection_string"),
            case_path=result["case_path"],
            message=result["message"],
            error_message=result.get("error_message")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start pvserver: {str(e)}")

@app.get("/api/pvservers", response_model=PVServerListResponse)
async def list_pvservers_endpoint():
    """List all active pvservers."""
    try:
        result = list_active_pvservers()
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return PVServerListResponse(
            pvservers=result["pvservers"],
            total_count=result["total_count"],
            port_range=result["port_range"],
            available_ports=result["available_ports"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list pvservers: {str(e)}")

@app.delete("/api/pvservers/{port}", response_model=PVServerStopResponse)
async def stop_pvserver_endpoint(port: int):
    """Stop a pvserver running on a specific port."""
    try:
        result = stop_pvserver_by_port(port)
        
        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        
        return PVServerStopResponse(
            status=result["status"],
            port=result["port"],
            message=result["message"],
            error_message=result.get("error_message")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop pvserver: {str(e)}")

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
