#!/usr/bin/env bash
#
# Remote Server Testing Script for FoamAI
# Tests what's actually running on the deployed server
#
# Usage: ./test-remote-server.sh [host] [key-path]

set -e

# Configuration from Terraform outputs
HOST=${1:-35.167.193.72}
KEY_PATH=${2:-~/.ssh/foamai-key}
USER="ubuntu"

echo "=========================================="
echo "FoamAI Remote Server Test"
echo "Target: $USER@$HOST"
echo "Key: $KEY_PATH"
echo "=========================================="

# Function to run SSH command
ssh_cmd() {
    local cmd="$1"
    local description="$2"
    
    echo -e "\n🔍 $description"
    echo "Command: $cmd"
    echo "----------------------------------------"
    
    if ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$USER@$HOST" "$cmd" 2>/dev/null; then
        echo "✓ Success"
    else
        echo "✗ Failed or timed out"
    fi
}

# Check if we can connect
echo -e "\n1. Testing SSH Connection"
echo "========================="
if ssh -i "$KEY_PATH" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$USER@$HOST" "echo 'SSH connection successful'" 2>/dev/null; then
    echo "✓ SSH connection working"
else
    echo "✗ SSH connection failed"
    echo "Make sure:"
    echo "  - Key file exists: $KEY_PATH"
    echo "  - Key has correct permissions: chmod 600 $KEY_PATH"
    echo "  - Security group allows SSH from your IP"
    exit 1
fi

# System information
ssh_cmd "uname -a" "System Information"
ssh_cmd "uptime" "System Uptime"
ssh_cmd "df -h" "Disk Usage"

# Docker status
echo -e "\n2. Docker Environment"
echo "===================="
ssh_cmd "docker --version" "Docker Version"
ssh_cmd "docker ps" "Running Containers"
ssh_cmd "docker images | head -10" "Docker Images"
ssh_cmd "docker-compose --version" "Docker Compose Version"

# FoamAI specific checks
echo -e "\n3. FoamAI Service Status"
echo "======================="
ssh_cmd "ls -la /opt/foamai/" "FoamAI Directory"
ssh_cmd "cat /opt/foamai/.env" "Environment Configuration"
ssh_cmd "systemctl status foamai" "FoamAI Service Status"
ssh_cmd "sudo journalctl -u foamai --no-pager -n 10" "Recent FoamAI Logs"

# Network and ports
echo -e "\n4. Network Configuration"
echo "======================="
ssh_cmd "ss -tlnp | grep -E ':8000|:11111'" "Listening Ports"
ssh_cmd "curl -s localhost:8000/ping" "Local API Test"

# Process information
echo -e "\n5. Running Processes"
echo "==================="
ssh_cmd "ps aux | grep -E 'docker|uvicorn|python' | grep -v grep" "Relevant Processes"

# Log files
echo -e "\n6. Recent Logs"
echo "============="
ssh_cmd "tail -20 /var/log/foamai-startup.log" "Startup Logs"
ssh_cmd "docker logs foamai-api --tail 10 2>/dev/null || echo 'No foamai-api container logs'" "API Container Logs"

# ECR and AWS
echo -e "\n7. AWS/ECR Status"
echo "================"
ssh_cmd "aws --version" "AWS CLI Version"
ssh_cmd "aws sts get-caller-identity" "AWS Identity"
ssh_cmd "/usr/local/bin/ecr-login" "ECR Login Test"

echo -e "\n========================================"
echo "Remote server test completed!"
echo ""
echo "💡 Manual commands you can run:"
echo "ssh -i $KEY_PATH $USER@$HOST"
echo "ssh -i $KEY_PATH $USER@$HOST 'docker ps'"
echo "ssh -i $KEY_PATH $USER@$HOST 'docker logs foamai-api'"
echo "ssh -i $KEY_PATH $USER@$HOST 'sudo systemctl restart foamai'"
echo "========================================" 