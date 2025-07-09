"""
ProcessValidator: A composable service for validating pvserver processes.

This module provides a clean way to compose process validation logic,
maintaining separation of concerns.
"""

from typing import Dict, List
from process_utils import validate_pvserver_pid


class ProcessValidator:
    """A service for validating that pvserver processes are running."""

    def is_running(self, record: Dict) -> bool:
        """
        Validate a single pvserver record.
        
        Args:
            record: Dictionary containing 'pvserver_pid' and 'pvserver_port'.
            
        Returns:
            bool: True if process is valid/running, False if dead.
        """
        if not record or not record.get('pvserver_pid') or not record.get('pvserver_port'):
            return False
            
        pid = record['pvserver_pid']
        port = record['pvserver_port']
        
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