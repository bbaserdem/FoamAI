import subprocess
import logging
import os
import time
import re
import glob
import shutil
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
        # OpenFOAM environment script path (with auto-detection)
        self.openfoam_bashrc = self._find_openfoam_bashrc()
        logger.info(f"Using OpenFOAM bashrc: {self.openfoam_bashrc}")
    
    def _find_openfoam_bashrc(self) -> str:
        """
        Find OpenFOAM bashrc file using environment variable or auto-detection.
        
        Returns:
            Path to OpenFOAM bashrc file
            
        Raises:
            CommandExecutionError: If no OpenFOAM installation found
        """
        # 1. Check environment variable first
        env_path = os.environ.get("OPENFOAM_BASHRC")
        if env_path and os.path.exists(env_path):
            logger.info(f"Using OpenFOAM bashrc from environment variable: {env_path}")
            return env_path
        
        # 2. Auto-detect using wildcards
        search_patterns = [
            "/opt/openfoam*/etc/bashrc",
            "/usr/lib/openfoam/openfoam*/etc/bashrc",
            "/usr/local/openfoam*/etc/bashrc",
        ]
        
        logger.info("Auto-detecting OpenFOAM installation...")
        all_matches = []
        
        for pattern in search_patterns:
            matches = glob.glob(pattern)
            if matches:
                logger.debug(f"Found {len(matches)} matches for pattern '{pattern}': {matches}")
                all_matches.extend(matches)
        
        if not all_matches:
            error_msg = "OpenFOAM installation not found. Searched patterns: " + ", ".join(search_patterns)
            logger.error(error_msg)
            raise CommandExecutionError(error_msg)
        
        # 3. Choose the best match (newest version)
        best_match = self._choose_newest_version(all_matches)
        logger.info(f"Auto-detected OpenFOAM bashrc: {best_match}")
        return best_match
    
    def _choose_newest_version(self, bashrc_paths: List[str]) -> str:
        """
        Choose the newest OpenFOAM version from multiple bashrc paths.
        
        Args:
            bashrc_paths: List of paths to OpenFOAM bashrc files
            
        Returns:
            Path to the newest version's bashrc file
        """
        if len(bashrc_paths) == 1:
            return bashrc_paths[0]
        
        def extract_version(path: str) -> int:
            """Extract version number from OpenFOAM path"""
            # Look for version patterns like 'openfoam2412', 'openfoam-2412', etc.
            version_match = re.search(r'openfoam[^\d]*(\d+)', path, re.IGNORECASE)
            if version_match:
                return int(version_match.group(1))
            # If no version found, treat as very old (0)
            return 0
        
        # Sort by version number and return the newest
        sorted_paths = sorted(bashrc_paths, key=extract_version, reverse=True)
        
        logger.info(f"Found {len(bashrc_paths)} OpenFOAM installations:")
        for i, path in enumerate(sorted_paths):
            version = extract_version(path)
            marker = " (selected)" if i == 0 else ""
            logger.info(f"  - {path} (version: {version}){marker}")
        
        return sorted_paths[0]
    def _save_run_copy(self, project_dir: Path, working_directory: str) -> str:
        """
        Save a copy of the active_run directory to a numbered run folder.
        
        Args:
            project_dir: Path to the project directory
            working_directory: The working directory that was used (usually 'active_run')
            
        Returns:
            str: The name of the created run directory (e.g., 'run_000')
            
        Raises:
            CommandExecutionError: If the copy operation fails
        """
        source_dir = project_dir / working_directory
        
        if not source_dir.exists():
            raise CommandExecutionError(f"Source directory does not exist: {source_dir}")
        
        # Find the next available run directory name
        run_counter = 0
        while True:
            run_dir_name = f"run_{run_counter:03d}"
            target_dir = project_dir / run_dir_name
            
            if not target_dir.exists():
                break
            run_counter += 1
            
            # Safety check to prevent infinite loop
            if run_counter > 9999:
                raise CommandExecutionError("Too many run directories (max 9999)")
        
        try:
            # Copy the entire directory tree
            shutil.copytree(source_dir, target_dir)
            logger.info(f"Saved run copy to: {run_dir_name}")
            return run_dir_name
            
        except Exception as e:
            raise CommandExecutionError(f"Failed to save run copy: {e}")

    
    def execute_command(
        self,
        project_path: str,
        command: str,
        args: Optional[List[str]] = None,
        environment: Optional[Dict[str, str]] = None,
        working_directory: str = "active_run",
        timeout: Optional[int] = None,
        save_run: bool = False
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
        
        # Prepare command with OpenFOAM environment sourcing
        cmd_list = self._prepare_command_with_openfoam_env(command, args)
        
        # Prepare environment
        exec_env = os.environ.copy()
        if environment:
            exec_env.update(environment)
        
        # Set timeout
        exec_timeout = timeout or self.default_timeout
        
        logger.info(f"Executing command with OpenFOAM environment: {command}")
        if args:
            logger.info(f"Command arguments: {args}")
        logger.info(f"Working directory: {work_dir}")
        logger.info(f"Timeout: {exec_timeout} seconds")
        logger.info(f"OpenFOAM bashrc: {self.openfoam_bashrc}")
        
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
            
            # Save run copy if requested and command was successful
            saved_run_directory = None
            if save_run and result.returncode == 0:
                try:
                    saved_run_directory = self._save_run_copy(project_dir, working_directory)
                    logger.info(f"Command completed successfully and run saved to: {saved_run_directory}")
                except Exception as e:
                    logger.error(f"Command succeeded but failed to save run copy: {e}")
                    # Don't fail the entire operation just because the copy failed

            logger.info(f"Command completed in {execution_time:.2f} seconds with exit code {result.returncode}")
            
            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "execution_time": round(execution_time, 2),
                "command": " ".join(cmd_list),
                "working_directory": str(work_dir),
                "timestamp": datetime.now().isoformat(),
                "saved_run_directory": saved_run_directory
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
    
    def _prepare_command_with_openfoam_env(self, command: str, args: Optional[List[str]] = None) -> List[str]:
        """
        Prepare command to run with OpenFOAM environment sourced.
        Wraps the command in bash -c with OpenFOAM sourcing.
        """
        
        # Build the full command string
        full_command = command
        if args:
            # Properly escape arguments for shell execution
            escaped_args = [self._shell_escape(arg) for arg in args]
            full_command = f"{command} {' '.join(escaped_args)}"
        
        # Create bash command that sources OpenFOAM environment first
        bash_command = f"source {self.openfoam_bashrc} && {full_command}"
        
        logger.debug(f"Prepared bash command: {bash_command}")
        
        return ["bash", "-c", bash_command]
    
    def _shell_escape(self, arg: str) -> str:
        """Escape shell arguments to prevent injection"""
        # Simple escaping - wrap in single quotes and escape any single quotes
        return f"'{arg.replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'"
    
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