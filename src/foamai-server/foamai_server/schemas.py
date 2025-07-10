"""
Pydantic schemas for the FoamAI API.

This module contains all request and response model definitions used by the FastAPI endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Tuple

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

class FileUploadResponse(BaseModel):
    status: str = Field(..., description="Status of the file upload operation")
    project_name: str = Field(..., description="Name of the project where file was uploaded")
    file_path: str = Field(..., description="Path where the file was saved relative to project root")
    absolute_path: str = Field(..., description="Absolute path where the file was saved")
    file_size: int = Field(..., description="Size of the uploaded file in bytes")
    created_directories: List[str] = Field(default_factory=list, description="List of directories that were created")
    overwritten: bool = Field(default=False, description="Whether an existing file was overwritten")
    message: str = Field(..., description="Success message") 