import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from config import PROJECTS_BASE_PATH, MAX_UPLOAD_SIZE
from database import (
    create_task, get_task, task_exists, update_task_status, update_task_rejection,
    get_all_tasks, get_tasks_by_status, delete_task, get_database_stats,
    get_all_running_pvservers_combined, count_all_running_pvservers,
    # Project-based pvserver functions
    create_project_pvserver, get_project_pvserver_info, set_project_pvserver_stopped,
    set_project_pvserver_error, get_all_project_pvservers, delete_project_pvserver,
    # Exception classes
    DatabaseError, TaskNotFoundError, ProjectPVServerError
)
from pvserver_service import PVServerService, PVServerServiceError
from project_service import ProjectService, ProjectError
from command_service import command_service, CommandExecutionError
from schemas import (
    TaskCreationRequest, TaskUpdateRequest, TaskResponse, TaskRejectionRequest,
    ProjectCreationRequest, ProjectResponse, ProjectListResponse, ProjectInfoResponse,
    FileUploadResponse, PVServerStartRequest, PVServerResponse, PVServerListResponse,
    PVServerStopResponse, ProjectPVServerStartRequest, ProjectPVServerResponse,
    ProjectPVServerInfoResponse, ProjectPVServerStopResponse, CombinedPVServerResponse,
    CommandRequest, CommandResponse,
    ErrorResponse, HealthCheckResponse, DatabaseStatsResponse
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
project_service = ProjectService()
pvserver_service = PVServerService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting FoamAI Server...")
    yield
    logger.info("Shutting down FoamAI Server...")

app = FastAPI(
    title="FoamAI Server",
    description="Backend API for FoamAI - AI-powered OpenFOAM simulation platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(ProjectError)
async def project_error_handler(request: Request, exc: ProjectError):
    """Handle project-related errors"""
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            detail=str(exc),
            error_type="ProjectError",
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )

@app.exception_handler(PVServerServiceError)
async def pvserver_error_handler(request: Request, exc: PVServerServiceError):
    """Handle pvserver-related errors"""
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            detail=str(exc),
            error_type="PVServerServiceError",
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )

@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError):
    """Handle database-related errors"""
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail=str(exc),
            error_type="DatabaseError",
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )

@app.exception_handler(TaskNotFoundError)
async def task_not_found_handler(request: Request, exc: TaskNotFoundError):
    """Handle task not found errors"""
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            detail=str(exc),
            error_type="TaskNotFoundError",
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )

@app.exception_handler(ProjectPVServerError)
async def project_pvserver_error_handler(request: Request, exc: ProjectPVServerError):
    """Handle project pvserver errors"""
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            detail=str(exc),
            error_type="ProjectPVServerError",
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )

@app.exception_handler(CommandExecutionError)
async def command_execution_error_handler(request: Request, exc: CommandExecutionError):
    """Handle command execution errors"""
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            detail=str(exc),
            error_type="CommandExecutionError",
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle pydantic validation errors"""
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
            "timestamp": datetime.now().isoformat()
        }
    )

# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint"""
    try:
        stats = get_database_stats()
        return HealthCheckResponse(
            status="healthy",
            timestamp=datetime.now(),
            database_connected=True,
            running_pvservers=stats.get('running_task_pvservers', 0),
            running_project_pvservers=stats.get('running_project_pvservers', 0)
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponse(
            status="unhealthy",
            timestamp=datetime.now(),
            database_connected=False,
            running_pvservers=0,
            running_project_pvservers=0
        )

# =============================================================================
# PROJECT ENDPOINTS
# =============================================================================

@app.post("/api/projects", response_model=ProjectResponse)
async def create_project(request: ProjectCreationRequest):
    """Create a new project"""
    result = project_service.create_project(request.project_name, request.description)
    return ProjectResponse(**result)

@app.get("/api/projects", response_model=ProjectListResponse)
async def list_projects():
    """List all projects"""
    projects = project_service.list_projects()
    return ProjectListResponse(projects=projects, count=len(projects))

@app.get("/api/projects/{project_name}", response_model=ProjectInfoResponse)
async def get_project(project_name: str):
    """Get project information"""
    project_info = project_service.get_project_info(project_name)
    return project_info

@app.delete("/api/projects/{project_name}")
async def delete_project(project_name: str):
    """Delete a project"""
    project_service.delete_project(project_name)
    return {"message": f"Project '{project_name}' deleted successfully"}

# =============================================================================
# FILE UPLOAD ENDPOINTS
# =============================================================================

@app.post("/api/projects/{project_name}/upload", response_model=FileUploadResponse)
async def upload_file(
    project_name: str,
    file: UploadFile = File(...),
    destination_path: str = Form(...)
):
    """Upload a file to a project's active_run directory"""
    # Check if project exists
    if not project_service.project_exists(project_name):
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
    
    # Check file size
    file_size = 0
    content = await file.read()
    file_size = len(content)
    
    if file_size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)}MB"
        )
    
    # Get project root and create active_run directory
    project_root = Path(PROJECTS_BASE_PATH) / project_name
    active_run_dir = project_root / "active_run"
    active_run_dir.mkdir(parents=True, exist_ok=True)
    
    # Construct full file path in active_run directory
    file_path = active_run_dir / destination_path
    
    # Create parent directories if they don't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write file
    with open(file_path, "wb") as f:
        f.write(content)
    
    return FileUploadResponse(
        filename=file.filename or "unknown",
        file_path=str(file_path.relative_to(project_root)),
        file_size=file_size,
        upload_time=datetime.now(),
        message=f"File uploaded successfully to {project_name}/active_run"
    )

# =============================================================================
# COMMAND EXECUTION ENDPOINTS
# =============================================================================

@app.post("/api/projects/{project_name}/run_command", response_model=CommandResponse)
async def run_command(project_name: str, request: CommandRequest):
    """Execute an OpenFOAM command in a project directory"""
    # Check if project exists
    if not project_service.project_exists(project_name):
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
    
    # Get project path
    project_path = Path(PROJECTS_BASE_PATH) / project_name
    
    # Optional: Validate OpenFOAM command (can be disabled for flexibility)
    if not command_service.validate_openfoam_command(request.command):
        suggestions = command_service.get_command_suggestions(request.command)
        suggestion_text = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        logger.warning(f"Unknown OpenFOAM command '{request.command}' for project '{project_name}'{suggestion_text}")
        # Note: We log a warning but don't block execution for flexibility
    
    try:
        # Execute the command
        result = command_service.execute_command(
            project_path=str(project_path),
            command=request.command,
            args=request.args,
            environment=request.environment,
            working_directory=request.working_directory,
            timeout=request.timeout
        )
        
        return CommandResponse(**result)
        
    except CommandExecutionError as e:
        # Re-raise as CommandExecutionError to be handled by the exception handler
        raise e
    except Exception as e:
        logger.error(f"Unexpected error executing command for project '{project_name}': {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error executing command: {str(e)}")

# =============================================================================
# TASK ENDPOINTS
# =============================================================================

@app.post("/api/tasks", response_model=TaskResponse)
async def create_task_endpoint(request: TaskCreationRequest):
    """Create a new task"""
    create_task(request.task_id, request.initial_status, request.initial_message)
    task_data = get_task(request.task_id)
    return TaskResponse(**task_data)

@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task_endpoint(task_id: str):
    """Get task by ID"""
    task_data = get_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return TaskResponse(**task_data)

@app.put("/api/tasks/{task_id}", response_model=TaskResponse)
async def update_task_endpoint(task_id: str, request: TaskUpdateRequest):
    """Update task status and information"""
    update_task_status(task_id, request.status, request.message, request.file_path, request.case_path)
    task_data = get_task(task_id)
    return TaskResponse(**task_data)

@app.post("/api/tasks/{task_id}/reject")
async def reject_task(task_id: str, request: TaskRejectionRequest):
    """Reject a task with optional comments"""
    update_task_rejection(task_id, request.comments)
    return {"message": f"Task '{task_id}' rejected successfully"}

@app.get("/api/tasks")
async def list_tasks(status: Optional[str] = None):
    """List all tasks, optionally filtered by status"""
    if status:
        tasks = get_tasks_by_status(status)
    else:
        tasks = get_all_tasks()
    return {"tasks": tasks, "count": len(tasks)}

@app.delete("/api/tasks/{task_id}")
async def delete_task_endpoint(task_id: str):
    """Delete a task"""
    if not task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    delete_task(task_id)
    return {"message": f"Task '{task_id}' deleted successfully"}

# =============================================================================
# LEGACY PVSERVER ENDPOINTS (Task-based)
# =============================================================================

@app.post("/api/start_pvserver", response_model=PVServerResponse)
async def start_pvserver(request: PVServerStartRequest):
    """Start a PVServer for a specific case (legacy task-based)"""
    result = pvserver_service.start_pvserver(request.case_path)
    return PVServerResponse(**result)

@app.delete("/api/pvservers/{port}", response_model=PVServerStopResponse)
async def stop_pvserver(port: int):
    """Stop a PVServer by port (legacy)"""
    result = pvserver_service.stop_pvserver(port)
    return PVServerStopResponse(**result)

@app.get("/api/pvservers", response_model=CombinedPVServerResponse)
async def list_all_pvservers():
    """List all running PVServers (both task and project-based)"""
    all_pvservers = get_all_running_pvservers_combined()
    
    # Separate task and project pvservers
    task_pvservers = [pv for pv in all_pvservers if pv.get('source') == 'task']
    project_pvservers = [pv for pv in all_pvservers if pv.get('source') == 'project']
    
    return CombinedPVServerResponse(
        task_pvservers=task_pvservers,
        project_pvservers=project_pvservers,
        total_count=len(all_pvservers),
        running_count=len(all_pvservers)
    )

# =============================================================================
# PROJECT-BASED PVSERVER ENDPOINTS
# =============================================================================

@app.post("/api/projects/{project_name}/pvserver/start", response_model=ProjectPVServerResponse)
async def start_project_pvserver(project_name: str, request: ProjectPVServerStartRequest):
    """Start a PVServer for a project using its active_run directory"""
    # Check if project exists
    if not project_service.project_exists(project_name):
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")
    
    # Construct active_run path
    project_root = Path(PROJECTS_BASE_PATH) / project_name
    active_run_path = project_root / "active_run"
    
    # Create active_run directory if it doesn't exist
    active_run_path.mkdir(parents=True, exist_ok=True)
    
    # Check if project already has a running pvserver
    existing_pvserver = get_project_pvserver_info(project_name)
    if existing_pvserver and existing_pvserver.get('status') == 'running':
        raise HTTPException(
            status_code=400,
            detail=f"Project '{project_name}' already has a running pvserver on port {existing_pvserver['port']}"
        )
    
    # Start the pvserver
    result = pvserver_service.start_pvserver(str(active_run_path))
    
    # Store in project pvserver database
    create_project_pvserver(
        project_name=project_name,
        port=result['port'],
        pid=result['pid'],
        case_path=str(active_run_path)
    )
    
    # Get the stored record to return complete info
    pvserver_info = get_project_pvserver_info(project_name)
    
    if not pvserver_info:
        raise ProjectPVServerError(f"Failed to retrieve pvserver info for project '{project_name}' after creation")
    
    return ProjectPVServerResponse(
        project_name=project_name,
        port=pvserver_info['port'],
        pid=pvserver_info['pid'],
        case_path=pvserver_info['case_path'],
        status=pvserver_info['status'],
        started_at=pvserver_info['started_at'],
        last_activity=pvserver_info['last_activity'],
        connection_string=pvserver_info.get('connection_string', f"localhost:{pvserver_info['port']}"),
        message=f"PVServer started successfully for project '{project_name}'"
    )

@app.delete("/api/projects/{project_name}/pvserver/stop", response_model=ProjectPVServerStopResponse)
async def stop_project_pvserver(project_name: str):
    """Stop the PVServer for a project"""
    # Get project pvserver info
    pvserver_info = get_project_pvserver_info(project_name)
    if not pvserver_info:
        raise HTTPException(status_code=404, detail=f"No pvserver found for project '{project_name}'")
    
    if pvserver_info.get('status') != 'running':
        raise HTTPException(
            status_code=400, 
            detail=f"PVServer for project '{project_name}' is not running (status: {pvserver_info.get('status')})"
        )
    
    # Stop the pvserver process
    try:
        pvserver_service.stop_pvserver(pvserver_info['port'])
    except PVServerServiceError as e:
        logger.warning(f"Failed to stop pvserver process: {e}")
        # Continue to update database even if process stop failed
    
    # Update database
    set_project_pvserver_stopped(project_name, "Stopped via API")
    
    return ProjectPVServerStopResponse(
        project_name=project_name,
        status="stopped",
        message=f"PVServer for project '{project_name}' stopped successfully",
        stopped_at=datetime.now()
    )

@app.get("/api/projects/{project_name}/pvserver/info", response_model=ProjectPVServerInfoResponse)
async def get_project_pvserver_info_endpoint(project_name: str):
    """Get PVServer information for a project"""
    pvserver_info = get_project_pvserver_info(project_name)
    
    if not pvserver_info:
        return ProjectPVServerInfoResponse(
            project_name=project_name,
            status="not_found"
        )
    
    return ProjectPVServerInfoResponse(
        project_name=project_name,
        port=pvserver_info.get('port'),
        pid=pvserver_info.get('pid'),
        case_path=pvserver_info.get('case_path'),
        status=pvserver_info['status'],
        started_at=pvserver_info.get('started_at'),
        last_activity=pvserver_info.get('last_activity'),
        connection_string=pvserver_info.get('connection_string'),
        error_message=pvserver_info.get('error_message')
    )

# =============================================================================
# SYSTEM ENDPOINTS
# =============================================================================

@app.get("/api/system/stats", response_model=DatabaseStatsResponse)
async def get_system_stats():
    """Get system statistics"""
    stats = get_database_stats()
    return DatabaseStatsResponse(
        total_tasks=stats.get('total_tasks', 0),
        running_task_pvservers=stats.get('running_task_pvservers', 0),
        total_project_pvservers=stats.get('total_project_pvservers', 0),
        running_project_pvservers=stats.get('running_project_pvservers', 0),
        timestamp=datetime.now()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
