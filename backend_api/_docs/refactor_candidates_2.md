# Refactoring Candidates for FoamAI `backend_api` (Round 2)

This document outlines further areas for refactoring within the `backend_api` codebase, following the initial refactoring pass. While the separation of concerns has been significantly improved, there are still opportunities to reduce complexity and improve maintainability.

---

## 1. Refactor Repetitive Celery Task Structure

**Problem:**
The issue of repetitive task logic in `celery_worker.py`, noted in the first refactoring report, persists. The tasks `generate_mesh_task`, `run_solver_task`, and `run_openfoam_command_task` still share a nearly identical structure:
1.  Update task status to `in_progress`.
2.  Wrap a `subprocess.run` call in a large `try...except` block.
3.  Handle `subprocess.CalledProcessError` and generic `Exception` types separately but with similar logic.
4.  Update task status to a final state (`completed`, `error`, etc.) within each block.
5.  Return a dictionary with status and results.

This boilerplate code makes the tasks verbose and difficult to maintain. A change to the error handling or status reporting logic needs to be manually duplicated across all tasks.

**Proposed Solution:**
Create a single, generic Celery task that encapsulates this shared workflow. This new task would accept the specific command and relevant metadata (like a description) as arguments and would handle all the boilerplate for status updates, subprocess execution, and error handling internally.

**Example (Conceptual):**
A single, generic task could be implemented using a decorator or a higher-order function to wrap the core command logic.

```python
# In celery_worker.py

from functools import wraps

def foam_task(description_template):
    """A decorator to create a standardized OpenFOAM Celery task."""
    def decorator(func):
        @wraps(func)
        def wrapper(task_id, case_path, *args, **kwargs):
            command = func(task_id, case_path, *args, **kwargs)
            description = description_template.format(*args, **kwargs)
            
            update_task_status(task_id, 'in_progress', description, case_path=case_path)
            
            try:
                # Run the generated command
                subprocess.run(command, cwd=case_path, capture_output=True, text=True, check=True)
                
                # Post-run logic
                foam_file_path = ensure_foam_file(case_path)
                message = f"{description} completed successfully."
                update_task_status(task_id, 'completed', message, foam_file_path, case_path)
                
                return {"status": "SUCCESS", "message": message}

            except subprocess.CalledProcessError as e:
                error_msg = f'{description} failed: {e.stderr}'
                update_task_status(task_id, 'error', error_msg, case_path=case_path)
                return {"status": "FAILURE", "message": error_msg, "error": e.stderr}
            except Exception as e:
                error_msg = f'Unexpected error during {description}: {str(e)}'
                update_task_status(task_id, 'error', error_msg, case_path=case_path)
                return {"status": "FAILURE", "message": error_msg, "error": str(e)}
        return wrapper
    return decorator

@celery_app.task
@foam_task("Generating mesh")
def generate_mesh_task(task_id, case_path):
    return ['blockMesh']

@celery_app.task
@foam_task("Running solver")
def run_solver_task(task_id, case_path):
    return ['foamRun']

@celery_app.task
@foam_task("Running OpenFOAM command: {command_str}")
def run_openfoam_command_task(task_id, case_path, command, command_str=""):
    return command
```

**Benefits:**
- **DRY (Don't Repeat Yourself):** Dramatically reduces the amount of duplicated code.
- **Maintainability:** Changes to error handling, status updates, or logging need to be made in only one place.
- **Clarity:** The individual task definitions become trivial, highlighting the single command they are responsible for executing.

---

## 2. Consolidate Process Validation Logic and Simplify Service Layer

**Problem:**
The `pvserver_service.py` module contains several functions that are essentially thin wrappers around data access layer (DAL) calls, complicated by duplicated process validation logic. For example:
- `get_running_pvserver_for_case_with_validation` calls `get_running_pvserver_for_case` from the DAL and then adds `validate_pvserver_pid`.
- `cleanup_stale_database_entries` and `cleanup_inactive_pvservers` both iterate over database records and call `validate_pvserver_pid`.
- The core business logic in `ensure_pvserver_for_task` also performs its own validation.

This creates a tangled control flow where it's not clear where the single source of truth for process validation is. It also makes the service layer more complex than necessary.

**Proposed Solution:**
Move the process validation logic into the data access layer (`database.py`). The DAL functions that return `pvserver` records should be responsible for ensuring those records correspond to live processes.

**Example Changes:**
1.  **Enhance DAL Functions:** Modify functions like `get_running_pvserver_for_case` in `database.py` to internally use `validate_pvserver_pid`. If a process is found to be dead, the function should automatically update its status to `stopped` and filter it from the result.
2.  **Simplify Service Layer:** Remove the wrapper functions from `pvserver_service.py` (e.g., `get_running_pvserver_for_case_with_validation`). The service layer can now trust that any "running" pvserver record it receives from the DAL is valid.
3.  **Centralize Configuration:** Move constants like `MAX_CONCURRENT_PVSERVERS` and `CLEANUP_THRESHOLD_HOURS` out of `pvserver_service.py` and into a dedicated configuration file (e.g., `config.py`) to improve separation of concerns.

**Benefits:**
- **Single Responsibility:** The DAL becomes the single source of truth for the state of `pvserver` records, including their validity.
- **Simplified Control Flow:** The service layer becomes much cleaner and easier to follow, as it no longer needs to re-validate data it receives from the DAL.
- **Reduced Complexity:** Eliminates redundant functions and duplicated validation checks.
- **Improved Configuration Management:** Centralizing configuration makes the system more flexible and easier to manage. 