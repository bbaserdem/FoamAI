from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from typing import Optional
import uuid
from datetime import datetime
import json
import os
from pathlib import Path

from schemas import (
    SubmitScenarioRequest, ApprovalRequest, OpenFOAMCommandRequest, StartPVServerRequest, ProjectRequest,
    PVServerInfo, PVServerStartResponse, PVServerListResponse, PVServerStopResponse,
    TaskStatusResponse, SubmitScenarioResponse, ResultsResponse, ProjectResponse, ProjectListResponse,
    FileUploadResponse
)

from celery_worker import celery_app, generate_mesh_task, run_solver_task, run_openfoam_command_task, cleanup_pvservers_task
from pvserver_service import (
    get_pvserver_info_with_validation, cleanup_inactive_pvservers,
    start_pvserver_for_case, list_active_pvservers, stop_pvserver_by_port,
    PVServerServiceError
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

# Set maximum file size to 300MB
MAX_FILE_SIZE = 300 * 1024 * 1024  # 300MB in bytes

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

def get_project_root(project_name: str) -> Path:
    """Get the root directory path for a project."""
    # This uses the same logic as project_service.py
    foam_run = os.environ.get('FOAM_RUN', '/tmp/foam_run')
    return Path(foam_run) / project_name

# Centralized exception handlers
@app.exception_handler(ProjectError)
async def project_error_handler(request, exc: ProjectError):
    """Handle all project-related errors with appropriate HTTP status codes."""
    from fastapi.responses import JSONResponse
    
    if isinstance(exc, InvalidProjectNameError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    elif isinstance(exc, ProjectExistsError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})
    elif isinstance(exc, ProjectConfigurationError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})
    else:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

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
    """Creates a new project directory under the FOAM_RUN path."""
    project_path = create_project(request.project_name)
    return ProjectResponse(
        status="success",
        project_name=request.project_name,
        path=str(project_path),
        message=f"Project '{request.project_name}' created successfully."
    )

@app.get("/api/projects", response_model=ProjectListResponse)
async def get_project_list():
    """Lists all existing projects in the FOAM_RUN directory."""
    projects = list_projects()
    return ProjectListResponse(projects=projects, count=len(projects))

@app.post("/api/projects/{project_name}/upload", response_model=FileUploadResponse)
async def upload_file(
    project_name: str,
    file: UploadFile = File(..., description="The file to upload"),
    destination_path: str = Form(..., description="Relative path within the project's active_run directory where the file should be saved")
):
    """
    Upload a file to a specific project's active_run directory at the given path.
    
    Creates directories as needed and allows overwriting existing files.
    Maximum file size is 300MB.
    """
    try:
        # Check if project exists
        project_root = get_project_root(project_name)
        if not project_root.exists():
            raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
        
        # Check file size
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File size ({file_size} bytes) exceeds maximum allowed size ({MAX_FILE_SIZE} bytes)"
            )
        
        # Construct the full file path within the active_run directory
        active_run_root = project_root / "active_run"
        file_path = active_run_root / destination_path
        absolute_path = file_path.resolve()
        
        # Check if file already exists
        file_existed = file_path.exists()
        
        # Create directories if they don't exist
        created_directories = []
        if not file_path.parent.exists():
            # Track which directories we're creating
            current_path = file_path.parent
            dirs_to_create = []
            
            while not current_path.exists() and current_path != project_root:
                # Show path relative to active_run for cleaner output
                if current_path == active_run_root:
                    dirs_to_create.append("active_run")
                else:
                    relative_path = current_path.relative_to(active_run_root)
                    dirs_to_create.append(f"active_run/{relative_path}")
                current_path = current_path.parent
            
            # Create the directories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            created_directories = list(reversed(dirs_to_create))
        
        # Write the file
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        return FileUploadResponse(
            status="success",
            project_name=project_name,
            file_path=f"active_run/{destination_path}",
            absolute_path=str(absolute_path),
            file_size=file_size,
            created_directories=created_directories,
            overwritten=file_existed,
            message=f"File uploaded successfully to active_run/{destination_path}"
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle any other errors
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

# --- CFD Task Endpoints ---

@app.post("/api/submit_scenario", response_model=SubmitScenarioResponse)
async def submit_scenario(request: SubmitScenarioRequest):
    """Submit a CFD scenario for processing."""
    task_id = str(uuid.uuid4())
    try:
        create_task(task_id, "pending", "Scenario submitted, starting mesh generation...")
        generate_mesh_task.delay(task_id)
        
        return SubmitScenarioResponse(
            task_id=task_id,
            status="pending",
            message="Scenario submitted successfully. Mesh generation started."
        )
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        # Catch other potential errors, e.g., Celery connection issues
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
            update_task_rejection(task_id, request.comments)
            return {"message": "Mesh rejected.", "task_id": task_id}
            
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task with ID '{task_id}' not found.")
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

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
    task_id = str(uuid.uuid4())
    try:
        description = request.description or f"Running command: {request.command}"
        create_task(task_id, "pending", f"Command submitted: {request.command}")
        
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

# --- PVServer Management Endpoints ---

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
    except PVServerServiceError as e:
        raise HTTPException(status_code=500, detail=f"A service error occurred during cleanup: {e}")
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
    except PVServerServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/start_pvserver", response_model=PVServerStartResponse)
async def start_pvserver_endpoint(request: StartPVServerRequest):
    """Start a pvserver for a specific case directory."""
    try:
        result = start_pvserver_for_case(request.case_path, request.port)
        
        return PVServerStartResponse(
            status=result["status"],
            port=result.get("port"),
            pid=result.get("pid"),
            connection_string=result.get("connection_string"),
            case_path=result["case_path"],
            message=result["message"],
            error_message=result.get("error_message")
        )
    except PVServerServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start pvserver: {str(e)}")

@app.get("/api/pvservers", response_model=PVServerListResponse)
async def list_pvservers_endpoint():
    """List all active pvservers."""
    try:
        result = list_active_pvservers()
        
        return PVServerListResponse(
            pvservers=result["pvservers"],
            total_count=result["total_count"],
            port_range=result["port_range"],
            available_ports=result["available_ports"]
        )
    except PVServerServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list pvservers: {str(e)}")

@app.delete("/api/pvservers/{port}", response_model=PVServerStopResponse)
async def stop_pvserver_endpoint(port: int):
    """Stop a pvserver running on a specific port."""
    try:
        result = stop_pvserver_by_port(port)
        
        return PVServerStopResponse(
            status=result["status"],
            port=result["port"],
            message=result["message"],
            error_message=result.get("error_message")
        )
    except PVServerServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
