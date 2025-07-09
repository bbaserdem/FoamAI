#!/bin/bash
# FoamAI EC2 Instance Startup Script
# This script runs on first boot to setup Docker and FoamAI services
# Updated to use GitHub Container Registry (ghcr.io) instead of Docker Hub

set -e  # Exit on any error

# Logging setup
LOG_FILE="/var/log/foamai-startup.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "=== FoamAI Startup Script Started: $(date) ==="

# Update system packages first
echo "Updating system packages..."
apt-get update -y
apt-get upgrade -y

# Install essential packages BEFORE using them
echo "Installing essential packages..."
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
    apt-transport-https

# Get AWS region from instance metadata (for potential future use)
AWS_REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)
echo "AWS Region: $AWS_REGION"

# Install Docker
echo "Installing Docker..."
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

echo "Docker installation completed successfully"

# Install Docker Compose (standalone for compatibility)
echo "Installing Docker Compose standalone..."
DOCKER_COMPOSE_VERSION="v2.24.1"
curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create symbolic link for docker-compose
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

echo "Docker Compose installation completed"

# Setup data volume
echo "Setting up data volume..."
# Format and mount the additional EBS volume if it exists
if [[ -b /dev/nvme1n1 ]] || [[ -b /dev/xvdf ]]; then
    # Determine the correct device name
    if [[ -b /dev/nvme1n1 ]]; then
        DEVICE="/dev/nvme1n1"
    else
        DEVICE="/dev/xvdf"
    fi
    
    echo "Found data volume at $DEVICE"
    
    # Create filesystem if not already formatted
    if ! blkid "$DEVICE"; then
        echo "Formatting data volume..."
        mkfs.ext4 "$DEVICE"
    fi
    
    # Create mount point and mount
    mkdir -p /data
    mount "$DEVICE" /data
    
    # Add to fstab for permanent mounting
    DEVICE_UUID=$(blkid -s UUID -o value "$DEVICE")
    echo "UUID=$DEVICE_UUID /data ext4 defaults,nofail 0 2" >> /etc/fstab
    
    # Set permissions
    chown ubuntu:ubuntu /data
    chmod 755 /data
    
    echo "Data volume mounted at /data"
else
    echo "No additional data volume found, creating /data directory on root volume"
    mkdir -p /data
    chown ubuntu:ubuntu /data
    chmod 755 /data
fi

# Setup application directories
echo "Setting up application directories..."
mkdir -p /opt/foamai
chown ubuntu:ubuntu /opt/foamai

# Clone the FoamAI repository
echo "Cloning FoamAI repository..."
cd /opt
git clone https://github.com/batuhan/foamai.git foamai
chown -R ubuntu:ubuntu /opt/foamai

# Create environment file for Docker Compose with GitHub Container Registry URLs
echo "Creating environment configuration..."
cat > /opt/foamai/.env << EOF
# FoamAI Environment Configuration
COMPOSE_PROJECT_NAME=foamai
DATA_DIR=/data
API_PORT=8000
PARAVIEW_PORT=11111

# GitHub Container Registry Configuration
GHCR_REGISTRY=ghcr.io
GITHUB_ORG=batuhan

# Docker image settings - Using GitHub Container Registry
GHCR_API_URL=ghcr.io/batuhan/foamai/api
GHCR_OPENFOAM_URL=ghcr.io/batuhan/foamai/openfoam
GHCR_PVSERVER_URL=ghcr.io/batuhan/foamai/pvserver
IMAGE_TAG=latest

# API Configuration
API_HOST=0.0.0.0
API_WORKERS=2

# OpenFOAM Configuration
OPENFOAM_VERSION=10

# ParaView Configuration
PARAVIEW_SERVER_PORT=11111
EOF

# Note: GitHub Container Registry for public repositories doesn't require authentication
# for pulling images, so no login script is needed

# Create systemd service for FoamAI with GHCR support
echo "Creating systemd service..."
cat > /etc/systemd/system/foamai.service << 'EOF'
[Unit]
Description=FoamAI CFD Assistant Services
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/foamai
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
echo "Setting up log rotation..."
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
echo "Waiting for Docker to be ready..."
sleep 10

# Pull Docker images from GitHub Container Registry
echo "Pulling Docker images from GitHub Container Registry..."
su - ubuntu -c "cd /opt/foamai && docker-compose pull" || echo "Docker images will be pulled when they become available"

# Start FoamAI services
echo "Starting FoamAI services..."
su - ubuntu -c "cd /opt/foamai && docker-compose up -d" || echo "Services will start when images are available"

# Create status check script
echo "Creating status check script..."
cat > /usr/local/bin/foamai-status << 'EOF'
#!/bin/bash
echo "=== FoamAI Status Check ==="
echo "Docker status:"
systemctl is-active docker

echo -e "\nRunning containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo -e "\nService endpoints:"
INSTANCE_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "API: http://$INSTANCE_IP:8000"
echo "API Docs: http://$INSTANCE_IP:8000/docs"
echo "ParaView Server: $INSTANCE_IP:11111"

echo -e "\nDisk usage:"
df -h /data 2>/dev/null || df -h /

echo -e "\nRecent logs:"
tail -n 10 /var/log/foamai-startup.log
EOF

chmod +x /usr/local/bin/foamai-status

# Create startup completion marker
echo "Creating startup completion marker..."
touch /var/log/foamai-startup-complete
echo "=== FoamAI Startup Script Completed: $(date) ===" 

# Final status
echo "=== Final System Status ==="
echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker-compose --version)"
echo "System uptime: $(uptime)"
echo "Available disk space:"
df -h /
echo ""
echo "FoamAI startup script completed successfully!"
echo "Check status with: sudo /usr/local/bin/foamai-status"
echo "View logs with: sudo tail -f /var/log/foamai-startup.log" 