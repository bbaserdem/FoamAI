#!/usr/bin/env bash
# FoamAI Minimal Bootstrap Script
# Downloads and executes the full deployment script from the repository

set -e

# Configuration from Terraform template
export DATA_VOLUME_SIZE_GB="${data_volume_size_gb}"
export FILESYSTEM_TYPE="${filesystem_type}"
export MOUNT_POINT="${mount_point}"
export EBS_WAIT_TIMEOUT="${wait_timeout}"
export DEPLOYMENT_PROFILE="${deployment_profile}"

# Logging setup
LOG_FILE="/var/log/foamai-startup.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "=== FoamAI Bootstrap Script Started: $(date) ==="
echo "Configuration: Volume=$${DATA_VOLUME_SIZE_GB}GB, FS=$${FILESYSTEM_TYPE}, Mount=$${MOUNT_POINT}"

# Update system and install git
apt-get update -y
apt-get install -y git curl wget

# Clone the repository to get the deployment script
echo "Cloning FoamAI repository for deployment scripts..."
git clone https://github.com/bbaserdem/FoamAI.git /tmp/FoamAI

# Make the deployment script executable
chmod +x /tmp/FoamAI/infra/user_data.sh

# Execute the full deployment script with our configuration
echo "Executing full deployment script..."
/tmp/FoamAI/infra/user_data.sh

# Cleanup
rm -rf /tmp/FoamAI

echo "=== FoamAI Bootstrap Script Completed: $(date) ===" 