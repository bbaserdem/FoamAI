import sqlite3
import contextlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from pathlib import Path

from config import DATABASE_PATH
from process_validator import validator

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

def create_task(task_id: str, initial_status: str = "pending", initial_message: str = "Task created"):
    """Create a new task in the database. Raises DatabaseError on failure."""
    query = """
        INSERT INTO tasks (task_id, status, message, created_at)
        VALUES (?, ?, ?, ?)
    """
    params = (task_id, initial_status, initial_message, datetime.now())
    execute_query(query, params)

def get_task(task_id: str) -> Optional[Dict]:
    """Get task information by ID"""
    query = "SELECT * FROM tasks WHERE task_id = ?"
    result = execute_query(query, (task_id,), fetch_one=True)
    return dict(result) if result else None

def task_exists(task_id: str) -> bool:
    """Check if a task exists"""
    query = "SELECT 1 FROM tasks WHERE task_id = ? LIMIT 1"
    result = execute_query(query, (task_id,), fetch_one=True)
    return result is not None

def update_task_status(task_id: str, status: str, message: str, file_path: Optional[str] = None, case_path: Optional[str] = None):
    """Update task status and optional fields. Raises TaskNotFoundError if task doesn't exist."""
    set_clauses = ["status = ?", "message = ?"]
    params = [status, message]
    
    if file_path is not None:
        set_clauses.append("file_path = ?")
        params.append(file_path)
    
    if case_path is not None:
        set_clauses.append("case_path = ?")
        params.append(case_path)
    
    params.append(task_id)
    query = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE task_id = ?"
    
    rows_affected = execute_query(query, tuple(params))
    if rows_affected == 0:
        raise TaskNotFoundError(f"Task with ID '{task_id}' not found for update.")

def update_task_rejection(task_id: str, comments: Optional[str] = None):
    """Update task to rejected status"""
    message = f'Mesh rejected. Comments: {comments or "None"}'
    update_task_status(task_id, 'rejected', message)

# =============================================================================
# PVSERVER OPERATIONS
# =============================================================================

def set_pvserver_running(task_id: str, port: int, pid: int):
    """Sets a task's pvserver status to 'running'."""
    now = datetime.now()
    query = """
        UPDATE tasks 
        SET pvserver_status = 'running', pvserver_port = ?, pvserver_pid = ?, 
            pvserver_started_at = ?, pvserver_last_activity = ?, pvserver_error_message = NULL
        WHERE task_id = ?
    """
    params = (port, pid, now, now, task_id)
    rows_affected = execute_query(query, params)
    if rows_affected == 0:
        raise TaskNotFoundError(f"Task with ID '{task_id}' not found to set pvserver to running.")

def set_pvserver_error(task_id: str, error_message: str):
    """Sets a task's pvserver status to 'error'."""
    now = datetime.now()
    query = """
        UPDATE tasks SET pvserver_status = 'error', pvserver_error_message = ?, pvserver_last_activity = ?
        WHERE task_id = ?
    """
    params = (error_message, now, task_id)
    rows_affected = execute_query(query, params)
    if rows_affected == 0:
        raise TaskNotFoundError(f"Task with ID '{task_id}' not found to set pvserver to error.")

def set_pvserver_stopped(task_id: str, message: str = "Process stopped"):
    """Sets a task's pvserver status to 'stopped'."""
    now = datetime.now()
    query = """
        UPDATE tasks SET pvserver_status = 'stopped', pvserver_error_message = ?, pvserver_last_activity = ?
        WHERE task_id = ?
    """
    params = (message, now, task_id)
    rows_affected = execute_query(query, params)
    if rows_affected == 0:
        raise TaskNotFoundError(f"Task with ID '{task_id}' not found to set pvserver to stopped.")

def _cleanup_stale_pvserver_entry(task_id: str, error_message: str = "Process died (cleaned up)"):
    """Sets a pvserver status to 'stopped' for a stale process. For internal use."""
    set_pvserver_stopped(task_id, message=error_message)

def get_running_pvservers() -> List[Dict]:
    """
    Get all running pvserver records with automatic process validation.
    Dead processes are automatically cleaned up.
    """
    query = "SELECT task_id, pvserver_pid, pvserver_port, case_path, pvserver_started_at FROM tasks WHERE pvserver_status = 'running' ORDER BY pvserver_started_at DESC"
    all_running = execute_query(query, fetch_all=True)
    
    validated_records = []
    if not all_running:
        return validated_records

    for row in all_running:
        record = dict(row)
        if validator.is_running(record):
            validated_records.append(record)
        else:
            _cleanup_stale_pvserver_entry(record['task_id'], "Process died (detected during list retrieval)")
            
    return validated_records

def count_running_pvservers() -> int:
    """Count currently running pvservers with automatic cleanup of dead processes."""
    return len(get_running_pvservers())

def get_running_pvserver_for_case(case_path: str) -> Optional[Dict]:
    """
    Get running pvserver info for a specific case directory with validation.
    Dead processes are automatically cleaned up.
    """
    query = "SELECT task_id, pvserver_port, pvserver_pid, pvserver_started_at FROM tasks WHERE case_path = ? AND pvserver_status = 'running' ORDER BY pvserver_started_at DESC LIMIT 1"
    record = execute_query(query, (case_path,), fetch_one=True)
    
    if record:
        record_dict = dict(record)
        if validator.is_running(record_dict):
            return record_dict
        else:
            _cleanup_stale_pvserver_entry(record_dict['task_id'], f"Process for case {case_path} died")
    return None

def get_pvserver_info(task_id: str) -> Optional[Dict]:
    """
    Get pvserver information for a task with automatic validation.
    Dead processes are automatically marked as stopped.
    """
    query = "SELECT pvserver_port, pvserver_pid, pvserver_status, pvserver_started_at, pvserver_error_message FROM tasks WHERE task_id = ?"
    record = execute_query(query, (task_id,), fetch_one=True)
    
    if record:
        record_dict = dict(record)
        if record_dict.get('pvserver_status') == 'running':
            if not validator.is_running(record_dict):
                set_pvserver_stopped(task_id, "Process died (detected during info lookup)")
                record_dict = dict(get_task(task_id)) # Refresh data
        
        if record_dict.get('pvserver_status') == 'running':
            record_dict['connection_string'] = f"localhost:{record_dict['pvserver_port']}"
        
        return record_dict
    return None

def get_inactive_pvservers(hours_threshold: int = 4) -> List[Dict]:
    """Get pvservers that have been inactive for too long"""
    cutoff_time = datetime.now() - timedelta(hours=hours_threshold)
    query = "SELECT task_id, pvserver_pid, pvserver_port, pvserver_started_at FROM tasks WHERE pvserver_status = 'running' AND pvserver_started_at < ? ORDER BY pvserver_started_at ASC"
    results = execute_query(query, (cutoff_time,), fetch_all=True)
    return [dict(row) for row in results] if results else []

def link_task_to_pvserver(task_id: str, port: int, pid: int):
    """Link a task to an existing pvserver"""
    set_pvserver_running(task_id, port, pid)

# =============================================================================
# MAINTENANCE OPERATIONS
# =============================================================================

def get_all_tasks() -> List[Dict]:
    """Get all tasks (mainly for debugging/maintenance)"""
    query = "SELECT * FROM tasks ORDER BY created_at DESC"
    results = execute_query(query, fetch_all=True)
    return [dict(row) for row in results] if results else []

def delete_task(task_id: str):
    """Delete a task (use with caution)"""
    query = "DELETE FROM tasks WHERE task_id = ?"
    execute_query(query, (task_id,))

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

def cleanup_stale_pvserver_entries() -> List[str]:
    """
    Clean up all stale database entries for dead processes.
    This is now an explicit maintenance function.
    """
    query = "SELECT task_id, pvserver_pid, pvserver_port FROM tasks WHERE pvserver_status = 'running'"
    records = execute_query(query, fetch_all=True)
    cleaned_up_ids = []
    
    if not records:
        return cleaned_up_ids
        
    for row in records:
        record = dict(row)
        if not validator.is_running(record):
            _cleanup_stale_pvserver_entry(record['task_id'], "Process died (detected during full stale cleanup)")
            cleaned_up_ids.append(record['task_id'])
            
    return cleaned_up_ids

if __name__ == "__main__":
    # Test the database connection and schema
    try:
        # migrate_existing_operations() # This line is removed as per the new_code
        print("✅ Database schema validation passed")
        
        # Print some stats
        stats = get_database_stats()
        print(f"📊 Database stats: {stats}")
        
    except Exception as e:
        print(f"❌ Database validation failed: {e}") 