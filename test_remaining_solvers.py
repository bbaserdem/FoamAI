#!/usr/bin/env python3
"""Test the remaining solvers that were failing."""

import sys
sys.path.append('src')

from agents.state import CFDState, SolverType
from agents.solver_selector import solver_selector_agent

def test_chtmultiregionfoam():
    """Test chtMultiRegionFoam selection."""
    print("=== Testing chtMultiRegionFoam ===")
    
    # Test 1: Heat exchanger with conjugate heat transfer
    state = {
        "verbose": True,
        "parsed_parameters": {
            "reynolds_number": 10000,
            "flow_type": "turbulent",
            "heat_transfer": True,
            "multi_region": True,
            "temperature": 350,
            "wall_temperature": 400
        },
        "geometry_info": {
            "type": "channel",
            "dimensions": {"length": 1.0, "height": 0.1, "width": 0.1}
        },
        "original_prompt": "Heat exchanger with conjugate heat transfer between fluid and solid",
        "errors": [],
        "warnings": []
    }
    
    result = solver_selector_agent(state)
    solver_name = result["solver_settings"]["solver"]
    print(f"Selected solver: {solver_name}")
    
    if solver_name == "chtMultiRegionFoam":
        print("✓ chtMultiRegionFoam correctly selected")
        return True
    else:
        print(f"✗ Expected chtMultiRegionFoam, got {solver_name}")
        return False

def test_reactingfoam():
    """Test reactingFoam selection."""
    print("\n=== Testing reactingFoam ===")
    
    # Test 1: Combustion chamber
    state = {
        "verbose": True,
        "parsed_parameters": {
            "reynolds_number": 50000,
            "flow_type": "turbulent",
            "combustion": True,
            "fuel": "methane",
            "oxidizer": "air",
            "temperature": 1500,
            "pressure": 500000
        },
        "geometry_info": {
            "type": "channel",
            "dimensions": {"length": 0.5, "height": 0.1, "width": 0.1}
        },
        "original_prompt": "Methane combustion in turbulent flow",
        "errors": [],
        "warnings": []
    }
    
    result = solver_selector_agent(state)
    solver_name = result["solver_settings"]["solver"]
    print(f"Selected solver: {solver_name}")
    
    if solver_name == "reactingFoam":
        print("✓ reactingFoam correctly selected")
        return True
    else:
        print(f"✗ Expected reactingFoam, got {solver_name}")
        return False

if __name__ == "__main__":
    print("Testing remaining solvers...")
    
    results = []
    results.append(test_chtmultiregionfoam())
    results.append(test_reactingfoam())
    
    if all(results):
        print("\n✅ All remaining solver tests passed!")
    else:
        print(f"\n❌ Some tests failed. Passed: {sum(results)}/{len(results)}") 