#!/usr/bin/env bash
# FoamAI Modular User Data Script
# Self-contained, robust EC2 instance startup script with embedded modules

# Exit on error, but handle it gracefully
set -e

# Configuration variables (set by Terraform template and environment)
export DEBUG="${DEBUG:-false}"
export DATA_VOLUME_SIZE_GB="${DATA_VOLUME_SIZE_GB}"
export FILESYSTEM_TYPE="${FILESYSTEM_TYPE}"
export MOUNT_POINT="${MOUNT_POINT}"
export EBS_WAIT_TIMEOUT="${EBS_WAIT_TIMEOUT}"
export FOAMAI_REPO_URL="${FOAMAI_REPO_URL:-https://github.com/bbaserdem/FoamAI.git}"
export FOAMAI_INSTALL_DIR="${FOAMAI_INSTALL_DIR:-/opt/FoamAI}"
export GITHUB_ORG="${GITHUB_ORG:-bbaserdem}"

# ========================================================================
# EMBEDDED MODULE: utils.sh - Utility Functions
# ========================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Global variables
LOG_FILE="/var/log/foamai-startup.log"
MAX_RETRIES=3
RETRY_DELAY=10

# Logging functions
log_info() {
    local message="$1"
    local log_entry="${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] [INFO] $message${NC}"
    echo -e "$log_entry" >&3 2>/dev/null || true  # To console (if available)
    echo -e "$log_entry" >> "$LOG_FILE"  # To log file
}

log_warn() {
    local message="$1"
    local log_entry="${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] [WARN] $message${NC}"
    echo -e "$log_entry" >&3 2>/dev/null || true  # To console (if available)
    echo -e "$log_entry" >> "$LOG_FILE"  # To log file
}

log_error() {
    local message="$1"
    local log_entry="${RED}[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR] $message${NC}"
    echo -e "$log_entry" >&3 2>/dev/null || true  # To console (if available)
    echo -e "$log_entry" >> "$LOG_FILE"  # To log file
}

log_debug() {
    local message="$1"
    if [[ "${DEBUG:-false}" == "true" ]]; then
        local log_entry="${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] [DEBUG] $message${NC}"
        echo -e "$log_entry" >&3 2>/dev/null || true  # To console (if available)
        echo -e "$log_entry" >> "$LOG_FILE"  # To log file
    fi
}

# Retry function with exponential backoff
retry_command() {
    local cmd="$1"
    local max_attempts="${2:-$MAX_RETRIES}"
    local delay="${3:-$RETRY_DELAY}"
    local attempt=1
    
    log_debug "Executing command with retry: $cmd"
    
    while [[ $attempt -le $max_attempts ]]; do
        log_debug "Attempt $attempt/$max_attempts: $cmd"
        
        if eval "$cmd"; then
            log_debug "Command succeeded on attempt $attempt"
            return 0
        else
            local exit_code=$?
            log_warn "Command failed on attempt $attempt/$max_attempts (exit code: $exit_code)"
            
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "Retrying in $delay seconds..."
                sleep "$delay"
                delay=$((delay * 2))  # Exponential backoff
            fi
            
            ((attempt++))
        fi
    done
    
    log_error "Command failed after $max_attempts attempts: $cmd"
    return 1
}

# Network connectivity check
check_network() {
    local test_hosts=("8.8.8.8" "1.1.1.1" "169.254.169.254")
    
    for host in "${test_hosts[@]}"; do
        if ping -c 1 -W 5 "$host" &>/dev/null; then
            log_info "Network connectivity confirmed (can reach $host)"
            return 0
        fi
    done
    
    log_error "Network connectivity check failed"
    return 1
}

# Service status check
check_service_status() {
    local service="$1"
    local timeout="${2:-30}"
    local elapsed=0
    
    log_info "Checking service status: $service"
    
    while [[ $elapsed -lt $timeout ]]; do
        if systemctl is-active --quiet "$service"; then
            log_info "Service $service is active"
            return 0
        fi
        
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    log_error "Service $service failed to start within $timeout seconds"
    return 1
}

# Validate command exists
require_command() {
    local cmd="$1"
    if ! command -v "$cmd" &> /dev/null; then
        log_error "Required command not found: $cmd"
        return 1
    fi
    log_debug "Required command available: $cmd"
    return 0
}

# Validate disk space
check_disk_space() {
    local path="${1:-/}"
    local min_free_gb="${2:-5}"
    
    local available_gb=$(df -BG "$path" | awk 'NR==2 {print $4}' | sed 's/G//')
    
    if [[ $available_gb -lt $min_free_gb ]]; then
        log_error "Insufficient disk space: ${available_gb}GB available, ${min_free_gb}GB required"
        return 1
    fi
    
    log_info "Disk space check passed: ${available_gb}GB available"
    return 0
}

# Initialize logging
init_logging() {
    mkdir -p "$(dirname "$LOG_FILE")"
    # Only redirect to log file, not to stdout/stderr to avoid interfering with function returns
    exec 3>&1 4>&2  # Save original stdout and stderr
    exec 1>>"$LOG_FILE" 2>&1  # Redirect both to log file only
    
    # For console output, we'll use explicit file descriptor 3 (original stdout)
    log_info "=== FoamAI Startup Script Started: $(date) ==="
    log_info "Script PID: $$"
    log_info "Log file: $LOG_FILE"
}

# ========================================================================
# EMBEDDED MODULE: 01_system_update.sh - System Update
# ========================================================================

system_update_main() {
    log_info "=== Starting System Update Module ==="
    
    # Check network connectivity first
    if ! check_network; then
        log_error "Network connectivity check failed"
        return 1
    fi
    
    # Check disk space
    if ! check_disk_space "/" 5; then
        log_error "Insufficient disk space for updates"
        return 1
    fi
    
    # Update package lists with retry
    log_info "Updating package lists..."
    if ! retry_command "apt-get update -y" 3 5; then
        log_error "Failed to update package lists"
        return 1
    fi
    
    # Upgrade system packages with retry
    log_info "Upgrading system packages..."
    if ! retry_command "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y" 3 10; then
        log_error "Failed to upgrade system packages"
        return 1
    fi
    
    # Install essential packages
    log_info "Installing essential packages..."
    local essential_packages=(
        "curl" "wget" "git" "unzip" "htop" "tree" "jq" "ca-certificates"
        "gnupg" "lsb-release" "software-properties-common" "apt-transport-https"
        "util-linux" "parted" "lsof" "net-tools"
    )
    
    local package_list="${essential_packages[*]}"
    if ! retry_command "DEBIAN_FRONTEND=noninteractive apt-get install -y $package_list" 3 10; then
        log_error "Failed to install essential packages"
        return 1
    fi
    
    # Verify critical packages
    local critical_packages=("curl" "wget" "git" "jq")
    for pkg in "${critical_packages[@]}"; do
        if ! require_command "$pkg"; then
            log_error "Critical package not available after installation: $pkg"
            return 1
        fi
    done
    
    # Get AWS metadata
    log_info "Retrieving AWS metadata..."
    local metadata_base="http://169.254.169.254/latest/meta-data"
    
    if ! retry_command "curl -f -s --max-time 5 $metadata_base/" 3 2; then
        log_error "AWS metadata service not available"
        return 1
    fi
    
    if ! AWS_REGION=$(retry_command "curl -f -s --max-time 5 $metadata_base/placement/region" 3 2); then
        log_error "Failed to get AWS region"
        return 1
    fi
    
    if ! AWS_INSTANCE_ID=$(retry_command "curl -f -s --max-time 5 $metadata_base/instance-id" 3 2); then
        log_error "Failed to get AWS instance ID"
        return 1
    fi
    
    if ! AWS_INSTANCE_TYPE=$(retry_command "curl -f -s --max-time 5 $metadata_base/instance-type" 3 2); then
        log_error "Failed to get AWS instance type"
        return 1
    fi
    
    # Export variables for use by other modules
    export AWS_REGION AWS_INSTANCE_ID AWS_INSTANCE_TYPE
    
    log_info "AWS metadata retrieved successfully:"
    log_info "  Region: $AWS_REGION"
    log_info "  Instance ID: $AWS_INSTANCE_ID"
    log_info "  Instance Type: $AWS_INSTANCE_TYPE"
    
    log_info "=== System Update Module Completed Successfully ==="
    return 0
}

# ========================================================================
# EMBEDDED MODULE: 02_docker_setup.sh - Docker Installation
# ========================================================================

docker_setup_main() {
    log_info "=== Starting Docker Setup Module ==="
    
    # Check if Docker is already installed
    if command -v docker &> /dev/null; then
        log_warn "Docker is already installed"
        local docker_version=$(docker --version)
        log_info "Current Docker version: $docker_version"
    else
        # Install Docker
        log_info "Installing Docker..."
        
        # Add Docker's official GPG key
        if ! retry_command "install -m 0755 -d /etc/apt/keyrings" 3 2; then
            log_error "Failed to create keyrings directory"
            return 1
        fi
        
        if ! retry_command "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg" 3 5; then
            log_error "Failed to add Docker GPG key"
            return 1
        fi
        
        if ! retry_command "chmod a+r /etc/apt/keyrings/docker.gpg" 3 2; then
            log_error "Failed to set GPG key permissions"
            return 1
        fi
        
        # Add Docker repository
        local docker_repo='deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable'
        
        if ! retry_command "echo \"$docker_repo\" | tee /etc/apt/sources.list.d/docker.list > /dev/null" 3 2; then
            log_error "Failed to add Docker repository"
            return 1
        fi
        
        # Update package index and install Docker
        if ! retry_command "apt-get update -y" 3 5; then
            log_error "Failed to update package index"
            return 1
        fi
        
        local docker_packages="docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
        if ! retry_command "DEBIAN_FRONTEND=noninteractive apt-get install -y $docker_packages" 3 15; then
            log_error "Failed to install Docker packages"
            return 1
        fi
        
        # Start and enable Docker service
        if ! retry_command "systemctl start docker" 3 5; then
            log_error "Failed to start Docker service"
            return 1
        fi
        
        if ! retry_command "systemctl enable docker" 3 5; then
            log_error "Failed to enable Docker service"
            return 1
        fi
        
        local docker_version=$(docker --version)
        log_info "Docker installed successfully: $docker_version"
    fi
    
    # Setup Docker permissions
    log_info "Setting up Docker permissions for ubuntu user..."
    if ! retry_command "usermod -aG docker ubuntu" 3 2; then
        log_error "Failed to add ubuntu user to docker group"
        return 1
    fi
    
    # Install Docker Compose standalone
    if ! command -v docker-compose &> /dev/null; then
        log_info "Installing Docker Compose standalone..."
        local DOCKER_COMPOSE_VERSION="v2.24.1"
        local compose_url="https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)"
        
        if ! retry_command "curl -L \"$compose_url\" -o /usr/local/bin/docker-compose" 3 10; then
            log_error "Failed to download Docker Compose"
            return 1
        fi
        
        if ! retry_command "chmod +x /usr/local/bin/docker-compose" 3 2; then
            log_error "Failed to make Docker Compose executable"
            return 1
        fi
        
        if ! retry_command "ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose" 3 2; then
            log_error "Failed to create Docker Compose symbolic link"
            return 1
        fi
        
        local compose_version=$(docker-compose --version)
        log_info "Docker Compose installed successfully: $compose_version"
    fi
    
    # Verify Docker installation
    if ! check_service_status "docker" 30; then
        log_error "Docker service is not running"
        return 1
    fi
    
    log_info "=== Docker Setup Module Completed Successfully ==="
    return 0
}

# ========================================================================
# EMBEDDED MODULE: 03_ebs_volume_setup.sh - EBS Volume Setup
# ========================================================================

# EBS volume utility functions
is_mounted() {
    local device="$1"
    mount | grep -q "^$device"
}

has_filesystem() {
    local device="$1"
    blkid "$device" &>/dev/null
}

get_device_size_gb() {
    local device="$1"
    if [[ -b "$device" ]]; then
        lsblk -n -o SIZE -b "$device" | head -1 | awk '{print int($1/1024/1024/1024)}'
    else
        echo "0"
    fi
}

is_expected_size() {
    local device="$1"
    local size_gb=$(get_device_size_gb "$device")
    local min_size_gb=$((DATA_VOLUME_SIZE_GB - (DATA_VOLUME_SIZE_GB * 10 / 100)))
    local max_size_gb=$((DATA_VOLUME_SIZE_GB + (DATA_VOLUME_SIZE_GB * 10 / 100)))
    
    log_debug "Device $device: size=${size_gb}GB, expected=${DATA_VOLUME_SIZE_GB}GB, range=${min_size_gb}-${max_size_gb}GB"
    [[ $size_gb -ge $min_size_gb && $size_gb -le $max_size_gb ]]
}

# Volume discovery strategies
find_data_volume_by_size() {
    log_info "Strategy 1: Searching for data volume by size (${DATA_VOLUME_SIZE_GB}GB)"
    
    local device_patterns=("/dev/nvme*n1" "/dev/xvd*" "/dev/sd*" "/dev/nvme*")
    
    for pattern in "${device_patterns[@]}"; do
        for device in $pattern; do
            if [[ -b "$device" ]] && ! is_mounted "$device" && is_expected_size "$device"; then
                if ! df / | grep -q "$device"; then
                    log_info "Found data volume by size: $device ($(get_device_size_gb "$device")GB)"
                    echo "$device"
                    return 0
                fi
            fi
        done
    done
    
    log_warn "No data volume found by size matching ${DATA_VOLUME_SIZE_GB}GB"
    return 1
}

discover_data_volume() {
    log_info "Starting data volume discovery process"
    
    local device=""
    if device=$(find_data_volume_by_size); then
        echo "$device"
        return 0
    fi
    
    log_error "All discovery strategies failed"
    return 1
}

wait_for_volumes() {
    log_info "Waiting for EBS volumes to be attached (timeout: ${EBS_WAIT_TIMEOUT}s)"
    
    local start_time=$(date +%s)
    
    while [[ $(($(date +%s) - start_time)) -lt $EBS_WAIT_TIMEOUT ]]; do
        if discover_data_volume &>/dev/null; then
            log_info "Data volume detected after $(($(date +%s) - start_time)) seconds"
            return 0
        fi
        
        log_debug "Waiting for volumes... ($(($(date +%s) - start_time))/${EBS_WAIT_TIMEOUT}s)"
        sleep 5
    done
    
    log_warn "Volume detection timed out after ${EBS_WAIT_TIMEOUT} seconds"
    return 1
}

ebs_volume_setup_main() {
    log_info "=== Starting EBS Volume Setup Module ==="
    log_info "Configuration: Expected size: ${DATA_VOLUME_SIZE_GB}GB, Filesystem: $FILESYSTEM_TYPE, Mount point: $MOUNT_POINT"
    
    # Wait for volumes to be available
    if ! wait_for_volumes; then
        log_warn "No additional data volume found, using root volume"
        mkdir -p "$MOUNT_POINT"
        chown ubuntu:ubuntu "$MOUNT_POINT"
        chmod 755 "$MOUNT_POINT"
        log_info "Created $MOUNT_POINT on root volume as fallback"
        return 0
    fi
    
    # Discover the data volume
    local device
    if ! device=$(discover_data_volume); then
        log_error "Failed to discover data volume"
        return 1
    fi
    
    log_info "Using device: $device ($(get_device_size_gb "$device")GB)"
    
    # Create filesystem if not already formatted
    if ! has_filesystem "$device"; then
        log_info "Creating $FILESYSTEM_TYPE filesystem on $device"
        if ! retry_command "mkfs.$FILESYSTEM_TYPE -F $device" 3 5; then
            log_error "Failed to create filesystem on $device"
            return 1
        fi
    fi
    
    # Create mount point and mount
    mkdir -p "$MOUNT_POINT"
    if ! retry_command "mount $device $MOUNT_POINT" 3 5; then
        log_error "Failed to mount $device to $MOUNT_POINT"
        return 1
    fi
    
    # Add to fstab for permanent mounting
    local device_uuid=$(blkid -s UUID -o value "$device")
    if [[ -n "$device_uuid" ]]; then
        if ! grep -q "$device_uuid" /etc/fstab; then
            echo "UUID=$device_uuid $MOUNT_POINT $FILESYSTEM_TYPE defaults,nofail 0 2" >> /etc/fstab
            log_info "Added UUID-based fstab entry for persistent mounting"
        fi
    fi
    
    # Set permissions
    chown ubuntu:ubuntu "$MOUNT_POINT"
    chmod 755 "$MOUNT_POINT"
    
    log_info "Data volume setup completed successfully"
    df -h "$MOUNT_POINT"
    
    log_info "=== EBS Volume Setup Module Completed Successfully ==="
    return 0
}

# ========================================================================
# EMBEDDED MODULE: 04_application_setup.sh - Application Setup
# ========================================================================

application_setup_main() {
    log_info "=== Starting Application Setup Module ==="
    
    # Setup application directories
    log_info "Setting up application directories..."
    mkdir -p "$FOAMAI_INSTALL_DIR"
    chown ubuntu:ubuntu "$FOAMAI_INSTALL_DIR"
    
    # Clone the FoamAI repository
    log_info "Cloning FoamAI repository..."
    if [[ -d "$FOAMAI_INSTALL_DIR/.git" ]]; then
        log_warn "Repository already exists, updating..."
        if ! su - ubuntu -c "cd $FOAMAI_INSTALL_DIR && git pull origin main"; then
            log_error "Failed to update existing repository"
            return 1
        fi
    else
        if [[ -d "$FOAMAI_INSTALL_DIR" ]]; then
            rm -rf "$FOAMAI_INSTALL_DIR"
        fi
        
        if ! retry_command "git clone $FOAMAI_REPO_URL $FOAMAI_INSTALL_DIR" 3 10; then
            log_error "Failed to clone repository"
            return 1
        fi
        
        chown -R ubuntu:ubuntu "$FOAMAI_INSTALL_DIR"
    fi
    
    # Verify repository structure
    if [[ ! -f "$FOAMAI_INSTALL_DIR/docker-compose.yml" ]]; then
        log_error "Repository appears to be invalid - missing docker-compose.yml"
        return 1
    fi
    
    # Create environment configuration
    log_info "Creating environment configuration..."
    local env_file="$FOAMAI_INSTALL_DIR/.env"
    
    local instance_ip
    if ! instance_ip=$(curl -f -s --max-time 10 http://169.254.169.254/latest/meta-data/public-ipv4); then
        log_warn "Could not get instance IP, using localhost"
        instance_ip="localhost"
    fi
    
    cat > "$env_file" << EOF
# FoamAI Environment Configuration
COMPOSE_PROJECT_NAME=foamai
DATA_DIR=$MOUNT_POINT
API_PORT=8000
PARAVIEW_PORT=11111

# GitHub Container Registry Configuration
GHCR_REGISTRY=ghcr.io
GITHUB_ORG=$GITHUB_ORG

# Docker Image Configuration
GHCR_API_URL=ghcr.io/$GITHUB_ORG/foamai/api
GHCR_OPENFOAM_URL=ghcr.io/$GITHUB_ORG/foamai/openfoam
GHCR_PVSERVER_URL=ghcr.io/$GITHUB_ORG/foamai/pvserver
IMAGE_TAG=latest

# API Configuration
API_HOST=0.0.0.0
API_WORKERS=2

# OpenFOAM Configuration
OPENFOAM_VERSION=10

# ParaView Configuration
PARAVIEW_SERVER_PORT=11111

# AWS Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
INSTANCE_IP=$instance_ip
EOF
    
    chown ubuntu:ubuntu "$env_file"
    chmod 600 "$env_file"
    
    # Create data directories
    local data_dirs=("$MOUNT_POINT/simulations" "$MOUNT_POINT/results" "$MOUNT_POINT/meshes" "$MOUNT_POINT/cases")
    for dir in "${data_dirs[@]}"; do
        mkdir -p "$dir"
        chown ubuntu:ubuntu "$dir"
        chmod 755 "$dir"
    done
    
    log_info "=== Application Setup Module Completed Successfully ==="
    return 0
}

# ========================================================================
# EMBEDDED MODULE: 05_service_setup.sh - Service Setup
# ========================================================================

service_setup_main() {
    log_info "=== Starting Service Setup Module ==="
    
    # Create systemd service
    log_info "Creating systemd service for FoamAI..."
    cat > "/etc/systemd/system/foamai.service" << EOF
[Unit]
Description=FoamAI CFD Assistant Services
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=ubuntu
Group=ubuntu
WorkingDirectory=$FOAMAI_INSTALL_DIR
Environment=HOME=/home/ubuntu
ExecStart=/usr/local/bin/docker-compose up -d --remove-orphans
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=300
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target
EOF
    
    chmod 644 "/etc/systemd/system/foamai.service"
    
    # Create status monitoring script
    cat > "/usr/local/bin/foamai-status" << 'EOF'
#!/bin/bash
echo "=== FoamAI Status Check ==="
echo "Docker status: $(systemctl is-active docker)"
echo "FoamAI status: $(systemctl is-active foamai)"
echo ""
echo "Running containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Cannot access Docker"
echo ""
echo "Service endpoints:"
INSTANCE_IP=$(curl -s --max-time 3 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "localhost")
echo "  API: http://$INSTANCE_IP:8000"
echo "  API Docs: http://$INSTANCE_IP:8000/docs"
echo "  ParaView Server: $INSTANCE_IP:11111"
echo ""
echo "Storage status:"
df -h /data 2>/dev/null || df -h /
EOF
    
    chmod +x "/usr/local/bin/foamai-status"
    
    # Setup log rotation
    cat > "/etc/logrotate.d/docker-containers" << 'EOF'
/var/lib/docker/containers/*/*.log {
    rotate 5
    daily
    compress
    size=50M
    missingok
    delaycompress
    copytruncate
}
EOF
    
    # Enable systemd service
    systemctl daemon-reload
    systemctl enable foamai
    
    log_info "=== Service Setup Module Completed Successfully ==="
    return 0
}

# ========================================================================
# EMBEDDED MODULE: 06_docker_operations.sh - Docker Operations
# ========================================================================

docker_operations_main() {
    log_info "=== Starting Docker Operations Module ==="
    
    # Wait for Docker to be fully ready
    log_info "Waiting for Docker to be fully ready..."
    local timeout=60
    local elapsed=0
    
    while [[ $elapsed -lt $timeout ]]; do
        if systemctl is-active --quiet docker && docker info &>/dev/null; then
            log_info "Docker is ready after $elapsed seconds"
            break
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    if [[ $elapsed -ge $timeout ]]; then
        log_error "Docker failed to become ready within $timeout seconds"
        return 1
    fi
    
    # Validate Docker Compose configuration
    if [[ ! -f "$FOAMAI_INSTALL_DIR/docker-compose.yml" ]]; then
        log_error "docker-compose.yml not found"
        return 1
    fi
    
    # Pull Docker images and start services
    log_info "Pulling Docker images and starting services..."
    local pull_and_start_cmd="cd $FOAMAI_INSTALL_DIR && newgrp docker -c 'docker-compose pull && docker-compose up -d --remove-orphans'"
    
    if ! su - ubuntu -c "$pull_and_start_cmd"; then
        log_error "Failed to pull images and start services"
        return 1
    fi
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # Test API endpoint
    local api_url="http://localhost:8000"
    for attempt in 1 2 3; do
        if curl -f -s --max-time 10 "$api_url/ping" &>/dev/null; then
            log_info "✓ API endpoint is responding"
            break
        elif [[ $attempt -eq 3 ]]; then
            log_warn "✗ API endpoint not responding after 3 attempts"
        else
            log_debug "API not ready, retrying in $((attempt * 5)) seconds..."
            sleep $((attempt * 5))
        fi
    done
    
    # Start FoamAI systemd service
    log_info "Starting FoamAI systemd service..."
    if ! systemctl start foamai; then
        log_error "Failed to start FoamAI service"
        return 1
    fi
    
    if ! check_service_status "foamai" 60; then
        log_error "FoamAI service failed to start"
        return 1
    fi
    
    log_info "=== Docker Operations Module Completed Successfully ==="
    return 0
}

# ========================================================================
# MAIN ORCHESTRATOR
# ========================================================================

# Pre-flight checks
pre_flight_checks() {
    log_info "=== Performing Pre-flight Checks ==="
    
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        return 1
    fi
    
    if ! id ubuntu &>/dev/null; then
        log_error "Ubuntu user does not exist"
        return 1
    fi
    
    if ! check_network; then
        log_error "Network connectivity check failed"
        return 1
    fi
    
    if ! check_disk_space "/" 10; then
        log_error "Insufficient disk space"
        return 1
    fi
    
    log_info "Pre-flight checks completed successfully"
    return 0
}

# Post-deployment validation
post_deployment_validation() {
    log_info "=== Performing Post-deployment Validation ==="
    
    sleep 30
    
    if ! systemctl is-active --quiet docker; then
        log_error "Docker service is not running"
        return 1
    fi
    
    if ! systemctl is-active --quiet foamai; then
        log_error "FoamAI service is not running"
        return 1
    fi
    
    if [[ ! -d "$MOUNT_POINT" ]] || [[ ! -w "$MOUNT_POINT" ]]; then
        log_error "Data directory is not accessible: $MOUNT_POINT"
        return 1
    fi
    
    log_info "Post-deployment validation completed successfully"
    return 0
}

# Create deployment summary
create_deployment_summary() {
    log_info "=== Creating Deployment Summary ==="
    
    local summary_file="/var/log/foamai-deployment-summary.log"
    local instance_ip=$(curl -s --max-time 3 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "localhost")
    
    {
        echo "=========================="
        echo "FoamAI Deployment Summary"
        echo "=========================="
        echo "Date: $(date)"
        echo "Instance: ${AWS_INSTANCE_ID:-unknown} (${AWS_INSTANCE_TYPE:-unknown})"
        echo "Region: ${AWS_REGION:-unknown}"
        echo ""
        echo "Services:"
        echo "  Docker: $(systemctl is-active docker)"
        echo "  FoamAI: $(systemctl is-active foamai)"
        echo ""
        echo "Endpoints:"
        echo "  API: http://$instance_ip:8000"
        echo "  API Docs: http://$instance_ip:8000/docs"
        echo "  ParaView: $instance_ip:11111"
        echo ""
        echo "Management:"
        echo "  Status: sudo foamai-status"
        echo "  Logs: sudo tail -f /var/log/foamai-startup.log"
        echo "=========================="
    } > "$summary_file"
    
    cat "$summary_file"
    return 0
}

# Handle script failure
handle_failure() {
    local exit_code=$1
    local failed_module=$2
    
    log_error "=== DEPLOYMENT FAILED ==="
    log_error "Failed module: $failed_module"
    
    local failure_report="/var/log/foamai-deployment-failure.log"
    {
        echo "=========================="
        echo "FoamAI Deployment Failure"
        echo "=========================="
        echo "Date: $(date)"
        echo "Failed Module: $failed_module"
        echo "Instance: ${AWS_INSTANCE_ID:-unknown}"
        echo ""
        echo "Last 20 lines of startup log:"
        tail -n 20 /var/log/foamai-startup.log 2>/dev/null || echo "No startup log available"
        echo "=========================="
    } > "$failure_report"
    
    return $exit_code
}

# Main execution function
main() {
    # Initialize logging
    init_logging
    
    log_info "=== Starting FoamAI Modular Deployment ==="
    log_info "Configuration: SIZE=${DATA_VOLUME_SIZE_GB}GB, FS=$FILESYSTEM_TYPE, MOUNT=$MOUNT_POINT"
    
    # Pre-flight checks
    if ! pre_flight_checks; then
        handle_failure 1 "pre_flight_checks"
        return 1
    fi
    
    # Execute modules in order
    local modules=(
        "system_update_main"
        "docker_setup_main"
        "ebs_volume_setup_main"
        "application_setup_main"
        "service_setup_main"
        "docker_operations_main"
    )
    
    for module in "${modules[@]}"; do
        if ! $module; then
            handle_failure 1 "$module"
            return 1
        fi
    done
    
    # Post-deployment validation
    if ! post_deployment_validation; then
        handle_failure 1 "post_deployment_validation"
        return 1
    fi
    
    # Create deployment summary
    create_deployment_summary
    
    # Create completion marker
    touch /var/log/foamai-startup-complete
    
    log_info "=== FoamAI Deployment Completed Successfully ==="
    return 0
}

# Script execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 