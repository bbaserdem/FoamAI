#!/usr/bin/env bash
# Docker Setup Module for FoamAI
# Handles Docker and Docker Compose installation with proper validation

# Source utilities
source "$(dirname "${BASH_SOURCE[0]}")/utils.sh"

# Install Docker
install_docker() {
    log_info "Starting Docker installation..."
    
    # Check if Docker is already installed
    if command -v docker &> /dev/null; then
        log_warn "Docker is already installed"
        local docker_version=$(docker --version)
        log_info "Current Docker version: $docker_version"
        return 0
    fi
    
    # Add Docker's official GPG key
    log_info "Adding Docker's official GPG key..."
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
    log_info "Adding Docker repository..."
    local docker_repo='deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable'
    
    if ! retry_command "echo \"$docker_repo\" | tee /etc/apt/sources.list.d/docker.list > /dev/null" 3 2; then
        log_error "Failed to add Docker repository"
        return 1
    fi
    
    # Update package index
    log_info "Updating package index..."
    if ! retry_command "apt-get update -y" 3 5; then
        log_error "Failed to update package index"
        return 1
    fi
    
    # Install Docker packages
    log_info "Installing Docker packages..."
    local docker_packages="docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
    
    if ! retry_command "DEBIAN_FRONTEND=noninteractive apt-get install -y $docker_packages" 3 15; then
        log_error "Failed to install Docker packages"
        return 1
    fi
    
    # Start and enable Docker service
    log_info "Starting and enabling Docker service..."
    if ! retry_command "systemctl start docker" 3 5; then
        log_error "Failed to start Docker service"
        return 1
    fi
    
    if ! retry_command "systemctl enable docker" 3 5; then
        log_error "Failed to enable Docker service"
        return 1
    fi
    
    # Verify Docker installation
    if ! check_service_status "docker" 30; then
        log_error "Docker service is not running"
        return 1
    fi
    
    # Test Docker functionality
    log_info "Testing Docker functionality..."
    if ! retry_command "docker run --rm hello-world" 3 10; then
        log_error "Docker functionality test failed"
        return 1
    fi
    
    local docker_version=$(docker --version)
    log_info "Docker installed successfully: $docker_version"
    return 0
}

# Setup Docker user permissions
setup_docker_permissions() {
    log_info "Setting up Docker permissions for ubuntu user..."
    
    # Add ubuntu user to docker group
    if ! retry_command "usermod -aG docker ubuntu" 3 2; then
        log_error "Failed to add ubuntu user to docker group"
        return 1
    fi
    
    # Verify group membership
    if groups ubuntu | grep -q docker; then
        log_info "Ubuntu user successfully added to docker group"
    else
        log_error "Failed to verify docker group membership"
        return 1
    fi
    
    # Create a test script to validate docker access for ubuntu user
    cat > /tmp/test_docker_access.sh << 'EOF'
#!/bin/bash
# Test Docker access for ubuntu user
if docker ps &>/dev/null; then
    echo "Docker access confirmed for ubuntu user"
    exit 0
else
    echo "Docker access failed for ubuntu user"
    exit 1
fi
EOF
    
    chmod +x /tmp/test_docker_access.sh
    
    # Test Docker access with newgrp to refresh group membership
    log_info "Testing Docker access for ubuntu user..."
    if su - ubuntu -c "newgrp docker -c '/tmp/test_docker_access.sh'" &>/dev/null; then
        log_info "Docker access validated for ubuntu user"
    else
        log_warn "Docker access test failed - user may need to logout/login"
    fi
    
    # Clean up test script
    rm -f /tmp/test_docker_access.sh
    
    return 0
}

# Install Docker Compose standalone
install_docker_compose() {
    log_info "Installing Docker Compose standalone..."
    
    # Check if Docker Compose is already installed
    if command -v docker-compose &> /dev/null; then
        log_warn "Docker Compose is already installed"
        local compose_version=$(docker-compose --version)
        log_info "Current Docker Compose version: $compose_version"
        return 0
    fi
    
    # Set Docker Compose version
    local DOCKER_COMPOSE_VERSION="v2.24.1"
    local compose_url="https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)"
    
    log_info "Downloading Docker Compose $DOCKER_COMPOSE_VERSION..."
    if ! retry_command "curl -L \"$compose_url\" -o /usr/local/bin/docker-compose" 3 10; then
        log_error "Failed to download Docker Compose"
        return 1
    fi
    
    # Make executable
    if ! retry_command "chmod +x /usr/local/bin/docker-compose" 3 2; then
        log_error "Failed to make Docker Compose executable"
        return 1
    fi
    
    # Create symbolic link
    if ! retry_command "ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose" 3 2; then
        log_error "Failed to create Docker Compose symbolic link"
        return 1
    fi
    
    # Verify installation
    if ! require_command "docker-compose"; then
        log_error "Docker Compose installation verification failed"
        return 1
    fi
    
    local compose_version=$(docker-compose --version)
    log_info "Docker Compose installed successfully: $compose_version"
    return 0
}

# Optimize Docker configuration
optimize_docker_config() {
    log_info "Optimizing Docker configuration..."
    
    # Create Docker daemon configuration
    local docker_config_dir="/etc/docker"
    local docker_config_file="$docker_config_dir/daemon.json"
    
    if ! mkdir -p "$docker_config_dir"; then
        log_error "Failed to create Docker configuration directory"
        return 1
    fi
    
    # Create optimized daemon configuration
    cat > "$docker_config_file" << 'EOF'
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "default-address-pools": [
        {
            "base": "172.17.0.0/12",
            "size": 24
        }
    ],
    "live-restore": true
}
EOF
    
    # Restart Docker to apply configuration
    log_info "Restarting Docker to apply configuration..."
    if ! retry_command "systemctl restart docker" 3 10; then
        log_error "Failed to restart Docker with new configuration"
        return 1
    fi
    
    # Wait for Docker to be ready
    if ! check_service_status "docker" 30; then
        log_error "Docker service failed to start after configuration"
        return 1
    fi
    
    log_info "Docker configuration optimized successfully"
    return 0
}

# Main function
main() {
    log_info "=== Starting Docker Setup Module ==="
    
    # Install Docker
    if ! install_docker; then
        log_error "Docker installation failed"
        return 1
    fi
    
    # Setup Docker permissions
    if ! setup_docker_permissions; then
        log_error "Docker permissions setup failed"
        return 1
    fi
    
    # Install Docker Compose
    if ! install_docker_compose; then
        log_error "Docker Compose installation failed"
        return 1
    fi
    
    # Optimize Docker configuration
    if ! optimize_docker_config; then
        log_error "Docker configuration optimization failed"
        return 1
    fi
    
    log_info "=== Docker Setup Module Completed Successfully ==="
    return 0
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 