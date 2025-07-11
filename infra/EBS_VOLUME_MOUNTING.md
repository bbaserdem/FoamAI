# Robust EBS Volume Mounting for FoamAI Deployment

## Overview

This document describes the configurable hybrid approach implemented for robust EBS volume mounting in FoamAI deployments. The solution addresses common cloud deployment challenges including device name unpredictability, timing issues, and provides comprehensive fallback mechanisms.

## Problem Statement

Traditional EBS volume mounting in cloud deployments faces several challenges:

1. **Device Name Unpredictability**: AWS maps EBS volumes to different device names depending on instance type
   - Older instances: `/dev/sdf` → `/dev/xvdf`
   - Newer instances: `/dev/sdf` → `/dev/nvme1n1`
   - Inconsistent mapping across instance types and regions

2. **Timing Issues**: EBS volumes may not be immediately available when user data script runs
3. **Hard-coded Configurations**: Fixed volume sizes and configurations limit deployment flexibility
4. **Poor Error Handling**: Scripts fail completely when volume mounting fails

## Solution: Configurable Hybrid Approach

### Architecture

The solution implements a three-phase approach:

1. **Dynamic Device Discovery with Waiting Logic**
2. **UUID-based Mounting After Formatting**
3. **Comprehensive Fallback Strategy**

### Key Components

#### 1. Template-based Configuration (`user_data.sh.tpl`)

Uses Terraform's `templatefile()` function to pass configuration variables:

```hcl
user_data = templatefile("${path.module}/user_data.sh.tpl", {
  data_volume_size_gb = var.data_volume_size
  filesystem_type     = var.data_volume_filesystem
  mount_point        = var.data_volume_mount_point
  wait_timeout       = var.ebs_wait_timeout
  deployment_profile = var.deployment_profile
})
```

#### 2. Multi-Strategy Device Discovery

The script attempts three discovery strategies in order:

**Strategy 1: Size-based Discovery (Most Flexible)**
- Searches for block devices matching expected size (±10% tolerance)
- Works regardless of device naming conventions
- Handles filesystem overhead calculations

**Strategy 2: AWS Metadata-based Discovery (Most Authoritative)**
- Uses AWS instance metadata to identify correct device
- Requires AWS CLI (available in later deployment phases)
- Provides definitive device mapping

**Strategy 3: Unused Device Discovery (Fallback)**
- Finds unformatted, unmounted devices
- Validates against root device to prevent conflicts
- Last resort for edge cases

#### 3. Waiting and Timeout Logic

```bash
# Configurable wait timeout with progress monitoring
WAIT_TIMEOUT="${wait_timeout}"
wait_for_volumes() {
    local start_time=$(date +%s)
    local timeout=$WAIT_TIMEOUT
    
    while [[ $(($(date +%s) - start_time)) -lt $timeout ]]; do
        if discover_data_volume &>/dev/null; then
            return 0
        fi
        sleep 5
    done
    return 1
}
```

#### 4. UUID-based Persistent Mounting

```bash
# Create UUID-based fstab entry for persistence
device_uuid=$(blkid -s UUID -o value "$device")
echo "UUID=$device_uuid $MOUNT_POINT $FILESYSTEM_TYPE defaults,nofail 0 2" >> /etc/fstab
```

## Configuration Variables

### Core Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `data_volume_size` | number | 100 | Size of EBS data volume in GB |
| `data_volume_filesystem` | string | "ext4" | Filesystem type (ext4, xfs) |
| `data_volume_mount_point` | string | "/data" | Mount point for data volume |
| `ebs_wait_timeout` | number | 300 | Timeout for volume detection (seconds) |
| `deployment_profile` | string | "standard" | Configuration profile |

### Deployment Profiles

| Profile | Description | Use Case |
|---------|-------------|----------|
| `minimal` | Small volume, basic setup | Testing, development |
| `standard` | Current default configuration | Production workloads |
| `performance` | Optimized for high-performance | Heavy CFD simulations |
| `development` | Development-specific settings | Local development |

## Usage Examples

### Basic Deployment

```hcl
# terraform.tfvars
data_volume_size = 100
data_volume_filesystem = "ext4"
deployment_profile = "standard"
```

### High-Performance Deployment

```hcl
# terraform.tfvars
data_volume_size = 500
data_volume_filesystem = "xfs"
deployment_profile = "performance"
ebs_wait_timeout = 600
```

### Development Deployment

```hcl
# terraform.tfvars
data_volume_size = 50
deployment_profile = "development"
ebs_wait_timeout = 180
```

## Fallback Mechanisms

### 1. Volume Not Found
- Creates mount point on root volume
- Logs warning but continues deployment
- Ensures Docker Compose can start

### 2. Formatting Fails
- Attempts to use existing filesystem
- Falls back to root volume if necessary
- Maintains deployment continuity

### 3. Mounting Fails
- Attempts alternative mount options
- Creates directory structure as fallback
- Logs detailed error information

## Monitoring and Debugging

### Enhanced Status Script

The deployment creates `/usr/local/bin/foamai-status` with comprehensive monitoring:

```bash
sudo foamai-status
```

Provides:
- Docker service status
- Container health
- Storage mount information
- Block device discovery results
- Recent deployment logs

### Log Analysis

Primary log location: `/var/log/foamai-startup.log`

```bash
# View deployment logs
sudo tail -f /var/log/foamai-startup.log

# Check for volume discovery issues
sudo grep -i "volume\|mount\|device" /var/log/foamai-startup.log

# Monitor filesystem status
sudo grep -i "filesystem\|uuid" /var/log/foamai-startup.log
```

## Troubleshooting

### Common Issues

**1. Volume Not Detected**
```bash
# Check available block devices
lsblk

# Verify Terraform configuration
terraform plan

# Check instance metadata
curl -s http://169.254.169.254/latest/meta-data/instance-id
```

**2. Mount Failures**
```bash
# Check device status
sudo blkid

# Verify filesystem
sudo fsck /dev/[device]

# Check mount options
cat /etc/fstab
```

**3. Size Mismatch**
```bash
# Check actual vs expected size
lsblk -o NAME,SIZE

# Verify Terraform variables
terraform console
> var.data_volume_size
```

### Recovery Procedures

**1. Remount Failed Volume**
```bash
# Identify the device
sudo lsblk

# Remount manually
sudo mount /dev/[device] /data

# Fix fstab if needed
sudo nano /etc/fstab
```

**2. Reset Volume Configuration**
```bash
# Restart deployment script section
sudo bash -c "source /var/log/foamai-startup.log && setup_data_volume"
```

## Security Considerations

### 1. Device Validation
- Verifies device size before formatting
- Prevents accidental formatting of wrong devices
- Validates mount points to prevent conflicts

### 2. Permission Management
- Sets proper ownership (ubuntu:ubuntu)
- Applies secure permissions (755)
- Maintains Docker container access

### 3. Encryption
- EBS volumes encrypted by default (Terraform configuration)
- Filesystem-level encryption available as option
- At-rest and in-transit encryption maintained

## Testing

### Unit Testing
- Volume discovery functions
- Size validation logic
- Timeout handling

### Integration Testing
- Full deployment scenarios
- Different instance types
- Various volume sizes

### Staging Validation
```bash
# Deploy staging instance
./deploy-fresh-instance.sh

# Validate volume mounting
ssh -i ./keys/foamai-key-staging ubuntu@[staging-ip] sudo foamai-status
```

## Performance Considerations

### 1. Discovery Speed
- Size-based discovery: ~1-2 seconds
- Metadata-based discovery: ~3-5 seconds
- Fallback discovery: ~5-10 seconds

### 2. Mount Time
- Fresh volume: ~30-60 seconds (formatting)
- Existing volume: ~5-10 seconds
- Fallback: ~1-2 seconds

### 3. Resource Usage
- Minimal CPU overhead
- No significant memory impact
- Network calls only for metadata

## Future Enhancements

### 1. Multi-Volume Support
- Support for multiple data volumes
- Automatic volume labeling
- Volume-specific configurations

### 2. Cloud Provider Agnostic
- Support for other cloud providers
- Generic device discovery
- Provider-specific optimizations

### 3. Advanced Monitoring
- Volume health checks
- Performance metrics
- Automatic alerts

## Conclusion

The configurable hybrid approach provides robust, flexible, and maintainable EBS volume mounting for FoamAI deployments. It addresses common cloud deployment challenges while maintaining compatibility with existing infrastructure and providing comprehensive fallback mechanisms.

The solution is designed to be:
- **Reliable**: Multiple discovery strategies with comprehensive error handling
- **Flexible**: Configurable through Terraform variables
- **Maintainable**: Well-documented with clear debugging procedures
- **Scalable**: Easily extended for additional use cases

For questions or issues, refer to the troubleshooting section or check the deployment logs for detailed error information. 