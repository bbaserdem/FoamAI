#!/usr/bin/env bash
# 
# FoamAI Quick Connectivity Test Script
# Tests basic external connectivity for deployment troubleshooting
#
# Usage: ./test-connectivity.sh [host]

set -e

# Configuration
HOST=${1:-localhost}
API_PORT=8000
PARAVIEW_PORT=11111
ECR_REGISTRY="843135096105.dkr.ecr.us-west-2.amazonaws.com"

echo "=========================================="
echo "FoamAI Quick Connectivity Test"
echo "Target Host: $HOST"
echo "=========================================="

# Function to test network connectivity
test_connectivity() {
    local host=$1
    local port=$2
    local description=$3
    
    echo -n "Testing $description ($host:$port)... "
    
    if timeout 5 bash -c "cat < /dev/null > /dev/tcp/$host/$port" 2>/dev/null; then
        echo "✓ SUCCESS"
        return 0
    else
        echo "✗ FAILED"
        return 1
    fi
}

# Function to test DNS resolution
test_dns() {
    local host=$1
    local description=$2
    
    echo -n "Testing DNS resolution for $description ($host)... "
    
    # Try different DNS tools in order of preference
    if command -v host >/dev/null 2>&1; then
        if host "$host" >/dev/null 2>&1; then
            echo "✓ SUCCESS"
            return 0
        fi
    elif command -v nslookup >/dev/null 2>&1; then
        if nslookup "$host" >/dev/null 2>&1; then
            echo "✓ SUCCESS"
            return 0
        fi
    elif command -v dig >/dev/null 2>&1; then
        if dig "$host" >/dev/null 2>&1; then
            echo "✓ SUCCESS"
            return 0
        fi
    else
        # Fallback: try to connect to port 80/443 as a connectivity test
        if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$host/80" 2>/dev/null || \
           timeout 3 bash -c "cat < /dev/null > /dev/tcp/$host/443" 2>/dev/null; then
            echo "✓ SUCCESS (connectivity test)"
            return 0
        fi
    fi
    
    echo "✗ FAILED"
    return 1
}

# Function to test HTTP endpoint
test_http() {
    local url=$1
    local description=$2
    
    echo -n "Testing $description ($url)... "
    
    if command -v curl >/dev/null 2>&1; then
        if curl -s --connect-timeout 5 --max-time 10 "$url" >/dev/null 2>&1; then
            echo "✓ SUCCESS"
            return 0
        else
            echo "✗ FAILED"
            return 1
        fi
    elif command -v wget >/dev/null 2>&1; then
        if wget --timeout=5 --tries=1 -q -O /dev/null "$url" 2>/dev/null; then
            echo "✓ SUCCESS"
            return 0
        else
            echo "✗ FAILED"
            return 1
        fi
    else
        echo "⚠ SKIPPED (no curl/wget)"
        return 2
    fi
}

echo ""
echo "1. DNS Resolution Tests"
echo "----------------------"

test_dns "google.com" "Internet connectivity"
test_dns "github.com" "GitHub access"
test_dns "docker.io" "Docker Hub access"
test_dns "$ECR_REGISTRY" "AWS ECR access"

if [ "$HOST" != "localhost" ]; then
    test_dns "$HOST" "Deployment host"
fi

echo ""
echo "2. Network Connectivity Tests"
echo "-----------------------------"

test_connectivity "google.com" "443" "HTTPS (google.com)"
test_connectivity "github.com" "443" "HTTPS (github.com)"
test_connectivity "docker.io" "443" "HTTPS (docker.io)"
test_connectivity "$ECR_REGISTRY" "443" "HTTPS (ECR)"

if [ "$HOST" != "localhost" ]; then
    test_connectivity "$HOST" "$API_PORT" "FastAPI service"
    test_connectivity "$HOST" "$PARAVIEW_PORT" "ParaView server"
fi

echo ""
echo "3. Service Endpoint Tests"
echo "-------------------------"

if [ "$HOST" = "localhost" ] || test_connectivity "$HOST" "$API_PORT" "API port check" >/dev/null 2>&1; then
    test_http "http://$HOST:$API_PORT/" "FastAPI root endpoint"
    test_http "http://$HOST:$API_PORT/ping" "FastAPI health check"
    test_http "http://$HOST:$API_PORT/docs" "FastAPI documentation"
else
    echo "⚠ Skipping API tests (port $API_PORT not accessible)"
fi

echo ""
echo "4. Docker/AWS CLI Tests"
echo "-----------------------"

# Test Docker
echo -n "Testing Docker daemon... "
if command -v docker >/dev/null 2>&1; then
    if docker version >/dev/null 2>&1; then
        echo "✓ SUCCESS"
    else
        echo "✗ FAILED (daemon not running)"
    fi
else
    echo "⚠ SKIPPED (Docker not installed)"
fi

# Test Docker Compose
echo -n "Testing Docker Compose... "
if command -v docker-compose >/dev/null 2>&1; then
    if docker-compose version >/dev/null 2>&1; then
        echo "✓ SUCCESS"
    else
        echo "✗ FAILED"
    fi
else
    echo "⚠ SKIPPED (Docker Compose not installed)"
fi

# Test AWS CLI
echo -n "Testing AWS CLI... "
if command -v aws >/dev/null 2>&1; then
    if aws sts get-caller-identity >/dev/null 2>&1; then
        echo "✓ SUCCESS (authenticated)"
    else
        echo "⚠ AVAILABLE (not authenticated)"
    fi
else
    echo "⚠ SKIPPED (AWS CLI not installed)"
fi

echo ""
echo "5. Container Status (if applicable)"
echo "-----------------------------------"

if [ -f "docker-compose.yml" ] && command -v docker-compose >/dev/null 2>&1; then
    echo "Docker Compose services status:"
    docker-compose ps 2>/dev/null || echo "⚠ Unable to get container status"
else
    echo "⚠ No docker-compose.yml found or Docker Compose not available"
fi

echo ""
echo "=========================================="
echo "Test completed. Check output above for any failures."
echo "==========================================" 