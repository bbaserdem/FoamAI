"""
ProcessValidator: A composable service for validating pvserver processes.

This module provides a clean way to compose process validation logic,
maintaining separation of concerns.
"""

from typing import Dict, List
import psutil

def validate_pvserver_pid(pid: int, expected_port: int = None) -> bool:
    """
    Validate that a PID is actually a running pvserver process.
    Optionally check if it's using the expected port.
    """
    if not pid:
        return False
    
    try:
        if not psutil.pid_exists(pid):
            return False
        
        process = psutil.Process(pid)
        
        # Check if it's actually a pvserver process
        # Be more flexible - check process name and command line
        process_name = process.name().lower()
        cmdline = process.cmdline()
        cmdline_str = ' '.join(cmdline).lower()
        
        # Valid if process name contains 'pvserver' OR command line contains 'pvserver'
        is_pvserver = 'pvserver' in process_name or 'pvserver' in cmdline_str
        
        if not is_pvserver:
            return False
        
        # If we have an expected port, validate it
        if expected_port:
            found_port = None
            
            # Look for '--server-port=PORT' or '--server-port PORT'
            port_arg_str = f'--server-port={expected_port}'
            if port_arg_str in cmdline:
                found_port = expected_port
            else:
                try:
                    idx = cmdline.index('--server-port')
                    if idx + 1 < len(cmdline):
                        found_port = int(cmdline[idx + 1])
                except (ValueError, IndexError):
                    pass
            
            if found_port != expected_port:
                return False
        
        return True
        
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


class ProcessValidator:
    """A service for validating that pvserver processes are running."""

    def is_running(self, record: Dict) -> bool:
        """
        Validate a single pvserver record.
        
        Args:
            record: Dictionary containing pvserver info. Supports both formats:
                    - Task-based: 'pvserver_pid' and 'pvserver_port'
                    - Project-based: 'pid' and 'port'
            
        Returns:
            bool: True if process is valid/running, False if dead.
        """
        if not record:
            return False
            
        # Support both task-based and project-based field names
        pid = record.get('pvserver_pid') or record.get('pid')
        port = record.get('pvserver_port') or record.get('port')
        
        if not pid or not port:
            return False
        
        return validate_pvserver_pid(pid, port)

    def filter_running(self, records: List[Dict]) -> List[Dict]:
        """
        Validate a list of pvserver records, filtering out dead processes.
        
        Args:
            records: List of dictionaries containing pvserver records.
            
        Returns:
            List[Dict]: Filtered list containing only valid/running processes.
        """
        return [record for record in records if self.is_running(record)]


# Global instance for easy import
validator = ProcessValidator() 