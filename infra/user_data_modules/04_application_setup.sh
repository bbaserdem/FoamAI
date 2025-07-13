#!/usr/bin/env bash
# Application Setup Module for FoamAI
# Handles repository cloning and environment configuration

# Source utilities
source "$(dirname "${BASH_SOURCE[0]}")/utils.sh"

# Configuration variables
FOAMAI_REPO_URL="${FOAMAI_REPO_URL:-https://github.com/bbaserdem/FoamAI.git}"
FOAMAI_INSTALL_DIR="${FOAMAI_INSTALL_DIR:-/opt/FoamAI}"
DATA_DIR="${MOUNT_POINT:-/data}"
GITHUB_ORG="${GITHUB_ORG:-bbaserdem}"

# Setup application directories
setup_directories() {
    log_info "Setting up application directories..."
    
    # Create the main application directory
    if ! mkdir -p "$FOAMAI_INSTALL_DIR"; then
        log_error "Failed to create application directory: $FOAMAI_INSTALL_DIR"
        return 1
    fi
    
    # Set ownership to ubuntu user
    if ! chown ubuntu:ubuntu "$FOAMAI_INSTALL_DIR"; then
        log_error "Failed to set ownership for $FOAMAI_INSTALL_DIR"
        return 1
    fi
    
    log_info "Application directories created successfully"
    return 0
}

# Clone the FoamAI repository
clone_repository() {
    log_info "Cloning FoamAI repository..."
    
    # Check if repository already exists
    if [[ -d "$FOAMAI_INSTALL_DIR/.git" ]]; then
        log_warn "Repository already exists at $FOAMAI_INSTALL_DIR"
        
        # Update existing repository
        log_info "Updating existing repository..."
        if ! su - ubuntu -c "cd $FOAMAI_INSTALL_DIR && git pull origin main"; then
            log_error "Failed to update existing repository"
            return 1
        fi
        
        log_info "Repository updated successfully"
        return 0
    fi
    
    # Remove directory if it exists but is not a git repository
    if [[ -d "$FOAMAI_INSTALL_DIR" ]]; then
        log_info "Removing existing non-git directory"
        rm -rf "$FOAMAI_INSTALL_DIR"
    fi
    
    # Clone the repository
    log_info "Cloning from: $FOAMAI_REPO_URL"
    if ! retry_command "git clone $FOAMAI_REPO_URL $FOAMAI_INSTALL_DIR" 3 10; then
        log_error "Failed to clone repository"
        return 1
    fi
    
    # Set ownership to ubuntu user
    if ! chown -R ubuntu:ubuntu "$FOAMAI_INSTALL_DIR"; then
        log_error "Failed to set ownership for cloned repository"
        return 1
    fi
    
    # Verify repository structure
    if [[ ! -f "$FOAMAI_INSTALL_DIR/docker-compose.yml" ]]; then
        log_error "Repository appears to be invalid - missing docker-compose.yml"
        return 1
    fi
    
    log_info "Repository cloned successfully"
    return 0
}

# Create environment configuration file
create_environment_config() {
    log_info "Creating environment configuration..."
    
    local env_file="$FOAMAI_INSTALL_DIR/.env"
    
    # Get instance IP for configuration
    local instance_ip
    if ! instance_ip=$(curl -f -s --max-time 10 http://169.254.169.254/latest/meta-data/public-ipv4); then
        log_warn "Could not get instance IP, using localhost"
        instance_ip="localhost"
    fi
    
    # Create environment file
    cat > "$env_file" << EOF
# FoamAI Environment Configuration
# Generated on $(date)

# Project Configuration
COMPOSE_PROJECT_NAME=foamai
PROJECT_NAME=FoamAI
ENVIRONMENT=production

# Directory Configuration
DATA_DIR=$DATA_DIR
FOAMAI_HOME=$FOAMAI_INSTALL_DIR

# Network Configuration
API_HOST=0.0.0.0
API_PORT=8000
PARAVIEW_PORT=11111
INSTANCE_IP=$instance_ip

# GitHub Container Registry Configuration
GHCR_REGISTRY=ghcr.io
GITHUB_ORG=$GITHUB_ORG

# Docker Image Configuration
GHCR_API_URL=ghcr.io/${GITHUB_ORG}/foamai/api
GHCR_OPENFOAM_URL=ghcr.io/${GITHUB_ORG}/foamai/openfoam
GHCR_PVSERVER_URL=ghcr.io/${GITHUB_ORG}/foamai/pvserver
IMAGE_TAG=latest

# API Configuration
API_WORKERS=2
API_TIMEOUT=300
API_LOG_LEVEL=info

# OpenFOAM Configuration
OPENFOAM_VERSION=10
OPENFOAM_PARALLEL=true

# ParaView Configuration
PARAVIEW_SERVER_PORT=11111
PARAVIEW_TIMEOUT=300

# AWS Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
AWS_INSTANCE_ID=${AWS_INSTANCE_ID:-unknown}
AWS_INSTANCE_TYPE=${AWS_INSTANCE_TYPE:-unknown}

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_RETENTION_DAYS=30

# Security Configuration
FOAMAI_SECRET_KEY=$(openssl rand -base64 32)
ALLOWED_HOSTS=localhost,127.0.0.1,$instance_ip

# Performance Configuration
MEMORY_LIMIT=8G
CPU_LIMIT=4
DISK_LIMIT=50G

# Backup Configuration
BACKUP_ENABLED=true
BACKUP_RETENTION_DAYS=7
BACKUP_SCHEDULE="0 2 * * *"

# Development Configuration
DEBUG=false
ENABLE_PROFILING=false
ENABLE_METRICS=true
EOF
    
    # Set proper permissions
    if ! chown ubuntu:ubuntu "$env_file"; then
        log_error "Failed to set ownership for environment file"
        return 1
    fi
    
    if ! chmod 600 "$env_file"; then
        log_error "Failed to set permissions for environment file"
        return 1
    fi
    
    log_info "Environment configuration created successfully"
    return 0
}

# Validate repository structure
validate_repository() {
    log_info "Validating repository structure..."
    
    local required_files=(
        "docker-compose.yml"
        "src/"
        "README.md"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -e "$FOAMAI_INSTALL_DIR/$file" ]]; then
            log_error "Required file/directory missing: $file"
            return 1
        fi
    done
    
    # Check for Python packages
    if [[ -f "$FOAMAI_INSTALL_DIR/pyproject.toml" ]]; then
        log_info "Found pyproject.toml"
    elif [[ -f "$FOAMAI_INSTALL_DIR/requirements.txt" ]]; then
        log_info "Found requirements.txt"
    else
        log_warn "No Python package configuration found"
    fi
    
    # Check for Docker Compose file validity
    if ! su - ubuntu -c "cd $FOAMAI_INSTALL_DIR && docker-compose config -q"; then
        log_error "Docker Compose configuration is invalid"
        return 1
    fi
    
    log_info "Repository structure validation passed"
    return 0
}

# Setup application permissions
setup_permissions() {
    log_info "Setting up application permissions..."
    
    # Ensure ubuntu user owns everything
    if ! chown -R ubuntu:ubuntu "$FOAMAI_INSTALL_DIR"; then
        log_error "Failed to set ownership for application directory"
        return 1
    fi
    
    # Set appropriate permissions
    if ! chmod -R 755 "$FOAMAI_INSTALL_DIR"; then
        log_error "Failed to set permissions for application directory"
        return 1
    fi
    
    # Make scripts executable
    if [[ -d "$FOAMAI_INSTALL_DIR/scripts" ]]; then
        if ! chmod +x "$FOAMAI_INSTALL_DIR"/scripts/*.sh 2>/dev/null; then
            log_debug "No shell scripts found in scripts directory"
        fi
    fi
    
    # Set proper permissions for sensitive files
    if [[ -f "$FOAMAI_INSTALL_DIR/.env" ]]; then
        chmod 600 "$FOAMAI_INSTALL_DIR/.env"
    fi
    
    log_info "Application permissions set successfully"
    return 0
}

# Create application log directory
setup_logging() {
    log_info "Setting up application logging..."
    
    local log_dir="$FOAMAI_INSTALL_DIR/logs"
    
    # Create log directory
    if ! mkdir -p "$log_dir"; then
        log_error "Failed to create log directory: $log_dir"
        return 1
    fi
    
    # Set permissions
    if ! chown ubuntu:ubuntu "$log_dir"; then
        log_error "Failed to set ownership for log directory"
        return 1
    fi
    
    if ! chmod 755 "$log_dir"; then
        log_error "Failed to set permissions for log directory"
        return 1
    fi
    
    log_info "Application logging setup completed"
    return 0
}

# Create application data directories
setup_data_directories() {
    log_info "Setting up application data directories..."
    
    local data_dirs=(
        "$DATA_DIR/simulations"
        "$DATA_DIR/results"
        "$DATA_DIR/meshes"
        "$DATA_DIR/cases"
        "$DATA_DIR/temp"
        "$DATA_DIR/uploads"
        "$DATA_DIR/backups"
    )
    
    for dir in "${data_dirs[@]}"; do
        if ! mkdir -p "$dir"; then
            log_error "Failed to create data directory: $dir"
            return 1
        fi
        
        if ! chown ubuntu:ubuntu "$dir"; then
            log_error "Failed to set ownership for data directory: $dir"
            return 1
        fi
        
        if ! chmod 755 "$dir"; then
            log_error "Failed to set permissions for data directory: $dir"
            return 1
        fi
    done
    
    log_info "Application data directories created successfully"
    return 0
}

# Main function
main() {
    log_info "=== Starting Application Setup Module ==="
    
    # Setup directories
    if ! setup_directories; then
        log_error "Directory setup failed"
        return 1
    fi
    
    # Clone repository
    if ! clone_repository; then
        log_error "Repository cloning failed"
        return 1
    fi
    
    # Create environment configuration
    if ! create_environment_config; then
        log_error "Environment configuration creation failed"
        return 1
    fi
    
    # Validate repository
    if ! validate_repository; then
        log_error "Repository validation failed"
        return 1
    fi
    
    # Setup permissions
    if ! setup_permissions; then
        log_error "Permission setup failed"
        return 1
    fi
    
    # Setup logging
    if ! setup_logging; then
        log_error "Logging setup failed"
        return 1
    fi
    
    # Setup data directories
    if ! setup_data_directories; then
        log_error "Data directory setup failed"
        return 1
    fi
    
    log_info "=== Application Setup Module Completed Successfully ==="
    return 0
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 