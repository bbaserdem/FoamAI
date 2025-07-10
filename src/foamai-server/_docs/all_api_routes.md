# Complete List of API Routes

This document provides a concise list of all available API endpoints.

## System Endpoints
- `GET /health`
- `GET /api/system/stats`

## Project Management Endpoints
- `POST /api/projects`
- `GET /api/projects`
- `GET /api/projects/{project_name}`
- `DELETE /api/projects/{project_name}`

## File and Command Endpoints
- `POST /api/projects/{project_name}/upload`
- `POST /api/projects/{project_name}/run_command`

## Project-Based PVServer Endpoints
- `POST /api/projects/{project_name}/pvserver/start`
- `DELETE /api/projects/{project_name}/pvserver/stop`
- `GET /api/projects/{project_name}/pvserver/info`

## Task-Based (Legacy) Endpoints
- `POST /api/tasks`
- `GET /api/tasks/{task_id}`
- `PUT /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/reject`
- `GET /api/tasks`
- `DELETE /api/tasks/{task_id}`

## Legacy PVServer Endpoints
- `POST /api/start_pvserver`: Starts a PVServer for a specific case path (task-based).
- `DELETE /api/pvservers/{port}`: Stops a running PVServer by its port number.
- `GET /api/pvservers`: Lists all running PVServers (both task-based and project-based). 