#!/usr/bin/env bash
# System Update Module for FoamAI
# Handles system package updates and essential package installation

# Source utilities
source "$(dirname "${BASH_SOURCE[0]}")/utils.sh"

# Update system packages
update_system_packages() {
    log_info "Starting system package update..."
    
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
    
    log_info "System package update completed successfully"
    return 0
}

# Install essential packages
install_essential_packages() {
    log_info "Installing essential packages..."
    
    local essential_packages=(
        "curl"
        "wget"
        "git"
        "unzip"
        "htop"
        "tree"
        "jq"
        "ca-certificates"
        "gnupg"
        "lsb-release"
        "software-properties-common"
        "apt-transport-https"
        "util-linux"
        "parted"
        "lsof"
        "net-tools"
    )
    
    # Install packages with retry
    local package_list="${essential_packages[*]}"
    log_info "Installing packages: $package_list"
    
    if ! retry_command "DEBIAN_FRONTEND=noninteractive apt-get install -y $package_list" 3 10; then
        log_error "Failed to install essential packages"
        return 1
    fi
    
    # Verify critical packages are installed
    local critical_packages=("curl" "wget" "git" "jq")
    for pkg in "${critical_packages[@]}"; do
        if ! require_command "$pkg"; then
            log_error "Critical package not available after installation: $pkg"
            return 1
        fi
    done
    
    log_info "Essential packages installed successfully"
    return 0
}

# Get AWS metadata
get_aws_metadata() {
    log_info "Retrieving AWS metadata..."
    
    local metadata_base="http://169.254.169.254/latest/meta-data"
    
    # Check if metadata service is available
    if ! retry_command "curl -f -s --max-time 5 $metadata_base/" 3 2; then
        log_error "AWS metadata service not available"
        return 1
    fi
    
    # Get region
    if ! AWS_REGION=$(retry_command "curl -f -s --max-time 5 $metadata_base/placement/region" 3 2); then
        log_error "Failed to get AWS region"
        return 1
    fi
    
    # Get instance ID
    if ! AWS_INSTANCE_ID=$(retry_command "curl -f -s --max-time 5 $metadata_base/instance-id" 3 2); then
        log_error "Failed to get AWS instance ID"
        return 1
    fi
    
    # Get instance type
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
    
    return 0
}

# Main function
main() {
    log_info "=== Starting System Update Module ==="
    
    # Update system packages
    if ! update_system_packages; then
        log_error "System update failed"
        return 1
    fi
    
    # Install essential packages
    if ! install_essential_packages; then
        log_error "Essential package installation failed"
        return 1
    fi
    
    # Get AWS metadata
    if ! get_aws_metadata; then
        log_error "AWS metadata retrieval failed"
        return 1
    fi
    
    log_info "=== System Update Module Completed Successfully ==="
    return 0
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 