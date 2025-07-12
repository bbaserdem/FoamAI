#!/usr/bin/env bash
# Utility functions for FoamAI user data scripts
# Provides logging, retry logic, and validation functions

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
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] [INFO] $message${NC}" | tee -a "$LOG_FILE"
}

log_warn() {
    local message="$1"
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] [WARN] $message${NC}" | tee -a "$LOG_FILE"
}

log_error() {
    local message="$1"
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR] $message${NC}" | tee -a "$LOG_FILE"
}

log_debug() {
    local message="$1"
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] [DEBUG] $message${NC}" | tee -a "$LOG_FILE"
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

# File existence check with timeout
wait_for_file() {
    local file_path="$1"
    local timeout="${2:-60}"
    local elapsed=0
    
    log_info "Waiting for file: $file_path"
    
    while [[ $elapsed -lt $timeout ]]; do
        if [[ -f "$file_path" ]]; then
            log_info "File found: $file_path"
            return 0
        fi
        
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    log_error "File not found after $timeout seconds: $file_path"
    return 1
}

# Block device check with timeout
wait_for_block_device() {
    local device_pattern="$1"
    local timeout="${2:-120}"
    local elapsed=0
    
    log_info "Waiting for block device matching: $device_pattern"
    
    while [[ $elapsed -lt $timeout ]]; do
        for device in $device_pattern; do
            if [[ -b "$device" ]]; then
                log_info "Block device found: $device"
                echo "$device"
                return 0
            fi
        done
        
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    log_error "No block device found matching pattern: $device_pattern"
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

# Validate network endpoint
check_endpoint() {
    local endpoint="$1"
    local timeout="${2:-10}"
    
    if curl -f --max-time "$timeout" "$endpoint" &>/dev/null; then
        log_info "Endpoint accessible: $endpoint"
        return 0
    else
        log_error "Endpoint not accessible: $endpoint"
        return 1
    fi
}

# Initialize logging
init_logging() {
    # Create log directory if it doesn't exist
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Start logging
    exec 1> >(tee -a "$LOG_FILE")
    exec 2>&1
    
    log_info "=== FoamAI Startup Script Started: $(date) ==="
    log_info "Script PID: $$"
    log_info "Log file: $LOG_FILE"
}

# Clean exit handler
cleanup_and_exit() {
    local exit_code="${1:-0}"
    log_info "=== FoamAI Startup Script Finished: $(date) ==="
    
    if [[ $exit_code -eq 0 ]]; then
        log_info "Script completed successfully"
        touch /var/log/foamai-startup-complete
    else
        log_error "Script failed with exit code: $exit_code"
        touch /var/log/foamai-startup-failed
    fi
    
    exit "$exit_code"
}

# Trap handler for cleanup
trap 'cleanup_and_exit $?' EXIT INT TERM 