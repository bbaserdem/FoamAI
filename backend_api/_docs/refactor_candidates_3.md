# Refactoring Candidates for FoamAI Backend API

This document outlines potential areas for refactoring within the `backend_api` directory. The goal of these suggestions is to improve code clarity, reduce complexity, enhance maintainability, and solidify the overall architecture.

---

### 1. Architectural Issue: Circular Dependency & Responsibility Violation

The most critical issue is the circular dependency between `database.py` and `process_validator.py`.

-   **What is happening:**
    -   `database.py` has enhanced functions (e.g., `get_running_pvservers_validated`) that need to validate if a process is still running.
    -   To do this, they import and use the `validator` from `process_validator.py`.
    -   The `validator`'s methods (e.g., `validate_and_update_status`) then import and call functions from `database.py` (e.g., `update_pvserver_status`) to clean up the database if a process is found to be dead.
    -   This loop is broken by using a local, function-level import inside `database.py`, which is a strong indicator of an architectural smell.

-   **Why this is a problem:**
    -   **Violation of Single Responsibility Principle (SRP):** The `ProcessValidator`'s job should be to *validate processes*. It should not be responsible for triggering database writes. This mixes the concerns of validation and data persistence.
    -   **Reduced Clarity:** The flow of control is confusing. A function in the database layer calls a validator, which then calls back into the database layer. This makes the code hard to follow and debug.
    -   **Brittleness:** This tangled dependency makes the code harder to change. Modifying a database function might have unexpected effects on the validator and vice-versa.

-   **Proposed Refactor:**
    1.  **Make the Validator Dumb:** The `ProcessValidator` methods should only return validation results (e.g., `True` or `False`). They should not accept callbacks or call database functions.
    2.  **Move Responsibility to the DAL:** The `_validated` functions within `database.py` should call the validator, inspect the result, and then perform any necessary database cleanup by calling other functions *within the same `database.py` module*.
    3.  **Remove Circular Dependency:** This change would remove the need for `process_validator.py` to import `database.py` at all, breaking the cycle and clarifying the layers of responsibility.

---

### 2. `process_utils.py`: Manual Process Management

This file is overly complex due to its attempt to manually manage the lifecycle of `pvserver` subprocesses.

-   **What is happening:**
    -   It uses global variables (`_active_pvservers`, `_shutdown_in_progress`) to maintain state.
    -   It uses custom signal handlers (`SIGCHLD`) to reap zombie processes.
    -   It uses `atexit` for cleanup on shutdown.
    -   It spawns threads from within signal handlers to perform database updates.

-   **Why this is a problem:**
    -   **Complexity and Brittleness:** This kind of low-level process management is notoriously difficult to get right. It's prone to race conditions and hard-to-debug issues, especially when mixed with Celery workers (as noted by the comments in the code).
    -   **Global State:** The use of global variables makes the code difficult to reason about and impossible to test in isolation.

-   **Proposed Refactor:**
    1.  **Create a `ProcessManager` Class:** Encapsulate all state (like the dictionary of active servers) and logic (start, stop, validate) within a singleton class. This would eliminate global variables and provide a clear, testable interface.
    2.  **Simplify or Replace Signal Handling:** Instead of complex signal handling, rely more on the "lazy cleanup" approach already present in the `_validated` database functions. Let the system periodically clean itself up when data is requested, rather than relying on brittle signal handlers. For a more robust solution, an external process supervisor like `systemd` or `supervisor` would be a much better long-term choice.

---

### 3. `pvserver_service.py`: Overly Complex Service Logic

This service contains several large, complex functions with tangled responsibilities.

-   **What is happening:**
    -   Functions like `ensure_pvserver_for_task` and `start_pvserver_for_case` are very long, contain numerous commented steps, and handle many concerns (checking limits, finding ports, starting processes, updating the database).
    -   Error handling is inconsistent. Some functions return dictionaries with an "error" key, while others raise exceptions. This complicates the calling code in `main.py`.
    -   The service is littered with `print()` statements for logging.

-   **Proposed Refactor:**
    1.  **Decompose Complex Functions:** Break down `ensure_pvserver_for_task` and `start_pvserver_for_case` into smaller, private helper functions with single responsibilities.
    2.  **Standardize Error Handling:** Consistently use exceptions for error conditions. Instead of `return {"status": "error", "message": ...}`, `raise PVServerServiceError(...)`. This allows the API layer in `main.py` to use a centralized exception handler.
    3.  **Use a Proper Logger:** Replace all `print()` calls with a standard logging library (e.g., Python's `logging` module). This provides levels, formatting, and better control over output.
    4.  **Consolidate Redundant Logic:** The logic for checking concurrency limits and finding available ports is repeated. This can be consolidated.

---

### 4. `database.py`: Inconsistent DAL

The Data Access Layer has several inconsistencies from a partial refactoring.

-   **What is happening:**
    -   There are pairs of functions for the same operation (e.g., `count_running_pvservers` vs. `count_running_pvservers_validated`).
    -   Database write operations (`create_task`, `update_task_status`) catch `DatabaseError` and return `False`, hiding the original error from the caller.
    -   `update_pvserver_status` is a long function that uses `if/elif/else` to build different SQL queries.

-   **Proposed Refactor:**
    1.  **Consolidate Function Pairs:** Remove the older, non-validating functions. The `_validated` functions should become the default, and their names should be simplified (e.g., `get_running_pvservers_validated` becomes `get_running_pvservers`).
    2.  **Propagate Exceptions:** Remove the `try...except` blocks that return `False`. Let `DatabaseError` exceptions propagate up to the service layer.
    3.  **Decompose `update_pvserver_status`:** Break this function into smaller, more specific functions like `set_pvserver_status_running`, `set_pvserver_status_error`, etc. This improves readability and reduces complexity.

---

### 5. `main.py`: API Layer Cleanup

The main API file has become cluttered.

-   **What is happening:**
    -   All Pydantic request/response models are defined in this file, making it very long.
    -   Exception handling logic is duplicated across many endpoints.
    -   The `/api/reject_mesh` endpoint is redundant, as `/api/approve_mesh` already handles both cases.

-   **Proposed Refactor:**
    1.  **Extract Models:** Move all Pydantic models to a new `backend_api/schemas.py` file.
    2.  **Centralize Exception Handling:** Create custom exception handlers (e.g., `@app.exception_handler(ProjectError)`) to handle custom exceptions from the service layer, reducing boilerplate code in the endpoints.
    3.  **Remove Redundant Endpoint:** Delete the `/api/reject_mesh` endpoint and update any client code to use `/api/approve_mesh` with `{"approved": false}`. 