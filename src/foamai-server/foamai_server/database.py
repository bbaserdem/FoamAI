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

class ProjectPVServerError(DatabaseError):
    """Exception raised for project pvserver-related errors"""
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

def init_project_pvserver_table():
    """Initialize the project_pvservers table if it doesn't exist"""
    query = """
        CREATE TABLE IF NOT EXISTS project_pvservers (
            project_name TEXT PRIMARY KEY,
            port INTEGER,
            pid INTEGER,
            case_path TEXT,
            status TEXT,
            started_at TIMESTAMP,
            last_activity TIMESTAMP,
            error_message TEXT
        )
    """
    execute_query(query)

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
# TASK-BASED PVSERVER OPERATIONS (Legacy)
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

# =============================================================================
# PROJECT-BASED PVSERVER OPERATIONS
# =============================================================================

def create_project_pvserver(project_name: str, port: int, pid: int, case_path: str):
    """Create a new project pvserver record. Raises ProjectPVServerError if project already has a pvserver."""
    # Initialize table if it doesn't exist
    init_project_pvserver_table()
    
    # Check if project already has a pvserver
    existing = get_project_pvserver_info(project_name)
    if existing and existing.get('status') == 'running':
        raise ProjectPVServerError(f"Project '{project_name}' already has a running pvserver on port {existing['port']}")
    
    now = datetime.now()
    query = """
        INSERT OR REPLACE INTO project_pvservers 
        (project_name, port, pid, case_path, status, started_at, last_activity, error_message)
        VALUES (?, ?, ?, ?, 'running', ?, ?, NULL)
    """
    params = (project_name, port, pid, case_path, now, now)
    execute_query(query, params)

def get_project_pvserver_info(project_name: str) -> Optional[Dict]:
    """
    Get pvserver information for a project with automatic validation.
    Dead processes are automatically marked as stopped.
    """
    # Initialize table if it doesn't exist
    init_project_pvserver_table()
    
    query = "SELECT * FROM project_pvservers WHERE project_name = ?"
    record = execute_query(query, (project_name,), fetch_one=True)
    
    if record:
        record_dict = dict(record)
        if record_dict.get('status') == 'running':
            # Validate the process is still running
            if not validator.is_running(record_dict):
                set_project_pvserver_stopped(project_name, "Process died (detected during info lookup)")
                # Refresh data after marking as stopped
                updated_record = execute_query(query, (project_name,), fetch_one=True)
                if updated_record:
                    record_dict = dict(updated_record)
        
        # Add connection string only if status is running
        if record_dict.get('status') == 'running':
            record_dict['connection_string'] = f"localhost:{record_dict['port']}"
        
        return record_dict
    return None

def set_project_pvserver_stopped(project_name: str, message: str = "Process stopped"):
    """Set a project's pvserver status to 'stopped'."""
    now = datetime.now()
    query = """
        UPDATE project_pvservers 
        SET status = 'stopped', error_message = ?, last_activity = ?
        WHERE project_name = ?
    """
    params = (message, now, project_name)
    rows_affected = execute_query(query, params)
    if rows_affected == 0:
        raise ProjectPVServerError(f"No pvserver found for project '{project_name}' to stop.")

def set_project_pvserver_error(project_name: str, error_message: str):
    """Set a project's pvserver status to 'error'."""
    now = datetime.now()
    query = """
        UPDATE project_pvservers 
        SET status = 'error', error_message = ?, last_activity = ?
        WHERE project_name = ?
    """
    params = (error_message, now, project_name)
    rows_affected = execute_query(query, params)
    if rows_affected == 0:
        raise ProjectPVServerError(f"No pvserver found for project '{project_name}' to set error.")

def get_all_project_pvservers() -> List[Dict]:
    """
    Get all project pvserver records with automatic process validation.
    Dead processes are automatically cleaned up.
    """
    # Initialize table if it doesn't exist
    init_project_pvserver_table()
    
    query = "SELECT * FROM project_pvservers ORDER BY started_at DESC"
    all_records = execute_query(query, fetch_all=True)
    
    validated_records = []
    if not all_records:
        return validated_records

    for row in all_records:
        record = dict(row)
        if record.get('status') == 'running':
            if validator.is_running(record):
                validated_records.append(record)
            else:
                set_project_pvserver_stopped(record['project_name'], "Process died (detected during list retrieval)")
                # Add the updated record
                updated_record = get_project_pvserver_info(record['project_name'])
                if updated_record:
                    validated_records.append(updated_record)
        else:
            validated_records.append(record)
            
    return validated_records

def get_running_project_pvservers() -> List[Dict]:
    """Get all running project pvservers with automatic process validation."""
    all_project_pvservers = get_all_project_pvservers()
    return [record for record in all_project_pvservers if record.get('status') == 'running']

def count_running_project_pvservers() -> int:
    """Count currently running project pvservers."""
    return len(get_running_project_pvservers())

def delete_project_pvserver(project_name: str):
    """Delete a project pvserver record completely."""
    query = "DELETE FROM project_pvservers WHERE project_name = ?"
    rows_affected = execute_query(query, (project_name,))
    if rows_affected == 0:
        raise ProjectPVServerError(f"No pvserver record found for project '{project_name}' to delete.")

# =============================================================================
# COMBINED PVSERVER OPERATIONS
# =============================================================================

def get_all_running_pvservers_combined() -> List[Dict]:
    """Get all running pvservers from both tasks and projects."""
    task_pvservers = get_running_pvservers()
    project_pvservers = get_running_project_pvservers()
    
    # Add source information
    for record in task_pvservers:
        record['source'] = 'task'
        record['identifier'] = record['task_id']
    
    for record in project_pvservers:
        record['source'] = 'project'
        record['identifier'] = record['project_name']
    
    return task_pvservers + project_pvservers

def count_all_running_pvservers() -> int:
    """Count all running pvservers from both tasks and projects."""
    return count_running_pvservers() + count_running_project_pvservers()

# =============================================================================
# LEGACY FUNCTIONS (keeping for backward compatibility)
# =============================================================================

def get_inactive_pvservers(hours_threshold: int = 4) -> List[Dict]:
    """Get inactive pvserver records older than the threshold"""
    cutoff_time = datetime.now() - timedelta(hours=hours_threshold)
    query = "SELECT task_id, pvserver_port, pvserver_pid, pvserver_last_activity FROM tasks WHERE pvserver_status = 'running' AND pvserver_last_activity < ? ORDER BY pvserver_last_activity ASC"
    return [dict(row) for row in execute_query(query, (cutoff_time,), fetch_all=True)]

def link_task_to_pvserver(task_id: str, port: int, pid: int):
    """Link a task to a running pvserver (for task-based operations)"""
    set_pvserver_running(task_id, port, pid)

def get_all_tasks() -> List[Dict]:
    """Get all tasks from the database"""
    query = "SELECT * FROM tasks ORDER BY created_at DESC"
    return [dict(row) for row in execute_query(query, fetch_all=True)]

def delete_task(task_id: str):
    """Delete a task from the database"""
    execute_query("DELETE FROM tasks WHERE task_id = ?", (task_id,))

def get_tasks_by_status(status: str) -> List[Dict]:
    """Get tasks by status"""
    query = "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC"
    return [dict(row) for row in execute_query(query, (status,), fetch_all=True)]

def get_database_stats() -> Dict:
    """Get database statistics"""
    stats = {}
    
    # Task stats
    task_count = execute_query("SELECT COUNT(*) as count FROM tasks", fetch_one=True)
    stats['total_tasks'] = task_count['count'] if task_count else 0
    
    running_task_pvservers = execute_query("SELECT COUNT(*) as count FROM tasks WHERE pvserver_status = 'running'", fetch_one=True)
    stats['running_task_pvservers'] = running_task_pvservers['count'] if running_task_pvservers else 0
    
    # Project stats
    try:
        init_project_pvserver_table()
        project_count = execute_query("SELECT COUNT(*) as count FROM project_pvservers", fetch_one=True)
        stats['total_project_pvservers'] = project_count['count'] if project_count else 0
        
        running_project_pvservers = execute_query("SELECT COUNT(*) as count FROM project_pvservers WHERE status = 'running'", fetch_one=True)
        stats['running_project_pvservers'] = running_project_pvservers['count'] if running_project_pvservers else 0
    except DatabaseError:
        stats['total_project_pvservers'] = 0
        stats['running_project_pvservers'] = 0
    
    return stats

def cleanup_stale_pvserver_entries() -> List[str]:
    """Clean up stale pvserver entries and return list of cleaned task IDs"""
    stale_entries = []
    
    # Clean up task-based pvservers
    running_pvservers = get_running_pvservers()  # This automatically cleans up stale entries
    
    # Clean up project-based pvservers
    running_project_pvservers = get_running_project_pvservers()  # This also cleans up stale entries
    
    return stale_entries

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