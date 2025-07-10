import os
import re
from pathlib import Path
from typing import List, Dict, Optional

from config import PROJECTS_BASE_PATH

class ProjectError(Exception):
    """Base exception for project-related errors."""
    pass

class ProjectConfigurationError(ProjectError):
    """Raised for configuration issues, like missing environment variables."""
    pass

class ProjectExistsError(ProjectError):
    """Raised when a project directory already exists."""
    pass

class InvalidProjectNameError(ProjectError):
    """Raised when a project name contains invalid characters."""
    pass

def get_foam_run_dir() -> Path:
    """
    Retrieves the base directory for projects from the FOAM_RUN environment variable.

    Returns:
        Path: The path to the FOAM_RUN directory.
    
    Raises:
        ProjectConfigurationError: If the FOAM_RUN environment variable is not set.
    """
    foam_run_path = os.environ.get('FOAM_RUN')
    if not foam_run_path:
        raise ProjectConfigurationError("The FOAM_RUN environment variable is not set on the server.")
    
    return Path(foam_run_path)

def validate_project_name(project_name: str):
    """
    Validates the project name against allowed characters.
    Allowed characters: alphanumeric, underscores, dashes, and periods.

    Args:
        project_name (str): The name of the project to validate.

    Raises:
        InvalidProjectNameError: If the project name is invalid.
    """
    if not re.match(r'^[a-zA-Z0-9_.-]+$', project_name):
        raise InvalidProjectNameError(
            f"Project name '{project_name}' contains invalid characters. "
            "Only alphanumeric characters, underscores, dashes, and periods are allowed."
        )

def create_project(project_name: str) -> Path:
    """
    Creates a new project directory.

    Args:
        project_name (str): The name for the new project.

    Returns:
        Path: The path to the newly created project directory.

    Raises:
        ProjectConfigurationError: If FOAM_RUN is not set.
        InvalidProjectNameError: If the project name is invalid.
        ProjectExistsError: If the project directory already exists.
        ProjectError: If an OS-level error occurs during creation.
    """
    validate_project_name(project_name)
    
    base_dir = get_foam_run_dir()
    project_path = base_dir / project_name
    
    if project_path.exists():
        raise ProjectExistsError(f"Project '{project_name}' already exists at {project_path}")
        
    try:
        project_path.mkdir(parents=True, exist_ok=False)
        print(f"✅ Successfully created project directory: {project_path}")
        return project_path
    except OSError as e:
        raise ProjectError(f"Failed to create project directory '{project_name}': {e}")


def list_projects() -> List[str]:
    """
    Lists all existing project directories.

    Returns:
        List[str]: A list of project names.
        
    Raises:
        ProjectConfigurationError: If FOAM_RUN is not set.
    """
    base_dir = get_foam_run_dir()
    
    if not base_dir.is_dir():
        return []

    return [d.name for d in base_dir.iterdir() if d.is_dir()]

# --- Service Class Wrapper ---

class ProjectService:
    """Service class for project operations"""
    
    def __init__(self):
        """Initialize the project service"""
        self.base_path = PROJECTS_BASE_PATH
        # Ensure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def create_project(self, project_name: str, description: Optional[str] = None) -> Dict:
        """Create a new project"""
        validate_project_name(project_name)
        
        project_path = self.base_path / project_name
        
        if project_path.exists():
            raise ProjectExistsError(f"Project '{project_name}' already exists at {project_path}")
            
        try:
            project_path.mkdir(parents=True, exist_ok=False)
            return {
                "project_name": project_name,
                "project_path": str(project_path),
                "description": description,
                "created": True
            }
        except OSError as e:
            raise ProjectError(f"Failed to create project directory '{project_name}': {e}")
    
    def list_projects(self) -> List[str]:
        """List all existing projects"""
        if not self.base_path.is_dir():
            return []
        
        return [d.name for d in self.base_path.iterdir() if d.is_dir()]
    
    def project_exists(self, project_name: str) -> bool:
        """Check if a project exists"""
        project_path = self.base_path / project_name
        return project_path.exists() and project_path.is_dir()
    
    def get_project_info(self, project_name: str) -> Dict:
        """Get project information"""
        if not self.project_exists(project_name):
            raise ProjectError(f"Project '{project_name}' not found")
        
        project_path = self.base_path / project_name
        return {
            "project_path": str(project_path),
            "exists": True,
            "is_directory": project_path.is_dir()
        }
    
    def delete_project(self, project_name: str):
        """Delete a project"""
        if not self.project_exists(project_name):
            raise ProjectError(f"Project '{project_name}' not found")
        
        project_path = self.base_path / project_name
        try:
            import shutil
            shutil.rmtree(project_path)
        except OSError as e:
            raise ProjectError(f"Failed to delete project '{project_name}': {e}")
    
    def get_project_path(self, project_name: str) -> Path:
        """Get the full path to a project"""
        return self.base_path / project_name 