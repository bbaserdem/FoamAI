"""
Remote Executor - Bridge between LangGraph agents and remote server API.

This module provides a unified interface for the LangGraph agents to interact
with the remote OpenFOAM server, replacing local subprocess calls and file
operations with API calls.
"""

import os
import json
import requests
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from loguru import logger

class RemoteExecutor:
    """
    Remote executor that translates LangGraph agent operations to server API calls.
    
    This class provides the same interface that agents expect for local operations
    but routes everything through the remote server API.
    """
    
    def __init__(self, server_url: str, project_name: str, timeout: int = 300):
        """
        Initialize remote executor.
        
        Args:
            server_url: Base URL of the remote server (e.g., "http://localhost:8000")
            project_name: Name of the project on the server
            timeout: Default timeout for requests in seconds
        """
        self.server_url = server_url.rstrip('/')
        self.project_name = project_name
        self.timeout = timeout
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': 'FoamAI-LangGraph/1.0'
        })
        
        logger.info(f"RemoteExecutor initialized for project '{project_name}' on server '{server_url}'")
    
    def _get_api_url(self, endpoint: str) -> str:
        """Get complete API URL for an endpoint"""
        return f"{self.server_url}{endpoint}"
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to server"""
        url = self._get_api_url(endpoint)
        
        try:
            logger.debug(f"Making {method} request to {url}")
            
            if method.upper() == 'GET':
                response = self.session.get(url, timeout=self.timeout, **kwargs)
            elif method.upper() == 'POST':
                response = self.session.post(url, timeout=self.timeout, **kwargs)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, timeout=self.timeout, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise RuntimeError(f"Server request failed: {str(e)}")
    
    # Project Management
    def ensure_project_exists(self) -> bool:
        """Ensure the project exists on the server"""
        try:
            response = self._make_request('GET', f'/api/projects/{self.project_name}')
            return True
        except RuntimeError:
            logger.warning(f"Project '{self.project_name}' does not exist on server")
            return False
    
    def create_project_if_not_exists(self, description: str = "") -> bool:
        """Create project if it doesn't exist"""
        if self.ensure_project_exists():
            return True
        
        try:
            data = {
                'project_name': self.project_name,
                'description': description
            }
            response = self._make_request('POST', '/api/projects', json=data)
            logger.info(f"Created project '{self.project_name}' on server")
            return True
        except RuntimeError as e:
            logger.error(f"Failed to create project: {str(e)}")
            return False
    
    # File Operations
    def upload_file(self, local_path: Union[str, Path], destination_path: str) -> Dict[str, Any]:
        """
        Upload a file to the project's active_run directory.
        
        Args:
            local_path: Local path to the file to upload
            destination_path: Relative path within the project's active_run directory
            
        Returns:
            Server response with upload details
        """
        local_path = Path(local_path)
        
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")
        
        url = self._get_api_url(f'/api/projects/{self.project_name}/upload')
        
        try:
            with open(local_path, 'rb') as f:
                files = {'file': (local_path.name, f)}
                data = {'destination_path': destination_path}
                
                response = self.session.post(url, files=files, data=data, timeout=self.timeout)
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"Uploaded {local_path} to {destination_path}")
                return result
                
        except requests.RequestException as e:
            logger.error(f"Failed to upload {local_path}: {str(e)}")
            raise RuntimeError(f"File upload failed: {str(e)}")
    
    def upload_text_file(self, content: str, destination_path: str, filename: str = None) -> Dict[str, Any]:
        """
        Upload text content as a file to the project.
        
        Args:
            content: Text content to upload
            destination_path: Relative path within the project's active_run directory
            filename: Optional filename (extracted from destination_path if not provided)
            
        Returns:
            Server response with upload details
        """
        import tempfile
        
        if filename is None:
            filename = Path(destination_path).name
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'_{filename}', delete=False) as tmp_file:
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            return self.upload_file(tmp_path, destination_path)
        finally:
            # Clean up temporary file
            os.unlink(tmp_path)
    
    def upload_multiple_files(self, file_mappings: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Upload multiple files to the project.
        
        Args:
            file_mappings: List of dicts with 'local_path' and 'destination_path'
            
        Returns:
            List of upload results
        """
        results = []
        for mapping in file_mappings:
            try:
                result = self.upload_file(mapping['local_path'], mapping['destination_path'])
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
    def run_command(self, command: str, args: List[str] = None, 
                   environment: Dict[str, str] = None,
                   working_directory: str = "active_run",
                   timeout: int = None) -> Dict[str, Any]:
        """
        Execute an OpenFOAM command on the server.
        
        Args:
            command: Command to execute (e.g., 'blockMesh', 'simpleFoam')
            args: Command arguments
            environment: Environment variables
            working_directory: Working directory within project
            timeout: Command timeout in seconds
            
        Returns:
            Command execution result with stdout, stderr, success status
        """
        data = {
            'command': command,
            'args': args or [],
            'environment': environment or {},
            'working_directory': working_directory,
            'timeout': timeout or self.timeout
        }
        
        url = self._get_api_url(f'/api/projects/{self.project_name}/run_command')
        
        try:
            logger.info(f"Running command '{command}' with args {args}")
            response = self.session.post(url, json=data, timeout=timeout or self.timeout)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('success'):
                logger.info(f"Command '{command}' completed successfully")
            else:
                logger.warning(f"Command '{command}' failed with exit code {result.get('exit_code')}")
            
            return result
            
        except requests.RequestException as e:
            logger.error(f"Failed to run command '{command}': {str(e)}")
            return {
                'success': False,
                'exit_code': -1,
                'stdout': '',
                'stderr': str(e),
                'error': f"Server communication failed: {str(e)}"
            }
    
    # Specialized OpenFOAM Commands
    def run_blockmesh(self, case_directory: str = "active_run") -> Dict[str, Any]:
        """Run blockMesh command"""
        return self.run_command('blockMesh', ['-case', '.'], working_directory=case_directory)
    
    def run_checkmesh(self, case_directory: str = "active_run") -> Dict[str, Any]:
        """Run checkMesh command"""
        return self.run_command('checkMesh', ['-case', '.'], working_directory=case_directory)
    
    def run_snappyhexmesh(self, case_directory: str = "active_run") -> Dict[str, Any]:
        """Run snappyHexMesh command"""
        return self.run_command('snappyHexMesh', ['-overwrite'], working_directory=case_directory)
    
    def run_toposet(self, case_directory: str = "active_run") -> Dict[str, Any]:
        """Run topoSet command"""
        return self.run_command('topoSet', ['-case', '.'], working_directory=case_directory)
    
    def run_createpatch(self, case_directory: str = "active_run") -> Dict[str, Any]:
        """Run createPatch command"""
        return self.run_command('createPatch', ['-overwrite'], working_directory=case_directory)
    
    def run_solver(self, solver: str, case_directory: str = "active_run", timeout: int = 1800) -> Dict[str, Any]:
        """Run OpenFOAM solver"""
        return self.run_command(solver, working_directory=case_directory, timeout=timeout)
    
    def run_foamrun(self, solver: str, case_directory: str = "active_run", timeout: int = 1800) -> Dict[str, Any]:
        """Run foamRun with specified solver"""
        return self.run_command('foamRun', ['-solver', solver], working_directory=case_directory, timeout=timeout)
    
    # ParaView Server Management
    def start_pvserver(self, port: Optional[int] = None) -> Dict[str, Any]:
        """Start ParaView server for the project"""
        data = {}
        if port:
            data['port'] = port
        
        return self._make_request('POST', f'/api/projects/{self.project_name}/pvserver/start', json=data)
    
    def stop_pvserver(self) -> Dict[str, Any]:
        """Stop ParaView server for the project"""
        return self._make_request('DELETE', f'/api/projects/{self.project_name}/pvserver/stop')
    
    def get_pvserver_info(self) -> Dict[str, Any]:
        """Get ParaView server information"""
        return self._make_request('GET', f'/api/projects/{self.project_name}/pvserver/info')
    
    # Utility Methods
    def get_project_info(self) -> Dict[str, Any]:
        """Get project information including files"""
        return self._make_request('GET', f'/api/projects/{self.project_name}')
    
    def health_check(self) -> Dict[str, Any]:
        """Check server health"""
        return self._make_request('GET', '/health')
    
    def cleanup(self):
        """Cleanup resources"""
        self.session.close()
        logger.info(f"RemoteExecutor cleanup completed for project '{self.project_name}'")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()


class LocalToRemoteAdapter:
    """
    Adapter to help transition LangGraph agents from local to remote execution.
    
    This class provides utility methods to help agents that were designed for
    local execution work with the RemoteExecutor.
    """
    
    def __init__(self, remote_executor: RemoteExecutor, local_case_dir: Optional[Path] = None):
        """
        Initialize adapter.
        
        Args:
            remote_executor: RemoteExecutor instance
            local_case_dir: Optional local case directory for temporary files
        """
        self.remote = remote_executor
        self.local_case_dir = local_case_dir or Path.cwd()
        
    def create_local_case_structure(self) -> Path:
        """Create local case directory structure for temporary files"""
        case_dir = self.local_case_dir / f"temp_{self.remote.project_name}"
        case_dir.mkdir(exist_ok=True)
        
        # Create standard OpenFOAM directories
        (case_dir / "0").mkdir(exist_ok=True)
        (case_dir / "constant").mkdir(exist_ok=True)
        (case_dir / "system").mkdir(exist_ok=True)
        (case_dir / "constant" / "triSurface").mkdir(exist_ok=True)
        
        return case_dir
    
    def write_and_upload_file(self, content: str, relative_path: str) -> Dict[str, Any]:
        """
        Write content to local file and upload to server.
        
        Args:
            content: File content
            relative_path: Relative path (e.g., "system/controlDict")
            
        Returns:
            Upload result
        """
        # Create local file
        local_file = self.local_case_dir / relative_path
        local_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(local_file, 'w') as f:
            f.write(content)
        
        # Upload to server
        return self.remote.upload_file(local_file, relative_path)
    
    def cleanup_local_files(self):
        """Clean up temporary local files"""
        import shutil
        temp_dir = self.local_case_dir / f"temp_{self.remote.project_name}"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}") 