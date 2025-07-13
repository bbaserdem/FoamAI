#!/usr/bin/env python3
"""
Comprehensive Solver Test Suite for FoamAI
Tests different solver selection scenarios with coarse meshes
"""

import subprocess
import sys
import time
import re
from typing import List, Dict, Any

def run_solver_test(prompt: str, test_name: str, expected_solver: str = None) -> Dict[str, Any]:
    """Run a FoamAI solver test and capture results."""
    print(f"\n{'='*60}")
    print(f"Testing: {test_name}")
    print(f"Prompt: {prompt}")
    if expected_solver:
        print(f"Expected Solver: {expected_solver}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Add coarse mesh to prompt for fast testing
        if "coarse" not in prompt.lower():
            test_prompt = f"{prompt} with coarse mesh"
        else:
            test_prompt = prompt
            
        cmd = [
            "uv", "run", "python", "src/foamai/cli.py", 
            "solve", test_prompt, 
            "--verbose", 
            "--no-user-approval"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=240  # 4 minute timeout
        )
        
        execution_time = time.time() - start_time
        
        # Extract key information
        selected_solver = extract_solver(result.stdout)
        converged = "SIMULATION COMPLETED" in result.stdout
        test_success = result.returncode == 0 and converged
        solver_match = (expected_solver is None or 
                       (selected_solver and expected_solver.lower() in selected_solver.lower()))
        
        return {
            "test_name": test_name,
            "prompt": prompt,
            "expected_solver": expected_solver,
            "selected_solver": selected_solver,
            "solver_match": solver_match,
            "converged": converged,
            "test_success": test_success,
            "execution_time": execution_time,
            "return_code": result.returncode,
            "errors": extract_errors(result.stdout, result.stderr)
        }
        
    except subprocess.TimeoutExpired:
        return {
            "test_name": test_name,
            "test_success": False,
            "selected_solver": "TIMEOUT",
            "execution_time": time.time() - start_time,
            "errors": ["Test timed out"]
        }
    except Exception as e:
        return {
            "test_name": test_name,
            "test_success": False,
            "selected_solver": "ERROR",
            "execution_time": time.time() - start_time,
            "errors": [str(e)]
        }

def extract_solver(stdout: str) -> str:
    """Extract selected solver from output."""
    patterns = [
        r"Selected (\w+) solver",
        r"Solver: (\w+)",
        r"Running (\w+)\.\.\."
    ]
    
    for pattern in patterns:
        match = re.search(pattern, stdout, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return "Unknown"

def extract_errors(stdout: str, stderr: str) -> List[str]:
    """Extract error messages."""
    errors = []
    error_patterns = [
        r"ERROR.*",
        r"FATAL.*",
        r"failed.*"
    ]
    
    combined = stdout + stderr
    for pattern in error_patterns:
        matches = re.findall(pattern, combined, re.IGNORECASE)
        errors.extend(matches[:2])
    
    return errors

def print_results(results: List[Dict[str, Any]]):
    """Print test results."""
    print(f"\n{'='*80}")
    print("SOLVER TEST RESULTS")
    print(f"{'='*80}")
    
    total = len(results)
    successful = sum(1 for r in results if r["test_success"])
    
    print(f"Total Tests: {total}")
    print(f"Successful: {successful}/{total} ({successful/total*100:.1f}%)")
    
    print(f"\n{'Test Name':<20} {'Solver':<12} {'Expected':<12} {'Status':<10}")
    print("-" * 60)
    
    for result in results:
        solver = result.get("selected_solver", "Unknown")[:11]
        expected = result.get("expected_solver", "Auto")[:11] if result.get("expected_solver") else "Auto"
        status = "SUCCESS" if result["test_success"] else "FAILED"
        
        print(f"{result['test_name']:<20} {solver:<12} {expected:<12} {status:<10}")
    
    # Show failed tests
    failed = [r for r in results if not r["test_success"]]
    if failed:
        print(f"\nFAILED TESTS:")
        for result in failed:
            print(f"X {result['test_name']}: {result.get('errors', ['Unknown error'])[0] if result.get('errors') else 'Unknown error'}")

def main():
    """Run solver tests."""
    print("Comprehensive Solver Testing for FoamAI")
    print("Using coarse meshes for fast execution")
    
    test_cases = [
        # Steady vs Unsteady
        {
            "name": "Steady_Cylinder",
            "prompt": "Steady flow around cylinder at Re 100",
            "expected": "simpleFoam"
        },
        {
            "name": "Unsteady_Cylinder", 
            "prompt": "Unsteady flow around cylinder at Re 1000",
            "expected": "pimpleFoam"
        },
        {
            "name": "Transient_Sphere",
            "prompt": "Transient flow around sphere at Re 500",
            "expected": "pimpleFoam"
        },
        
        # Different geometries
        {
            "name": "Pipe_Flow",
            "prompt": "Flow through pipe at Re 2000",
            "expected": "pimpleFoam"
        },
        {
            "name": "Channel_Flow",
            "prompt": "Flow through channel at Re 1000", 
            "expected": "pimpleFoam"
        },
        {
            "name": "Airfoil_Flow",
            "prompt": "Flow around airfoil at Re 5000",
            "expected": "pimpleFoam"
        },
        
        # High Reynolds (turbulent)
        {
            "name": "Turbulent_Flow",
            "prompt": "Turbulent flow around cylinder at Re 50000",
            "expected": "simpleFoam"
        },
        
        # Compressible flows
        {
            "name": "Supersonic_Flow",
            "prompt": "Supersonic flow around sphere at Mach 2.0",
            "expected": "rhoCentralFoam"
        },
        {
            "name": "Nozzle_Flow",
            "prompt": "Flow through nozzle at Mach 1.5", 
            "expected": "rhoCentralFoam"
        },
        
        # Heat transfer
        {
            "name": "Heat_Transfer",
            "prompt": "Natural convection around heated cylinder",
            "expected": "buoyantSimpleFoam"
        },
        
        # Special cases
        {
            "name": "Low_Re_Flow",
            "prompt": "Creeping flow around sphere at Re 0.1",
            "expected": "simpleFoam"
        },
        {
            "name": "Two_Phase",
            "prompt": "Two-phase flow with water and air",
            "expected": "interFoam"
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nRunning test {i}/{len(test_cases)}: {test_case['name']}")
        result = run_solver_test(
            test_case["prompt"], 
            test_case["name"], 
            test_case.get("expected")
        )
        results.append(result)
        time.sleep(1)  # Brief pause
    
    print_results(results)
    
    failed_count = sum(1 for r in results if not r["test_success"])
    if failed_count == 0:
        print(f"\n🎉 ALL SOLVER TESTS PASSED!")
        return 0
    else:
        print(f"\n!  {failed_count} TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 