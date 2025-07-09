# FoamAI Backend API - Incremental Implementation Plan

## Current State Assessment

**Existing Foundation (from FOAMAI_API_prd.md):**
- ✅ Basic FastAPI structure with `/api/submit_scenario`, `/api/task_status/{task_id}`, `/api/approve_mesh`
- ✅ SQLite database schema and setup
- ✅ Celery worker with mesh generation and solver tasks
- ✅ Redis broker configuration
- ✅ Basic OpenFOAM integration (blockMesh, icoFoam)

**Target Specification:** SERVER_INTEGRATION.md compliance

**Validation Scripts Created:**
- ✅ `validate_deployment.py` - Remote API testing from local machine
- ✅ `ec2_validation.sh` - EC2 instance validation script
- ✅ `VALIDATION_README.md` - Usage instructions

---

## Phase 1: Core API Foundation & Deployment Validation (Week 1)

### 1.1 Environment Setup & Dependencies
**Goals:**
- Get existing code running on EC2
- Set up development environment
- Validate basic deployment

**Tasks:**
- [ ] Update `requirements.txt` with all dependencies
- [ ] Set up EC2 instance with OpenFOAM and ParaView
- [ ] Test Redis and Celery worker startup on EC2
- [ ] Run `ec2_validation.sh` to verify OpenFOAM installation
- [ ] Verify cavity case runs successfully at `/home/ubuntu/cavity_tutorial`

**Deliverables:**
- Working EC2 deployment environment
- ✅ EC2 validation script passes
- OpenFOAM cavity case runs successfully

### 1.2 API Compliance & Enhancement
**Goals:**
- Align existing endpoints with SERVER_INTEGRATION.md spec
- Add missing endpoints
- Standardize response formats

**Tasks:**
- [ ] Update response formats to match SERVER_INTEGRATION.md exactly
- [ ] Add `/api/reject_mesh` endpoint (separate from approve)
- [ ] Add `/api/results/{task_id}` endpoint
- [ ] Add health check endpoints (`/api/health`, `/api/version`)
- [ ] Implement proper HTTP status codes (200, 202, 400, 404, 500)
- [ ] Add request validation and error handling

**Deliverables:**
- Compliant API endpoints
- Enhanced error handling

### 1.3 Database Schema Enhancement
**Goals:**
- Extend database to support full workflow
- Add result storage and metadata

**Tasks:**
- [ ] Update database schema to include `file_path`, `time_steps`, `available_fields`
- [ ] Add database migration script
- [ ] Create helper functions for database operations
- [ ] Add connection pooling for better performance

**Deliverables:**
- Enhanced database schema
- Database utility functions

---

## Phase 2: Basic Workflow Validation (Week 2)

### 2.1 Remote API Testing
**Goals:**
- Test API endpoints from local machine
- Validate request/response formats
- Test error conditions

**Tasks:**
- [ ] Run `validate_deployment.py` against EC2 instance
- [ ] Test scenario submission and task status polling
- [ ] Test mesh approval workflow
- [ ] Test complete end-to-end workflow
- [ ] Fix any issues found by validation script

**Validation Script Tests:**
```python
# validate_deployment.py includes:
- test_api_health()
- test_submit_scenario()
- test_task_status()
- test_mesh_approval()
- test_full_workflow()
```

**Deliverables:**
- ✅ Remote validation script passes
- API endpoints work from local machine
- End-to-end workflow completes successfully

### 2.2 ParaView Server Setup & Testing
**Goals:**
- Set up ParaView server for visualization
- Test client-server connection
- Validate OpenFOAM file reading

**Tasks:**
- [ ] Start pvserver on EC2 instance (port 11111)
- [ ] Test ParaView server connection from local machine
- [ ] Connect local ParaView client to EC2 pvserver
- [ ] Load cavity case results in ParaView
- [ ] Test visualization of velocity and pressure fields

**Test Procedure:**
1. Start pvserver: `pvserver --server-port=11111 --disable-xdisplay-test`
2. Connect from local ParaView: File → Connect → EC2_HOST:11111
3. Open cavity case: `/home/ubuntu/cavity_tutorial/cavity.foam`
4. Visualize fields: pressure (p), velocity (U)

**Deliverables:**
- ParaView server running on EC2
- Local ParaView client connects successfully
- Cavity case visualizes correctly

---

## Phase 3: Desktop App Integration Preparation (Week 3)

### 3.1 Enhanced OpenFOAM Integration
**Goals:**
- Improve OpenFOAM case handling for desktop app
- Add result processing and metadata extraction
- Support proper file organization

**Tasks:**
- [ ] Update cavity case to use proper working directory structure
- [ ] Implement result file parsing (time directories, field files)
- [ ] Extract available fields and time steps for API responses
- [ ] Create proper `.foam` file generation
- [ ] Add case cleanup utilities
- [ ] Test case directory permissions and access

**Deliverables:**
- Enhanced OpenFOAM case management
- Result metadata extraction
- File organization system

### 3.2 API Enhancements for Desktop Integration
**Goals:**
- Add missing SERVER_INTEGRATION.md endpoints
- Improve error handling and user feedback
- Optimize for desktop app workflow

**Tasks:**
- [ ] Add `/api/results/{task_id}` endpoint with proper metadata
- [ ] Implement better error messages and status updates
- [ ] Add file path validation and security checks
- [ ] Improve task status messages for user feedback
- [ ] Add proper timeout handling for long-running tasks

**Deliverables:**
- Complete API endpoint implementation
- Enhanced error handling and user feedback
- Improved task management

### 3.3 Production Readiness
**Goals:**
- Add logging and monitoring
- Implement proper configuration management
- Prepare for desktop app integration

**Tasks:**
- [ ] Add comprehensive logging throughout API
- [ ] Create configuration file for deployment settings
- [ ] Add process monitoring and restart capabilities
- [ ] Implement proper shutdown procedures
- [ ] Add basic security measures (file path validation)

**Deliverables:**
- Production-ready logging system
- Configuration management
- Process monitoring

---

## Validation Script Organization

```
backend_api/
├── validate_deployment.py    # Remote API testing from local machine
├── ec2_validation.sh        # EC2 instance validation 
├── VALIDATION_README.md     # Usage instructions
├── main.py                  # FastAPI application
├── celery_worker.py         # Celery worker tasks
├── database_setup.py        # Database initialization
├── requirements.txt         # Python dependencies
└── run_cavity.sh           # OpenFOAM cavity case execution
```

---

## Success Criteria

### Phase 1 Complete:
- [ ] ✅ EC2 validation script passes
- [ ] ✅ OpenFOAM cavity case runs successfully
- [ ] API endpoints respond correctly
- [ ] Database operations work reliably
- [ ] Celery tasks execute successfully

### Phase 2 Complete:
- [ ] ✅ Remote validation script passes
- [ ] Full workflow can be scripted end-to-end
- [ ] ParaView server runs and accepts connections
- [ ] Local ParaView client connects to EC2 pvserver
- [ ] Cavity case visualizes correctly in ParaView

### Phase 3 Complete:
- [ ] All SERVER_INTEGRATION.md endpoints implemented
- [ ] OpenFOAM integration is robust and reliable
- [ ] API responses include proper metadata
- [ ] Error handling provides clear user feedback
- [ ] System is ready for desktop app integration

---

## Next Steps After Completion

1. **Desktop App Integration**: Begin integration with PySide6 desktop application
2. **LLM Integration**: Add natural language processing capabilities  
3. **Advanced Features**: Multiple case templates, improved user experience
4. **Production Deployment**: Enhanced monitoring and scaling
5. **User Testing**: Conduct user acceptance testing with real CFD scenarios

---

## Development Guidelines

- **Focus on MVP**: Prioritize getting basic workflow working over comprehensive features
- **Test Early**: Use validation scripts to catch issues quickly
- **Document Changes**: Update validation scripts as API evolves
- **Keep It Simple**: Avoid over-engineering for the MVP phase
- **Validate Continuously**: Run validation scripts after each change

This streamlined plan focuses on practical deployment validation and desktop app integration readiness, with simple scripts to verify functionality at each step. 