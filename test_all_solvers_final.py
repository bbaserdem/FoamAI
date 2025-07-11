#!/usr/bin/env python3
"""Final comprehensive test for all 6 OpenFOAM solvers supported by FoamAI."""

import sys
import subprocess
import json
sys.path.append('src')

from agents.state import CFDState, SolverType
from agents.solver_selector import solver_selector_agent

def test_all_solvers():
    """Test all 6 solver selection scenarios."""
    print("🧪 COMPREHENSIVE SOLVER TESTS")
    print("=" * 50)
    
    test_cases = [
        {
            "name": "simpleFoam",
            "state": {
                "verbose": False,
                "parsed_parameters": {"reynolds_number": 100, "analysis_type": "steady"},
                "geometry_info": {"type": "cylinder", "dimensions": {"diameter": 0.1}},
                "original_prompt": "Steady drag coefficient calculation",
                "errors": [], "warnings": []
            }
        },
        {
            "name": "pimpleFoam",
            "state": {
                "verbose": False,
                "parsed_parameters": {"reynolds_number": 200},
                "geometry_info": {"type": "cylinder", "dimensions": {"diameter": 0.1}},
                "original_prompt": "Vortex shedding simulation",
                "errors": [], "warnings": []
            }
        },
        {
            "name": "interFoam",
            "state": {
                "verbose": False,
                "parsed_parameters": {"is_multiphase": True, "phases": ["water", "air"]},
                "geometry_info": {"type": "channel", "dimensions": {"length": 2.0, "height": 1.0}},
                "original_prompt": "Dam break simulation with water and air",
                "errors": [], "warnings": []
            }
        },
        {
            "name": "rhoPimpleFoam",
            "state": {
                "verbose": False,
                "parsed_parameters": {"mach_number": 0.8, "compressible": True},
                "geometry_info": {"type": "airfoil", "dimensions": {"chord": 0.1}},
                "original_prompt": "Transonic flow over airfoil",
                "errors": [], "warnings": []
            }
        },
        {
            "name": "chtMultiRegionFoam",
            "state": {
                "verbose": False,
                "parsed_parameters": {"heat_transfer": True, "multi_region": True},
                "geometry_info": {"type": "channel", "dimensions": {"length": 1.0, "height": 0.1}},
                "original_prompt": "Heat exchanger with conjugate heat transfer between fluid and solid",
                "errors": [], "warnings": []
            }
        },
        {
            "name": "reactingFoam",
            "state": {
                "verbose": False,
                "parsed_parameters": {"combustion": True, "fuel": "methane"},
                "geometry_info": {"type": "channel", "dimensions": {"length": 0.5, "height": 0.1}},
                "original_prompt": "Methane combustion in turbulent flow",
                "errors": [], "warnings": []
            }
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. Testing {test_case['name']}... ", end="")
        
        try:
            result = solver_selector_agent(test_case["state"])
            selected_solver = result["solver_settings"]["solver"]
            
            if selected_solver == test_case["name"]:
                print("✅ PASS")
                results.append(True)
            else:
                print(f"❌ FAIL (got {selected_solver})")
                results.append(False)
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            results.append(False)
    
    return results

def print_summary(results):
    """Print test summary."""
    solvers = ["simpleFoam", "pimpleFoam", "interFoam", "rhoPimpleFoam", "chtMultiRegionFoam", "reactingFoam"]
    
    print("\n" + "="*60)
    print("🎉 SOLVER TEST SUMMARY")
    print("="*60)
    
    for i, (solver, passed) in enumerate(zip(solvers, results)):
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {status} {solver}")
    
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! All 6 OpenFOAM solvers working correctly!")
    else:
        print(f"\n⚠️  {total - passed} tests failed.")
    
    print("="*60)

if __name__ == "__main__":
    print("🧪 TESTING ALL 6 OPENFOAM SOLVERS")
    
    results = test_all_solvers()
    print_summary(results)
    
    sys.exit(0 if all(results) else 1) 