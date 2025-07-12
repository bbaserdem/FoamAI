#!/usr/bin/env bash
# Test script for FoamAI user data modules
# Validates module structure and basic functionality

set -e

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULES_DIR="$SCRIPT_DIR"

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Test logging
echo "=========================================="
echo "FoamAI User Data Modules Test Suite"
echo "=========================================="
echo "Test started: $(date)"
echo ""

# Test utility functions
test_utils() {
    echo "Testing utils.sh..."
    
    # Test if utils.sh can be sourced
    if source "$MODULES_DIR/utils.sh"; then
        echo "✓ utils.sh can be sourced"
        ((TESTS_PASSED++))
    else
        echo "✗ utils.sh cannot be sourced"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Test logging functions
    if declare -f log_info &>/dev/null; then
        echo "✓ log_info function exists"
        ((TESTS_PASSED++))
    else
        echo "✗ log_info function missing"
        ((TESTS_FAILED++))
    fi
    
    if declare -f retry_command &>/dev/null; then
        echo "✓ retry_command function exists"
        ((TESTS_PASSED++))
    else
        echo "✗ retry_command function missing"
        ((TESTS_FAILED++))
    fi
    
    if declare -f check_network &>/dev/null; then
        echo "✓ check_network function exists"
        ((TESTS_PASSED++))
    else
        echo "✗ check_network function missing"
        ((TESTS_FAILED++))
    fi
    
    echo ""
}

# Test individual module structure
test_module_structure() {
    local module_file="$1"
    local module_name="$(basename "$module_file")"
    
    echo "Testing $module_name..."
    
    # Check if file exists
    if [[ ! -f "$module_file" ]]; then
        echo "✗ $module_name: File does not exist"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Check if file is executable
    if [[ ! -x "$module_file" ]]; then
        echo "✗ $module_name: File is not executable"
        ((TESTS_FAILED++))
        return 1
    fi
    
    # Check if file has proper shebang
    if head -1 "$module_file" | grep -q "^#!/usr/bin/env bash"; then
        echo "✓ $module_name: Has proper shebang"
        ((TESTS_PASSED++))
    else
        echo "✗ $module_name: Missing or incorrect shebang"
        ((TESTS_FAILED++))
    fi
    
    # Check if file sources utils.sh
    if grep -q 'source.*utils\.sh' "$module_file"; then
        echo "✓ $module_name: Sources utils.sh"
        ((TESTS_PASSED++))
    else
        echo "✗ $module_name: Does not source utils.sh"
        ((TESTS_FAILED++))
    fi
    
    # Check if file has main function
    if grep -q '^main()' "$module_file"; then
        echo "✓ $module_name: Has main function"
        ((TESTS_PASSED++))
    else
        echo "✗ $module_name: Missing main function"
        ((TESTS_FAILED++))
    fi
    
    # Check if file has proper execution guard
    if grep -q 'if.*BASH_SOURCE.*main' "$module_file"; then
        echo "✓ $module_name: Has execution guard"
        ((TESTS_PASSED++))
    else
        echo "✗ $module_name: Missing execution guard"
        ((TESTS_FAILED++))
    fi
    
    echo ""
}

# Test syntax validation
test_syntax() {
    local module_file="$1"
    local module_name="$(basename "$module_file")"
    
    echo "Testing syntax of $module_name..."
    
    # Check bash syntax
    if bash -n "$module_file" 2>/dev/null; then
        echo "✓ $module_name: Syntax is valid"
        ((TESTS_PASSED++))
    else
        echo "✗ $module_name: Syntax errors detected"
        ((TESTS_FAILED++))
    fi
    
    echo ""
}

# Test function availability after sourcing
test_function_availability() {
    local module_file="$1"
    local module_name="$(basename "$module_file")"
    
    echo "Testing function availability in $module_name..."
    
    # Source the module in a subshell to avoid conflicts
    (
        source "$MODULES_DIR/utils.sh"
        source "$module_file"
        
        if declare -f main &>/dev/null; then
            echo "✓ $module_name: main function available after sourcing"
            exit 0
        else
            echo "✗ $module_name: main function not available after sourcing"
            exit 1
        fi
    )
    
    if [[ $? -eq 0 ]]; then
        ((TESTS_PASSED++))
    else
        ((TESTS_FAILED++))
    fi
    
    echo ""
}

# Main test execution
main() {
    # Test utils first
    test_utils
    
    # Test each module
    local modules=(
        "01_system_update.sh"
        "02_docker_setup.sh"
        "03_ebs_volume_setup.sh"
        "04_application_setup.sh"
        "05_service_setup.sh"
        "06_docker_operations.sh"
    )
    
    for module in "${modules[@]}"; do
        local module_file="$MODULES_DIR/$module"
        
        test_module_structure "$module_file"
        test_syntax "$module_file"
        test_function_availability "$module_file"
    done
    
    # Test main orchestrator
    echo "Testing main orchestrator..."
    local main_script="$SCRIPT_DIR/../user_data_improved.sh"
    
    if [[ -f "$main_script" ]]; then
        echo "✓ Main orchestrator exists"
        ((TESTS_PASSED++))
        
        if [[ -x "$main_script" ]]; then
            echo "✓ Main orchestrator is executable"
            ((TESTS_PASSED++))
        else
            echo "✗ Main orchestrator is not executable"
            ((TESTS_FAILED++))
        fi
        
        if bash -n "$main_script" 2>/dev/null; then
            echo "✓ Main orchestrator syntax is valid"
            ((TESTS_PASSED++))
        else
            echo "✗ Main orchestrator has syntax errors"
            ((TESTS_FAILED++))
        fi
    else
        echo "✗ Main orchestrator does not exist"
        ((TESTS_FAILED++))
    fi
    
    echo ""
    
    # Test summary
    echo "=========================================="
    echo "Test Summary"
    echo "=========================================="
    echo "Tests passed: $TESTS_PASSED"
    echo "Tests failed: $TESTS_FAILED"
    echo "Total tests: $((TESTS_PASSED + TESTS_FAILED))"
    echo ""
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo "🎉 All tests passed!"
        echo "The modular user data scripts are ready for deployment."
        return 0
    else
        echo "❌ Some tests failed."
        echo "Please fix the issues before deploying."
        return 1
    fi
}

# Run tests
main "$@" 