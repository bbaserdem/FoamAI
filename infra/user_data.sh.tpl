#!/usr/bin/env bash
# FoamAI EC2 Instance Startup Script (Template)
# This script runs on first boot to setup Docker and FoamAI services
# Implements robust EBS volume mounting with configurable hybrid approach
#
# Template Variables:
# - data_volume_size_gb: Expected size of the data volume in GB
# - filesystem_type: Filesystem type (ext4, xfs)
# - mount_point: Where to mount the data volume
# - wait_timeout: Timeout in seconds for EBS volume detection
# - deployment_profile: Configuration profile (minimal, standard, performance, development)

set -e  # Exit on any error

# Configuration from Terraform template
readonly EXPECTED_SIZE_GB="${data_volume_size_gb}"
readonly FILESYSTEM_TYPE="${filesystem_type}"
readonly MOUNT_POINT="${mount_point}"
readonly WAIT_TIMEOUT="${wait_timeout}"
readonly DEPLOYMENT_PROFILE="${deployment_profile}"

# Allow environment variable overrides for testing/debugging
DATA_VOLUME_SIZE_GB=$${DATA_VOLUME_SIZE_GB:-$EXPECTED_SIZE_GB}
FILESYSTEM_TYPE_OVERRIDE=$${FILESYSTEM_TYPE:-$FILESYSTEM_TYPE}
MOUNT_POINT_OVERRIDE=$${MOUNT_POINT:-$MOUNT_POINT}
WAIT_TIMEOUT_OVERRIDE=$${WAIT_TIMEOUT:-$WAIT_TIMEOUT}

# Logging setup
LOG_FILE="/var/log/foamai-startup.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "=== FoamAI Startup Script Started: $(date) ==="
echo "Configuration: Volume=$${DATA_VOLUME_SIZE_GB}GB, FS=$${FILESYSTEM_TYPE_OVERRIDE}, Mount=$${MOUNT_POINT_OVERRIDE}, Profile=$${DEPLOYMENT_PROFILE}"

# Enhanced logging function
log() {
    local level="$1"
    shift
    echo "[$$(date \"+%Y-%m-%d %H:%M:%S\")] [$level] $*"
}

log "INFO" "Starting FoamAI deployment with robust EBS volume mounting"

# Update system packages first
log "INFO" "Updating system packages..."
apt-get update -y
apt-get upgrade -y

# Install essential packages BEFORE using them
log "INFO" "Installing essential packages..."
apt-get install -y \
    curl \
    wget \
    git \
    unzip \
    htop \
    tree \
    jq \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common \
    apt-transport-https \
    util-linux \
    parted

# Get AWS region from instance metadata
AWS_REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
log "INFO" "AWS Region: $AWS_REGION"

# ========================================================================
# ROBUST EBS VOLUME MOUNTING IMPLEMENTATION
# ========================================================================

# Utility functions for device detection and validation
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
    local min_size_gb=$((DATA_VOLUME_SIZE_GB - (DATA_VOLUME_SIZE_GB * 10 / 100)))  # 10% tolerance
    local max_size_gb=$((DATA_VOLUME_SIZE_GB + (DATA_VOLUME_SIZE_GB * 10 / 100)))
    
    log "DEBUG" "Device $device: size=$${size_gb}GB, expected=$${DATA_VOLUME_SIZE_GB}GB, range=$${min_size_gb}-$${max_size_gb}GB" >&2
    [[ $size_gb -ge $min_size_gb && $size_gb -le $max_size_gb ]]
}

# Strategy 1: Size-based discovery (most flexible)
find_data_volume_by_size() {
    log "INFO" "Strategy 1: Searching for data volume by size ($${DATA_VOLUME_SIZE_GB}GB)" >&2
    
    for device in /dev/nvme*n1 /dev/xvd* /dev/sd* /dev/nvme*; do
        if [[ -b "$device" ]] && ! is_mounted "$device" && is_expected_size "$device"; then
            log "INFO" "Found data volume by size: $device ($(get_device_size_gb "$device")GB)" >&2
            echo "$device"
            return 0
        fi
    done
    
    log "WARN" "No data volume found by size matching $${DATA_VOLUME_SIZE_GB}GB" >&2
    return 1
}

# Strategy 2: AWS metadata-based discovery (most authoritative)
find_data_volume_by_metadata() {
    log "INFO" "Strategy 2: Searching for data volume using AWS metadata" >&2
    
    # Get instance ID
    local instance_id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
    if [[ -z "$instance_id" ]]; then
        log "WARN" "Could not get instance ID from metadata" >&2
        return 1
    fi
    
    # Try to use AWS CLI if available (may not be installed yet)
    if command -v aws &> /dev/null; then
        log "INFO" "Using AWS CLI to query volume attachments" >&2
        # This would require AWS CLI setup, which happens later
        # For now, skip this strategy during initial deployment
    fi
    
    log "INFO" "AWS metadata strategy not available during initial deployment" >&2
    return 1
}

# Strategy 3: Unused device discovery (fallback)
find_unused_device() {
    log "INFO" "Strategy 3: Searching for unused devices" >&2
    
    for device in /dev/nvme*n1 /dev/xvd* /dev/sd*; do
        if [[ -b "$device" ]] && ! is_mounted "$device" && ! has_filesystem "$device"; then
            # Additional check: ensure it's not the root device
            if ! df / | grep -q "$device"; then
                log "INFO" "Found unused device: $device ($(get_device_size_gb "$device")GB)" >&2
                echo "$device"
                return 0
            fi
        fi
    done
    
    log "WARN" "No unused devices found" >&2
    return 1
}

# Main data volume discovery function
discover_data_volume() {
    log "INFO" "Starting data volume discovery process" >&2
    
    # Try each strategy in order of preference
    local device=""
    
    # Strategy 1: Size-based discovery
    if device=$(find_data_volume_by_size); then
        echo "$device"
        return 0
    fi
    
    # Strategy 2: AWS metadata-based discovery
    if device=$(find_data_volume_by_metadata); then
        echo "$device"
        return 0
    fi
    
    # Strategy 3: Unused device discovery
    if device=$(find_unused_device); then
        echo "$device"
        return 0
    fi
    
    log "ERROR" "All discovery strategies failed" >&2
    return 1
}

# Wait for EBS volumes to be attached
wait_for_volumes() {
    log "INFO" "Waiting for EBS volumes to be attached (timeout: $${WAIT_TIMEOUT_OVERRIDE}s)"
    
    local start_time=$(date +%s)
    local timeout=$WAIT_TIMEOUT_OVERRIDE
    
    while [[ $(($(date +%s) - start_time)) -lt $timeout ]]; do
        # Check if we can discover any data volume
        if discover_data_volume &>/dev/null; then
            log "INFO" "Data volume detected after $(($(date +%s) - start_time)) seconds"
            return 0
        fi
        
        log "DEBUG" "Waiting for volumes... ($(($(date +%s) - start_time))/$${timeout}s)"
        sleep 5
    done
    
    log "WARN" "Volume detection timed out after $${timeout} seconds"
    return 1
}

# Setup data volume with comprehensive error handling
setup_data_volume() {
    log "INFO" "Setting up data volume..."
    
    # Wait for volumes to be available
    if ! wait_for_volumes; then
        log "WARN" "No additional data volume found after waiting, using root volume"
        mkdir -p "$MOUNT_POINT_OVERRIDE"
        chown ubuntu:ubuntu "$MOUNT_POINT_OVERRIDE"
        chmod 755 "$MOUNT_POINT_OVERRIDE"
        log "INFO" "Created $MOUNT_POINT_OVERRIDE on root volume as fallback"
        return 0
    fi
    
    # Discover the data volume
    local device
    if ! device=$(discover_data_volume); then
        log "ERROR" "Failed to discover data volume"
        return 1
    fi
    
    log "INFO" "Using device: $device ($(get_device_size_gb "$device")GB)"
    
    # Create filesystem if not already formatted
    if ! has_filesystem "$device"; then
        log "INFO" "Creating $FILESYSTEM_TYPE_OVERRIDE filesystem on $device"
        if ! mkfs.$FILESYSTEM_TYPE_OVERRIDE "$device"; then
            log "ERROR" "Failed to create filesystem on $device"
            return 1
        fi
        log "INFO" "Filesystem created successfully"
    else
        log "INFO" "Device $device already has a filesystem"
    fi
    
    # Create mount point
    mkdir -p "$MOUNT_POINT_OVERRIDE"
    
    # Mount the device
    if mount "$device" "$MOUNT_POINT_OVERRIDE"; then
        log "INFO" "Successfully mounted $device to $MOUNT_POINT_OVERRIDE"
    else
        log "ERROR" "Failed to mount $device to $MOUNT_POINT_OVERRIDE"
        return 1
    fi
    
    # Get UUID for persistent mounting
    local device_uuid=$(blkid -s UUID -o value "$device")
    if [[ -n "$device_uuid" ]]; then
        log "INFO" "Device UUID: $device_uuid"
        
        # Add to fstab using UUID for persistence
        if ! grep -q "$device_uuid" /etc/fstab; then
            echo "UUID=$device_uuid $MOUNT_POINT_OVERRIDE $FILESYSTEM_TYPE_OVERRIDE defaults,nofail 0 2" >> /etc/fstab
            log "INFO" "Added UUID-based fstab entry for persistent mounting"
        fi
    else
        log "WARN" "Could not get UUID for device $device"
    fi
    
    # Set proper permissions
    chown ubuntu:ubuntu "$MOUNT_POINT_OVERRIDE"
    chmod 755 "$MOUNT_POINT_OVERRIDE"
    
    # Verify the mount
    if df "$MOUNT_POINT_OVERRIDE" | grep -q "$device"; then
        log "INFO" "Data volume setup completed successfully"
        df -h "$MOUNT_POINT_OVERRIDE"
    else
        log "ERROR" "Mount verification failed"
        return 1
    fi
    
    return 0
}

# Execute the data volume setup
log "INFO" "=== Starting Data Volume Setup ==="
if setup_data_volume; then
    log "INFO" "✓ Data volume setup completed successfully"
else
    log "ERROR" "✗ Data volume setup failed, creating fallback directory"
    mkdir -p "$MOUNT_POINT_OVERRIDE"
    chown ubuntu:ubuntu "$MOUNT_POINT_OVERRIDE"
    chmod 755 "$MOUNT_POINT_OVERRIDE"
fi

# ========================================================================
# DOCKER INSTALLATION
# ========================================================================

# Install Docker
log "INFO" "Installing Docker..."
# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository to Apt sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index and install Docker
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker service
systemctl start docker
systemctl enable docker

# Add ubuntu user to docker group
usermod -aG docker ubuntu

log "INFO" "Docker installation completed successfully"

# Install Docker Compose (standalone for compatibility)
log "INFO" "Installing Docker Compose standalone..."
DOCKER_COMPOSE_VERSION="v2.24.1"
curl -L "https://github.com/docker/compose/releases/download/$${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create symbolic link for docker-compose
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

log "INFO" "Docker Compose installation completed"

# ========================================================================
# APPLICATION SETUP
# ========================================================================

# Setup application directories
log "INFO" "Setting up application directories..."
mkdir -p /opt/FoamAI
chown ubuntu:ubuntu /opt/FoamAI

# Clone the FoamAI repository
log "INFO" "Cloning FoamAI repository..."
cd /opt
git clone https://github.com/bbaserdem/FoamAI.git FoamAI
chown -R ubuntu:ubuntu /opt/FoamAI

# Create environment file for Docker Compose
log "INFO" "Creating environment configuration..."
cat > /opt/FoamAI/.env << EOF
# FoamAI Environment Configuration
COMPOSE_PROJECT_NAME=foamai
DATA_DIR=$MOUNT_POINT_OVERRIDE
API_PORT=8000
PARAVIEW_PORT=11111

# Configuration Profile
DEPLOYMENT_PROFILE=$DEPLOYMENT_PROFILE

# GitHub Container Registry Configuration
GHCR_REGISTRY=ghcr.io
GITHUB_ORG=batuhan

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

# Create systemd service for FoamAI
log "INFO" "Creating systemd service..."
cat > /etc/systemd/system/foamai.service << 'EOF'
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

# Enable the service
systemctl daemon-reload
systemctl enable foamai.service

# Setup log rotation for Docker containers
log "INFO" "Setting up log rotation..."
cat > /etc/logrotate.d/docker-containers << 'EOF'
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

# Wait for Docker to be fully ready
log "INFO" "Waiting for Docker to be ready..."
sleep 10

# Pull Docker images
log "INFO" "Pulling Docker images from GitHub Container Registry..."
su - ubuntu -c "cd /opt/FoamAI && docker-compose pull" || log "WARN" "Docker images will be pulled when they become available"

# Start FoamAI services
log "INFO" "Starting FoamAI services..."
su - ubuntu -c "cd /opt/FoamAI && docker-compose up -d" || log "WARN" "Services will start when images are available"

# Create enhanced status check script
log "INFO" "Creating enhanced status check script..."
cat > /usr/local/bin/foamai-status << 'EOF'
#!/bin/bash
echo "=== FoamAI Status Check ==="
echo "Timestamp: $(date)"
echo ""

echo "Docker status:"
systemctl is-active docker
echo ""

echo "Running containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

echo "Service endpoints:"
INSTANCE_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "Public IP: $INSTANCE_IP"
echo "API: http://$INSTANCE_IP:8000"
echo "API Docs: http://$INSTANCE_IP:8000/docs"
echo "ParaView Server: $INSTANCE_IP:11111"
echo ""

echo "Storage status:"
echo "Data volume mount:"
df -h /data 2>/dev/null || echo "No /data mount found"
echo ""
echo "Disk usage:"
df -h /
echo ""

echo "Volume discovery information:"
echo "All block devices:"
lsblk
echo ""

echo "Mount points:"
mount | grep -E "(ext4|xfs|/data)" || echo "No relevant mounts found"
echo ""

echo "Recent startup logs:"
tail -n 20 /var/log/foamai-startup.log
EOF

chmod +x /usr/local/bin/foamai-status

# Create startup completion marker
log "INFO" "Creating startup completion marker..."
touch /var/log/foamai-startup-complete
log "INFO" "=== FoamAI Startup Script Completed: $(date) ==="

# Final status
log "INFO" "=== Final System Status ==="
log "INFO" "Docker version: $(docker --version)"
log "INFO" "Docker Compose version: $(docker-compose --version)"
log "INFO" "System uptime: $(uptime)"
log "INFO" "Storage status:"
df -h /
if [[ -d "$MOUNT_POINT_OVERRIDE" ]]; then
    log "INFO" "Data volume status:"
    df -h "$MOUNT_POINT_OVERRIDE" 2>/dev/null || log "INFO" "Data directory exists but not mounted separately"
fi
log "INFO" ""
log "INFO" "FoamAI startup script completed successfully!"
log "INFO" "Check status with: sudo /usr/local/bin/foamai-status"
log "INFO" "View logs with: sudo tail -f /var/log/foamai-startup.log" 