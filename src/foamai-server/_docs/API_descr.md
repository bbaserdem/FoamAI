# FoamAI Server API Documentation

## Project-Based Workflow API

This document describes the REST API endpoints for FoamAI Server's project-based workflow, which allows users to create projects, upload files, and manage ParaView servers (pvservers) for OpenFOAM simulations.

### Base URL
```
http://your-server:8000
```

---

## Health Check

### GET /health
Check server health and status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-10T12:00:00.000000",
  "database_connected": true,
  "running_pvservers": 0,
  "running_project_pvservers": 0
}
```

---

## Project Management

### POST /api/projects
Create a new project.

**Request Body:**
```json
{
  "project_name": "my_simulation_project",
  "description": "CFD simulation of airflow around a cylinder"
}
```

**Response (200):**
```json
{
  "project_name": "my_simulation_project",
  "project_path": "/home/ubuntu/foam_projects/my_simulation_project",
  "description": "CFD simulation of airflow around a cylinder",
  "created_at": "2025-01-10T12:00:00.000000",
  "message": "Project created successfully"
}
```

**Error Responses:**
- `400`: Project name already exists or invalid
- `500`: Server error creating project

### GET /api/projects
List all projects.

**Response (200):**
```json
{
  "projects": [
    {
      "project_name": "my_simulation_project",
      "project_path": "/home/ubuntu/foam_projects/my_simulation_project",
      "description": "CFD simulation of airflow around a cylinder",
      "created_at": "2025-01-10T12:00:00.000000"
    }
  ],
  "count": 1
}
```

### GET /api/projects/{project_name}
Get information about a specific project.

**Response (200):**
```json
{
  "project_name": "my_simulation_project",
  "project_path": "/home/ubuntu/foam_projects/my_simulation_project",
  "description": "CFD simulation of airflow around a cylinder",
  "created_at": "2025-01-10T12:00:00.000000",
  "files": ["system/controlDict", "constant/polyMesh/blockMeshDict"],
  "file_count": 2,
  "total_size": 1024
}
```

**Error Responses:**
- `404`: Project not found

### DELETE /api/projects/{project_name}
Delete a project and all its files.

**Response (200):**
```json
{
  "message": "Project 'my_simulation_project' deleted successfully"
}
```

**Error Responses:**
- `404`: Project not found
- `500`: Error deleting project

---

## File Management

### POST /api/projects/{project_name}/upload
Upload a file to a project's active_run directory.

**Request:** Multipart form data
- `file`: File to upload (max 300MB)
- `destination_path`: Relative path within active_run directory

**Example using curl:**
```bash
curl -X POST \
  -F "file=@blockMeshDict" \
  -F "destination_path=constant/polyMesh/blockMeshDict" \
  http://your-server:8000/api/projects/my_project/upload
```

**Response (200):**
```json
{
  "filename": "blockMeshDict",
  "file_path": "active_run/constant/polyMesh/blockMeshDict",
  "file_size": 2048,
  "upload_time": "2025-01-10T12:00:00.000000",
  "message": "File uploaded successfully to my_project/active_run"
}
```

**Error Responses:**
- `404`: Project not found
- `413`: File too large (max 300MB)
- `500`: Upload failed

---

## Project-Based PVServer Management

### POST /api/projects/{project_name}/pvserver/start
Start a ParaView server for a project.

**Request Body:**
```json
{
  "port": 11111
}
```
*Note: Port is optional. If not specified, an available port will be automatically assigned.*

**Response (200):**
```json
{
  "project_name": "my_simulation_project",
  "port": 11111,
  "pid": 12345,
  "case_path": "/home/ubuntu/foam_projects/my_simulation_project/active_run",
  "status": "running",
  "started_at": "2025-01-10T12:00:00.000000",
  "last_activity": "2025-01-10T12:00:00.000000",
  "connection_string": "localhost:11111",
  "message": "PVServer started successfully for project 'my_simulation_project'"
}
```

**Error Responses:**
- `404`: Project not found
- `400`: Project already has a running pvserver
- `500`: Failed to start pvserver

### GET /api/projects/{project_name}/pvserver/info
Get ParaView server information for a project.

**Response (200) - PVServer exists:**
```json
{
  "project_name": "my_simulation_project",
  "port": 11111,
  "pid": 12345,
  "case_path": "/home/ubuntu/foam_projects/my_simulation_project/active_run",
  "status": "running",
  "started_at": "2025-01-10T12:00:00.000000",
  "last_activity": "2025-01-10T12:00:00.000000",
  "connection_string": "localhost:11111",
  "error_message": null
}
```

**Response (200) - No PVServer:**
```json
{
  "project_name": "my_simulation_project",
  "status": "not_found",
  "port": null,
  "pid": null,
  "case_path": null,
  "connection_string": null
}
```

### DELETE /api/projects/{project_name}/pvserver/stop
Stop the ParaView server for a project.

**Response (200):**
```json
{
  "project_name": "my_simulation_project",
  "status": "stopped",
  "message": "PVServer for project 'my_simulation_project' stopped successfully",
  "stopped_at": "2025-01-10T12:00:00.000000"
}
```

**Error Responses:**
- `404`: No pvserver found for project
- `400`: PVServer is not running

---

## System Information

### GET /api/pvservers
List all running PVServers (both task-based and project-based).

**Response (200):**
```json
{
  "task_pvservers": [
    {
      "task_id": "direct_11112_20250110120000",
      "port": 11112,
      "pid": 12346,
      "case_path": "/path/to/case",
      "status": "running",
      "connection_string": "localhost:11112",
      "created_at": "2025-01-10T12:00:00.000000"
    }
  ],
  "project_pvservers": [
    {
      "project_name": "my_simulation_project",
      "port": 11111,
      "pid": 12345,
      "case_path": "/home/ubuntu/foam_projects/my_simulation_project/active_run",
      "status": "running",
      "connection_string": "localhost:11111",
      "started_at": "2025-01-10T12:00:00.000000"
    }
  ],
  "total_count": 2,
  "running_count": 2
}
```

### GET /api/system/stats
Get system statistics.

**Response (200):**
```json
{
  "total_tasks": 5,
  "running_task_pvservers": 1,
  "total_project_pvservers": 3,
  "running_project_pvservers": 1,
  "timestamp": "2025-01-10T12:00:00.000000"
}
```

---

## Typical Project-Based Workflow

### 1. Create a Project
```bash
curl -X POST http://your-server:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "cavity_flow",
    "description": "3D cavity flow simulation"
  }'
```

### 2. Upload OpenFOAM Case Files
```bash
# Upload blockMeshDict
curl -X POST \
  -F "file=@blockMeshDict" \
  -F "destination_path=constant/polyMesh/blockMeshDict" \
  http://your-server:8000/api/projects/cavity_flow/upload

# Upload controlDict
curl -X POST \
  -F "file=@controlDict" \
  -F "destination_path=system/controlDict" \
  http://your-server:8000/api/projects/cavity_flow/upload
```

### 3. Start PVServer for Visualization
```bash
curl -X POST http://your-server:8000/api/projects/cavity_flow/pvserver/start \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 4. Connect ParaView Client
Use the returned `connection_string` (e.g., `localhost:11111`) to connect your ParaView client to the server.

### 5. Stop PVServer When Done
```bash
curl -X DELETE http://your-server:8000/api/projects/cavity_flow/pvserver/stop
```

### 6. Clean Up (Optional)
```bash
curl -X DELETE http://your-server:8000/api/projects/cavity_flow
```

---

## Error Handling

All endpoints return appropriate HTTP status codes:

- **200**: Success
- **400**: Bad request (invalid parameters, duplicate resources)
- **404**: Resource not found
- **413**: Payload too large (file upload)
- **422**: Validation error
- **500**: Internal server error

Error responses include detailed error information:
```json
{
  "detail": "Project 'nonexistent_project' not found",
  "error_type": "ProjectError",
  "timestamp": "2025-01-10T12:00:00.000000"
}
```

---

## Notes

- **File Storage**: All project files are stored in the server's `foam_projects` directory under `{project_name}/active_run/`
- **PVServer Ports**: Available ports range from 11111-11116 by default
- **File Size Limits**: Maximum upload size is 300MB per file
- **Concurrent PVServers**: Limited by server configuration (default: 5 concurrent)
- **Process Management**: PVServers are automatically cleaned up on server shutdown
- **Database**: All project and pvserver information is stored in SQLite database 