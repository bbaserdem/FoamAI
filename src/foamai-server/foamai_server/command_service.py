import subprocess
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class CommandExecutionError(Exception):
    """Custom exception for command execution errors"""
    pass

class CommandService:
    """Service for executing OpenFOAM commands in project directories"""
    
    def __init__(self):
        self.default_timeout = 300  # 5 minutes
        self.max_output_size = 10 * 1024 * 1024  # 10MB limit for output
    
    def execute_command(
        self,
        project_path: str,
        command: str,
        args: Optional[List[str]] = None,
        environment: Optional[Dict[str, str]] = None,
        working_directory: str = "active_run",
        timeout: Optional[int] = None
    ) -> Dict:
        """
        Execute a command in the specified project directory.
        
        Args:
            project_path: Full path to the project directory
            command: Command to execute (e.g., "blockMesh")
            args: List of command arguments
            environment: Additional environment variables
            working_directory: Subdirectory within project (default: "active_run")
            timeout: Timeout in seconds (default: 300)
            
        Returns:
            Dict containing execution results
            
        Raises:
            CommandExecutionError: If execution fails
        """
        start_time = time.time()
        
        # Validate inputs
        project_dir = Path(project_path)
        if not project_dir.exists():
            raise CommandExecutionError(f"Project directory does not exist: {project_path}")
        
        # Setup working directory
        work_dir = project_dir / working_directory
        if not work_dir.exists():
            logger.info(f"Creating working directory: {work_dir}")
            work_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare command
        cmd_list = [command]
        if args:
            cmd_list.extend(args)
        
        # Prepare environment
        exec_env = os.environ.copy()
        if environment:
            exec_env.update(environment)
        
        # Set timeout
        exec_timeout = timeout or self.default_timeout
        
        logger.info(f"Executing command: {' '.join(cmd_list)}")
        logger.info(f"Working directory: {work_dir}")
        logger.info(f"Timeout: {exec_timeout} seconds")
        
        try:
            # Execute command
            result = subprocess.run(
                cmd_list,
                cwd=str(work_dir),
                env=exec_env,
                capture_output=True,
                text=True,
                timeout=exec_timeout
            )
            
            execution_time = time.time() - start_time
            
            # Truncate output if too large
            stdout = self._truncate_output(result.stdout, "stdout")
            stderr = self._truncate_output(result.stderr, "stderr")
            
            logger.info(f"Command completed in {execution_time:.2f} seconds with exit code {result.returncode}")
            
            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "execution_time": round(execution_time, 2),
                "command": " ".join(cmd_list),
                "working_directory": str(work_dir),
                "timestamp": datetime.now().isoformat()
            }
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            error_msg = f"Command timed out after {exec_timeout} seconds"
            logger.error(error_msg)
            raise CommandExecutionError(error_msg)
            
        except FileNotFoundError:
            error_msg = f"Command not found: {command}"
            logger.error(error_msg)
            raise CommandExecutionError(error_msg)
            
        except PermissionError:
            error_msg = f"Permission denied executing command: {command}"
            logger.error(error_msg)
            raise CommandExecutionError(error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error executing command: {e}"
            logger.error(error_msg)
            raise CommandExecutionError(error_msg)
    
    def _truncate_output(self, output: str, output_type: str) -> str:
        """Truncate output if it exceeds maximum size"""
        if not output:
            return ""
        
        output_bytes = output.encode('utf-8')
        if len(output_bytes) <= self.max_output_size:
            return output
        
        # Truncate and add warning
        truncated = output_bytes[:self.max_output_size].decode('utf-8', errors='ignore')
        warning = f"\n\n[WARNING: {output_type} truncated - exceeded {self.max_output_size // (1024*1024)}MB limit]"
        
        logger.warning(f"Truncated {output_type} output (exceeded {self.max_output_size} bytes)")
        return truncated + warning
    
    def validate_openfoam_command(self, command: str) -> bool:
        """
        Validate if a command is a known OpenFOAM command.
        This is a basic validation - can be expanded later.
        """
        known_commands = {
            # Mesh generation
            'blockMesh', 'snappyHexMesh', 'extrudeMesh',
            # Solvers
            'foamRun', 'simpleFoam', 'pimpleFoam', 'icoFoam', 'potentialFoam',
            # Utilities
            'checkMesh', 'decomposePar', 'reconstructPar', 'paraFoam',
            'foamToVTK', 'sample', 'postProcess',
            # Pre/post processing
            'setFields', 'mapFields', 'changeDictionary', 'transformPoints'
        }
        
        return command in known_commands
    
    def get_command_suggestions(self, command: str) -> List[str]:
        """Get suggestions for similar commands if validation fails"""
        known_commands = [
            'blockMesh', 'snappyHexMesh', 'foamRun', 'simpleFoam', 
            'checkMesh', 'decomposePar', 'reconstructPar'
        ]
        
        # Simple suggestion based on partial matches
        suggestions = [cmd for cmd in known_commands if command.lower() in cmd.lower()]
        return suggestions[:5]  # Return top 5 suggestions


# Global instance for easy import
command_service = CommandService() 