# Command Execution Feature

This document describes the new command execution functionality that allows running OpenFOAM commands directly on the server through the API.

## Overview

The command execution feature enables remote execution of OpenFOAM commands (and other system commands) within project directories. This is particularly useful for:

- Running mesh generation commands (`blockMesh`, `snappyHexMesh`)
- Executing solvers (`foamRun`, `simpleFoam`, `pimpleFoam`)
- Running utilities (`checkMesh`, `decomposePar`, `reconstructPar`)
- Performing post-processing operations

## API Endpoint

**POST** `/api/projects/{project_name}/run_command`

### Request Format

```json
{
  "command": "blockMesh",
  "args": ["-case", "."],
  "environment": {
    "WM_PROJECT_DIR": "/opt/openfoam8"
  },
  "working_directory": "active_run",
  "timeout": 300
}
```

### Response Format

```json
{
  "success": true,
  "exit_code": 0,
  "stdout": "Creating block mesh from \"system/blockMeshDict\"...",
  "stderr": "",
  "execution_time": 2.45,
  "command": "blockMesh -case .",
  "working_directory": "/home/ubuntu/foam_projects/my_project/active_run",
  "timestamp": "2025-01-10T12:00:00.000000"
}
```

## Features

### 1. Flexible Command Execution
- Execute any system command (not just OpenFOAM)
- Support for command arguments
- Custom environment variables
- Configurable working directory

### 2. Robust Error Handling
- Timeout protection (default: 5 minutes)
- Capture both stdout and stderr
- Proper exit code reporting
- Output size limits (10MB max)

### 3. OpenFOAM Command Validation
- Built-in validation for common OpenFOAM commands
- Suggestions for similar commands if validation fails
- Logging of unknown commands (but execution still allowed)

### 4. Security Features
- Commands execute within project directories only
- No shell interpretation (uses subprocess directly)
- Timeout protection against runaway processes
- Output size limits to prevent memory issues

## Usage Examples

### Basic Mesh Generation

```bash
curl -X POST http://your-server:8000/api/projects/cavity_flow/run_command \
  -H "Content-Type: application/json" \
  -d '{
    "command": "blockMesh",
    "args": ["-case", "."]
  }'
```

### Solver Execution with Custom Timeout

```bash
curl -X POST http://your-server:8000/api/projects/cavity_flow/run_command \
  -H "Content-Type: application/json" \
  -d '{
    "command": "foamRun",
    "args": ["-solver", "incompressibleFluid"],
    "timeout": 1800
  }'
```

### Mesh Quality Check

```bash
curl -X POST http://your-server:8000/api/projects/cavity_flow/run_command \
  -H "Content-Type: application/json" \
  -d '{
    "command": "checkMesh",
    "args": ["-case", "."]
  }'
```

### Custom Environment Variables

```bash
curl -X POST http://your-server:8000/api/projects/cavity_flow/run_command \
  -H "Content-Type: application/json" \
  -d '{
    "command": "foamRun",
    "args": ["-solver", "incompressibleFluid"],
    "environment": {
      "OMP_NUM_THREADS": "4",
      "FOAM_SIGFPE": "1"
    }
  }'
```

## Best Practices

### 1. Timeout Management
- Set appropriate timeouts for long-running commands
- Default timeout is 300 seconds (5 minutes)
- Consider mesh size and complexity when setting timeouts

### 2. Working Directory
- Default working directory is `active_run` within the project
- Can be changed to any subdirectory within the project
- Directory is created automatically if it doesn't exist

### 3. Output Handling
- Check both `success` flag and `exit_code` for command status
- Large outputs are automatically truncated (10MB limit)
- Both stdout and stderr are captured

### 4. Error Recovery
- Failed commands return `success: false` with error details
- Timeout errors are clearly indicated
- Command not found errors provide suggestions

## Common OpenFOAM Commands

### Mesh Generation
- `blockMesh` - Generate structured mesh from blockMeshDict
- `snappyHexMesh` - Generate unstructured mesh
- `extrudeMesh` - Extrude 2D mesh to 3D

### Solvers
- `foamRun` - Run solver specified in controlDict
- `simpleFoam` - Steady-state solver for turbulent flow
- `pimpleFoam` - Transient solver for turbulent flow
- `icoFoam` - Transient solver for laminar flow

### Utilities
- `checkMesh` - Check mesh quality
- `decomposePar` - Decompose case for parallel processing
- `reconstructPar` - Reconstruct parallel case
- `foamToVTK` - Convert to VTK format for visualization

## Testing

Use the provided test script to verify functionality:

```bash
python3 test_command_execution.py
```

The test script will:
1. Create a test project
2. Upload necessary OpenFOAM files
3. Execute various commands
4. Test error handling and timeouts
5. Verify output handling

## Implementation Details

### Architecture
- `CommandService` class handles command execution
- Subprocess-based execution with proper timeout handling
- Output truncation to prevent memory issues
- Comprehensive error handling and logging

### Security Considerations
- Commands execute within project sandbox
- No shell interpretation (direct subprocess execution)
- Timeout protection against runaway processes
- Output size limits to prevent DoS attacks

### Performance
- Asynchronous execution support
- Efficient output capture
- Proper resource cleanup
- Detailed execution timing

## Troubleshooting

### Common Issues

1. **Command Not Found**
   - Ensure OpenFOAM is properly installed on the server
   - Check that the command is in the system PATH
   - Verify command spelling and capitalization

2. **Timeout Errors**
   - Increase timeout for long-running commands
   - Check system resources (CPU, memory)
   - Consider breaking down complex operations

3. **Permission Errors**
   - Ensure proper file permissions in project directory
   - Check that the server process has execution rights
   - Verify directory structure is correct

4. **Output Truncation**
   - Large outputs are automatically truncated at 10MB
   - Consider redirecting output to files for very large results
   - Use appropriate logging levels for debugging

## Future Enhancements

Potential future improvements:
- Job queue system for long-running commands
- Progress tracking for running commands
- Command history and logging
- Resource usage monitoring
- Parallel execution support
- Custom command templates 