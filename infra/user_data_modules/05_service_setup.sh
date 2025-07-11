#!/usr/bin/env bash
# Service Setup Module for FoamAI
# Handles systemd services, log rotation, and monitoring setup

# Source utilities
source "$(dirname "${BASH_SOURCE[0]}")/utils.sh"

# Configuration variables
FOAMAI_INSTALL_DIR="${FOAMAI_INSTALL_DIR:-/opt/FoamAI}"
SERVICE_NAME="foamai"
SERVICE_USER="ubuntu"

# Create systemd service for FoamAI
create_systemd_service() {
    log_info "Creating systemd service for FoamAI..."
    
    local service_file="/etc/systemd/system/${SERVICE_NAME}.service"
    
    # Create the service file
    cat > "$service_file" << EOF
[Unit]
Description=FoamAI CFD Assistant Services
Documentation=https://github.com/bbaserdem/FoamAI
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$FOAMAI_INSTALL_DIR
Environment=HOME=/home/$SERVICE_USER
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
Environment=DOCKER_HOST=unix:///var/run/docker.sock

# Pre-start checks
ExecStartPre=/bin/bash -c 'if [ ! -f $FOAMAI_INSTALL_DIR/docker-compose.yml ]; then echo "docker-compose.yml not found"; exit 1; fi'
ExecStartPre=/bin/bash -c 'if ! /usr/bin/docker ps >/dev/null 2>&1; then echo "Docker daemon not accessible"; exit 1; fi'
ExecStartPre=/bin/bash -c 'if ! /usr/local/bin/docker-compose config -q; then echo "Docker Compose configuration invalid"; exit 1; fi'

# Main service commands
ExecStart=/usr/local/bin/docker-compose up -d --remove-orphans
ExecStop=/usr/local/bin/docker-compose down
ExecReload=/usr/local/bin/docker-compose restart

# Restart policy
TimeoutStartSec=300
TimeoutStopSec=60
RestartSec=30
StartLimitInterval=300
StartLimitBurst=3

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$FOAMAI_INSTALL_DIR /tmp /var/tmp
ReadOnlyPaths=/etc /usr

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF
    
    # Set proper permissions
    if ! chmod 644 "$service_file"; then
        log_error "Failed to set permissions for service file"
        return 1
    fi
    
    log_info "Systemd service file created successfully"
    return 0
}

# Create service management scripts
create_service_scripts() {
    log_info "Creating service management scripts..."
    
    # Create start script
    cat > "/usr/local/bin/foamai-start" << 'EOF'
#!/bin/bash
# FoamAI Start Script
set -e

echo "Starting FoamAI services..."
systemctl start foamai
systemctl status foamai --no-pager
echo "FoamAI services started successfully"
EOF
    
    # Create stop script
    cat > "/usr/local/bin/foamai-stop" << 'EOF'
#!/bin/bash
# FoamAI Stop Script
set -e

echo "Stopping FoamAI services..."
systemctl stop foamai
echo "FoamAI services stopped successfully"
EOF
    
    # Create restart script
    cat > "/usr/local/bin/foamai-restart" << 'EOF'
#!/bin/bash
# FoamAI Restart Script
set -e

echo "Restarting FoamAI services..."
systemctl restart foamai
systemctl status foamai --no-pager
echo "FoamAI services restarted successfully"
EOF
    
    # Make scripts executable
    chmod +x /usr/local/bin/foamai-start
    chmod +x /usr/local/bin/foamai-stop
    chmod +x /usr/local/bin/foamai-restart
    
    log_info "Service management scripts created successfully"
    return 0
}

# Setup log rotation
setup_log_rotation() {
    log_info "Setting up log rotation..."
    
    # Docker container logs
    cat > "/etc/logrotate.d/docker-containers" << 'EOF'
/var/lib/docker/containers/*/*.log {
    rotate 10
    daily
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    size 50M
    maxage 30
    postrotate
        /bin/systemctl reload docker || true
    endscript
}
EOF
    
    # FoamAI application logs
    cat > "/etc/logrotate.d/foamai" << EOF
$FOAMAI_INSTALL_DIR/logs/*.log {
    rotate 7
    daily
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $SERVICE_USER $SERVICE_USER
    size 10M
    maxage 14
    postrotate
        systemctl reload foamai || true
    endscript
}

/var/log/foamai-*.log {
    rotate 14
    daily
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    size 50M
    maxage 30
}
EOF
    
    # Test log rotation configuration
    if ! logrotate -d /etc/logrotate.d/docker-containers &>/dev/null; then
        log_error "Docker log rotation configuration test failed"
        return 1
    fi
    
    if ! logrotate -d /etc/logrotate.d/foamai &>/dev/null; then
        log_error "FoamAI log rotation configuration test failed"
        return 1
    fi
    
    log_info "Log rotation setup completed successfully"
    return 0
}

# Create status monitoring script
create_status_script() {
    log_info "Creating status monitoring script..."
    
    cat > "/usr/local/bin/foamai-status" << 'EOF'
#!/bin/bash
# FoamAI Status Check Script

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== FoamAI Status Check ===${NC}"
echo "Timestamp: $(date)"
echo ""

# System Information
echo -e "${BLUE}System Information:${NC}"
echo "  Hostname: $(hostname)"
echo "  Uptime: $(uptime -p)"
echo "  Load Average: $(cut -d' ' -f1-3 /proc/loadavg)"
echo ""

# AWS Information
echo -e "${BLUE}AWS Information:${NC}"
if INSTANCE_IP=$(curl -s --max-time 3 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null); then
    echo "  Public IP: $INSTANCE_IP"
else
    echo "  Public IP: Not available"
fi

if INSTANCE_ID=$(curl -s --max-time 3 http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null); then
    echo "  Instance ID: $INSTANCE_ID"
else
    echo "  Instance ID: Not available"
fi
echo ""

# Docker Status
echo -e "${BLUE}Docker Status:${NC}"
if systemctl is-active --quiet docker; then
    echo -e "  Docker Service: ${GREEN}Active${NC}"
    echo "  Docker Version: $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'Unknown')"
else
    echo -e "  Docker Service: ${RED}Inactive${NC}"
fi
echo ""

# FoamAI Service Status
echo -e "${BLUE}FoamAI Service Status:${NC}"
if systemctl is-active --quiet foamai; then
    echo -e "  FoamAI Service: ${GREEN}Active${NC}"
    echo "  Service Started: $(systemctl show foamai --property=ActiveEnterTimestamp --value | cut -d' ' -f2-3)"
else
    echo -e "  FoamAI Service: ${RED}Inactive${NC}"
fi
echo ""

# Container Status
echo -e "${BLUE}Container Status:${NC}"
if command -v docker >/dev/null 2>&1 && docker ps >/dev/null 2>&1; then
    echo "  Running Containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -20
else
    echo -e "  ${RED}Cannot access Docker${NC}"
fi
echo ""

# Service Endpoints
echo -e "${BLUE}Service Endpoints:${NC}"
if [[ -n "$INSTANCE_IP" ]]; then
    echo "  API: http://$INSTANCE_IP:8000"
    echo "  API Docs: http://$INSTANCE_IP:8000/docs"
    echo "  ParaView Server: $INSTANCE_IP:11111"
else
    echo "  API: http://localhost:8000"
    echo "  API Docs: http://localhost:8000/docs"
    echo "  ParaView Server: localhost:11111"
fi
echo ""

# Storage Status
echo -e "${BLUE}Storage Status:${NC}"
echo "  Root Filesystem:"
df -h / | tail -1 | awk '{print "    Usage: " $3 "/" $2 " (" $5 ")"}'

if mountpoint -q /data; then
    echo "  Data Volume:"
    df -h /data | tail -1 | awk '{print "    Usage: " $3 "/" $2 " (" $5 ")"}'
else
    echo "  Data Volume: Not mounted (using root filesystem)"
fi
echo ""

# Network Status
echo -e "${BLUE}Network Status:${NC}"
echo "  Network Interfaces:"
ip route | grep default | head -3 | awk '{print "    " $0}'

echo "  DNS Resolution:"
if nslookup google.com >/dev/null 2>&1; then
    echo -e "    DNS: ${GREEN}Working${NC}"
else
    echo -e "    DNS: ${RED}Failed${NC}"
fi
echo ""

# Service Health Checks
echo -e "${BLUE}Service Health:${NC}"
if command -v curl >/dev/null 2>&1; then
    if curl -f -s --max-time 5 http://localhost:8000/ping >/dev/null 2>&1; then
        echo -e "  API Health: ${GREEN}OK${NC}"
    else
        echo -e "  API Health: ${RED}Failed${NC}"
    fi
else
    echo "  API Health: Cannot test (curl not available)"
fi
echo ""

# Recent Logs
echo -e "${BLUE}Recent Logs:${NC}"
echo "  FoamAI Startup Log (last 5 lines):"
if [[ -f /var/log/foamai-startup.log ]]; then
    tail -n 5 /var/log/foamai-startup.log | sed 's/^/    /'
else
    echo "    No startup log found"
fi

echo ""
echo "  System Journal (last 3 entries):"
journalctl -u foamai --no-pager -n 3 --output=short 2>/dev/null | sed 's/^/    /' || echo "    No journal entries"

echo ""
echo -e "${BLUE}=== Status Check Complete ===${NC}"
EOF
    
    # Make executable
    if ! chmod +x /usr/local/bin/foamai-status; then
        log_error "Failed to make status script executable"
        return 1
    fi
    
    log_info "Status monitoring script created successfully"
    return 0
}

# Create health check script
create_health_check() {
    log_info "Creating health check script..."
    
    cat > "/usr/local/bin/foamai-health" << 'EOF'
#!/bin/bash
# FoamAI Health Check Script
# Returns 0 if healthy, 1 if unhealthy

# Check if Docker is running
if ! systemctl is-active --quiet docker; then
    echo "ERROR: Docker service is not active"
    exit 1
fi

# Check if FoamAI service is running
if ! systemctl is-active --quiet foamai; then
    echo "ERROR: FoamAI service is not active"
    exit 1
fi

# Check if API is responding
if command -v curl >/dev/null 2>&1; then
    if ! curl -f -s --max-time 10 http://localhost:8000/ping >/dev/null 2>&1; then
        echo "ERROR: API is not responding"
        exit 1
    fi
fi

# Check disk space
ROOT_USAGE=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [[ $ROOT_USAGE -gt 90 ]]; then
    echo "ERROR: Root filesystem usage is ${ROOT_USAGE}%"
    exit 1
fi

# Check if data directory is accessible
if [[ ! -d /data ]]; then
    echo "ERROR: Data directory not found"
    exit 1
fi

if [[ ! -w /data ]]; then
    echo "ERROR: Data directory not writable"
    exit 1
fi

echo "OK: All health checks passed"
exit 0
EOF
    
    # Make executable
    if ! chmod +x /usr/local/bin/foamai-health; then
        log_error "Failed to make health check script executable"
        return 1
    fi
    
    log_info "Health check script created successfully"
    return 0
}

# Setup monitoring with cron
setup_monitoring() {
    log_info "Setting up monitoring with cron..."
    
    # Create monitoring cron job
    cat > "/etc/cron.d/foamai-monitoring" << 'EOF'
# FoamAI Monitoring Jobs
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Health check every 5 minutes
*/5 * * * * root /usr/local/bin/foamai-health >> /var/log/foamai-health.log 2>&1

# Status check every hour
0 * * * * root /usr/local/bin/foamai-status >> /var/log/foamai-status.log 2>&1

# Log cleanup daily
0 3 * * * root find /var/log -name "foamai-*.log" -mtime +30 -delete 2>/dev/null || true
EOF
    
    # Set proper permissions
    if ! chmod 644 /etc/cron.d/foamai-monitoring; then
        log_error "Failed to set permissions for monitoring cron job"
        return 1
    fi
    
    log_info "Monitoring setup completed successfully"
    return 0
}

# Enable and start systemd service
enable_service() {
    log_info "Enabling and configuring FoamAI service..."
    
    # Reload systemd daemon
    if ! systemctl daemon-reload; then
        log_error "Failed to reload systemd daemon"
        return 1
    fi
    
    # Enable the service
    if ! systemctl enable "$SERVICE_NAME"; then
        log_error "Failed to enable FoamAI service"
        return 1
    fi
    
    # Don't start the service yet - that will be done by the Docker operations module
    log_info "FoamAI service enabled successfully"
    return 0
}

# Main function
main() {
    log_info "=== Starting Service Setup Module ==="
    
    # Create systemd service
    if ! create_systemd_service; then
        log_error "Systemd service creation failed"
        return 1
    fi
    
    # Create service management scripts
    if ! create_service_scripts; then
        log_error "Service script creation failed"
        return 1
    fi
    
    # Setup log rotation
    if ! setup_log_rotation; then
        log_error "Log rotation setup failed"
        return 1
    fi
    
    # Create status monitoring script
    if ! create_status_script; then
        log_error "Status script creation failed"
        return 1
    fi
    
    # Create health check script
    if ! create_health_check; then
        log_error "Health check script creation failed"
        return 1
    fi
    
    # Setup monitoring
    if ! setup_monitoring; then
        log_error "Monitoring setup failed"
        return 1
    fi
    
    # Enable systemd service
    if ! enable_service; then
        log_error "Service enablement failed"
        return 1
    fi
    
    log_info "=== Service Setup Module Completed Successfully ==="
    return 0
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 