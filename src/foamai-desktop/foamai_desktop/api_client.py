"""
Project API Client for OpenFOAM Desktop Application
Handles all REST API communication with the project-based server
"""
import requests
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from .config import Config

logger = logging.getLogger(__name__)

class ProjectAPIClient:
    """Client for communicating with the OpenFOAM project-based server API"""
    
    def __init__(self):
        self.base_url = Config.get_server_url()
        self.timeout = Config.REQUEST_TIMEOUT
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'OpenFOAM-Desktop-App/1.0'
        })
        
        # Current project context
        self.current_project = None
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                     files: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """
        Make a generic HTTP request to the server
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint key from config
            data: Optional data to send with request
            files: Optional files to upload
            **kwargs: Additional parameters for endpoint formatting
            
        Returns:
            Response data as dictionary
            
        Raises:
            requests.RequestException: If request fails
        """
        try:
            url = Config.get_api_url(endpoint, **kwargs)
            
            logger.info(f"Making {method} request to {url}")
            
            # Prepare request parameters
            request_kwargs = {
                'timeout': self.timeout
            }
            
            if files:
                # For file uploads, don't set Content-Type header
                if data:
                    request_kwargs['data'] = data
                request_kwargs['files'] = files
            else:
                # For JSON requests
                if data:
                    request_kwargs['json'] = data
                    
            if method.upper() == 'GET':
                response = self.session.get(url, **request_kwargs)
            elif method.upper() == 'POST':
                response = self.session.post(url, **request_kwargs)
            elif method.upper() == 'PUT':
                response = self.session.put(url, **request_kwargs)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, **request_kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                return response.json()
            except json.JSONDecodeError:
                return {'message': response.text}
                
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise
    
    # Health and System Information
    def check_health(self) -> Dict[str, Any]:
        """Check server health and status"""
        return self._make_request('GET', 'health')
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        return self._make_request('GET', 'system_stats')
    
    def list_all_pvservers(self) -> Dict[str, Any]:
        """List all running PVServers (task-based and project-based)"""
        return self._make_request('GET', 'list_pvservers')
    
    # Project Management
    def create_project(self, project_name: str, description: str = "") -> Dict[str, Any]:
        """
        Create a new project
        
        Args:
            project_name: Name of the project
            description: Optional description
            
        Returns:
            Server response with project details
        """
        data = {
            'project_name': project_name,
            'description': description
        }
        
        response = self._make_request('POST', 'projects', data)
        
        # Set as current project if successful
        if response.get('project_name'):
            self.current_project = project_name
            
        return response
    
    def list_projects(self) -> Dict[str, Any]:
        """List all projects"""
        return self._make_request('GET', 'projects')
    
    def get_project(self, project_name: str) -> Dict[str, Any]:
        """
        Get information about a specific project
        
        Args:
            project_name: Name of the project
            
        Returns:
            Project details including files and metadata
        """
        return self._make_request('GET', 'project_detail', project_name=project_name)
    
    def delete_project(self, project_name: str) -> Dict[str, Any]:
        """
        Delete a project and all its files
        
        Args:
            project_name: Name of the project to delete
            
        Returns:
            Server response confirming deletion
        """
        response = self._make_request('DELETE', 'project_delete', project_name=project_name)
        
        # Clear current project if it was deleted
        if self.current_project == project_name:
            self.current_project = None
            
        return response
    
    def set_current_project(self, project_name: str) -> bool:
        """
        Set the current project context
        
        Args:
            project_name: Name of the project to set as current
            
        Returns:
            True if project exists and was set, False otherwise
        """
        try:
            # Verify project exists
            self.get_project(project_name)
            self.current_project = project_name
            return True
        except requests.RequestException:
            return False
    
    # File Management
    def upload_file(self, file_path: str, destination_path: str, 
                   project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload a file to a project's active_run directory
        
        Args:
            file_path: Path to the local file to upload
            destination_path: Relative path within active_run directory
            project_name: Project name (uses current project if not specified)
            
        Returns:
            Server response with upload details
        """
        project_name = project_name or self.current_project
        if not project_name:
            raise ValueError("No project specified and no current project set")
        
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Check file size
        file_size = file_path.stat().st_size
        max_size = Config.MAX_UPLOAD_SIZE * 1024 * 1024  # Convert MB to bytes
        if file_size > max_size:
            raise ValueError(f"File too large: {file_size} bytes (max: {max_size} bytes)")
        
        # Prepare file upload
        files = {
            'file': (file_path.name, open(file_path, 'rb'))
        }
        
        data = {
            'destination_path': destination_path
        }
        
        try:
            return self._make_request('POST', 'upload_file', data=data, files=files, 
                                    project_name=project_name)
        finally:
            # Always close the file
            files['file'][1].close()
    
    def upload_multiple_files(self, file_mappings: List[Dict[str, str]], 
                            project_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Upload multiple files to a project
        
        Args:
            file_mappings: List of dicts with 'local_path' and 'destination_path'
            project_name: Project name (uses current project if not specified)
            
        Returns:
            List of server responses for each upload
        """
        results = []
        for mapping in file_mappings:
            try:
                result = self.upload_file(
                    mapping['local_path'], 
                    mapping['destination_path'],
                    project_name
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to upload {mapping['local_path']}: {str(e)}")
                results.append({
                    'success': False,
                    'error': str(e),
                    'file': mapping['local_path']
                })
        
        return results
    
    # Command Execution
    def run_command(self, command: str, args: Optional[List[str]] = None,
                   environment: Optional[Dict[str, str]] = None,
                   working_directory: str = "active_run",
                   timeout: int = 300,
                   project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute an OpenFOAM command in a project directory
        
        Args:
            command: OpenFOAM command to execute
            args: Optional list of command arguments
            environment: Optional environment variables
            working_directory: Directory within project to run command
            timeout: Timeout in seconds
            project_name: Project name (uses current project if not specified)
            
        Returns:
            Server response with command execution results
        """
        project_name = project_name or self.current_project
        if not project_name:
            raise ValueError("No project specified and no current project set")
        
        data = {
            'command': command,
            'args': args or [],
            'environment': environment or {},
            'working_directory': working_directory,
            'timeout': timeout
        }
        
        return self._make_request('POST', 'run_command', data, project_name=project_name)
    
    def run_blockmesh(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """Run blockMesh command"""
        return self.run_command('blockMesh', ['-case', '.'], project_name=project_name)
    
    def run_checkmesh(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """Run checkMesh command"""
        return self.run_command('checkMesh', ['-case', '.'], project_name=project_name)
    
    def run_solver(self, solver: str, project_name: Optional[str] = None, 
                  timeout: int = 1800) -> Dict[str, Any]:
        """Run OpenFOAM solver"""
        return self.run_command(solver, timeout=timeout, project_name=project_name)
    
    def run_foamrun(self, solver: str, project_name: Optional[str] = None,
                   timeout: int = 1800) -> Dict[str, Any]:
        """Run foamRun with specified solver"""
        return self.run_command('foamRun', ['-solver', solver], timeout=timeout, 
                              project_name=project_name)
    
    # ParaView Server Management
    def start_pvserver(self, port: Optional[int] = None, 
                      project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Start a ParaView server for a project
        
        Args:
            port: Optional port number (auto-assigned if not specified)
            project_name: Project name (uses current project if not specified)
            
        Returns:
            Server response with ParaView server details
        """
        project_name = project_name or self.current_project
        if not project_name:
            raise ValueError("No project specified and no current project set")
        
        data = {}
        if port:
            data['port'] = port
        
        return self._make_request('POST', 'start_pvserver', data, project_name=project_name)
    
    def stop_pvserver(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Stop the ParaView server for a project
        
        Args:
            project_name: Project name (uses current project if not specified)
            
        Returns:
            Server response confirming stop
        """
        project_name = project_name or self.current_project
        if not project_name:
            raise ValueError("No project specified and no current project set")
        
        return self._make_request('DELETE', 'stop_pvserver', project_name=project_name)
    
    def get_pvserver_info(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get ParaView server information for a project
        
        Args:
            project_name: Project name (uses current project if not specified)
            
        Returns:
            ParaView server details
        """
        project_name = project_name or self.current_project
        if not project_name:
            raise ValueError("No project specified and no current project set")
        
        return self._make_request('GET', 'pvserver_info', project_name=project_name)
    
    def get_pvserver_connection_string(self, project_name: Optional[str] = None) -> Optional[str]:
        """
        Get ParaView server connection string for a project
        
        Args:
            project_name: Project name (uses current project if not specified)
            
        Returns:
            Connection string (host:port) or None if no server running
        """
        try:
            info = self.get_pvserver_info(project_name)
            return info.get('connection_string')
        except requests.RequestException:
            return None
    
    # Utility Methods
    def test_connection(self) -> bool:
        """
        Test if the server is reachable
        
        Returns:
            True if server is reachable, False otherwise
        """
        try:
            response = self.check_health()
            return response.get('status') == 'healthy'
        except requests.RequestException:
            return False
    
    def get_current_project(self) -> Optional[str]:
        """Get the current project name"""
        return self.current_project
    
    def close(self):
        """Close the session"""
        self.session.close()
    
    def _get_timestamp(self) -> str:
        """Get current timestamp as string"""
        return datetime.now().isoformat()


# For backward compatibility, create alias
APIClient = ProjectAPIClient 