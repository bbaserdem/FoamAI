# Desktop Application - Server Integration Specification

This document outlines the requirements for server infrastructure to integrate with the OpenFOAM Desktop Application. The desktop app expects two main server components: a **REST API Server** and a **ParaView Server (pvserver)**.

## Architecture Overview

```
┌─────────────────────┐    REST API     ┌─────────────────────┐
│   Desktop App       │◄──────────────►│   API Server        │
│   (PySide6/Qt)      │                 │   (Python/Flask)    │
│                     │                 │                     │
│                     │    ParaView     │                     │
│   ParaView Widget   │◄──────────────►│   pvserver          │
│                     │   Connection    │   (Port 11111)      │
└─────────────────────┘                 └─────────────────────┘
```

## 1. REST API Server Requirements

The desktop application communicates with a REST API server for all non-visualization tasks. The server must implement the following endpoints:

### Base Configuration
- **Protocol**: HTTP/HTTPS
- **Content-Type**: `application/json`
- **Default Port**: 8000 (configurable)
- **Base URL**: `http://server_hostname:8000/api/`

### Required Endpoints

#### 1.1 Submit Simulation Scenario
```http
POST /api/submit_scenario
Content-Type: application/json

{
  "scenario": "I want to see effects of 10 mph wind on a cube sitting on the ground",
  "user_id": "optional_user_identifier"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "task_id": "mesh_gen_12345",
  "message": "Understood: simulating 10 mph wind on a cube. Generating mesh...",
  "estimated_time": 30
}
```

**Response (Error):**
```json
{
  "status": "error",
  "message": "Invalid scenario description",
  "details": "Please provide more specific parameters"
}
```

#### 1.2 Check Task Status
```http
GET /api/task_status/{task_id}
```

**Response:**
```json
{
  "status": "in_progress",
  "task_id": "mesh_gen_12345",
  "progress": 65,
  "message": "Generating mesh...",
  "file_path": null
}
```

**Status Values:**
- `"in_progress"` - Task is running
- `"completed"` - Task finished successfully
- `"error"` - Task failed
- `"waiting_approval"` - Mesh ready for user validation

#### 1.3 Mesh Approval/Rejection
```http
POST /api/approve_mesh
Content-Type: application/json

{
  "task_id": "mesh_gen_12345",
  "approved": true,
  "feedback": "Mesh looks good, proceed with simulation"
}
```

```http
POST /api/reject_mesh
Content-Type: application/json

{
  "task_id": "mesh_gen_12345",
  "approved": false,
  "feedback": "Mesh is too coarse near the cube, please refine"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Mesh approved. Starting simulation...",
  "new_task_id": "simulation_67890"
}
```

#### 1.4 Get Results
```http
GET /api/results/{task_id}
```

**Response:**
```json
{
  "status": "completed",
  "task_id": "simulation_67890",
  "file_path": "/path/to/results/case.foam",
  "file_type": "openfoam",
  "time_steps": [0, 0.1, 0.2, 0.3, 0.4, 0.5],
  "available_fields": ["p", "U", "k", "epsilon", "nut"]
}
```

### Error Handling
All endpoints should return appropriate HTTP status codes:
- `200` - Success
- `202` - Accepted (for async operations)
- `400` - Bad Request (invalid input)
- `404` - Not Found (invalid task_id)
- `500` - Internal Server Error

## 2. ParaView Server (pvserver) Requirements

The desktop application connects directly to a ParaView server for visualization rendering.

### Configuration
- **Port**: 11111 (default, configurable)
- **Protocol**: ParaView client-server protocol
- **Connection**: `paraview.simple.Connect("server_hostname", 11111)`

### Server Setup Commands
```bash
# Start pvserver (example)
pvserver --server-port=11111 --disable-xdisplay-test
```

### Requirements
- **ParaView Version**: 5.9+ recommended
- **Qt Support**: Required for proper rendering
- **OpenFOAM Reader**: Must be available (`vtkOpenFOAMReader`)
- **Multi-client Support**: Should handle multiple desktop app connections

### File Access
The pvserver must have access to OpenFOAM case files at the paths returned by the REST API. Ensure:
- File permissions allow pvserver to read `.foam` files
- Directory structure is accessible
- Network file systems are properly mounted if applicable

## 3. File Format Specifications

### OpenFOAM Case Structure
The desktop application expects standard OpenFOAM case structure:
```
case_directory/
├── case.foam                 # Main case file
├── constant/
│   ├── polyMesh/
│   └── physicalProperties
├── system/
│   ├── controlDict
│   ├── fvSchemes
│   └── fvSolution
├── 0/                        # Initial time directory
│   ├── p
│   ├── U
│   └── k
└── [time_directories]/       # Solution time steps
    ├── 0.1/
    ├── 0.2/
    └── ...
```

### Supported Field Names
The desktop app recognizes these common OpenFOAM fields:
- `p` - Pressure
- `U` - Velocity
- `k` - Kinetic Energy
- `epsilon` - Dissipation Rate
- `omega` - Specific Dissipation Rate
- `nut` - Turbulent Viscosity
- `nuTilda` - Modified Viscosity
- `v2` - Velocity Scale
- `f` - Elliptic Relaxation

## 4. Communication Flow

### Typical Workflow
1. **User Input**: Desktop app sends scenario to `/api/submit_scenario`
2. **Mesh Generation**: Server processes request, generates mesh
3. **Status Polling**: Desktop app polls `/api/task_status/{task_id}`
4. **Mesh Visualization**: When ready, desktop app connects to pvserver and loads mesh
5. **User Validation**: User approves/rejects mesh via `/api/approve_mesh` or `/api/reject_mesh`
6. **Simulation**: Server runs OpenFOAM simulation
7. **Results Visualization**: Desktop app loads results via pvserver

### Connection Management
- Desktop app maintains persistent connection to pvserver during session
- REST API calls are stateless and can be load-balanced
- Handle connection drops gracefully with reconnection logic

## 5. Configuration Interface

The desktop application reads server configuration from `config.py`:

```python
# config.py
class Config:
    # REST API Server
    API_BASE_URL = "http://localhost:8000/api"
    API_TIMEOUT = 30  # seconds
    
    # ParaView Server
    PARAVIEW_HOST = "localhost"
    PARAVIEW_PORT = 11111
    
    # Polling intervals
    STATUS_POLL_INTERVAL = 2  # seconds
    MAX_POLL_ATTEMPTS = 300   # 10 minutes max
```

Server teams should coordinate these values with the desktop application deployment.

## 6. Security Considerations

### Authentication (Optional)
If authentication is required:
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "engineer123",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "status": "success",
  "token": "jwt_token_here",
  "expires_in": 3600
}
```

Then include in subsequent requests:
```http
Authorization: Bearer jwt_token_here
```

### Network Security
- Consider VPN or SSH tunneling for pvserver connections
- Use HTTPS for REST API in production
- Validate all file paths to prevent directory traversal

## 7. Performance Requirements

### REST API
- Response time: < 500ms for status endpoints
- Concurrent users: Support at least 10 simultaneous users
- File upload: Handle large mesh files (up to 1GB)

### ParaView Server
- Memory: Support meshes up to 10M cells
- Rendering: Target 30 FPS for interactive visualization
- Network: Optimize for low-latency image streaming

## 8. Testing & Validation

### Test Endpoints
Provide test endpoints for validation:
```http
GET /api/health
GET /api/version
POST /api/test/simple_case
```

### Sample Test Case
A simple test case should be available:
- Basic cube geometry
- Simple boundary conditions
- Quick solve time (< 1 minute)
- All standard fields available

## 9. Troubleshooting

### Common Issues
1. **ParaView Connection Failed**
   - Check pvserver is running on correct port
   - Verify firewall settings
   - Ensure Qt support is available

2. **File Not Found Errors**
   - Verify file paths returned by API are accessible to pvserver
   - Check file permissions
   - Ensure network mounts are working

3. **Slow Performance**
   - Monitor server resource usage
   - Check network latency between components
   - Consider local file caching

### Logging Requirements
Please log:
- All REST API requests/responses
- ParaView server connections/disconnections
- File access operations
- Error conditions with stack traces

## 10. Support & Contact

For integration questions or issues:
- Include relevant log files
- Specify desktop app version
- Provide server configuration details
- Include sample .foam files if applicable

---

**Note**: This specification is for the desktop application integration. The actual OpenFOAM simulation setup, AI workflow, and mesh generation logic are handled by the server teams and not covered in this document. 
