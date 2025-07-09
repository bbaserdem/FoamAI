# Zombie Process Handling Implementation

This document describes the robust zombie process handling implementation for the FoamAI pvserver management system.

## Problem Statement

The original pvserver management system had a critical flaw: when ParaView clients disconnected, the pvserver processes would be killed but the Celery worker wouldn't reap the child processes. This led to:

1. **Zombie processes**: Dead processes that remain in the process table
2. **Database inconsistency**: Database showing processes as "running" when they were actually dead
3. **Port allocation issues**: Stale database entries preventing port reuse
4. **Resource leaks**: Accumulation of zombie processes over time

## Solution Overview

We implemented a multi-layered approach to handle zombie processes robustly:

### 1. Signal Handler Strategy
- **SIGCHLD Signal Handler**: Automatic reaping of dead child processes
- **Process Groups**: Isolate pvserver processes for better lifecycle management
- **Thread-Safe Cleanup**: Proper synchronization using threading locks

### 2. Lazy Cleanup Strategy
- **Process Validation**: Always verify PIDs before making allocation decisions
- **Database Reconciliation**: Clean up stale entries when detected
- **Immediate Robustness**: System works correctly even with stale data

### 3. Enhanced Tracking
- **In-Memory Tracking**: Track active processes for faster cleanup
- **Database Consistency**: Maintain accurate process state
- **Health Monitoring**: Built-in system state reporting

## Implementation Details

### Core Components

#### 1. Signal Handlers (`pvserver_manager.py`)
```python
def setup_signal_handlers():
    """Set up signal handlers for automatic zombie process cleanup"""
    def reap_children(signum, frame):
        """Signal handler to reap zombie children"""
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:  # No more children to reap
                    break
                # Update database and tracking
            except OSError:
                break
    
    signal.signal(signal.SIGCHLD, reap_children)
```

#### 2. Process Groups
```python
def start_pvserver(case_path: str, port: int, task_id: str) -> int:
    """Start pvserver in its own process group"""
    process = subprocess.Popen(
        cmd,
        preexec_fn=os.setpgrp  # Create new process group
    )
```

#### 3. Process Validation
```python
def validate_pvserver_pid(pid: int, expected_port: int = None) -> bool:
    """Validate that a PID is actually a running pvserver process"""
    if not psutil.pid_exists(pid):
        return False
    
    process = psutil.Process(pid)
    if process.name() != 'pvserver':
        return False
    
    # Optional port validation
    return True
```

#### 4. Lazy Cleanup
```python
def cleanup_stale_database_entries():
    """Clean up database entries for dead processes"""
    # Get all "running" records
    # Validate each process
    # Update database for dead processes
```

### Integration Points

#### 1. Celery Worker Integration
```python
@worker_ready.connect
def setup_worker_signal_handlers(**kwargs):
    """Set up signal handlers when worker starts"""
    setup_signal_handlers()
```

#### 2. Process Lifecycle Management
- **Start**: Process groups + signal handlers + tracking
- **Monitor**: Process validation + health checks
- **Cleanup**: Automatic reaping + database updates

## Key Features

### 1. Automatic Zombie Reaping
- Signal handlers automatically reap dead children
- Database updated when processes die
- No manual intervention required

### 2. Robust Process Validation
- Always verify process existence before allocation
- Check process name and port binding
- Handle edge cases (access denied, zombie processes)

### 3. Database Consistency
- Lazy cleanup removes stale entries
- Process validation before every operation
- Automatic reconciliation between system state and database

### 4. Resource Management
- Proper port allocation and reuse
- Process group isolation
- Thread-safe operations

### 5. Monitoring and Debugging
- Health check endpoints
- Active process summaries
- Comprehensive error handling

## Testing

### Test Suite (`test_zombie_handling.py`)
- **Signal Handler Setup**: Validates SIGCHLD handler registration
- **Process Validation**: Tests PID validation logic
- **PVServer Lifecycle**: Full process lifecycle testing
- **Lazy Cleanup**: Stale entry cleanup validation
- **Database Consistency**: Data integrity checks
- **Zombie Simulation**: Theoretical zombie handling

### Local Testing (`test_local_zombie_handling.py`)
- Platform-independent tests
- Database cleanup validation
- Tracking system verification
- Zombie scenario simulation

## Deployment Instructions

### 1. Update Dependencies
The implementation requires these dependencies (already in requirements.txt):
- `psutil==6.1.1`
- `requests==2.32.3`

### 2. Database Migration
If upgrading from an older version:
```bash
# Backup existing database
cp tasks.db tasks.db.backup

# Remove old database and recreate with new schema
rm tasks.db
python database_setup.py
```

### 3. Celery Worker Restart
After deployment, restart the Celery worker to enable signal handlers:
```bash
# Stop existing worker
pkill -f "celery worker"

# Start new worker with signal handling
celery -A celery_worker worker --loglevel=info
```

### 4. Verification
Run the test suite to verify implementation:
```bash
python test_local_zombie_handling.py
```

## Production Considerations

### 1. Signal Handler Safety
- Signal handlers use thread-safe operations
- Non-blocking system calls (WNOHANG)
- Proper error handling for edge cases

### 2. Performance Impact
- Minimal overhead from signal handling
- Efficient process validation using psutil
- Lazy cleanup only when needed

### 3. Monitoring
- Health check endpoints for system state
- Comprehensive logging of process lifecycle
- Database consistency monitoring

### 4. Error Recovery
- Graceful handling of process access errors
- Automatic cleanup of inconsistent states
- Fallback mechanisms for edge cases

## API Changes

### New Endpoints
- `POST /api/cleanup_pvservers`: Manual cleanup trigger
- `GET /api/pvserver_info/{task_id}`: Process state information

### Enhanced Responses
All task responses now include pvserver information:
```json
{
  "pvserver": {
    "status": "running",
    "port": 11111,
    "pid": 12345,
    "connection_string": "localhost:11111",
    "reused": false
  }
}
```

## Troubleshooting

### Common Issues

1. **Signal Handler Not Working**
   - Ensure worker is restarted after deployment
   - Check for conflicting signal handlers
   - Verify SIGCHLD is not being ignored

2. **Process Validation Failures**
   - Ensure psutil is installed and working
   - Check process permissions
   - Verify ParaView/pvserver installation

3. **Database Inconsistencies**
   - Run manual cleanup: `cleanup_stale_database_entries()`
   - Check database permissions
   - Verify schema is up to date

### Debug Commands
```bash
# Check active processes
python -c "from pvserver_manager import get_active_pvserver_summary; print(get_active_pvserver_summary())"

# Manual cleanup
python -c "from pvserver_manager import cleanup_stale_database_entries; print(cleanup_stale_database_entries())"

# Process validation
python -c "from pvserver_manager import validate_pvserver_pid; print(validate_pvserver_pid(PID))"
```

## Future Enhancements

1. **Periodic Health Checks**: Background task to monitor system health
2. **Metrics Collection**: Detailed process lifecycle metrics
3. **Auto-scaling**: Dynamic port range adjustment
4. **Process Affinity**: CPU core binding for better performance
5. **Container Support**: Docker/Kubernetes integration

## Conclusion

This implementation provides a robust, production-ready solution for zombie process handling in the FoamAI pvserver management system. The multi-layered approach ensures system reliability while maintaining performance and providing comprehensive monitoring capabilities. 