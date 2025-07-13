#!/usr/bin/env python3
"""
Comprehensive Solver Test Suite for FoamAI
Tests all available solvers across different scenarios with coarse meshes
"""

import subprocess
import sys
import time
import re
from typing import List, Dict, Any

def run_foamai_solver_test(prompt: str, test_name: str, expected_solver: str = None) -> Dict[str, Any]:
    """Run a FoamAI solver test and capture results."""
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"Prompt: {prompt}")
    print(f"Expected Solver: {expected_solver or 'Auto-detect'}")
    print(f"{'='*80}")
    
    start_time = time.time()
    
    try:
        # Add coarse mesh specification to prompt to speed up testing
        if "coarse" not in prompt.lower():
            coarse_prompt = f"{prompt} with coarse mesh"
        else:
            coarse_prompt = prompt
            
        # Run FoamAI with no user approval to test solver selection
        cmd = [
            "uv", "run", "python", "src/foamai/cli.py", 
            "solve", coarse_prompt, 
            "--verbose", 
            "--no-user-approval"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per test
        )
        
        execution_time = time.time() - start_time
        
        # Extract solver information from output
        selected_solver = extract_solver_from_output(result.stdout)
        solver_confidence = extract_solver_confidence(result.stdout)
        flow_type = extract_flow_type(result.stdout)
        analysis_type = extract_analysis_type(result.stdout)
        reynolds_number = extract_reynolds_number(result.stdout)
        geometry_type = extract_geometry_type(result.stdout)
        
        # Check for convergence
        converged = check_convergence(result.stdout)
        residuals = extract_final_residuals(result.stdout)
        
        # Check for errors
        errors = extract_errors(result.stdout, result.stderr)
        
        # Determine test result
        test_success = result.returncode == 0 and converged
        solver_match = (expected_solver is None or 
                       (selected_solver and expected_solver.lower() in selected_solver.lower()))
        
        return {
            "test_name": test_name,
            "prompt": prompt,
            "expected_solver": expected_solver,
            "selected_solver": selected_solver,
            "solver_confidence": solver_confidence,
            "solver_match": solver_match,
            "flow_type": flow_type,
            "analysis_type": analysis_type,
            "reynolds_number": reynolds_number,
            "geometry_type": geometry_type,
            "converged": converged,
            "residuals": residuals,
            "execution_time": execution_time,
            "test_success": test_success,
            "return_code": result.returncode,
            "errors": errors,
            "stdout": result.stdout if result.returncode != 0 else "",
            "stderr": result.stderr if result.returncode != 0 else ""
        }
        
    except subprocess.TimeoutExpired:
        return {
            "test_name": test_name,
            "prompt": prompt,
            "expected_solver": expected_solver,
            "selected_solver": "TIMEOUT",
            "solver_confidence": 0.0,
            "solver_match": False,
            "test_success": False,
            "execution_time": time.time() - start_time,
            "return_code": -1,
            "errors": ["Test timed out after 5 minutes"],
            "converged": False,
            "residuals": {},
            "stdout": "",
            "stderr": ""
        }
    except Exception as e:
        return {
            "test_name": test_name,
            "prompt": prompt,
            "expected_solver": expected_solver,
            "selected_solver": "ERROR",
            "solver_confidence": 0.0,
            "solver_match": False,
            "test_success": False,
            "execution_time": time.time() - start_time,
            "return_code": -1,
            "errors": [str(e)],
            "converged": False,
            "residuals": {},
            "stdout": "",
            "stderr": ""
        }

def extract_solver_from_output(stdout: str) -> str:
    """Extract selected solver from FoamAI output."""
    patterns = [
        r"Selected (\w+) solver",
        r"Solver: (\w+)",
        r"Using solver: (\w+)",
        r"Running (\w+)\.\.\."
    ]
    
    for pattern in patterns:
        match = re.search(pattern, stdout, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return "Unknown"

def extract_solver_confidence(stdout: str) -> float:
    """Extract solver selection confidence."""
    match = re.search(r"confidence: ([\d.]+)", stdout, re.IGNORECASE)
    return float(match.group(1)) if match else 0.0

def extract_flow_type(stdout: str) -> str:
    """Extract flow type from output."""
    match = re.search(r"Flow type: FlowType\.(\w+)", stdout)
    return match.group(1) if match else "Unknown"

def extract_analysis_type(stdout: str) -> str:
    """Extract analysis type from output."""
    match = re.search(r"Analysis type: AnalysisType\.(\w+)", stdout)
    return match.group(1) if match else "Unknown"

def extract_reynolds_number(stdout: str) -> float:
    """Extract Reynolds number from output."""
    match = re.search(r"Reynolds Number.*?([0-9.]+)", stdout)
    return float(match.group(1)) if match else 0.0

def extract_geometry_type(stdout: str) -> str:
    """Extract geometry type from output."""
    match = re.search(r"Geometry Type.*?GeometryType\.(\w+)", stdout)
    return match.group(1) if match else "Unknown"

def check_convergence(stdout: str) -> bool:
    """Check if simulation converged."""
    convergence_patterns = [
        r"SIMULATION COMPLETED:",
        r"Converged.*?✅ Yes",
        r"simulation completed successfully"
    ]
    
    for pattern in convergence_patterns:
        if re.search(pattern, stdout, re.IGNORECASE):
            return True
    
    return False

def extract_final_residuals(stdout: str) -> Dict[str, float]:
    """Extract final residuals from output."""
    residuals = {}
    
    # Look for residual patterns
    patterns = [
        r"(\w+) Residual.*?([0-9.e-]+)",
        r"Final residuals.*?'(\w+)': ([0-9.e-]+)"
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, stdout, re.IGNORECASE)
        for match in matches:
            try:
                field, value = match
                residuals[field] = float(value)
            except:
                pass
    
    return residuals

def extract_errors(stdout: str, stderr: str) -> List[str]:
    """Extract error messages from output."""
    errors = []
    
    error_patterns = [
        r"ERROR.*",
        r"FATAL.*",
        r"failed.*",
        r"error:.*",
        r"cannot.*",
        r"No such.*"
    ]
    
    combined_output = stdout + "\n" + stderr
    
    for pattern in error_patterns:
        matches = re.findall(pattern, combined_output, re.IGNORECASE)
        errors.extend(matches[:3])  # Limit to first 3 matches per pattern
    
    return errors

def print_comprehensive_results(results: List[Dict[str, Any]]):
    """Print comprehensive test results."""
    print(f"\n{'='*100}")
    print("COMPREHENSIVE SOLVER TEST RESULTS")
    print(f"{'='*100}")
    
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r["test_success"])
    converged_tests = sum(1 for r in results if r["converged"])
    solver_matches = sum(1 for r in results if r["solver_match"])
    
    print(f"Total Tests: {total_tests}")
    print(f"Successful Tests: {successful_tests}/{total_tests} ({successful_tests/total_tests*100:.1f}%)")
    print(f"Converged Simulations: {converged_tests}/{total_tests} ({converged_tests/total_tests*100:.1f}%)")
    print(f"Correct Solver Selection: {solver_matches}/{total_tests} ({solver_matches/total_tests*100:.1f}%)")
    
    print(f"\n{'='*100}")
    print("DETAILED RESULTS:")
    print(f"{'='*100}")
    
    # Print summary table
    print(f"{'Test Name':<25} {'Solver':<12} {'Expected':<12} {'Conv':<6} {'Time':<6} {'Status':<10}")
    print("-" * 95)
    
    for result in results:
        solver = result["selected_solver"][:11] if result["selected_solver"] else "Unknown"
        expected = result["expected_solver"][:11] if result["expected_solver"] else "Auto"
        converged = "✅ YES" if result["converged"] else "❌ NO"
        time_str = f"{result['execution_time']:.1f}s"
        status = "SUCCESS" if result["test_success"] else "FAILED"
        
        print(f"{result['test_name']:<25} {solver:<12} {expected:<12} {converged:<6} {time_str:<6} {status:<10}")
    
    # Print solver distribution
    print(f"\n{'='*100}")
    print("SOLVER DISTRIBUTION:")
    print(f"{'='*100}")
    
    solver_counts = {}
    for result in results:
        solver = result["selected_solver"]
        if solver not in solver_counts:
            solver_counts[solver] = 0
        solver_counts[solver] += 1
    
    for solver, count in sorted(solver_counts.items()):
        percentage = count / total_tests * 100
        print(f"{solver:<20}: {count:>3} tests ({percentage:>5.1f}%)")
    
    # Print failed tests details
    failed_tests = [r for r in results if not r["test_success"]]
    if failed_tests:
        print(f"\n{'='*100}")
        print("FAILED TESTS - DETAILED INFORMATION:")
        print(f"{'='*100}")
        
        for result in failed_tests:
            print(f"\n❌ {result['test_name']}")
            print(f"   Prompt: {result['prompt']}")
            print(f"   Expected: {result['expected_solver']}")
            print(f"   Selected: {result['selected_solver']}")
            print(f"   Return Code: {result['return_code']}")
            print(f"   Converged: {result['converged']}")
            if result["errors"]:
                print(f"   Errors:")
                for error in result["errors"][:3]:  # Show first 3 errors
                    print(f"     - {error}")

def main():
    """Run comprehensive solver tests."""
    print("Starting Comprehensive Solver Test Suite for FoamAI")
    print("Testing all available solvers with coarse meshes for fast execution")
    
    # Define comprehensive test cases covering different solver scenarios
    test_cases = [
        # INCOMPRESSIBLE STEADY FLOWS (simpleFoam expected)
        {
            "name": "Steady Cylinder",
            "prompt": "Steady flow around cylinder at Re 100 with coarse mesh",
            "expected": "simpleFoam"
        },
        {
            "name": "Steady Sphere",
            "prompt": "Steady state flow around sphere at Re 50 with coarse mesh",
            "expected": "simpleFoam"
        },
        {
            "name": "Steady Pipe",
            "prompt": "Steady flow through pipe at Re 500 with coarse mesh",
            "expected": "simpleFoam"
        },
        
        # INCOMPRESSIBLE UNSTEADY FLOWS (pimpleFoam expected)
        {
            "name": "Unsteady Cylinder",
            "prompt": "Transient flow around cylinder at Re 200 with coarse mesh",
            "expected": "pimpleFoam"
        },
        {
            "name": "Vortex Shedding",
            "prompt": "Flow around cylinder at Re 1000 with coarse mesh",
            "expected": "pimpleFoam"
        },
        {
            "name": "Unsteady Airfoil",
            "prompt": "Unsteady flow around airfoil at Re 5000 with coarse mesh",
            "expected": "pimpleFoam"
        },
        
        # TURBULENT FLOWS (k-epsilon/k-omega expected)
        {
            "name": "Turbulent Cylinder",
            "prompt": "Turbulent flow around cylinder at Re 50000 with coarse mesh",
            "expected": "simpleFoam"  # or k-epsilon variant
        },
        {
            "name": "Turbulent Pipe",
            "prompt": "Turbulent flow through pipe at Re 10000 with coarse mesh",
            "expected": "simpleFoam"
        },
        {
            "name": "Turbulent Channel",
            "prompt": "Turbulent flow through channel at Re 20000 with coarse mesh",
            "expected": "simpleFoam"
        },
        
        # COMPRESSIBLE FLOWS (sonicFoam/rhoCentralFoam expected)
        {
            "name": "Supersonic Flow",
            "prompt": "Supersonic flow around sphere at Mach 2.0 with coarse mesh",
            "expected": "rhoCentralFoam"
        },
        {
            "name": "Transonic Airfoil",
            "prompt": "Transonic flow around airfoil at Mach 0.8 with coarse mesh",
            "expected": "rhoCentralFoam"
        },
        {
            "name": "Nozzle Flow",
            "prompt": "Flow through converging-diverging nozzle at Mach 1.5 with coarse mesh",
            "expected": "rhoCentralFoam"
        },
        
        # HEAT TRANSFER (buoyantSimpleFoam/buoyantPimpleFoam expected)
        {
            "name": "Natural Convection",
            "prompt": "Natural convection around heated cylinder with coarse mesh",
            "expected": "buoyantSimpleFoam"
        },
        {
            "name": "Mixed Convection",
            "prompt": "Mixed convection in heated channel at Re 1000 with coarse mesh",
            "expected": "buoyantPimpleFoam"
        },
        
        # MULTIPHASE FLOWS (interFoam/multiphaseEulerFoam expected)
        {
            "name": "Two Phase Flow",
            "prompt": "Two-phase flow of water and air in pipe with coarse mesh",
            "expected": "interFoam"
        },
        {
            "name": "Free Surface",
            "prompt": "Free surface flow around obstacle with water and air with coarse mesh",
            "expected": "interFoam"
        },
        
        # SPECIAL CASES
        {
            "name": "Low Reynolds",
            "prompt": "Creeping flow around sphere at Re 0.1 with coarse mesh",
            "expected": "simpleFoam"
        },
        {
            "name": "High Speed Flow",
            "prompt": "High speed flow around cone at Mach 3.0 with coarse mesh",
            "expected": "rhoCentralFoam"
        },
        {
            "name": "Reactive Flow",
            "prompt": "Combustion in chamber with methane and air with coarse mesh",
            "expected": "reactingFoam"
        },
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nRunning test {i}/{len(test_cases)}: {test_case['name']}")
        result = run_foamai_solver_test(
            test_case["prompt"], 
            test_case["name"], 
            test_case["expected"]
        )
        results.append(result)
        
        # Brief pause between tests
        time.sleep(2)
    
    # Print comprehensive results
    print_comprehensive_results(results)
    
    # Return overall success status
    failed_tests = [r for r in results if not r["test_success"]]
    if not failed_tests:
        print(f"\n🎉 ALL SOLVER TESTS PASSED! 🎉")
        return 0
    else:
        print(f"\n⚠️  {len(failed_tests)} SOLVER TESTS FAILED")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 