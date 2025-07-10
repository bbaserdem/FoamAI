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