#!/usr/bin/env bash
# Test script to verify public access to GitHub Container Registry images

GITHUB_ORG="bbaserdem"
IMAGES=("api" "openfoam" "pvserver")

echo "Testing public access to GitHub Container Registry images..."
echo "=============================================="

for image in "${IMAGES[@]}"; do
    IMAGE_URL="ghcr.io/${GITHUB_ORG}/foamai/${image}:latest"
    echo -n "Testing ${IMAGE_URL}... "
    
    # Try to pull the image manifest without authentication
    if docker manifest inspect "${IMAGE_URL}" &>/dev/null; then
        echo "✓ PUBLIC ACCESS CONFIRMED"
    else
        echo "✗ STILL PRIVATE OR NOT FOUND"
    fi
done

echo ""
echo "If images are still private, make them public via GitHub UI."
echo "Once public, no authentication is needed for pulling." 