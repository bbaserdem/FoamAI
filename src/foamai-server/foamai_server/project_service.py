import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

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


def scan_active_run_directory(active_run_path: Path) -> Tuple[List[str], int, int]:
    """
    Scan the active_run directory and return file information.
    
    Args:
        active_run_path: Path to the active_run directory
        
    Returns:
        Tuple of (file_paths, file_count, total_size)
        - file_paths: List of file paths relative to active_run
        - file_count: Number of readable files
        - total_size: Total size of readable files in bytes
    """
    if not active_run_path.exists() or not active_run_path.is_dir():
        return [], 0, 0
    
    files = []
    total_size = 0
    
    try:
        # Use rglob to recursively find all files
        for item in active_run_path.rglob("*"):
            if item.is_file():
                try:
                    # Get path relative to active_run directory
                    relative_path = item.relative_to(active_run_path)
                    files.append(str(relative_path))
                    # Get file size
                    total_size += item.stat().st_size
                except (PermissionError, OSError, FileNotFoundError):
                    # Skip files we can't read or that disappeared
                    continue
    except (PermissionError, OSError):
        # If we can't even scan the directory, return empty results
        return [], 0, 0
    
    return files, len(files), total_size


def read_project_description(project_path: Path) -> str:
    """
    Read the project description from description.txt file.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        Project description string, or empty string if file doesn't exist
    """
    description_file = project_path / "description.txt"
    try:
        if description_file.exists():
            return description_file.read_text(encoding='utf-8').strip()
    except (PermissionError, OSError, UnicodeDecodeError):
        # If we can't read the file, return empty string
        pass
    return ""


def write_project_description(project_path: Path, description: str):
    """
    Write the project description to description.txt file.
    
    Args:
        project_path: Path to the project directory
        description: Description text to write
    """
    if description:
        description_file = project_path / "description.txt"
        try:
            description_file.write_text(description, encoding='utf-8')
        except (PermissionError, OSError):
            # If we can't write the file, don't fail the project creation
            pass


def get_directory_creation_time(directory_path: Path) -> datetime:
    """
    Get the creation time of a directory.
    
    Args:
        directory_path: Path to the directory
        
    Returns:
        datetime object representing creation time
    """
    try:
        stat_info = directory_path.stat()
        # Use st_ctime (creation time on Windows, metadata change time on Unix)
        # Fall back to st_mtime (modification time) if needed
        timestamp = getattr(stat_info, 'st_birthtime', stat_info.st_ctime)
        return datetime.fromtimestamp(timestamp)
    except (OSError, AttributeError):
        # If we can't get the time, return current time as fallback
        return datetime.now()


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
            
            # Write description file if provided
            if description:
                write_project_description(project_path, description)
            
            return {
                "project_name": project_name,
                "project_path": str(project_path),
                "description": description or "",
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
        active_run_path = project_path / "active_run"
        
        # Get project description
        description = read_project_description(project_path)
        
        # Get creation time
        created_at = get_directory_creation_time(project_path)
        
        # Scan active_run directory for files
        files, file_count, total_size = scan_active_run_directory(active_run_path)
        
        return {
            "project_name": project_name,
            "project_path": str(project_path),
            "description": description,
            "created_at": created_at,
            "files": files,
            "file_count": file_count,
            "total_size": total_size
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