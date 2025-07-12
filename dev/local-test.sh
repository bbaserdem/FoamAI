#!/usr/bin/env bash
# FoamAI Local Testing Script
# Tests the deployment logic locally without AWS costs

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOCAL_DATA_DIR="${SCRIPT_DIR}/local-data"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.local.yml"

# Container runtime detection
CONTAINER_RUNTIME=""
COMPOSE_COMMAND=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Detect container runtime (Docker or Podman)
detect_container_runtime() {
    log "Detecting container runtime..."
    
    # Check if docker command is available (could be native Docker or Podman alias)
    if command -v docker &> /dev/null; then
        # Test if docker command works
        if docker ps &>/dev/null 2>&1; then
            CONTAINER_RUNTIME="docker"
            log "✅ Detected Docker (or Podman with docker alias)"
        else
            CONTAINER_RUNTIME="docker"
            log "✅ Detected Docker command (may need service start)"
        fi
    elif command -v podman &> /dev/null; then
        CONTAINER_RUNTIME="podman"
        log "✅ Detected Podman"
    else
        error "❌ Neither Docker nor Podman found"
    fi
    
    # Always use docker-compose since it's drop-in replaceable
    if command -v docker-compose &> /dev/null; then
        COMPOSE_COMMAND="docker-compose"
        log "✅ Using docker-compose"
    else
        error "❌ docker-compose not found"
    fi
}

# Check container runtime service status
check_container_service() {
    log "Checking container runtime service..."
    
    # Test docker command (whether it's native Docker or Podman alias)
    if docker ps &>/dev/null 2>&1; then
        log "✅ Container runtime working"
    elif docker version &>/dev/null 2>&1; then
        log "✅ Container runtime accessible (may need to start containers)"
    else
        # If docker command fails, try setting up Podman socket for docker-compose
        if command -v podman &>/dev/null; then
            log "Setting up Podman socket for docker-compose compatibility..."
            
            # Enable and start podman socket if not running
            if ! systemctl --user is-active podman.socket &>/dev/null; then
                systemctl --user enable --now podman.socket &>/dev/null || true
            fi
            
            # Set DOCKER_HOST for docker-compose to use Podman socket
            export DOCKER_HOST="unix:///run/user/$UID/podman/podman.sock"
            
            # Test again
            if docker ps &>/dev/null 2>&1; then
                log "✅ Container runtime working with Podman socket"
            else
                warn "❌ Container runtime not responding - may need manual setup"
            fi
        else
            warn "❌ Container runtime not responding - may need manual setup"
        fi
    fi
}

# Create local data directory (simulates /data mount)
setup_local_environment() {
    log "Setting up local testing environment..."
    
    # Detect container runtime first
    detect_container_runtime
    check_container_service
    
    # Create local data directory
    mkdir -p "${LOCAL_DATA_DIR}"
    chmod 755 "${LOCAL_DATA_DIR}"
    
    # Create local .env file
    cat > "${SCRIPT_DIR}/.env" << EOF
# Local Development Environment
COMPOSE_PROJECT_NAME=foamai-local
DATA_DIR=${LOCAL_DATA_DIR}
API_PORT=8000
PARAVIEW_PORT=11111
DEVELOPMENT=true

# Docker image settings - Local build
DOCKER_BUILDKIT=1
COMPOSE_DOCKER_CLI_BUILD=1

# Container runtime configuration
# If using Podman with docker-compose, set socket path
DOCKER_HOST=unix:///run/user/$UID/podman/podman.sock
EOF
    
    log "Local environment setup complete"
}

# Build all container images locally
build_images() {
    # Ensure container runtime is detected
    if [ -z "$CONTAINER_RUNTIME" ] || [ -z "$COMPOSE_COMMAND" ]; then
        detect_container_runtime
        check_container_service
    fi
    
    log "Building container images locally with ${CONTAINER_RUNTIME}..."
    
    cd "${SCRIPT_DIR}"
    
    # Build images with build cache
    ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" build --parallel
    
    # Verify images were built
    if docker images | grep -q "foamai"; then
        log "✅ Container images built successfully"
    else
        error "❌ Failed to build container images"
    fi
}

# Test individual services
test_service_health() {
    local service="$1"
    local max_attempts=30
    local attempt=0
    
    log "Testing ${service} service health..."
    
    while [ $attempt -lt $max_attempts ]; do
        if ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" exec -T "${service}" echo "Health check" >/dev/null 2>&1; then
            log "✅ ${service} service is healthy"
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 2
    done
    
    warn "❌ ${service} service health check failed after ${max_attempts} attempts"
    return 1
}

# Test API endpoints
test_api_endpoints() {
    log "Testing API endpoints..."
    
    # Wait for API to be ready
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -f -s http://localhost:8000/ping > /dev/null 2>&1; then
            break
        fi
        
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        error "❌ API did not become ready in time"
    fi
    
    # Test ping endpoint
    if curl -f -s http://localhost:8000/ping | grep -q "pong"; then
        log "✅ /ping endpoint working"
    else
        error "❌ /ping endpoint failed"
    fi
    
    # Test root endpoint
    if curl -f -s http://localhost:8000/ | grep -q "FoamAI API is running"; then
        log "✅ Root endpoint working"
    else
        error "❌ Root endpoint failed"
    fi
    
    # Test docs endpoint
    if curl -f -s http://localhost:8000/docs > /dev/null; then
        log "✅ /docs endpoint accessible"
    else
        error "❌ /docs endpoint failed"
    fi
}

# Test ParaView server
test_paraview_server() {
    log "Testing ParaView server..."
    
    # Test port connectivity
    if nc -z localhost 11111 2>/dev/null; then
        log "✅ ParaView server port accessible"
    else
        error "❌ ParaView server port not accessible"
    fi
    
    # Test process is running
    if ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" exec -T pvserver pgrep pvserver > /dev/null 2>&1; then
        log "✅ ParaView server process running"
    else
        warn "❌ ParaView server process not detected"
    fi
}

# Test OpenFOAM installation
test_openfoam() {
    log "Testing OpenFOAM installation..."
    
    # Test OpenFOAM environment
    if ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" exec -T openfoam bash -c "source /opt/openfoam10/etc/bashrc && which blockMesh" > /dev/null 2>&1; then
        log "✅ OpenFOAM environment working"
    else
        error "❌ OpenFOAM environment failed"
    fi
    
    # Test basic OpenFOAM command
    if ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" exec -T openfoam bash -c "source /opt/openfoam10/etc/bashrc && blockMesh -help" > /dev/null 2>&1; then
        log "✅ OpenFOAM blockMesh command working"
    else
        error "❌ OpenFOAM blockMesh command failed"
    fi
}

# Test data volume sharing
test_data_volume() {
    log "Testing data volume sharing..."
    
    # Create test file in API container
    ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" exec -T api bash -c "echo 'test-data' > /data/test-file.txt"
    
    # Check if file is visible in other containers
    if ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" exec -T openfoam cat /data/test-file.txt | grep -q "test-data"; then
        log "✅ Data volume sharing working"
    else
        error "❌ Data volume sharing failed"
    fi
    
    # Clean up
    ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" exec -T api rm -f /data/test-file.txt
}

# Start services
start_services() {
    # Ensure container runtime is detected
    if [ -z "$CONTAINER_RUNTIME" ] || [ -z "$COMPOSE_COMMAND" ]; then
        detect_container_runtime
        check_container_service
    fi
    
    log "Starting all services with ${CONTAINER_RUNTIME}..."
    
    cd "${SCRIPT_DIR}"
    
    # Start services in background
    ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" up -d
    
    # Wait for services to be ready
    sleep 10
    
    # Check if all services are running
    if ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" ps | grep -q "Up"; then
        log "✅ Services started successfully"
    else
        error "❌ Failed to start services"
    fi
}

# Stop services
stop_services() {
    # Ensure container runtime is detected
    if [ -z "$CONTAINER_RUNTIME" ] || [ -z "$COMPOSE_COMMAND" ]; then
        detect_container_runtime
        check_container_service
    fi
    
    log "Stopping services..."
    
    cd "${SCRIPT_DIR}"
    ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" down
    
    log "Services stopped"
}

# Clean up everything
cleanup() {
    # Ensure container runtime is detected
    if [ -z "$CONTAINER_RUNTIME" ] || [ -z "$COMPOSE_COMMAND" ]; then
        detect_container_runtime
        check_container_service
    fi
    
    log "Cleaning up local environment..."
    
    cd "${SCRIPT_DIR}"
    
    # Stop and remove containers
    ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" down -v
    
    # Remove built images
    docker images | grep "foamai" | awk '{print $3}' | xargs -r docker rmi -f
    
    # Remove local data directory
    rm -rf "${LOCAL_DATA_DIR}"
    
    # Remove .env file
    rm -f "${SCRIPT_DIR}/.env"
    
    log "Cleanup complete"
}

# Show service status
show_status() {
    # Ensure container runtime is detected
    if [ -z "$CONTAINER_RUNTIME" ] || [ -z "$COMPOSE_COMMAND" ]; then
        detect_container_runtime
        check_container_service
    fi
    
    log "Service Status:"
    
    cd "${SCRIPT_DIR}"
    
    echo ""
    echo "=== Container Status ==="
    ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" ps
    
    echo ""
    echo "=== Service Health ==="
    echo "API: http://localhost:8000"
    echo "API Docs: http://localhost:8000/docs"
    echo "ParaView: localhost:11111"
    
    echo ""
    echo "=== Quick Tests ==="
    echo "API Ping: $(curl -f -s http://localhost:8000/ping 2>/dev/null || echo "FAILED")"
    echo "ParaView Port: $(nc -z localhost 11111 2>/dev/null && echo "ACCESSIBLE" || echo "FAILED")"
}

# Show logs
show_logs() {
    local service="$1"
    
    # Ensure container runtime is detected
    if [ -z "$CONTAINER_RUNTIME" ] || [ -z "$COMPOSE_COMMAND" ]; then
        detect_container_runtime
        check_container_service
    fi
    
    cd "${SCRIPT_DIR}"
    
    if [ -n "$service" ]; then
        ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" logs -f "$service"
    else
        ${COMPOSE_COMMAND} -f "${COMPOSE_FILE}" logs -f
    fi
}

# Run comprehensive tests
run_tests() {
    log "Running comprehensive local tests..."
    
    # Detect container runtime if not already done
    if [ -z "$CONTAINER_RUNTIME" ]; then
        detect_container_runtime
        check_container_service
    fi
    
    # Start services
    start_services
    
    # Wait for services to stabilize
    sleep 15
    
    # Run tests
    test_api_endpoints
    test_paraview_server
    test_openfoam
    test_data_volume
    
    # Show final status
    show_status
    
    log "✅ All tests completed successfully!"
}

# Help message
show_help() {
    echo "FoamAI Local Testing Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  setup         Set up local testing environment"
    echo "  build         Build Docker images locally"
    echo "  start         Start all services"
    echo "  stop          Stop all services"
    echo "  test          Run comprehensive tests"
    echo "  status        Show service status"
    echo "  logs [service] Show logs (optionally for specific service)"
    echo "  cleanup       Clean up everything"
    echo "  help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 setup && $0 build && $0 test"
    echo "  $0 start && $0 status"
    echo "  $0 logs api"
    echo "  $0 cleanup"
}

# Main execution
main() {
    case "${1:-help}" in
        setup)
            setup_local_environment
            ;;
        build)
            build_images
            ;;
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        test)
            run_tests
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$2"
            ;;
        cleanup)
            cleanup
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "Unknown command: $1"
            show_help
            ;;
    esac
}

main "$@" 