# Refactoring Candidates for FoamAI `backend_api`

This document outlines potential areas for refactoring within the `backend_api` codebase. The goal of these suggestions is to improve modularity, reduce complexity, and increase maintainability and testability. The primary candidates for refactoring are `pvserver_manager.py` and `celery_worker.py`.

---

## 1. Introduce a Data Access Layer (DAL) / Repository Pattern

**Problem:**
Database logic (raw SQL queries) is currently scattered across multiple files, primarily `pvserver_manager.py` and `celery_worker.py`. This leads to:
- **Duplicated Code:** Functions like `update_pvserver_status` in `pvserver_manager.py` and `update_task_status` in `celery_worker.py` have overlapping responsibilities.
- **Maintenance Overhead:** Changing the database schema requires finding and updating raw SQL strings in many different places.
- **Poor Testability:** It's difficult to test business logic without also testing the database interactions.
- **Mixed Concerns:** High-level application logic is tightly coupled with low-level database access.

**Proposed Solution:**
Create a new module, for instance `backend_api/database.py` or `backend_api/repository.py`, to handle all interactions with the SQLite database.

**Example Changes:**
- This new module would contain functions like `get_task(task_id)`, `update_task_status(task_id, status, message)`, `get_running_pvserver_for_case(case_path)`, etc.
- In `pvserver_manager.py` and `celery_worker.py`, replace all `sqlite3.connect(...)` blocks and `cursor.execute(...)` calls with calls to the functions in the new data access layer.

**Benefits:**
- **Centralization:** All database logic lives in one place.
- **Simplicity:** The rest of the code becomes cleaner and more focused on its primary responsibility.
- **Flexibility:** It would be much easier to switch to a different database or add an ORM in the future.

---

## 2. Decouple Process and Port Management from Business Logic

**Problem:**
The `pvserver_manager.py` file is a large module (nearly 500 lines) that acts as a "God Object." It manages:
- `pvserver` process lifecycles (`subprocess`, `psutil`).
- Network port allocation and checking.
- Database state.
- High-level business logic (`ensure_pvserver_for_task`).

This violates the Single Responsibility Principle and makes the module difficult to understand, test, and maintain.

**Proposed Solution:**
Break `pvserver_manager.py` into smaller, more focused modules:

1.  **`process_utils.py`:** Would contain functions for starting, stopping, and validating external processes (e.g., `start_pvserver`, `stop_process`, `is_pid_running`). This module would wrap `subprocess` and `psutil`.
2.  **`port_utils.py`:** A simple utility for finding and checking the availability of network ports.
3.  **`pvserver_service.py` (or a refactored `pvserver_manager.py`):** This would become a higher-level service layer. It would orchestrate the other modules and contain the core business logic, but it would not perform low-level process or database operations directly.

**Benefits:**
- **Modularity:** Each part of the system has a clear, well-defined responsibility.
- **Testability:** Each module can be tested independently. For example, you could mock the `process_utils` module to test the service layer without actually starting any processes.
- **Readability:** Smaller, focused files are easier to read and understand.

---

## 3. Refactor Repetitive Celery Task Structure

**Problem:**
The tasks within `celery_worker.py` (`generate_mesh_task`, `run_solver_task`, `run_openfoam_command_task`) are highly repetitive. They all follow the same basic pattern:
1.  Update task status to `in_progress`.
2.  Wrap a `subprocess.run` call in a `try...except` block.
3.  Call `ensure_foam_file`.
4.  Call `start_pvserver_for_task`.
5.  Update task status to a final state (`completed`, `error`, etc.).

This boilerplate code makes the tasks verbose and harder to maintain.

**Proposed Solution:**
Create a generic Celery task or a higher-order function that encapsulates this shared logic.

**Example (Conceptual):**
A single, generic task could take the core command as an argument and handle all the surrounding boilerplate for status updates, error handling, and `pvserver` management.

```python
# In celery_worker.py

def _run_foam_command(command, case_path, task_id):
    # Just the subprocess part
    subprocess.run(command, cwd=case_path, check=True)

@celery_app.task(bind=True)
def foam_task_runner(self, command, case_path, description):
    """A generic task to run any foam command."""
    task_id = self.request.id
    
    # Delegate to DAL
    db.update_task_status(task_id, 'in_progress', description)
    
    try:
        _run_foam_command(command, case_path, task_id)
        
        # Post-run logic
        fs.ensure_foam_file(case_path)
        pvserver_info = pvserver_service.ensure_pvserver_for_task(task_id, case_path)
        
        db.update_task_status(task_id, 'completed', 'Command executed successfully.')
        return {'status': 'SUCCESS', 'pvserver': pvserver_info}

    except Exception as e:
        db.update_task_status(task_id, 'error', str(e))
        return {'status': 'FAILURE', 'error': str(e)}

# The old tasks would now just be calls to the new generic task.
def generate_mesh(task_id):
    foam_task_runner.delay(['blockMesh'], '/path/to/case', 'Generating mesh...')
```

**Benefits:**
- **DRY (Don't Repeat Yourself):** Eliminates a significant amount of redundant code.
- **Maintainability:** Changes to the task execution flow (e.g., how pvservers are started) only need to be made in one place.
- **Clarity:** The individual tasks become much simpler, effectively just declaring the specific command that needs to be run. 