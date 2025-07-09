"""
ProcessValidator: A composable service for validating pvserver processes.

This module provides a clean way to compose process validation logic with 
database operations, maintaining separation of concerns while eliminating 
code duplication.
"""

from typing import Dict, List, Optional, Callable
from datetime import datetime

from process_utils import validate_pvserver_pid
from database import update_pvserver_status, cleanup_stale_pvserver_entry


class ProcessValidator:
    """
    A composable service for validating pvserver processes.
    
    This class provides methods to validate process records and can be 
    used to compose validation logic with DAL operations.
    """
    
    def __init__(self):
        pass
    
    def validate_single_record(self, record: Dict, 
                             cleanup_callback: Optional[Callable[[str, str], bool]] = None) -> bool:
        """
        Validate a single pvserver record.
        
        Args:
            record: Dictionary containing 'task_id', 'pvserver_pid', 'pvserver_port'
            cleanup_callback: Optional function to call if process is dead
            
        Returns:
            bool: True if process is valid/running, False if dead
        """
        if not record or not record.get('pvserver_pid') or not record.get('pvserver_port'):
            return False
            
        pid = record['pvserver_pid']
        port = record['pvserver_port']
        task_id = record['task_id']
        
        # Validate the process is actually running
        if validate_pvserver_pid(pid, port):
            return True
        
        # Process is dead, perform cleanup if callback provided
        if cleanup_callback:
            cleanup_callback(task_id, "Process died (detected during validation)")
        
        return False
    
    def validate_record_list(self, records: List[Dict], 
                           cleanup_callback: Optional[Callable[[str, str], bool]] = None) -> List[Dict]:
        """
        Validate a list of pvserver records, filtering out dead processes.
        
        Args:
            records: List of dictionaries containing pvserver records
            cleanup_callback: Optional function to call for dead processes
            
        Returns:
            List[Dict]: Filtered list containing only valid/running processes
        """
        validated_records = []
        
        for record in records:
            if self.validate_single_record(record, cleanup_callback):
                validated_records.append(record)
        
        return validated_records
    
    def validate_and_update_status(self, record: Dict) -> bool:
        """
        Validate a record and update its status if the process is dead.
        
        Args:
            record: Dictionary containing pvserver record
            
        Returns:
            bool: True if process is valid/running, False if dead
        """
        def update_status_callback(task_id: str, error_message: str) -> bool:
            return update_pvserver_status(task_id, 'stopped', error_message=error_message)
        
        return self.validate_single_record(record, update_status_callback)
    
    def validate_and_cleanup_stale(self, record: Dict) -> bool:
        """
        Validate a record and clean up stale database entry if process is dead.
        
        Args:
            record: Dictionary containing pvserver record
            
        Returns:
            bool: True if process is valid/running, False if dead
        """
        def cleanup_callback(task_id: str, error_message: str) -> bool:
            return cleanup_stale_pvserver_entry(task_id, error_message)
        
        return self.validate_single_record(record, cleanup_callback)
    
    def filter_running_processes(self, records: List[Dict]) -> List[Dict]:
        """
        Filter a list of records to only include running processes.
        Does not perform any database updates.
        
        Args:
            records: List of dictionaries containing pvserver records
            
        Returns:
            List[Dict]: Filtered list containing only valid/running processes
        """
        return self.validate_record_list(records, cleanup_callback=None)
    
    def cleanup_stale_records(self, records: List[Dict]) -> List[str]:
        """
        Clean up stale database entries for dead processes.
        
        Args:
            records: List of dictionaries containing pvserver records
            
        Returns:
            List[str]: List of cleaned up task identifiers
        """
        cleaned_up = []
        
        def cleanup_callback(task_id: str, error_message: str) -> bool:
            if cleanup_stale_pvserver_entry(task_id, error_message):
                cleaned_up.append(f"task_{task_id}")
                return True
            return False
        
        # Process all records and track cleanups
        self.validate_record_list(records, cleanup_callback)
        
        return cleaned_up


# Global instance for easy import
validator = ProcessValidator() 