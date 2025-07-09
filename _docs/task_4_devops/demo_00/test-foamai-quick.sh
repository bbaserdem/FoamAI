#!/usr/bin/env bash
#
# Quick FoamAI Service Testing Script
# Tests current functionality and provides manual testing commands
#
# Usage: ./test-foamai-quick.sh [host]

set -e

# Configuration
HOST=${1:-localhost}
API_PORT=8000
PARAVIEW_PORT=11111

echo "=========================================="
echo "FoamAI Service Quick Test"
echo "Target: $HOST:$API_PORT"
echo "=========================================="

# Function to test an endpoint
test_endpoint() {
    local url=$1
    local description=$2
    local expected_status=${3:-200}
    
    echo -n "Testing $description... "
    
    response=$(curl -s -w "%{http_code}" -o /tmp/response.txt "$url" 2>/dev/null || echo "000")
    
    if [ "$response" = "$expected_status" ]; then
        echo "✓ SUCCESS ($response)"
        if [ "$expected_status" = "200" ] && [ -s /tmp/response.txt ]; then
            echo "  Response: $(cat /tmp/response.txt)"
        fi
    else
        echo "✗ FAILED ($response)"
        [ -s /tmp/response.txt ] && echo "  Response: $(cat /tmp/response.txt)"
    fi
}

echo -e "\n1. Basic API Tests"
echo "----------------------"
test_endpoint "http://$HOST:$API_PORT/" "Root endpoint"
test_endpoint "http://$HOST:$API_PORT/ping" "Health check"
test_endpoint "http://$HOST:$API_PORT/docs" "API documentation"
test_endpoint "http://$HOST:$API_PORT/openapi.json" "OpenAPI schema"

echo -e "\n2. Infrastructure Tests"
echo "----------------------"
echo -n "Testing ParaView server port... "
if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$HOST/$PARAVIEW_PORT" 2>/dev/null; then
    echo "✓ SUCCESS (port $PARAVIEW_PORT accessible)"
else
    echo "✗ FAILED (port $PARAVIEW_PORT not accessible)"
fi

echo -e "\n3. Future CFD Endpoints (Expected to fail for now)"
echo "----------------------"
test_endpoint "http://$HOST:$API_PORT/simulation/create" "CFD simulation endpoint" 404
test_endpoint "http://$HOST:$API_PORT/openfoam/solvers" "OpenFOAM solvers endpoint" 404
test_endpoint "http://$HOST:$API_PORT/agents/interpret" "NL interpretation endpoint" 404

echo -e "\n4. Manual Testing Commands"
echo "=========================="
echo "You can test the service manually using these commands:"
echo ""
echo "# Test API endpoints:"
echo "curl http://$HOST:$API_PORT/"
echo "curl http://$HOST:$API_PORT/ping"
echo "curl -s http://$HOST:$API_PORT/openapi.json | jq '.paths'"
echo ""
echo "# View API documentation in browser:"
echo "open http://$HOST:$API_PORT/docs"
echo ""
echo "# Test ParaView server port:"
echo "nc -zv $HOST $PARAVIEW_PORT"
echo ""
echo "# Monitor API logs (if running locally):"
echo "docker logs -f foamai-api"
echo ""
echo "# Check all containers (if running locally):"
echo "docker ps | grep foamai"
echo ""
echo "# Performance test:"
echo "ab -n 100 -c 10 http://$HOST:$API_PORT/ping"

echo -e "\n5. Service Status Summary"
echo "========================="
# Quick status check
if curl -s "http://$HOST:$API_PORT/ping" | grep -q "pong"; then
    echo "🟢 FoamAI API: RUNNING"
else
    echo "🔴 FoamAI API: NOT RESPONDING"
fi

if timeout 3 bash -c "cat < /dev/null > /dev/tcp/$HOST/$PARAVIEW_PORT" 2>/dev/null; then
    echo "🟢 ParaView Server: ACCESSIBLE"
else
    echo "🔴 ParaView Server: NOT ACCESSIBLE"
fi

echo ""
echo "🔮 CFD Features: NOT YET IMPLEMENTED (Expected)"
echo "📋 Next: Implement OpenFOAM integration and natural language processing"

# Cleanup
rm -f /tmp/response.txt

echo ""
echo "=========================================="
echo "Quick test completed!"
echo "For comprehensive testing, run:"
echo "python test-foamai-service.py --host $HOST --verbose"
echo "==========================================" 