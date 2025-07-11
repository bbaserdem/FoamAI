#!/usr/bin/env bash
# FoamAI Fresh Deployment Script
# Creates a parallel staging instance for testing without affecting production

set -e

# Configuration
ENVIRONMENT="staging"
CONFIG_FILE="terraform.tfvars.staging"
SSH_KEY_NAME="foamai-key-staging"
TERRAFORM_STATE_SUFFIX="staging"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if terraform is installed
    if ! command -v terraform &> /dev/null; then
        error "Terraform is not installed. Please install terraform first."
    fi
    
    # Check if AWS CLI is installed and configured
    if ! command -v aws &> /dev/null; then
        error "AWS CLI is not installed. Please install AWS CLI first."
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS credentials not configured. Please run 'aws configure' first."
    fi
    
    log "Prerequisites check passed ✓"
}

# Generate SSH key pair for staging
generate_ssh_key() {
    log "Generating SSH key pair for staging environment..."
    
    # Create keys directory within the repo
    mkdir -p ./keys
    
    if [ ! -f ./keys/${SSH_KEY_NAME} ]; then
        ssh-keygen -t ed25519 -f ./keys/${SSH_KEY_NAME} -N "" -C "foamai-staging-deployment"
        chmod 600 ./keys/${SSH_KEY_NAME}
        chmod 644 ./keys/${SSH_KEY_NAME}.pub
        log "SSH key pair generated at ./keys/${SSH_KEY_NAME}"
    else
        log "SSH key pair already exists at ./keys/${SSH_KEY_NAME}"
    fi
}

# Update terraform.tfvars.staging with actual SSH key
update_config() {
    log "Updating staging configuration..."
    
    # Get the public key content from local keys directory
    SSH_PUBLIC_KEY=$(cat ./keys/${SSH_KEY_NAME}.pub)
    
    # Update the config file
    sed -i "s|public_key_content = \"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... your-email@example.com\"|public_key_content = \"$SSH_PUBLIC_KEY\"|" $CONFIG_FILE
    
    log "Configuration updated with actual SSH key"
}

# Initialize Terraform for staging
init_terraform() {
    log "Initializing Terraform for staging environment..."
    
    # Initialize terraform with a different state file
    terraform init -backend-config="key=foamai-${TERRAFORM_STATE_SUFFIX}.tfstate"
    
    log "Terraform initialized for staging environment"
}

# Plan the deployment
plan_deployment() {
    log "Planning staging deployment..."
    
    terraform plan -var-file=$CONFIG_FILE -out=staging.tfplan
    
    log "Deployment plan created. Review the output above."
    
    # Ask for confirmation
    read -p "Do you want to proceed with the deployment? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "Deployment cancelled by user."
        exit 0
    fi
}

# Apply the deployment
apply_deployment() {
    log "Applying staging deployment..."
    
    terraform apply staging.tfplan
    
    log "Staging deployment completed!"
}

# Get deployment information
get_deployment_info() {
    log "Getting deployment information..."
    
    # Get outputs from terraform
    STAGING_IP=$(terraform output -raw public_ip 2>/dev/null || echo "N/A")
    API_URL=$(terraform output -raw api_endpoint 2>/dev/null || echo "N/A")
    PARAVIEW_ENDPOINT=$(terraform output -raw paraview_endpoint 2>/dev/null || echo "N/A")
    SSH_COMMAND=$(terraform output -raw ssh_connection 2>/dev/null || echo "N/A")
    
    echo ""
    echo "======================================"
    echo "    FRESH DEPLOYMENT INFORMATION"
    echo "======================================"
    echo "Environment: $ENVIRONMENT"
    echo "Public IP: $STAGING_IP"
    echo "API Endpoint: $API_URL"
    echo "ParaView Server: $PARAVIEW_ENDPOINT"
    echo "SSH Command: $SSH_COMMAND"
    echo "======================================"
    echo ""
}

# Test the deployment
test_deployment() {
    log "Testing the fresh deployment..."
    
    if [ "$STAGING_IP" != "N/A" ]; then
        log "Waiting for services to start (60 seconds)..."
        sleep 60
        
        # Test API endpoint
        log "Testing API endpoint..."
        if curl -f -s --connect-timeout 10 --max-time 30 "http://$STAGING_IP:8000/ping" > /dev/null; then
            log "✓ API endpoint is accessible"
        else
            warn "✗ API endpoint is not yet accessible (services may still be starting)"
        fi
        
        # Test ParaView port
        log "Testing ParaView server port..."
        if timeout 10 bash -c "cat < /dev/null > /dev/tcp/$STAGING_IP/11111" 2>/dev/null; then
            log "✓ ParaView server port is accessible"
        else
            warn "✗ ParaView server port is not yet accessible (services may still be starting)"
        fi
        
        # Test SSH connectivity
        log "Testing SSH connectivity..."
        if timeout 10 ssh -i ./keys/${SSH_KEY_NAME} -o ConnectTimeout=10 -o StrictHostKeyChecking=no ubuntu@$STAGING_IP 'echo "SSH connection successful"' 2>/dev/null; then
            log "✓ SSH connection is working"
        else
            warn "✗ SSH connection failed"
        fi
    else
        warn "Could not get staging IP address. Check terraform outputs manually."
    fi
}

# Provide next steps
provide_next_steps() {
    echo ""
    echo "======================================"
    echo "           NEXT STEPS"
    echo "======================================"
    echo "1. SSH into the staging instance:"
    echo "   ssh -i ./keys/${SSH_KEY_NAME} ubuntu@$STAGING_IP"
    echo ""
    echo "2. Check service status:"
    echo "   sudo foamai-status"
    echo ""
    echo "3. View startup logs:"
    echo "   sudo tail -f /var/log/foamai-startup.log"
    echo ""
    echo "4. Test API endpoints:"
    echo "   curl -f $API_URL/ping"
    echo "   curl -f $API_URL/docs"
    echo ""
    echo "5. Compare with production:"
    echo "   curl -f http://35.167.193.72:8000/ping"
    echo ""
    echo "6. When testing is complete, clean up:"
    echo "   terraform destroy -var-file=$CONFIG_FILE"
    echo "======================================"
}

# Main execution
main() {
    log "Starting FoamAI fresh deployment process..."
    
    # Change to infra directory
    cd "$(dirname "$0")"
    
    check_prerequisites
    generate_ssh_key
    update_config
    init_terraform
    plan_deployment
    apply_deployment
    get_deployment_info
    test_deployment
    provide_next_steps
    
    log "Fresh deployment process completed successfully!"
}

# Script help
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "FoamAI Fresh Deployment Script"
    echo "Usage: $0 [options]"
    echo ""
    echo "This script creates a parallel staging instance for testing"
    echo "without affecting the production deployment."
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  --cleanup      Destroy the staging environment"
    echo ""
    echo "Prerequisites:"
    echo "  - Terraform installed"
    echo "  - AWS CLI installed and configured"
    echo "  - Proper AWS permissions"
    exit 0
fi

# Cleanup option
if [ "$1" = "--cleanup" ]; then
    log "Cleaning up staging environment..."
    terraform destroy -var-file=$CONFIG_FILE -auto-approve
    log "Staging environment destroyed."
    exit 0
fi

# Run main function
main "$@" 