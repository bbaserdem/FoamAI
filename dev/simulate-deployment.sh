#!/usr/bin/env bash
# FoamAI Deployment Simulation Script
# Simulates the AWS EC2 user data deployment logic locally

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SIM_ROOT="${SCRIPT_DIR}/simulation"
SIM_DATA_DIR="${SIM_ROOT}/data"
SIM_LOG_FILE="${SIM_ROOT}/foamai-startup.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
    # Ensure log directory exists before writing
    mkdir -p "$(dirname "${SIM_LOG_FILE}")"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1" >> "${SIM_LOG_FILE}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
    mkdir -p "$(dirname "${SIM_LOG_FILE}")"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN] $1" >> "${SIM_LOG_FILE}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    mkdir -p "$(dirname "${SIM_LOG_FILE}")"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $1" >> "${SIM_LOG_FILE}"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
    mkdir -p "$(dirname "${SIM_LOG_FILE}")"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $1" >> "${SIM_LOG_FILE}"
}

# Initialize simulation environment
init_simulation() {
    log "Initializing deployment simulation environment..."
    
    # Create simulation directory structure
    mkdir -p "${SIM_ROOT}"
    mkdir -p "${SIM_DATA_DIR}"
    mkdir -p "${SIM_ROOT}/var/log"
    mkdir -p "${SIM_ROOT}/opt/FoamAI"
    mkdir -p "${SIM_ROOT}/etc/systemd/system"
    
    # Create log file
    touch "${SIM_LOG_FILE}"
    
    # Set permissions
    chmod 755 "${SIM_DATA_DIR}"
    
    log "Simulation environment initialized"
}

# Simulate system updates (skip actual updates)
simulate_system_updates() {
    log "Simulating system updates..."
    
    # Simulate the apt-get update & upgrade
    sleep 2
    
    log "✅ System updates simulated successfully"
}

# Simulate package installation
simulate_package_installation() {
    log "Simulating essential package installation..."
    
    # Check if required tools are available locally
    local missing_tools=()
    
    for tool in curl wget git docker docker-compose; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        warn "Missing tools that would be installed: ${missing_tools[*]}"
    else
        log "✅ All required tools are available locally"
    fi
}

# Simulate EBS volume mounting (the most complex part)
simulate_ebs_volume_mounting() {
    log "Simulating EBS volume mounting logic..."
    
    # Create a fake block device file to simulate EBS volume
    local fake_device="${SIM_ROOT}/dev_nvme1n1"
    
    # Create fake device with expected size
    dd if=/dev/zero of="$fake_device" bs=1M count=100 2>/dev/null
    
    # Simulate volume discovery
    log "Simulating volume discovery process..."
    
    # Simulate the complex discovery logic from user_data.sh.tpl
    local data_volume_size_gb=100
    local filesystem_type="ext4"
    local mount_point="${SIM_DATA_DIR}"
    local wait_timeout=10
    
    # Test the discovery functions (simplified)
    log "Testing size-based discovery..."
    local fake_size=$(stat -c%s "$fake_device" 2>/dev/null || echo 0)
    local fake_size_gb=$((fake_size / 1024 / 1024 / 1024))
    
    if [ "$fake_size_gb" -eq 0 ]; then
        fake_size_gb=1  # Simulate 1GB for testing
    fi
    
    log "Fake device size: ${fake_size_gb}GB (expected: ${data_volume_size_gb}GB)"
    
    # Simulate filesystem creation
    log "Simulating filesystem creation..."
    
    # Create a fake filesystem identifier
    echo "fake-filesystem-${filesystem_type}" > "${fake_device}.fstype"
    
    # Simulate mount operation
    log "Simulating mount operation..."
    
    # Create mount point
    mkdir -p "$mount_point"
    
    # Simulate successful mount
    echo "fake-device $mount_point $filesystem_type defaults,nofail 0 2" > "${SIM_ROOT}/etc/fstab.sim"
    
    log "✅ EBS volume mounting simulation completed"
}

# Simulate container runtime installation
simulate_docker_installation() {
    log "Simulating container runtime installation..."
    
    # Check for Docker or Podman
    if command -v podman &> /dev/null; then
        if docker --version 2>/dev/null | grep -qi podman; then
            log "✅ Podman is installed locally (with docker alias)"
            log "Podman version: $(podman --version)"
        else
            log "✅ Podman is installed locally"
            log "Podman version: $(podman --version)"
        fi
    elif command -v docker &> /dev/null; then
        log "✅ Docker is already installed locally"
        log "Docker version: $(docker --version)"
    else
        warn "Neither Docker nor Podman found locally - Docker would be installed on EC2"
    fi
    
    # Check for compose
    if command -v docker-compose &> /dev/null; then
        log "✅ Docker Compose is available locally"
        log "Docker Compose version: $(docker-compose --version)"
    elif command -v podman-compose &> /dev/null; then
        log "✅ Podman Compose is available locally"
        log "Podman Compose version: $(podman-compose --version)"
    else
        warn "Neither docker-compose nor podman-compose found locally - would be installed on EC2"
    fi
}

# Simulate repository cloning
simulate_repository_cloning() {
    log "Simulating repository cloning..."
    
    # Copy current repository to simulation directory
    local sim_repo="${SIM_ROOT}/opt/FoamAI"
    
    # Create a minimal copy of the repo structure
    mkdir -p "${sim_repo}"
    
    # Copy essential files
    cp -r "${PROJECT_ROOT}/docker" "${sim_repo}/" 2>/dev/null || true
    cp "${PROJECT_ROOT}/docker-compose.yml" "${sim_repo}/" 2>/dev/null || true
    cp -r "${PROJECT_ROOT}/src" "${sim_repo}/" 2>/dev/null || true
    
    log "✅ Repository cloning simulated"
}

# Simulate environment configuration
simulate_environment_configuration() {
    log "Simulating environment configuration..."
    
    # Create .env file (similar to user_data.sh.tpl)
    local env_file="${SIM_ROOT}/opt/FoamAI/.env"
    
    cat > "$env_file" << EOF
# FoamAI Environment Configuration (Simulated)
COMPOSE_PROJECT_NAME=foamai
DATA_DIR=${SIM_DATA_DIR}
API_PORT=8000
PARAVIEW_PORT=11111

# Configuration Profile
DEPLOYMENT_PROFILE=development

# GitHub Container Registry Configuration
GHCR_REGISTRY=ghcr.io
GITHUB_ORG=bbaserdem

# Docker image settings - Using GitHub Container Registry
GHCR_API_URL=ghcr.io/bbaserdem/foamai/api
GHCR_OPENFOAM_URL=ghcr.io/bbaserdem/foamai/openfoam
GHCR_PVSERVER_URL=ghcr.io/bbaserdem/foamai/pvserver
IMAGE_TAG=latest

# API Configuration
API_HOST=0.0.0.0
API_WORKERS=2

# OpenFOAM Configuration
OPENFOAM_VERSION=10

# ParaView Configuration
PARAVIEW_SERVER_PORT=11111
EOF
    
    log "✅ Environment configuration created"
}

# Simulate systemd service creation
simulate_systemd_service() {
    log "Simulating systemd service creation..."
    
    # Create systemd service file
    local service_file="${SIM_ROOT}/etc/systemd/system/foamai.service"
    
    cat > "$service_file" << 'EOF'
[Unit]
Description=FoamAI CFD Assistant Services
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/FoamAI
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=300
User=ubuntu
Group=ubuntu
Environment=HOME=/home/ubuntu

[Install]
WantedBy=multi-user.target
EOF
    
    log "✅ Systemd service file created"
}

# Simulate Docker image pulling
simulate_docker_image_pulling() {
    log "Simulating Docker image pulling..."
    
    # Check if images are available locally or from registry
    local images=("ghcr.io/bbaserdem/foamai/api:latest" "ghcr.io/bbaserdem/foamai/openfoam:latest" "ghcr.io/bbaserdem/foamai/pvserver:latest")
    
    for image in "${images[@]}"; do
        if docker image inspect "$image" &>/dev/null; then
            log "✅ Image $image is available locally"
        else
            warn "Image $image not available locally - would be pulled from registry"
        fi
    done
}

# Simulate service startup
simulate_service_startup() {
    log "Simulating service startup..."
    
    # Check if we can actually start services locally
    if (command -v docker-compose &> /dev/null || command -v podman-compose &> /dev/null) && [ -f "${SIM_ROOT}/opt/FoamAI/docker-compose.yml" ]; then
        if command -v docker-compose &> /dev/null; then
            log "✅ Docker Compose is available for service startup"
        else
            log "✅ Podman Compose is available for service startup"
        fi
    else
        warn "Neither docker-compose nor podman-compose available - services would be started on EC2"
    fi
}

# Simulate status check script creation
simulate_status_script() {
    log "Simulating status check script creation..."
    
    # Create foamai-status script
    local status_script="${SIM_ROOT}/usr/local/bin/foamai-status"
    
    mkdir -p "$(dirname "$status_script")"
    
    cat > "$status_script" << 'EOF'
#!/usr/bin/env bash
echo "=== FoamAI Status Check (Simulated) ==="
echo "Timestamp: $(date)"
echo ""

echo "Container runtime status:"
if command -v podman &> /dev/null; then
    echo "Podman: $(podman --version)"
elif command -v docker &> /dev/null; then
    echo "Docker: $(docker --version)"
else
    echo "No container runtime found"
fi
echo ""

echo "Running containers:"
echo "foamai-api      Up      0.0.0.0:8000->8000/tcp"
echo "foamai-openfoam Up"
echo "foamai-pvserver Up      0.0.0.0:11111->11111/tcp"
echo ""

echo "Service endpoints:"
echo "Public IP: 127.0.0.1 (simulated)"
echo "API: http://127.0.0.1:8000"
echo "API Docs: http://127.0.0.1:8000/docs"
echo "ParaView Server: 127.0.0.1:11111"
echo ""

echo "Storage status:"
echo "Data volume mount:"
echo "/dev/fake-device on /data type ext4 (rw,relatime)"
echo ""

echo "Recent startup logs:"
echo "Simulation completed successfully"
EOF
    
    chmod +x "$status_script"
    
    # Verify the script was created correctly
    if [ -f "$status_script" ]; then
        log "✅ Status check script created at $status_script"
    else
        error "❌ Failed to create status check script"
    fi
}

# Test the simulated deployment
test_simulation() {
    log "Testing simulated deployment..."
    
    # Test data directory
    if [ -d "${SIM_DATA_DIR}" ]; then
        log "✅ Data directory exists"
    else
        error "❌ Data directory missing"
    fi
    
    # Test configuration files
    if [ -f "${SIM_ROOT}/opt/FoamAI/.env" ]; then
        log "✅ Environment configuration exists"
    else
        error "❌ Environment configuration missing"
    fi
    
    # Test service file
    if [ -f "${SIM_ROOT}/etc/systemd/system/foamai.service" ]; then
        log "✅ Systemd service file exists"
    else
        error "❌ Systemd service file missing"
    fi
    
    # Test status script
    local status_script="${SIM_ROOT}/usr/local/bin/foamai-status"
    if [ -f "$status_script" ]; then
        if [ -x "$status_script" ]; then
            log "✅ Status script exists and is executable"
        else
            warn "❌ Status script exists but is not executable"
            ls -la "$status_script"
        fi
    else
        error "❌ Status script missing"
    fi
    
    log "✅ Simulation test completed successfully"
}

# Show simulation results
show_simulation_results() {
    log "Deployment simulation results:"
    
    echo ""
    echo "======================================"
    echo "    DEPLOYMENT SIMULATION RESULTS"
    echo "======================================"
    echo "Simulation Directory: ${SIM_ROOT}"
    echo "Data Directory: ${SIM_DATA_DIR}"
    echo "Log File: ${SIM_LOG_FILE}"
    echo ""
    echo "=== Created Files ==="
    find "${SIM_ROOT}" -type f | sort
    echo ""
    echo "=== Log Contents ==="
    tail -20 "${SIM_LOG_FILE}"
    echo ""
    echo "=== Test Status Script ==="
    if [ -x "${SIM_ROOT}/usr/local/bin/foamai-status" ]; then
        # Execute the status script with explicit bash
        bash "${SIM_ROOT}/usr/local/bin/foamai-status"
    else
        echo "❌ Status script not found or not executable"
        ls -la "${SIM_ROOT}/usr/local/bin/" 2>/dev/null || echo "Directory not found"
    fi
    echo "======================================"
}

# Clean up simulation
cleanup_simulation() {
    log "Cleaning up simulation environment..."
    
    if [ -d "${SIM_ROOT}" ]; then
        rm -rf "${SIM_ROOT}"
        log "✅ Simulation environment cleaned up"
    else
        log "No simulation environment to clean up"
    fi
}

# Run full deployment simulation
run_full_simulation() {
    log "Running full deployment simulation..."
    
    # Initialize
    init_simulation
    
    # Simulate all deployment steps
    simulate_system_updates
    simulate_package_installation
    simulate_ebs_volume_mounting
    simulate_docker_installation
    simulate_repository_cloning
    simulate_environment_configuration
    simulate_systemd_service
    simulate_docker_image_pulling
    simulate_service_startup
    simulate_status_script
    
    # Test the simulation
    test_simulation
    
    # Show results
    show_simulation_results
    
    log "✅ Full deployment simulation completed successfully!"
}

# Show help
show_help() {
    echo "FoamAI Deployment Simulation Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  init          Initialize simulation environment"
    echo "  full          Run complete deployment simulation"
    echo "  test          Test the simulation results"
    echo "  results       Show simulation results"
    echo "  cleanup       Clean up simulation environment"
    echo "  help          Show this help message"
    echo ""
    echo "This script simulates the AWS EC2 user data deployment process locally"
    echo "to help identify issues before deploying to AWS."
}

# Main execution
main() {
    case "${1:-help}" in
        init)
            init_simulation
            ;;
        full)
            run_full_simulation
            ;;
        test)
            test_simulation
            ;;
        results)
            show_simulation_results
            ;;
        cleanup)
            cleanup_simulation
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