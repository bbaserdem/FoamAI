#!/bin/bash
# EC2 Instance Validation Script for FoamAI Backend
# Run this script ON the EC2 instance to validate OpenFOAM and ParaView setup

set -e  # Exit on any error

echo "🚀 FoamAI EC2 Instance Validation"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "ℹ️  $1"
}

# Test 1: Check OpenFOAM installation
echo -e "\n🔍 Testing OpenFOAM installation..."
if command -v blockMesh &> /dev/null; then
    print_success "OpenFOAM is installed and available"
    echo "OpenFOAM version: $(foamVersion 2>/dev/null || echo 'Version check failed')"
else
    print_error "OpenFOAM not found in PATH"
    exit 1
fi

# Test 2: Check cavity tutorial directory
echo -e "\n📁 Checking cavity tutorial directory..."
CAVITY_DIR="/home/ubuntu/cavity_tutorial"
if [ -d "$CAVITY_DIR" ]; then
    print_success "Cavity tutorial directory exists: $CAVITY_DIR"
else
    print_error "Cavity tutorial directory not found: $CAVITY_DIR"
    exit 1
fi

# Test 3: Run cavity case
echo -e "\n🌊 Running cavity case..."
cd "$CAVITY_DIR"

# Clean previous runs
print_info "Cleaning previous runs..."
foamCleanTutorials

# Run blockMesh
print_info "Running blockMesh..."
if blockMesh > blockMesh.log 2>&1; then
    print_success "blockMesh completed successfully"
else
    print_error "blockMesh failed"
    cat blockMesh.log
    exit 1
fi

# Run solver
print_info "Running solver (foamRun)..."
if foamRun > foamRun.log 2>&1; then
    print_success "Solver completed successfully"
else
    print_error "Solver failed"
    cat foamRun.log
    exit 1
fi

# Create .foam file
print_info "Creating .foam file..."
touch cavity.foam
if [ -f "cavity.foam" ]; then
    print_success ".foam file created successfully"
else
    print_error "Failed to create .foam file"
    exit 1
fi

# Check results
print_info "Checking results..."
if [ -d "constant/polyMesh" ]; then
    print_success "Mesh files found in constant/polyMesh"
else
    print_error "Mesh files not found"
    exit 1
fi

# Count time directories
TIME_DIRS=$(ls -d [0-9]* 2>/dev/null | wc -l)
if [ "$TIME_DIRS" -gt 0 ]; then
    print_success "Found $TIME_DIRS time directories"
    ls -la [0-9]* | head -5
else
    print_error "No time directories found"
    exit 1
fi

# Test 4: Check ParaView installation
echo -e "\n🎨 Testing ParaView installation..."
if command -v pvserver &> /dev/null; then
    print_success "ParaView server (pvserver) is installed"
    echo "ParaView version: $(pvserver --version 2>/dev/null | head -1 || echo 'Version check failed')"
else
    print_error "pvserver not found in PATH"
    exit 1
fi

# Test 5: Check if pvserver can start (quick test)
echo -e "\n🔌 Testing pvserver startup..."
print_info "Starting pvserver on port 11111 (will stop after 5 seconds)..."

# Start pvserver in background
timeout 5s pvserver --server-port=11111 --disable-xdisplay-test > pvserver.log 2>&1 &
PVSERVER_PID=$!

# Wait a moment for startup
sleep 2

# Check if process is running
if kill -0 $PVSERVER_PID 2>/dev/null; then
    print_success "pvserver started successfully"
    # Kill the test process
    kill $PVSERVER_PID 2>/dev/null || true
    wait $PVSERVER_PID 2>/dev/null || true
else
    print_error "pvserver failed to start"
    cat pvserver.log
    exit 1
fi

# Test 6: Check network connectivity
echo -e "\n🌐 Testing network connectivity..."
print_info "Checking if port 11111 is available..."
if netstat -ln | grep -q ":11111"; then
    print_warning "Port 11111 is already in use"
else
    print_success "Port 11111 is available"
fi

# Test 7: Check API dependencies
echo -e "\n🐍 Testing Python/API dependencies..."
if command -v python3 &> /dev/null; then
    print_success "Python3 is available"
    echo "Python version: $(python3 --version)"
else
    print_error "Python3 not found"
    exit 1
fi

if command -v redis-server &> /dev/null; then
    print_success "Redis server is available"
else
    print_warning "Redis server not found (may need to install)"
fi

# Summary
echo -e "\n🏁 VALIDATION SUMMARY"
echo "===================="
print_success "OpenFOAM cavity case runs successfully"
print_success "ParaView server can start"
print_success "All basic components are working"

echo -e "\n📋 NEXT STEPS:"
echo "1. Start the API server: cd /path/to/backend_api && python3 main.py"
echo "2. Start Celery worker: celery -A celery_worker worker --loglevel=info"
echo "3. Start pvserver: pvserver --server-port=11111 --disable-xdisplay-test"
echo "4. Test from local machine: python3 validate_deployment.py YOUR_EC2_HOST"

echo -e "\n🎯 USEFUL COMMANDS:"
echo "# Start pvserver persistently:"
echo "nohup pvserver --server-port=11111 --disable-xdisplay-test > pvserver.log 2>&1 &"
echo ""
echo "# Monitor pvserver:"
echo "tail -f pvserver.log"
echo ""
echo "# Check if pvserver is running:"
echo "netstat -ln | grep 11111"
echo ""
echo "# Connect from local ParaView:"
echo "# File → Connect → Add Server → Host: YOUR_EC2_HOST, Port: 11111"

print_success "EC2 validation completed successfully! 🎉" 