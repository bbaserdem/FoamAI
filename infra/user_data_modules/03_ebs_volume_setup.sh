#!/usr/bin/env bash
# EBS Volume Setup Module for FoamAI
# Handles robust EBS volume detection, formatting, and mounting

# Source utilities
source "$(dirname "${BASH_SOURCE[0]}")/utils.sh"

# Configuration variables
EXPECTED_SIZE_GB="${DATA_VOLUME_SIZE_GB:-100}"
FILESYSTEM_TYPE="${FILESYSTEM_TYPE:-ext4}"
MOUNT_POINT="${MOUNT_POINT:-/data}"
WAIT_TIMEOUT="${EBS_WAIT_TIMEOUT:-300}"

# Utility functions for EBS volume handling
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
    local min_size_gb=$((EXPECTED_SIZE_GB - (EXPECTED_SIZE_GB * 10 / 100)))  # 10% tolerance
    local max_size_gb=$((EXPECTED_SIZE_GB + (EXPECTED_SIZE_GB * 10 / 100)))
    
    log_debug "Device $device: size=${size_gb}GB, expected=${EXPECTED_SIZE_GB}GB, range=${min_size_gb}-${max_size_gb}GB"
    [[ $size_gb -ge $min_size_gb && $size_gb -le $max_size_gb ]]
}

# Strategy 1: Size-based discovery (most flexible)
find_data_volume_by_size() {
    log_info "Strategy 1: Searching for data volume by size (${EXPECTED_SIZE_GB}GB)"
    
    # Common device patterns for different instance types
    local device_patterns=(
        "/dev/nvme*n1"    # Nitro instances
        "/dev/xvd*"       # Xen instances
        "/dev/sd*"        # Older instances
        "/dev/nvme*"      # Any nvme device
    )
    
    for pattern in "${device_patterns[@]}"; do
        for device in $pattern; do
            if [[ -b "$device" ]] && ! is_mounted "$device" && is_expected_size "$device"; then
                # Additional check: ensure it's not the root device
                if ! df / | grep -q "$device"; then
                    log_info "Found data volume by size: $device ($(get_device_size_gb "$device")GB)"
                    echo "$device"
                    return 0
                fi
            fi
        done
    done
    
    log_warn "No data volume found by size matching ${EXPECTED_SIZE_GB}GB"
    return 1
}

# Strategy 2: AWS metadata-based discovery (most authoritative)
find_data_volume_by_metadata() {
    log_info "Strategy 2: Searching for data volume using AWS metadata"
    
    # Get instance ID
    local instance_id
    if ! instance_id=$(curl -f -s --max-time 5 http://169.254.169.254/latest/meta-data/instance-id); then
        log_warn "Could not get instance ID from metadata"
        return 1
    fi
    
    # Try to use AWS CLI if available
    if ! command -v aws &> /dev/null; then
        log_info "AWS CLI not available for metadata strategy"
        return 1
    fi
    
    # Get volumes attached to this instance
    local volumes
    if ! volumes=$(aws ec2 describe-volumes --filters "Name=attachment.instance-id,Values=$instance_id" --query 'Volumes[].Attachments[].Device' --output text 2>/dev/null); then
        log_warn "Could not query volumes via AWS CLI"
        return 1
    fi
    
    # Find the non-root volume
    for device in $volumes; do
        # Convert AWS device name to actual device name
        local actual_device
        case "$device" in
            /dev/sdf) actual_device="/dev/nvme1n1" ;;  # Common mapping
            /dev/xvdf) actual_device="/dev/xvdf" ;;
            *) actual_device="$device" ;;
        esac
        
        if [[ -b "$actual_device" ]] && ! is_mounted "$actual_device" && is_expected_size "$actual_device"; then
            log_info "Found data volume via metadata: $actual_device ($(get_device_size_gb "$actual_device")GB)"
            echo "$actual_device"
            return 0
        fi
    done
    
    log_warn "No suitable data volume found via metadata"
    return 1
}

# Strategy 3: Unused device discovery (fallback)
find_unused_device() {
    log_info "Strategy 3: Searching for unused devices"
    
    local device_patterns=(
        "/dev/nvme*n1"
        "/dev/xvd*"
        "/dev/sd*"
    )
    
    for pattern in "${device_patterns[@]}"; do
        for device in $pattern; do
            if [[ -b "$device" ]] && ! is_mounted "$device" && ! has_filesystem "$device"; then
                # Additional check: ensure it's not the root device
                if ! df / | grep -q "$device"; then
                    log_info "Found unused device: $device ($(get_device_size_gb "$device")GB)"
                    echo "$device"
                    return 0
                fi
            fi
        done
    done
    
    log_warn "No unused devices found"
    return 1
}

# Main data volume discovery function
discover_data_volume() {
    log_info "Starting data volume discovery process"
    
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
    
    log_error "All discovery strategies failed"
    return 1
}

# Wait for EBS volumes to be attached
wait_for_volumes() {
    log_info "Waiting for EBS volumes to be attached (timeout: ${WAIT_TIMEOUT}s)"
    
    local start_time=$(date +%s)
    
    while [[ $(($(date +%s) - start_time)) -lt $WAIT_TIMEOUT ]]; do
        # Check if we can discover any data volume
        if discover_data_volume &>/dev/null; then
            log_info "Data volume detected after $(($(date +%s) - start_time)) seconds"
            return 0
        fi
        
        log_debug "Waiting for volumes... ($(($(date +%s) - start_time))/${WAIT_TIMEOUT}s)"
        sleep 5
    done
    
    log_warn "Volume detection timed out after ${WAIT_TIMEOUT} seconds"
    return 1
}

# Format device with filesystem
format_device() {
    local device="$1"
    
    log_info "Creating $FILESYSTEM_TYPE filesystem on $device"
    
    # Check if device already has a filesystem
    if has_filesystem "$device"; then
        log_info "Device $device already has a filesystem"
        return 0
    fi
    
    # Format the device
    case "$FILESYSTEM_TYPE" in
        ext4)
            if ! retry_command "mkfs.ext4 -F $device" 3 5; then
                log_error "Failed to create ext4 filesystem on $device"
                return 1
            fi
            ;;
        xfs)
            if ! retry_command "mkfs.xfs -f $device" 3 5; then
                log_error "Failed to create xfs filesystem on $device"
                return 1
            fi
            ;;
        *)
            log_error "Unsupported filesystem type: $FILESYSTEM_TYPE"
            return 1
            ;;
    esac
    
    log_info "Filesystem created successfully on $device"
    return 0
}

# Mount device
mount_device() {
    local device="$1"
    
    log_info "Mounting $device to $MOUNT_POINT"
    
    # Create mount point
    if ! mkdir -p "$MOUNT_POINT"; then
        log_error "Failed to create mount point: $MOUNT_POINT"
        return 1
    fi
    
    # Mount the device
    if ! retry_command "mount $device $MOUNT_POINT" 3 5; then
        log_error "Failed to mount $device to $MOUNT_POINT"
        return 1
    fi
    
    # Verify the mount
    if ! df "$MOUNT_POINT" | grep -q "$device"; then
        log_error "Mount verification failed for $device"
        return 1
    fi
    
    log_info "Successfully mounted $device to $MOUNT_POINT"
    return 0
}

# Setup persistent mounting via fstab
setup_persistent_mount() {
    local device="$1"
    
    log_info "Setting up persistent mount for $device"
    
    # Get UUID for persistent mounting
    local device_uuid
    if ! device_uuid=$(blkid -s UUID -o value "$device"); then
        log_error "Could not get UUID for device $device"
        return 1
    fi
    
    log_info "Device UUID: $device_uuid"
    
    # Check if entry already exists in fstab
    if grep -q "$device_uuid" /etc/fstab; then
        log_info "fstab entry already exists for UUID $device_uuid"
        return 0
    fi
    
    # Add to fstab using UUID for persistence
    local fstab_entry="UUID=$device_uuid $MOUNT_POINT $FILESYSTEM_TYPE defaults,nofail 0 2"
    
    if ! echo "$fstab_entry" >> /etc/fstab; then
        log_error "Failed to add fstab entry"
        return 1
    fi
    
    log_info "Added fstab entry for persistent mounting"
    
    # Test the fstab entry
    if ! mount -a; then
        log_error "fstab entry test failed"
        return 1
    fi
    
    return 0
}

# Set proper permissions
setup_permissions() {
    log_info "Setting up permissions for $MOUNT_POINT"
    
    # Set ownership to ubuntu user
    if ! chown ubuntu:ubuntu "$MOUNT_POINT"; then
        log_error "Failed to set ownership for $MOUNT_POINT"
        return 1
    fi
    
    # Set permissions
    if ! chmod 755 "$MOUNT_POINT"; then
        log_error "Failed to set permissions for $MOUNT_POINT"
        return 1
    fi
    
    log_info "Permissions set successfully for $MOUNT_POINT"
    return 0
}

# Create fallback directory
create_fallback_directory() {
    log_warn "Creating fallback directory on root volume"
    
    # Create mount point
    if ! mkdir -p "$MOUNT_POINT"; then
        log_error "Failed to create fallback directory: $MOUNT_POINT"
        return 1
    fi
    
    # Set permissions
    if ! setup_permissions; then
        log_error "Failed to set permissions for fallback directory"
        return 1
    fi
    
    log_info "Fallback directory created at $MOUNT_POINT"
    return 0
}

# Main EBS volume setup function
setup_data_volume() {
    log_info "Setting up data volume..."
    
    # Wait for volumes to be available
    if ! wait_for_volumes; then
        log_warn "No additional data volume found, using root volume"
        return create_fallback_directory
    fi
    
    # Discover the data volume
    local device
    if ! device=$(discover_data_volume); then
        log_error "Failed to discover data volume"
        return create_fallback_directory
    fi
    
    log_info "Using device: $device ($(get_device_size_gb "$device")GB)"
    
    # Format the device
    if ! format_device "$device"; then
        log_error "Failed to format device $device"
        return 1
    fi
    
    # Mount the device
    if ! mount_device "$device"; then
        log_error "Failed to mount device $device"
        return 1
    fi
    
    # Setup persistent mounting
    if ! setup_persistent_mount "$device"; then
        log_error "Failed to setup persistent mounting"
        return 1
    fi
    
    # Set proper permissions
    if ! setup_permissions; then
        log_error "Failed to set permissions"
        return 1
    fi
    
    # Final verification
    log_info "Data volume setup completed successfully"
    log_info "Mount information:"
    df -h "$MOUNT_POINT"
    
    return 0
}

# Main function
main() {
    log_info "=== Starting EBS Volume Setup Module ==="
    log_info "Configuration:"
    log_info "  Expected size: ${EXPECTED_SIZE_GB}GB"
    log_info "  Filesystem: $FILESYSTEM_TYPE"
    log_info "  Mount point: $MOUNT_POINT"
    log_info "  Wait timeout: ${WAIT_TIMEOUT}s"
    
    # Setup data volume
    if ! setup_data_volume; then
        log_error "Data volume setup failed, creating fallback"
        if ! create_fallback_directory; then
            log_error "Fallback directory creation failed"
            return 1
        fi
    fi
    
    log_info "=== EBS Volume Setup Module Completed Successfully ==="
    return 0
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 