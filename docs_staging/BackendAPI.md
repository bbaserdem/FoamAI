# FoamAI Backend API Documentation

The FoamAI backend provides a comprehensive REST API for managing CFD simulations, project organization, and ParaView visualization servers. Built with FastAPI and Celery for asynchronous task processing.

## Table of Contents
- [Overview](#overview)
- [API Workflow](#api-workflow)
- [Authentication](#authentication)
- [Base URLs](#base-urls)
- [Core API Endpoints](#core-api-endpoints)
- [Project Management](#project-management)
- [CFD Task Management](#cfd-task-management)
- [ParaView Server Management](#paraview-server-management)
- [System Endpoints](#system-endpoints)
- [Request/Response Models](#requestresponse-models)
- [Error Handling](#error-handling)
- [WebSocket Events](#websocket-events)

## Overview

The FoamAI API follows a task-based asynchronous architecture where CFD operations are submitted as jobs and processed by Celery workers. The API supports:

- **Natural Language CFD Setup**: Convert user descriptions into OpenFOAM configurations
- **Asynchronous Processing**: Long-running simulations handled via background tasks
- **Mesh Validation Workflow**: User approval system for generated meshes
- **ParaView Integration**: Automatic visualization server management
- **Project Organization**: Multi-project workspace management

### Technology Stack
- **API Framework**: FastAPI 
- **Task Queue**: Celery with Redis broker
- **Database**: SQLite for task and project metadata
- **Process Management**: Custom PVServer lifecycle management
- **Container Support**: Docker deployment ready

## API Workflow

```mermaid
graph TD
    A[Client Submits Scenario] --> B[POST /api/submit_scenario]
    B --> C[Generate Mesh Task]
    C --> D[Task Status: waiting_approval]
    D --> E[Client Polls Status]
    E --> F{Mesh Approved?}
    F -->|Yes| G[POST /api/approve_mesh]
    F -->|No| H[Mesh Rejected]
    G --> I[Run Solver Task]
    I --> J[Start PVServer]
    J --> K[Task Status: completed]
    K --> L[GET /api/results/{task_id}]
    L --> M[Visualization Ready]
    
    H --> N[Update Status: rejected]
    
    style A fill:#e1f5fe
    style M fill:#c8e6c9
    style N fill:#ffcdd2
    
    subgraph "Background Processing"
        C
        I
        J
    end
    
    subgraph "User Interaction"
        A
        E
        F
    end
    
    subgraph "Results & Visualization"
        L
        M
    end
```

## Authentication

**Current Status**: No authentication required for MVP
**Future Enhancement**: JWT-based authentication planned for multi-user support

## Base URLs

| Environment | Base URL | Description |
|-------------|----------|-------------|
| **Development** | `http://localhost:8000` | Local development server |
| **Production** | `http://your-server:8000` | Production deployment |
| **API Prefix** | `/api/` | All endpoints prefixed with `/api/` |

## Core API Endpoints

### Health & Status

#### GET `/`
**Description**: Basic health check endpoint

**Response**:
```json
{
  "message": "FoamAI API is running"
}
```

#### GET `/api/health`
**Description**: Detailed health check with timestamp

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

#### GET `/api/version`
**Description**: Get API version information

**Response**:
```json
{
  "version": "1.0.0",
  "api_name": "FoamAI API"
}
```

## Project Management

### Create New Project

#### POST `/api/projects`
**Description**: Creates a new project directory under the FOAM_RUN path

**Request Body**:
```json
{
  "project_name": "my_cfd_project"
}
```

**Response** (201 Created):
```json
{
  "status": "success",
  "project_name": "my_cfd_project",
  "path": "/home/ubuntu/foam_projects/my_cfd_project",
  "message": "Project 'my_cfd_project' created successfully."
}
```

**Validation Rules**:
- Allowed characters: alphanumeric, underscores, dashes, periods
- No duplicate project names
- Must be valid filesystem name

### List Projects

#### GET `/api/projects`
**Description**: Lists all existing projects in the FOAM_RUN directory

**Response**:
```json
{
  "projects": ["cavity_flow", "pipe_analysis", "airfoil_study"],
  "count": 3
}
```

## CFD Task Management

### Submit Simulation Scenario

#### POST `/api/submit_scenario`
**Description**: Submit a CFD scenario for processing with natural language description

**Request Body**:
```json
{
  "scenario_description": "I want to see effects of 10 mph wind on a cube sitting on the ground",
  "mesh_complexity": "medium",
  "solver_type": "incompressible"
}
```

**Response** (202 Accepted):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Scenario submitted successfully. Mesh generation started."
}
```

**Parameters**:
- `scenario_description`: Natural language description of the CFD scenario
- `mesh_complexity`: "low", "medium", or "high" (default: "medium")
- `solver_type`: Solver type identifier (default: "incompressible")

### Check Task Status

#### GET `/api/task_status/{task_id}`
**Description**: Get the current status of a specific task

**Response**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "waiting_approval",
  "message": "Mesh generated. Please review and approve.",
  "file_path": "/home/ubuntu/cavity_tutorial/cavity.foam",
  "case_path": "/home/ubuntu/cavity_tutorial",
  "pvserver": {
    "status": "running",
    "port": 11111,
    "pid": 1234,
    "connection_string": "localhost:11111"
  },
  "created_at": "2024-01-15T10:30:00.123456"
}
```

**Status Values**:
- `pending`: Task submitted, not yet started
- `running`: Task currently executing
- `waiting_approval`: Mesh generated, awaiting user approval
- `completed`: Task finished successfully
- `failed`: Task encountered an error
- `rejected`: User rejected the mesh

### Approve/Reject Mesh

#### POST `/api/approve_mesh`
**Description**: Approve or reject the generated mesh for a task

**Request Body**:
```json
{
  "approved": true,
  "comments": "Mesh looks good, proceed with simulation"
}
```

**Query Parameters**:
- `task_id`: The task ID to approve/reject

**Response** (Approved):
```json
{
  "message": "Mesh approved. Simulation started.",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response** (Rejected):
```json
{
  "message": "Mesh rejected.",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Get Simulation Results

#### GET `/api/results/{task_id}`
**Description**: Get the results of a completed simulation

**Response**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "message": "Simulation completed successfully",
  "file_path": "/home/ubuntu/cavity_tutorial/cavity.foam",
  "case_path": "/home/ubuntu/cavity_tutorial",
  "output": null,
  "pvserver": {
    "status": "running",
    "port": 11111,
    "pid": 1234,
    "connection_string": "localhost:11111"
  }
}
```

### Run Custom OpenFOAM Command

#### POST `/api/run_openfoam_command`
**Description**: Execute a custom OpenFOAM command in a specific case directory

**Request Body**:
```json
{
  "command": "checkMesh",
  "case_path": "/home/ubuntu/cavity_tutorial",
  "description": "Validate mesh quality"
}
```

**Response** (202 Accepted):
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "pending",
  "message": "OpenFOAM command submitted: checkMesh",
  "command": "checkMesh",
  "case_path": "/home/ubuntu/cavity_tutorial"
}
```

## ParaView Server Management

### Start PVServer

#### POST `/api/start_pvserver`
**Description**: Start a ParaView server for a specific case directory

**Request Body**:
```json
{
  "case_path": "/home/ubuntu/cavity_tutorial",
  "port": 11111
}
```

**Response**:
```json
{
  "status": "running",
  "port": 11111,
  "pid": 1234,
  "connection_string": "localhost:11111",
  "case_path": "/home/ubuntu/cavity_tutorial",
  "message": "PVServer started successfully",
  "error_message": null
}
```

### List Active PVServers

#### GET `/api/pvservers`
**Description**: List all currently active ParaView servers

**Response**:
```json
{
  "pvservers": [
    {
      "port": 11111,
      "pid": 1234,
      "case_path": "/home/ubuntu/cavity_tutorial",
      "status": "running",
      "connection_string": "localhost:11111"
    },
    {
      "port": 11112,
      "pid": 1235,
      "case_path": "/home/ubuntu/pipe_flow",
      "status": "running",
      "connection_string": "localhost:11112"
    }
  ],
  "total_count": 2,
  "port_range": [11111, 11200],
  "available_ports": 88
}
```

### Stop PVServer

#### DELETE `/api/pvservers/{port}`
**Description**: Stop a ParaView server running on a specific port

**Response**:
```json
{
  "status": "stopped",
  "port": 11111,
  "message": "PVServer stopped successfully",
  "error_message": null
}
```

### Get PVServer Info for Task

#### GET `/api/pvserver_info/{task_id}`
**Description**: Get detailed ParaView server information for a specific task

**Response**:
```json
{
  "status": "running",
  "port": 11111,
  "pid": 1234,
  "connection_string": "localhost:11111",
  "reused": false,
  "error_message": null
}
```

### Cleanup Inactive PVServers

#### POST `/api/cleanup_pvservers`
**Description**: Manually trigger cleanup of inactive ParaView servers

**Response**:
```json
{
  "status": "success",
  "message": "Cleaned up 2 inactive pvservers",
  "cleaned_up": [
    {"port": 11113, "pid": 1236},
    {"port": 11114, "pid": 1237}
  ]
}
```

## System Endpoints

All system endpoints provide administrative functionality for monitoring and maintenance.

## Request/Response Models

### Core Data Models

#### Task Status Values
```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running" 
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
```

#### PVServer Status
```python
class PVServerStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    STARTING = "starting"
    STOPPING = "stopping"
```

### Request Models

#### SubmitScenarioRequest
```json
{
  "scenario_description": "string (required)",
  "mesh_complexity": "string (optional, default: 'medium')",
  "solver_type": "string (optional, default: 'incompressible')"
}
```

#### ApprovalRequest
```json
{
  "approved": "boolean (required)",
  "comments": "string (optional)"
}
```

#### OpenFOAMCommandRequest
```json
{
  "command": "string (required)",
  "case_path": "string (required)", 
  "description": "string (optional)"
}
```

#### StartPVServerRequest
```json
{
  "case_path": "string (required)",
  "port": "integer (optional)"
}
```

#### ProjectRequest
```json
{
  "project_name": "string (required, alphanumeric + _-. only)"
}
```

### Response Models

#### Standard Error Response
```json
{
  "detail": "string (error description)"
}
```

#### TaskStatusResponse
```json
{
  "task_id": "string",
  "status": "string",
  "message": "string",
  "file_path": "string (optional)",
  "case_path": "string (optional)",
  "pvserver": "PVServerInfo (optional)",
  "created_at": "string (ISO datetime, optional)"
}
```

#### PVServerInfo
```json
{
  "status": "string",
  "port": "integer (optional)",
  "pid": "integer (optional)", 
  "connection_string": "string (optional)",
  "reused": "boolean (optional)",
  "error_message": "string (optional)"
}
```

## Error Handling

### HTTP Status Codes

| Code | Description | Common Causes |
|------|-------------|---------------|
| **200** | Success | Request completed successfully |
| **201** | Created | Resource created (e.g., new project) |
| **202** | Accepted | Async task submitted successfully |
| **400** | Bad Request | Invalid input parameters |
| **404** | Not Found | Task/resource doesn't exist |
| **409** | Conflict | Resource already exists (e.g., duplicate project) |
| **500** | Internal Server Error | Database/system error |

### Error Response Format

All errors follow a consistent format:

```json
{
  "detail": "Detailed error message explaining what went wrong"
}
```

### Common Error Scenarios

#### Task Not Found (404)
```json
{
  "detail": "Task with ID '550e8400-e29b-41d4-a716-446655440000' not found."
}
```

#### Invalid Approval State (400)
```json
{
  "detail": "Task is not waiting for approval"
}
```

#### Project Already Exists (409)
```json
{
  "detail": "Project 'my_project' already exists"
}
```

#### Database Error (500)
```json
{
  "detail": "Database error: Connection failed"
}
```

#### PVServer Service Error (400/500)
```json
{
  "detail": "A service error occurred during cleanup: Port 11111 is not available"
}
```

### Error Handling Best Practices

1. **Always check HTTP status codes** before processing response data
2. **Parse error details** from the `detail` field for user-friendly messages
3. **Implement retry logic** for 500-level errors
4. **Validate inputs** client-side to minimize 400-level errors
5. **Handle async task failures** by checking task status regularly

## WebSocket Events

**Status**: Not currently implemented
**Future Enhancement**: Real-time task status updates via WebSocket connections

### Planned WebSocket Events

```javascript
// Task status updates
{
  "event": "task_status_changed",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "message": "Simulation progress: 45%"
}

// PVServer events
{
  "event": "pvserver_started", 
  "port": 11111,
  "connection_string": "localhost:11111"
}

// System events
{
  "event": "system_warning",
  "message": "High memory usage detected"
}
```

## Development & Testing

### Running the API Server

```bash
# Development mode
cd src/foamai-server
uv run python -m foamai_server.main

# Production mode with Uvicorn
uv run uvicorn foamai_server.main:app --host 0.0.0.0 --port 8000
```

### API Documentation

Interactive API documentation is automatically available:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

### Testing Endpoints

```bash
# Health check
curl http://localhost:8000/api/health

# Submit scenario
curl -X POST http://localhost:8000/api/submit_scenario \
  -H "Content-Type: application/json" \
  -d '{"scenario_description": "Test wind over cube"}'

# Check task status
curl http://localhost:8000/api/task_status/YOUR_TASK_ID

# List projects
curl http://localhost:8000/api/projects
```

### Integration with FoamAI Components

The backend API integrates with:

- **foamai-core**: Natural language processing and CFD logic
- **foamai-desktop**: GUI client for user interactions
- **foamai-client**: CLI tools for automation
- **Docker containers**: OpenFOAM and ParaView services
- **AWS infrastructure**: Production deployment

For complete integration examples, see the [Contributing Guide](Contributing.md) and [DevOps Guide](DevOps.md).

---

*This API documentation reflects the current implementation and will be updated as new features are added. For the most up-to-date endpoint information, always refer to the interactive API docs at `/docs`.*