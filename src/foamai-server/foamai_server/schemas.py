"""
Pydantic schemas for the FoamAI API.

This module contains all request and response model definitions used by the FastAPI endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# =============================================================================
# TASK-RELATED SCHEMAS
# =============================================================================

class TaskCreationRequest(BaseModel):
    task_id: str = Field(..., description="Unique identifier for the task")
    initial_status: str = Field(default="pending", description="Initial status of the task")
    initial_message: str = Field(default="Task created", description="Initial message for the task")

class TaskUpdateRequest(BaseModel):
    status: str = Field(..., description="New status for the task")
    message: str = Field(..., description="Status update message")
    file_path: Optional[str] = Field(None, description="Optional file path associated with the task")
    case_path: Optional[str] = Field(None, description="Optional case path for the task")

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
    file_path: Optional[str] = None
    case_path: Optional[str] = None
    created_at: datetime
    # PVServer fields (for task-based pvservers)
    pvserver_port: Optional[int] = None
    pvserver_pid: Optional[int] = None
    pvserver_status: Optional[str] = None
    pvserver_started_at: Optional[datetime] = None
    pvserver_last_activity: Optional[datetime] = None
    pvserver_error_message: Optional[str] = None

class TaskRejectionRequest(BaseModel):
    comments: Optional[str] = Field(None, description="Optional comments about the rejection")

# =============================================================================
# PROJECT-RELATED SCHEMAS
# =============================================================================

class ProjectCreationRequest(BaseModel):
    project_name: str = Field(..., description="Name of the project to create")
    description: Optional[str] = Field(None, description="Optional description of the project")

class ProjectResponse(BaseModel):
    project_name: str
    project_path: str
    description: Optional[str] = None
    created: bool

class ProjectListResponse(BaseModel):
    projects: List[str]
    count: int

class ProjectInfoResponse(BaseModel):
    """Enhanced response for project info with file listing and metadata"""
    project_name: str
    project_path: str
    description: str
    created_at: datetime
    files: List[str]
    file_count: int
    total_size: int

# =============================================================================
# FILE UPLOAD SCHEMAS
# =============================================================================

class FileUploadResponse(BaseModel):
    filename: str
    file_path: str
    file_size: int
    upload_time: datetime
    message: str

# =============================================================================
# PVSERVER SCHEMAS
# =============================================================================

class PVServerStartRequest(BaseModel):
    case_path: str = Field(..., description="Path to the OpenFOAM case directory")

class PVServerResponse(BaseModel):
    port: int
    pid: int
    case_path: str
    status: str
    started_at: datetime
    connection_string: str
    message: str

class PVServerListResponse(BaseModel):
    pvservers: List[Dict[str, Any]]
    count: int

class PVServerStopResponse(BaseModel):
    port: int
    status: str
    message: str

class ClearAllPVServersResponse(BaseModel):
    """Response for clearing all pvserver processes"""
    status: str
    total_stopped: int
    total_failed: int
    database_stopped: int
    database_failed: int
    system_stopped: int
    system_failed: int
    errors: List[str]
    message: str

# =============================================================================
# PROJECT-BASED PVSERVER SCHEMAS
# =============================================================================

class ProjectPVServerStartRequest(BaseModel):
    """Request to start a pvserver for a project (uses active_run directory)"""
    pass  # No additional fields needed - project_name comes from path, uses active_run

class ProjectPVServerResponse(BaseModel):
    """Response for project pvserver operations"""
    project_name: str
    port: int
    pid: int
    case_path: str
    status: str
    started_at: datetime
    last_activity: datetime
    connection_string: str
    message: str
    error_message: Optional[str] = None

class ProjectPVServerInfoResponse(BaseModel):
    """Response for project pvserver info"""
    project_name: str
    port: Optional[int] = None
    pid: Optional[int] = None
    case_path: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    connection_string: Optional[str] = None
    error_message: Optional[str] = None

class ProjectPVServerStopResponse(BaseModel):
    """Response for stopping a project pvserver"""
    project_name: str
    status: str
    message: str
    stopped_at: datetime

# =============================================================================
# COMBINED PVSERVER SCHEMAS
# =============================================================================

class CombinedPVServerResponse(BaseModel):
    """Response for listing all pvservers (both task and project-based)"""
    task_pvservers: List[Dict[str, Any]]
    project_pvservers: List[Dict[str, Any]]
    total_count: int
    running_count: int

# =============================================================================
# ERROR SCHEMAS
# =============================================================================

class ErrorResponse(BaseModel):
    detail: str
    error_type: str
    timestamp: datetime

class ValidationErrorResponse(BaseModel):
    detail: str
    errors: List[Dict[str, Any]]
    timestamp: datetime

# =============================================================================
# COMMAND EXECUTION SCHEMAS
# =============================================================================

class CommandRequest(BaseModel):
    """Request to execute a command in a project directory"""
    command: str = Field(..., description="Command to execute (e.g., 'blockMesh')")
    args: Optional[List[str]] = Field(None, description="List of command arguments")
    environment: Optional[Dict[str, str]] = Field(None, description="Additional environment variables")
    working_directory: str = Field("active_run", description="Working directory within project (default: active_run)")
    timeout: Optional[int] = Field(None, description="Timeout in seconds (default: 300)")
    save_run: Optional[bool] = Field(False, description="Save a copy of the active_run directory after successful execution (default: false)")

class CommandResponse(BaseModel):
    """Response from command execution"""
    success: bool = Field(..., description="Whether the command executed successfully")
    exit_code: int = Field(..., description="Exit code of the command")
    stdout: str = Field(..., description="Standard output from the command")
    stderr: str = Field(..., description="Standard error from the command")
    execution_time: float = Field(..., description="Execution time in seconds")
    command: str = Field(..., description="Full command that was executed")
    working_directory: str = Field(..., description="Directory where command was executed")
    timestamp: str = Field(..., description="ISO timestamp of execution")
    saved_run_directory: Optional[str] = Field(None, description="Directory name where the run was saved (e.g., 'run_000')")

# =============================================================================
# SYSTEM SCHEMAS
# =============================================================================

class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime
    database_connected: bool
    running_pvservers: int
    running_project_pvservers: int

class DatabaseStatsResponse(BaseModel):
    total_tasks: int
    running_task_pvservers: int
    total_project_pvservers: int
    running_project_pvservers: int
    timestamp: datetime 