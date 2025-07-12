#!/usr/bin/env bash
# Script to migrate existing GitHub Container Registry images to include /foamai/ prefix

set -e

# Configuration
GITHUB_USERNAME="${GITHUB_USERNAME:-bbaserdem}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
REGISTRY="ghcr.io"
ORG="${GITHUB_USERNAME}"
PROJECT="foamai"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_error() {
    echo -e "${RED}[!]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[*]${NC} $1"
}

# Check if GitHub token is set
if [[ -z "${GITHUB_TOKEN}" ]]; then
    print_error "GITHUB_TOKEN environment variable is not set!"
    echo "Please set it with: export GITHUB_TOKEN=your_token_here"
    echo "You can create a token at: https://github.com/settings/tokens/new"
    echo "Required permissions: write:packages"
    exit 1
fi

# Login to GitHub Container Registry
print_status "Logging in to GitHub Container Registry..."
echo "${GITHUB_TOKEN}" | docker login ${REGISTRY} -u ${GITHUB_USERNAME} --password-stdin

if [[ $? -ne 0 ]]; then
    print_error "Failed to login to GitHub Container Registry"
    exit 1
fi

# Migrate each image
IMAGES=("api" "openfoam" "pvserver")

for image in "${IMAGES[@]}"; do
    OLD_IMAGE="${REGISTRY}/${ORG}/${image}:latest"
    NEW_IMAGE="${REGISTRY}/${ORG}/${PROJECT}/${image}:latest"
    
    print_status "Migrating ${image} image..."
    
    # Pull the existing image
    print_status "Pulling ${OLD_IMAGE}..."
    if docker pull ${OLD_IMAGE}; then
        # Tag with new name
        print_status "Tagging as ${NEW_IMAGE}..."
        docker tag ${OLD_IMAGE} ${NEW_IMAGE}
        
        # Push to new location
        print_status "Pushing ${NEW_IMAGE}..."
        if docker push ${NEW_IMAGE}; then
            print_status "Successfully migrated ${image} image!"
        else
            print_error "Failed to push ${image} to new location"
        fi
    else
        print_warning "Image ${OLD_IMAGE} not found, skipping..."
    fi
done

print_status "Migration complete!"
echo ""
print_warning "Next steps:"
echo "1. Go to https://github.com/${GITHUB_USERNAME}?tab=packages"
echo "2. Make each new package (with /foamai/ prefix) public"
echo "3. Test with: ./test-public-access.sh"
echo "4. Once confirmed working, you can delete the old packages without /foamai/" 