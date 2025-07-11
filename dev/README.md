# 🚀 FoamAI Local Testing & Deployment Debugging

This directory contains tools to test your FoamAI deployment locally **before** spending money on AWS deployments. Use these tools to identify and fix issues in a local environment.

## 📋 **Current Deployment Issues Analysis**

Based on your codebase analysis, here are the main failure points:

### 🔴 **High-Risk Areas**
1. **Complex EBS Volume Mounting** - ~200 lines of bash logic with multiple fallback strategies
2. **Docker Image Availability** - Dependencies on GitHub Container Registry
3. **Service Startup Timing** - OpenFOAM, ParaView, and API must start in correct order
4. **Network Configuration** - Multiple ports and inter-service communication

### 🟡 **Medium-Risk Areas**
1. **Environment Configuration** - Complex .env file generation
2. **Systemd Service Management** - Service file creation and enablement
3. **File Permissions** - Volume mounting and user permissions

### 🟢 **Low-Risk Areas**
1. **System Package Installation** - Standard apt-get operations
2. **Repository Cloning** - Simple git operations

## 🛠️ **Local Testing Tools**

### 1. **Container Environment Testing** (`local-test.sh`)
Test your multi-service container setup locally without AWS (supports both Docker and Podman):

```bash
# Setup and run comprehensive tests
./local-test.sh setup
./local-test.sh build
./local-test.sh test

# Individual operations
./local-test.sh start    # Start services
./local-test.sh status   # Check status
./local-test.sh logs     # View logs
./local-test.sh stop     # Stop services
./local-test.sh cleanup  # Clean up
```

**What it tests:**
- ✅ Container image building (Docker/Podman)
- ✅ Service startup and health checks
- ✅ API endpoints functionality
- ✅ ParaView server connectivity
- ✅ OpenFOAM installation
- ✅ Data volume sharing

### 2. **Deployment Logic Simulation** (`simulate-deployment.sh`)
Simulate the AWS EC2 user data script locally:

```bash
# Run full deployment simulation
./simulate-deployment.sh full

# Individual steps
./simulate-deployment.sh init     # Initialize environment
./simulate-deployment.sh test     # Test simulation
./simulate-deployment.sh results  # Show results
./simulate-deployment.sh cleanup  # Clean up
```

**What it simulates:**
- ✅ System updates and package installation
- ✅ EBS volume mounting logic
- ✅ Docker installation
- ✅ Repository cloning
- ✅ Environment configuration
- ✅ Systemd service creation
- ✅ Service startup sequence

### 3. **Local Development Environment** (`docker-compose.local.yml`)
A production-like environment for development:

```bash
# Start local development environment
cd dev
docker-compose -f docker-compose.local.yml up -d

# Check status
docker-compose -f docker-compose.local.yml ps

# View logs
docker-compose -f docker-compose.local.yml logs -f

# Stop environment
docker-compose -f docker-compose.local.yml down
```

## 📊 **Recommended Testing Workflow**

### Phase 1: Local Docker Testing
```bash
cd dev
./local-test.sh setup && ./local-test.sh build && ./local-test.sh test
```

**Expected Results:**
- ✅ All 3 Docker images build successfully
- ✅ All services start and pass health checks
- ✅ API endpoints respond correctly
- ✅ ParaView server is accessible
- ✅ OpenFOAM commands work
- ✅ Data volume sharing works

### Phase 2: Deployment Logic Testing
```bash
./simulate-deployment.sh full
```

**Expected Results:**
- ✅ All deployment steps complete without errors
- ✅ Configuration files are created correctly
- ✅ Service files are generated properly
- ✅ EBS volume mounting logic works

### Phase 3: Fix Issues Found
Based on test results, fix issues in:
- `docker/*/Dockerfile` - Image building issues
- `docker-compose.yml` - Service orchestration issues
- `infra/user_data.sh.tpl` - Deployment logic issues

### Phase 4: Test AWS Deployment
Only after local tests pass:
```bash
cd ../infra
./deploy-fresh-instance.sh
```

## 🔧 **Common Issues & Solutions**

### Issue 1: Container Images Won't Build
**Symptoms:** Build failures, missing dependencies
**Solution:**
```bash
# Test locally first
./local-test.sh build

# Check specific image (adjust command for your container runtime)
docker build -f ../docker/api/Dockerfile ..
# OR for Podman:
podman build -f ../docker/api/Dockerfile ..

# Fix Dockerfile issues then test again
```

### Issue 2: Services Won't Start
**Symptoms:** Container exits, health check failures
**Solution:**
```bash
# Check logs
./local-test.sh logs api

# Test individual service
docker-compose -f docker-compose.local.yml up api

# Fix service configuration
```

### Issue 3: API Endpoints Don't Work
**Symptoms:** 404 errors, connection refused
**Solution:**
```bash
# Test API locally
curl http://localhost:8000/ping

# Check if API is properly configured
./local-test.sh test
```

### Issue 4: EBS Volume Mounting Issues
**Symptoms:** /data directory not mounted, permission issues
**Solution:**
```bash
# Test mounting logic
./simulate-deployment.sh full

# Check simulation results
cat dev/simulation/foamai-startup.log
```

### Issue 5: Service Startup Timing
**Symptoms:** Services start before dependencies are ready
**Solution:**
```bash
# Check dependency order in docker-compose.yml
# Increase health check intervals
# Add proper wait conditions
```

## 📈 **Debugging Tips**

### 1. **Enable Verbose Logging**
```bash
# Add to docker-compose.yml
environment:
  - DEBUG=true
  - VERBOSE=true
```

### 2. **Check Service Dependencies**
```bash
# Verify service startup order
docker-compose -f docker-compose.local.yml ps
docker-compose -f docker-compose.local.yml logs
```

### 3. **Test Individual Components**
```bash
# Test OpenFOAM
docker-compose -f docker-compose.local.yml exec openfoam bash -c "source /opt/openfoam10/etc/bashrc && blockMesh -help"

# Test ParaView
nc -zv localhost 11111

# Test API
curl -f http://localhost:8000/ping
```

### 4. **Monitor Resource Usage**
```bash
# Check container resources
docker stats

# Check disk usage
df -h dev/local-data/
```

## 🚨 **Emergency Procedures**

### If Local Tests Fail
1. **Don't deploy to AWS** - Fix issues locally first
2. **Check logs** - Use `./local-test.sh logs`
3. **Test individual services** - Isolate the problem
4. **Clean and rebuild** - Use `./local-test.sh cleanup && ./local-test.sh setup`

### If AWS Deployment Fails
1. **SSH into instance** - Check logs at `/var/log/foamai-startup.log`
2. **Run status check** - Use `sudo foamai-status`
3. **Check service status** - Use `docker-compose ps`
4. **Test locally** - Reproduce the issue in dev environment

## 📋 **Pre-Deployment Checklist**

Before deploying to AWS, ensure:

- [ ] ✅ `./local-test.sh test` passes completely
- [ ] ✅ `./simulate-deployment.sh full` completes without errors
- [ ] ✅ All Docker images build successfully
- [ ] ✅ All services start and pass health checks
- [ ] ✅ API endpoints return expected responses
- [ ] ✅ ParaView server is accessible
- [ ] ✅ OpenFOAM commands work properly
- [ ] ✅ Data volume sharing works between containers
- [ ] ✅ Environment configuration is correct
- [ ] ✅ Service files are generated properly

## 🎯 **Success Metrics**

Your deployment is ready when:
- **Build Time:** < 10 minutes for all images
- **Startup Time:** < 2 minutes for all services
- **API Response:** < 100ms for /ping endpoint
- **Health Checks:** All services pass within 60 seconds
- **Resource Usage:** < 80% CPU, < 80% Memory during startup

## 📚 **Additional Resources**

- **Production Deployment:** See `../infra/README.md`
- **Service Testing:** See `../docs/TESTING.md`
- **Architecture Overview:** See `../docs/cfd_project_vision.md`
- **Troubleshooting:** See `../docs/task_4_devops/workflow.md`

---

**🎉 Use these tools to save time and money by catching deployment issues early!** 