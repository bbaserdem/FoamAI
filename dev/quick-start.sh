#!/usr/bin/env bash
# FoamAI Quick Start Testing Script
# Runs the most important tests to validate your deployment setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')] INFO: $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check for container runtime (Docker command - could be native or Podman alias)
    if command -v docker &> /dev/null; then
        log "✅ Detected Docker command"
        
        # Test if docker command works
        if docker ps &> /dev/null 2>&1; then
            log "✅ Container runtime is working"
        else
            warn "Container runtime may need setup, but command exists"
        fi
    elif command -v podman &> /dev/null; then
        log "✅ Detected Podman"
        
        # Test podman command
        if ! podman ps &>/dev/null; then
            warn "Podman may need setup"
        fi
    else
        error "Neither Docker nor Podman is installed. Please install one of them first."
    fi
    
    # Check for compose command
    if ! command -v docker-compose &> /dev/null; then
        error "docker-compose is not installed. Please install it first."
    fi
    
    log "✅ Prerequisites check passed"
}

# Quick test sequence
run_quick_tests() {
    log "Running quick validation tests..."
    
    # Test 1: Deployment simulation
    info "🧪 Testing deployment logic simulation..."
    if ./simulate-deployment.sh full; then
        log "✅ Deployment simulation passed"
    else
        error "❌ Deployment simulation failed - check the output above for details"
    fi
    
    # Test 2: Local Docker setup
    info "🐳 Testing local Docker environment..."
    if ./local-test.sh setup && ./local-test.sh build; then
        log "✅ Docker setup and build passed"
    else
        error "❌ Docker setup failed"
    fi
    
    # Test 3: Service startup
    info "🚀 Testing service startup..."
    if ./local-test.sh start; then
        log "✅ Services started successfully"
        sleep 10  # Give services time to stabilize
        
        # Test 4: Basic functionality
        info "🔬 Testing basic functionality..."
        if ./local-test.sh test; then
            log "✅ All functionality tests passed"
        else
            warn "❌ Some functionality tests failed"
        fi
    else
        error "❌ Service startup failed"
    fi
    
    # Cleanup
    ./local-test.sh stop
    ./simulate-deployment.sh cleanup
    
    log "🎉 Quick tests completed!"
}

# Show results and recommendations
show_results() {
    echo ""
    echo "======================================"
    echo "    QUICK TEST RESULTS"
    echo "======================================"
    echo ""
    echo "✅ Your deployment setup is working locally!"
    echo ""
    echo "Next steps:"
    echo "1. Review any warnings above"
    echo "2. Run full test suite: ./local-test.sh test"
    echo "3. Deploy to AWS: cd ../infra && ./deploy-fresh-instance.sh"
    echo ""
    echo "If you encounter issues:"
    echo "- Check logs: ./local-test.sh logs"
    echo "- Debug individual services: ./local-test.sh start && docker-compose -f docker-compose.local.yml logs"
    echo "- Review the README.md for detailed troubleshooting"
    echo ""
    echo "======================================"
}

# Main execution
main() {
    echo "🚀 FoamAI Quick Start Testing"
    echo "This script will validate your deployment setup locally"
    echo ""
    
    check_prerequisites
    run_quick_tests
    show_results
}

main "$@" 