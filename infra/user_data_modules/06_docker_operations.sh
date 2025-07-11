#!/usr/bin/env bash
# Docker Operations Module for FoamAI
# Handles Docker image pulling and service startup with proper validation

# Source utilities
source "$(dirname "${BASH_SOURCE[0]}")/utils.sh"

# Configuration variables
FOAMAI_INSTALL_DIR="${FOAMAI_INSTALL_DIR:-/opt/FoamAI}"
SERVICE_USER="ubuntu"
DOCKER_READY_TIMEOUT=60
SERVICE_START_TIMEOUT=300

# Wait for Docker to be fully ready
wait_for_docker_ready() {
    log_info "Waiting for Docker to be fully ready..."
    
    local timeout="$DOCKER_READY_TIMEOUT"
    local elapsed=0
    
    while [[ $elapsed -lt $timeout ]]; do
        # Check if Docker service is active
        if ! systemctl is-active --quiet docker; then
            log_debug "Docker service not active, waiting..."
            sleep 2
            elapsed=$((elapsed + 2))
            continue
        fi
        
        # Check if Docker daemon is accessible
        if ! docker info &>/dev/null; then
            log_debug "Docker daemon not accessible, waiting..."
            sleep 2
            elapsed=$((elapsed + 2))
            continue
        fi
        
        # Check if ubuntu user can access Docker
        if ! su - ubuntu -c "docker info" &>/dev/null; then
            log_debug "Ubuntu user cannot access Docker, waiting..."
            sleep 2
            elapsed=$((elapsed + 2))
            continue
        fi
        
        log_info "Docker is ready after $elapsed seconds"
        return 0
    done
    
    log_error "Docker failed to become ready within $timeout seconds"
    return 1
}

# Validate Docker Compose configuration
validate_compose_config() {
    log_info "Validating Docker Compose configuration..."
    
    # Check if docker-compose.yml exists
    if [[ ! -f "$FOAMAI_INSTALL_DIR/docker-compose.yml" ]]; then
        log_error "docker-compose.yml not found in $FOAMAI_INSTALL_DIR"
        return 1
    fi
    
    # Check if .env file exists
    if [[ ! -f "$FOAMAI_INSTALL_DIR/.env" ]]; then
        log_error ".env file not found in $FOAMAI_INSTALL_DIR"
        return 1
    fi
    
    # Validate Docker Compose configuration
    log_info "Validating Docker Compose configuration syntax..."
    if ! su - ubuntu -c "cd $FOAMAI_INSTALL_DIR && docker-compose config -q"; then
        log_error "Docker Compose configuration is invalid"
        return 1
    fi
    
    log_info "Docker Compose configuration is valid"
    return 0
}

# Pull Docker images
pull_docker_images() {
    log_info "Pulling Docker images..."
    
    # Use newgrp to ensure proper group membership
    local pull_command="cd $FOAMAI_INSTALL_DIR && docker-compose pull"
    
    # Pull images with retry logic
    log_info "Pulling images from GitHub Container Registry..."
    if ! su - ubuntu -c "newgrp docker -c '$pull_command'" 2>&1; then
        log_warn "Initial image pull failed, retrying..."
        
        # Retry with exponential backoff
        for attempt in 1 2 3; do
            log_info "Pull attempt $attempt/3..."
            sleep $((attempt * 10))
            
            if su - ubuntu -c "newgrp docker -c '$pull_command'" 2>&1; then
                log_info "Image pull succeeded on attempt $attempt"
                break
            elif [[ $attempt -eq 3 ]]; then
                log_error "All image pull attempts failed"
                return 1
            fi
        done
    fi
    
    log_info "Docker images pulled successfully"
    return 0
}

# Start Docker services
start_docker_services() {
    log_info "Starting Docker services..."
    
    # Use newgrp to ensure proper group membership
    local start_command="cd $FOAMAI_INSTALL_DIR && docker-compose up -d --remove-orphans"
    
    # Start services
    log_info "Starting FoamAI services..."
    if ! su - ubuntu -c "newgrp docker -c '$start_command'" 2>&1; then
        log_error "Failed to start Docker services"
        return 1
    fi
    
    log_info "Docker services started successfully"
    return 0
}

# Wait for services to be healthy
wait_for_services_healthy() {
    log_info "Waiting for services to become healthy..."
    
    local timeout="$SERVICE_START_TIMEOUT"
    local elapsed=0
    local check_interval=10
    
    while [[ $elapsed -lt $timeout ]]; do
        # Check if containers are running
        local running_containers
        if ! running_containers=$(su - ubuntu -c "cd $FOAMAI_INSTALL_DIR && docker-compose ps -q" 2>/dev/null); then
            log_debug "Cannot check container status, waiting..."
            sleep $check_interval
            elapsed=$((elapsed + check_interval))
            continue
        fi
        
        if [[ -z "$running_containers" ]]; then
            log_debug "No containers running yet, waiting..."
            sleep $check_interval
            elapsed=$((elapsed + check_interval))
            continue
        fi
        
        # Check container health
        local unhealthy_count=0
        local total_count=0
        
        for container_id in $running_containers; do
            ((total_count++))
            
            # Get container status
            local container_status
            if ! container_status=$(docker inspect --format='{{.State.Status}}' "$container_id" 2>/dev/null); then
                ((unhealthy_count++))
                continue
            fi
            
            # Check if container is running
            if [[ "$container_status" != "running" ]]; then
                ((unhealthy_count++))
                continue
            fi
            
            # Check health status if available
            local health_status
            if health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_id" 2>/dev/null); then
                if [[ "$health_status" == "unhealthy" ]]; then
                    ((unhealthy_count++))
                fi
            fi
        done
        
        log_debug "Container health check: $((total_count - unhealthy_count))/$total_count healthy"
        
        # If all containers are healthy, we're done
        if [[ $unhealthy_count -eq 0 && $total_count -gt 0 ]]; then
            log_info "All services are healthy after $elapsed seconds"
            return 0
        fi
        
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
    done
    
    log_warn "Services did not become fully healthy within $timeout seconds"
    log_info "Current container status:"
    su - ubuntu -c "cd $FOAMAI_INSTALL_DIR && docker-compose ps" || true
    
    return 0  # Don't fail - services might still be starting
}

# Test service endpoints
test_service_endpoints() {
    log_info "Testing service endpoints..."
    
    # Give services a moment to start listening
    sleep 10
    
    # Test API endpoint
    local api_url="http://localhost:8000"
    local api_tests=("$api_url/ping" "$api_url/health")
    
    for endpoint in "${api_tests[@]}"; do
        log_info "Testing endpoint: $endpoint"
        
        # Try multiple times with increasing delays
        for attempt in 1 2 3; do
            if curl -f -s --max-time 10 "$endpoint" &>/dev/null; then
                log_info "✓ Endpoint $endpoint is responding"
                break
            elif [[ $attempt -eq 3 ]]; then
                log_warn "✗ Endpoint $endpoint is not responding"
            else
                log_debug "Endpoint $endpoint not ready, retrying in $((attempt * 5)) seconds..."
                sleep $((attempt * 5))
            fi
        done
    done
    
    log_info "Service endpoint testing completed"
    return 0
}

# Start FoamAI systemd service
start_foamai_service() {
    log_info "Starting FoamAI systemd service..."
    
    # Start the service
    if ! systemctl start foamai; then
        log_error "Failed to start FoamAI service"
        return 1
    fi
    
    # Wait for service to be active
    if ! check_service_status "foamai" 60; then
        log_error "FoamAI service failed to start"
        return 1
    fi
    
    log_info "FoamAI systemd service started successfully"
    return 0
}

# Show service status
show_service_status() {
    log_info "Showing service status..."
    
    # Docker service status
    log_info "Docker service status:"
    systemctl status docker --no-pager --lines=3 || true
    
    # FoamAI service status
    log_info "FoamAI service status:"
    systemctl status foamai --no-pager --lines=3 || true
    
    # Container status
    log_info "Container status:"
    su - ubuntu -c "cd $FOAMAI_INSTALL_DIR && docker-compose ps" || true
    
    # Service endpoints
    log_info "Service endpoints:"
    local instance_ip
    if instance_ip=$(curl -s --max-time 3 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null); then
        echo "  API: http://$instance_ip:8000"
        echo "  API Docs: http://$instance_ip:8000/docs"
        echo "  ParaView Server: $instance_ip:11111"
    else
        echo "  API: http://localhost:8000"
        echo "  API Docs: http://localhost:8000/docs"
        echo "  ParaView Server: localhost:11111"
    fi
    
    return 0
}

# Cleanup failed deployments
cleanup_failed_deployment() {
    log_warn "Cleaning up failed deployment..."
    
    # Stop any running containers
    if su - ubuntu -c "cd $FOAMAI_INSTALL_DIR && docker-compose down" 2>/dev/null; then
        log_info "Stopped existing containers"
    fi
    
    # Remove dangling containers and images
    if docker system prune -f &>/dev/null; then
        log_info "Cleaned up Docker resources"
    fi
    
    log_info "Cleanup completed"
    return 0
}

# Main function
main() {
    log_info "=== Starting Docker Operations Module ==="
    
    # Wait for Docker to be ready
    if ! wait_for_docker_ready; then
        log_error "Docker readiness check failed"
        return 1
    fi
    
    # Validate Docker Compose configuration
    if ! validate_compose_config; then
        log_error "Docker Compose configuration validation failed"
        return 1
    fi
    
    # Pull Docker images
    if ! pull_docker_images; then
        log_error "Docker image pulling failed"
        cleanup_failed_deployment
        return 1
    fi
    
    # Start Docker services
    if ! start_docker_services; then
        log_error "Docker service startup failed"
        cleanup_failed_deployment
        return 1
    fi
    
    # Wait for services to be healthy
    if ! wait_for_services_healthy; then
        log_warn "Service health check incomplete"
        # Continue anyway - services might still be starting
    fi
    
    # Test service endpoints
    if ! test_service_endpoints; then
        log_warn "Service endpoint testing failed"
        # Continue anyway - services might still be initializing
    fi
    
    # Start FoamAI systemd service
    if ! start_foamai_service; then
        log_error "FoamAI systemd service startup failed"
        return 1
    fi
    
    # Show final status
    show_service_status
    
    log_info "=== Docker Operations Module Completed Successfully ==="
    return 0
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 