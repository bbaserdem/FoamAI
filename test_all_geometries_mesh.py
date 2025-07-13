#!/usr/bin/env python3
"""
Comprehensive Mesh Generation Test for All Built-in Geometries
Tests mesh generation for all supported geometry types in FoamAI
"""

import subprocess
import sys
import time
from typing import List, Dict, Any

def run_foamai_test(prompt: str, test_name: str) -> Dict[str, Any]:
    """Run a FoamAI test and capture results."""
    print(f"\n{'='*60}")
    print(f"Testing: {test_name}")
    print(f"Prompt: {prompt}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Run FoamAI with no user approval to test mesh generation only
        cmd = [
            "uv", "run", "python", "src/foamai/cli.py", 
            "solve", prompt, 
            "--verbose", 
            "--no-user-approval"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout per test
        )
        
        execution_time = time.time() - start_time
        
        # Check if mesh generation succeeded
        mesh_success = "Generated mesh with" in result.stdout
        workflow_success = result.returncode == 0
        
        # Extract mesh info if available
        mesh_cells = "unknown"
        if "Generated mesh with" in result.stdout:
            try:
                import re
                match = re.search(r"Generated mesh with (\d+) cells", result.stdout)
                if match:
                    mesh_cells = match.group(1)
            except:
                pass
        
        return {
            "test_name": test_name,
            "prompt": prompt,
            "success": workflow_success,
            "mesh_success": mesh_success,
            "mesh_cells": mesh_cells,
            "execution_time": execution_time,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "errors": extract_errors(result.stdout, result.stderr)
        }
        
    except subprocess.TimeoutExpired:
        return {
            "test_name": test_name,
            "prompt": prompt,
            "success": False,
            "mesh_success": False,
            "mesh_cells": "timeout",
            "execution_time": time.time() - start_time,
            "return_code": -1,
            "stdout": "",
            "stderr": "",
            "errors": ["Test timed out after 120 seconds"]
        }
    except Exception as e:
        return {
            "test_name": test_name,
            "prompt": prompt,
            "success": False,
            "mesh_success": False,
            "mesh_cells": "error",
            "execution_time": time.time() - start_time,
            "return_code": -1,
            "stdout": "",
            "stderr": "",
            "errors": [str(e)]
        }

def extract_errors(stdout: str, stderr: str) -> List[str]:
    """Extract error messages from output."""
    errors = []
    
    # Look for common error patterns
    error_patterns = [
        r"ERROR.*",
        r"Mesh generation failed.*",
        r"unsupported operand type.*",
        r"TypeError.*",
        r"ValueError.*",
        r"KeyError.*",
        r"AttributeError.*"
    ]
    
    import re
    combined_output = stdout + "\n" + stderr
    
    for pattern in error_patterns:
        matches = re.findall(pattern, combined_output, re.IGNORECASE)
        errors.extend(matches[:3])  # Limit to first 3 matches per pattern
    
    return errors

def print_results_summary(results: List[Dict[str, Any]]):
    """Print a summary of all test results."""
    print(f"\n{'='*80}")
    print("COMPREHENSIVE MESH GENERATION TEST RESULTS")
    print(f"{'='*80}")
    
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r["success"])
    mesh_successful_tests = sum(1 for r in results if r["mesh_success"])
    
    print(f"Total Tests: {total_tests}")
    print(f"Overall Success: {successful_tests}/{total_tests} ({successful_tests/total_tests*100:.1f}%)")
    print(f"Mesh Generation Success: {mesh_successful_tests}/{total_tests} ({mesh_successful_tests/total_tests*100:.1f}%)")
    
    print(f"\n{'='*80}")
    print("DETAILED RESULTS:")
    print(f"{'='*80}")
    
    # Print summary table
    print(f"{'Test Name':<25} {'Mesh':<6} {'Cells':<8} {'Time':<6} {'Status':<10}")
    print("-" * 70)
    
    for result in results:
        mesh_status = "✅ PASS" if result["mesh_success"] else "❌ FAIL"
        cells_str = str(result["mesh_cells"])[:7]
        time_str = f"{result['execution_time']:.1f}s"
        overall_status = "SUCCESS" if result["success"] else "FAILED"
        
        print(f"{result['test_name']:<25} {mesh_status:<6} {cells_str:<8} {time_str:<6} {overall_status:<10}")
    
    # Print detailed failure information
    failed_tests = [r for r in results if not r["mesh_success"]]
    if failed_tests:
        print(f"\n{'='*80}")
        print("FAILED TESTS - DETAILED ERROR INFORMATION:")
        print(f"{'='*80}")
        
        for result in failed_tests:
            print(f"\n❌ {result['test_name']}")
            print(f"   Prompt: {result['prompt']}")
            print(f"   Return Code: {result['return_code']}")
            if result["errors"]:
                print(f"   Errors:")
                for error in result["errors"]:
                    print(f"     - {error}")
            else:
                print(f"   No specific errors found in output")

def main():
    """Run comprehensive mesh generation tests."""
    print("Starting Comprehensive Mesh Generation Test Suite")
    print("This will test all built-in geometry types in FoamAI")
    
    # Define test cases for each geometry type
    test_cases = [
        # CYLINDER tests
        {
            "name": "Cylinder External",
            "prompt": "Flow around cylinder at Re 1000"
        },
        {
            "name": "Cylinder High Re",
            "prompt": "Turbulent flow around cylinder at Re 100000"
        },
        {
            "name": "Cylinder Low Re",
            "prompt": "Flow around 1cm cylinder at Re 10"
        },
        
        # SPHERE tests
        {
            "name": "Sphere External",
            "prompt": "Flow around sphere at Re 1000"
        },
        {
            "name": "Sphere Turbulent",
            "prompt": "Turbulent flow around 5cm sphere at 10 m/s"
        },
        
        # CUBE tests
        {
            "name": "Cube External",
            "prompt": "Flow around cube at Re 1000"
        },
        {
            "name": "Cube Square",
            "prompt": "Flow around square obstacle at 2 m/s"
        },
        
        # AIRFOIL tests
        {
            "name": "Airfoil External",
            "prompt": "Flow around airfoil at Re 10000"
        },
        {
            "name": "NACA Airfoil",
            "prompt": "Flow around NACA 0012 airfoil at 20 m/s"
        },
        
        # PIPE tests
        {
            "name": "Pipe Internal",
            "prompt": "Flow through pipe at Re 2000"
        },
        {
            "name": "Pipe Laminar",
            "prompt": "Laminar flow through 5cm diameter pipe at 1 m/s"
        },
        
        # CHANNEL tests
        {
            "name": "Channel Flow",
            "prompt": "Flow through rectangular channel at Re 1000"
        },
        {
            "name": "Channel Turbulent",
            "prompt": "Turbulent flow through channel at 5 m/s"
        },
        
        # NOZZLE tests
        {
            "name": "Nozzle Flow",
            "prompt": "Flow through converging-diverging nozzle at 0.5 Mach"
        },
        {
            "name": "Subsonic Nozzle",
            "prompt": "Subsonic flow through nozzle with 2:1 expansion ratio"
        },
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nRunning test {i}/{len(test_cases)}: {test_case['name']}")
        result = run_foamai_test(test_case["prompt"], test_case["name"])
        results.append(result)
        
        # Brief pause between tests
        time.sleep(1)
    
    # Print comprehensive results
    print_results_summary(results)
    
    # Return overall success status
    mesh_failures = [r for r in results if not r["mesh_success"]]
    if not mesh_failures:
        print(f"\n🎉 ALL MESH GENERATION TESTS PASSED! 🎉")
        return 0
    else:
        print(f"\n⚠️  {len(mesh_failures)} MESH GENERATION TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 