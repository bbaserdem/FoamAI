import sqlite3
import contextlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from pathlib import Path

from config import DATABASE_PATH

class DatabaseError(Exception):
    """Custom exception for database-related errors"""
    pass

class TaskNotFoundError(DatabaseError):
    """Exception raised when a task is not found"""
    pass

@contextlib.contextmanager
def get_connection():
    """Context manager for database connections with proper cleanup"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        raise DatabaseError(f"Database operation failed: {e}")
    finally:
        if conn:
            conn.close()

def execute_query(query: str, params: tuple = (), fetch_one: bool = False, fetch_all: bool = False) -> Any:
    """Execute a query with proper error handling and connection management"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if fetch_one:
            return cursor.fetchone()
        elif fetch_all:
            return cursor.fetchall()
        else:
            conn.commit()
            return cursor.rowcount

# =============================================================================
# TASK OPERATIONS
# =============================================================================

def create_task(task_id: str, initial_status: str = "pending", initial_message: str = "Task created") -> bool:
    """Create a new task in the database"""
    query = """
        INSERT INTO tasks (task_id, status, message, created_at)
        VALUES (?, ?, ?, ?)
    """
    params = (task_id, initial_status, initial_message, datetime.now())
    
    try:
        execute_query(query, params)
        return True
    except DatabaseError:
        return False

def get_task(task_id: str) -> Optional[Dict]:
    """Get task information by ID"""
    query = "SELECT * FROM tasks WHERE task_id = ?"
    result = execute_query(query, (task_id,), fetch_one=True)
    
    if result:
        return dict(result)
    return None

def task_exists(task_id: str) -> bool:
    """Check if a task exists"""
    query = "SELECT 1 FROM tasks WHERE task_id = ? LIMIT 1"
    result = execute_query(query, (task_id,), fetch_one=True)
    return result is not None

def update_task_status(task_id: str, status: str, message: str, file_path: Optional[str] = None, case_path: Optional[str] = None) -> bool:
    """Update task status and optional fields"""
    # Build dynamic query based on provided fields
    set_clauses = ["status = ?", "message = ?"]
    params = [status, message]
    
    if file_path is not None:
        set_clauses.append("file_path = ?")
        params.append(file_path)
    
    if case_path is not None:
        set_clauses.append("case_path = ?")
        params.append(case_path)
    
    params.append(task_id)  # For WHERE clause
    
    query = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE task_id = ?"
    
    try:
        rows_affected = execute_query(query, tuple(params))
        return rows_affected > 0
    except DatabaseError:
        return False

def update_task_rejection(task_id: str, comments: Optional[str] = None) -> bool:
    """Update task to rejected status"""
    message = f'Mesh rejected. Comments: {comments or "None"}'
    return update_task_status(task_id, 'rejected', message)

# =============================================================================
# PVSERVER OPERATIONS
# =============================================================================

def get_running_pvservers() -> List[Dict]:
    """Get all running pvserver records"""
    query = """
        SELECT task_id, pvserver_pid, pvserver_port, case_path, pvserver_started_at
        FROM tasks 
        WHERE pvserver_status = 'running'
        ORDER BY pvserver_started_at DESC
    """
    results = execute_query(query, fetch_all=True)
    return [dict(row) for row in results] if results else []

def count_running_pvservers() -> int:
    """Count currently running pvservers"""
    query = "SELECT COUNT(*) FROM tasks WHERE pvserver_status = 'running'"
    result = execute_query(query, fetch_one=True)
    return result[0] if result else 0

def get_running_pvserver_for_case(case_path: str) -> Optional[Dict]:
    """Get running pvserver info for a specific case directory"""
    query = """
        SELECT task_id, pvserver_port, pvserver_pid, pvserver_started_at 
        FROM tasks 
        WHERE case_path = ? AND pvserver_status = 'running'
        ORDER BY pvserver_started_at DESC
        LIMIT 1
    """
    result = execute_query(query, (case_path,), fetch_one=True)
    return dict(result) if result else None

def update_pvserver_status(task_id: str, status: str, port: Optional[int] = None, pid: Optional[int] = None, error_message: Optional[str] = None) -> bool:
    """Update pvserver status in database"""
    now = datetime.now()
    
    if status == 'running':
        query = """
            UPDATE tasks 
            SET pvserver_status = ?, pvserver_port = ?, pvserver_pid = ?, 
                pvserver_started_at = ?, pvserver_last_activity = ?, pvserver_error_message = NULL
            WHERE task_id = ?
        """
        params = (status, port, pid, now, now, task_id)
    elif status == 'error':
        query = """
            UPDATE tasks 
            SET pvserver_status = ?, pvserver_error_message = ?, pvserver_last_activity = ?
            WHERE task_id = ?
        """
        params = (status, error_message, now, task_id)
    else:  # stopped
        query = """
            UPDATE tasks 
            SET pvserver_status = ?, pvserver_last_activity = ?
            WHERE task_id = ?
        """
        params = (status, now, task_id)
    
    try:
        rows_affected = execute_query(query, params)
        return rows_affected > 0
    except DatabaseError:
        return False

def cleanup_stale_pvserver_entry(task_id: str, error_message: str = "Process died (cleaned up by lazy cleanup)") -> bool:
    """Clean up a single stale pvserver entry"""
    query = """
        UPDATE tasks 
        SET pvserver_status = 'stopped', 
            pvserver_last_activity = ?, 
            pvserver_error_message = ?
        WHERE task_id = ?
    """
    params = (datetime.now(), error_message, task_id)
    
    try:
        rows_affected = execute_query(query, params)
        return rows_affected > 0
    except DatabaseError:
        return False

def get_pvserver_info(task_id: str) -> Optional[Dict]:
    """Get pvserver information for a task"""
    query = """
        SELECT pvserver_port, pvserver_pid, pvserver_status, 
               pvserver_started_at, pvserver_error_message
        FROM tasks 
        WHERE task_id = ?
    """
    result = execute_query(query, (task_id,), fetch_one=True)
    return dict(result) if result else None

def get_inactive_pvservers(hours_threshold: int = 4) -> List[Dict]:
    """Get pvservers that have been inactive for too long"""
    cutoff_time = datetime.now() - timedelta(hours=hours_threshold)
    query = """
        SELECT task_id, pvserver_pid, pvserver_port, pvserver_started_at
        FROM tasks 
        WHERE pvserver_status = 'running' 
        AND pvserver_started_at < ?
        ORDER BY pvserver_started_at ASC
    """
    results = execute_query(query, (cutoff_time,), fetch_all=True)
    return [dict(row) for row in results] if results else []

def link_task_to_pvserver(task_id: str, port: int, pid: int) -> bool:
    """Link a task to an existing pvserver"""
    return update_pvserver_status(task_id, 'running', port, pid)

# =============================================================================
# MAINTENANCE OPERATIONS
# =============================================================================

def get_all_tasks() -> List[Dict]:
    """Get all tasks (mainly for debugging/maintenance)"""
    query = "SELECT * FROM tasks ORDER BY created_at DESC"
    results = execute_query(query, fetch_all=True)
    return [dict(row) for row in results] if results else []

def delete_task(task_id: str) -> bool:
    """Delete a task (use with caution)"""
    query = "DELETE FROM tasks WHERE task_id = ?"
    try:
        rows_affected = execute_query(query, (task_id,))
        return rows_affected > 0
    except DatabaseError:
        return False

def get_tasks_by_status(status: str) -> List[Dict]:
    """Get all tasks with a specific status"""
    query = "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC"
    results = execute_query(query, (status,), fetch_all=True)
    return [dict(row) for row in results] if results else []

def get_database_stats() -> Dict:
    """Get database statistics for monitoring"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Total tasks
        cursor.execute("SELECT COUNT(*) FROM tasks")
        total_tasks = cursor.fetchone()[0]
        
        # Tasks by status
        cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
        status_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # PVServer stats
        cursor.execute("SELECT pvserver_status, COUNT(*) FROM tasks WHERE pvserver_status IS NOT NULL GROUP BY pvserver_status")
        pvserver_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {
            'total_tasks': total_tasks,
            'status_counts': status_counts,
            'pvserver_counts': pvserver_counts,
            'timestamp': datetime.now().isoformat()
        }

# =============================================================================
# MIGRATION HELPERS (for gradual migration)
# =============================================================================

def migrate_existing_operations():
    """Helper function to validate the database schema matches expectations"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if all expected columns exist
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [column[1] for column in cursor.fetchall()]
        
        expected_columns = [
            'task_id', 'status', 'message', 'file_path', 'case_path',
            'pvserver_port', 'pvserver_pid', 'pvserver_status',
            'pvserver_started_at', 'pvserver_last_activity', 
            'pvserver_error_message', 'created_at'
        ]
        
        missing_columns = [col for col in expected_columns if col not in columns]
        
        if missing_columns:
            raise DatabaseError(f"Missing database columns: {missing_columns}")
        
        return True

# =============================================================================
# ENHANCED DAL FUNCTIONS WITH PROCESS VALIDATION
# =============================================================================

def get_running_pvservers_validated() -> List[Dict]:
    """
    Get all running pvserver records with automatic process validation.
    Dead processes are automatically cleaned up.
    
    Returns:
        List[Dict]: List of verified running pvserver records
    """
    from process_validator import validator
    
    # Get all records marked as running
    records = get_running_pvservers()
    
    # Validate and clean up dead processes
    return validator.validate_record_list(records, cleanup_callback=cleanup_stale_pvserver_entry)

def get_running_pvserver_for_case_validated(case_path: str) -> Optional[Dict]:
    """
    Get running pvserver info for a specific case directory with validation.
    Dead processes are automatically cleaned up.
    
    Args:
        case_path: Path to the case directory
        
    Returns:
        Optional[Dict]: Validated pvserver record or None if not found/dead
    """
    from process_validator import validator
    
    # Get the record from database
    record = get_running_pvserver_for_case(case_path)
    
    if record:
        # Validate and clean up if dead
        if validator.validate_and_cleanup_stale(record):
            return record
    
    return None

def get_pvserver_info_validated(task_id: str) -> Optional[Dict]:
    """
    Get pvserver information for a task with automatic validation.
    Dead processes are automatically marked as stopped.
    
    Args:
        task_id: The task ID
        
    Returns:
        Optional[Dict]: Validated pvserver info or None if not found
    """
    from process_validator import validator
    
    # Get the record from database
    record = get_pvserver_info(task_id)
    
    if record:
        # If it's marked as running, validate the process
        if record.get('pvserver_status') == 'running':
            # Create a record format that validator expects
            validation_record = {
                'task_id': task_id,
                'pvserver_pid': record.get('pvserver_pid'),
                'pvserver_port': record.get('pvserver_port')
            }
            
            # Validate and update status if dead
            if not validator.validate_and_update_status(validation_record):
                # Process is dead, update the record
                record['pvserver_status'] = 'stopped'
                record['pvserver_error_message'] = "Process died (detected during info lookup)"
        
        # Add connection string for running processes
        if record.get('pvserver_status') == 'running':
            record['connection_string'] = f"localhost:{record['pvserver_port']}"
        
        return record
    
    return None

def count_running_pvservers_validated() -> int:
    """
    Count currently running pvservers with automatic cleanup of dead processes.
    
    Returns:
        int: Number of actually running pvservers
    """
    # Get validated records (this will clean up dead processes)
    validated_records = get_running_pvservers_validated()
    return len(validated_records)

def cleanup_stale_pvserver_entries() -> List[str]:
    """
    Clean up all stale database entries for dead processes.
    
    Returns:
        List[str]: List of cleaned up task identifiers
    """
    from process_validator import validator
    
    # Get all records marked as running
    records = get_running_pvservers()
    
    # Clean up stale records
    return validator.cleanup_stale_records(records)

if __name__ == "__main__":
    # Test the database connection and schema
    try:
        migrate_existing_operations()
        print("✅ Database schema validation passed")
        
        # Print some stats
        stats = get_database_stats()
        print(f"📊 Database stats: {stats}")
        
    except Exception as e:
        print(f"❌ Database validation failed: {e}") 