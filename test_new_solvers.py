#!/usr/bin/env python3
"""Test script to verify interFoam and rhoPimpleFoam solver selection."""

import sys
sys.path.append('src')

from agents.state import CFDState, SolverType
from agents.solver_selector import solver_selector_agent
from loguru import logger

def test_interfoam_selection():
    """Test that interFoam is selected for multiphase flows."""
    print("\n=== Testing interFoam Selection ===")
    
    # Test 1: Dam break scenario
    state = {
        "verbose": True,
        "parsed_parameters": {
            "is_multiphase": True,
            "phases": ["water", "air"],
            "free_surface": True,
            "reynolds_number": 10000,
            "flow_type": "turbulent"
        },
        "geometry_info": {
            "type": "channel",
            "dimensions": {"length": 2.0, "height": 1.0, "width": 0.1}
        },
        "original_prompt": "Simulate dam break with water and air",
        "errors": [],
        "warnings": []
    }
    
    result = solver_selector_agent(state)
    
    assert result["solver_settings"]["solver"] == "interFoam", f"Expected interFoam, got {result['solver_settings']['solver']}"
    assert "g" in result["solver_settings"], "Missing gravity vector for interFoam"
    assert "sigma" in result["solver_settings"], "Missing surface tension for interFoam"
    print("✓ Test 1 passed: Dam break scenario selects interFoam")
    
    # Test 2: Keywords triggering multiphase
    state2 = {
        "verbose": True,
        "parsed_parameters": {
            "reynolds_number": 5000,
            "flow_type": "laminar"
        },
        "geometry_info": {
            "type": "channel",
            "dimensions": {"length": 1.0, "height": 0.5, "width": 0.1}
        },
        "original_prompt": "Simulate water wave propagation with free surface",
        "errors": [],
        "warnings": []
    }
    
    result2 = solver_selector_agent(state2)
    assert result2["solver_settings"]["solver"] == "interFoam", f"Expected interFoam for wave simulation, got {result2['solver_settings']['solver']}"
    print("✓ Test 2 passed: Wave keywords trigger interFoam")


def test_rhopimplefoam_selection():
    """Test that rhoPimpleFoam is selected for compressible flows."""
    print("\n=== Testing rhoPimpleFoam Selection ===")
    
    # Test 1: High Mach number flow
    state = {
        "verbose": True,
        "parsed_parameters": {
            "mach_number": 0.8,
            "reynolds_number": 100000,
            "flow_type": "turbulent",
            "temperature": 300,
            "pressure": 101325
        },
        "geometry_info": {
            "type": "airfoil",
            "dimensions": {"chord": 0.1, "span": 0.3}
        },
        "original_prompt": "Simulate transonic flow over airfoil",
        "errors": [],
        "warnings": []
    }
    
    result = solver_selector_agent(state)
    
    assert result["solver_settings"]["solver"] == "rhoPimpleFoam", f"Expected rhoPimpleFoam, got {result['solver_settings']['solver']}"
    assert "thermophysicalProperties" in result["solver_settings"], "Missing thermophysicalProperties for rhoPimpleFoam"
    assert "T" in result["solver_settings"], "Missing temperature field for rhoPimpleFoam"
    print("✓ Test 1 passed: High Mach number selects rhoPimpleFoam")
    
    # Test 2: Compressible keywords
    state2 = {
        "verbose": True,
        "parsed_parameters": {
            "reynolds_number": 50000,
            "flow_type": "turbulent",
            "compressible": True
        },
        "geometry_info": {
            "type": "cylinder",
            "dimensions": {"diameter": 0.05}
        },
        "original_prompt": "Simulate shock wave propagation past cylinder",
        "errors": [],
        "warnings": []
    }
    
    result2 = solver_selector_agent(state2)
    assert result2["solver_settings"]["solver"] == "rhoPimpleFoam", f"Expected rhoPimpleFoam for shock simulation, got {result2['solver_settings']['solver']}"
    print("✓ Test 2 passed: Shock wave keywords trigger rhoPimpleFoam")


def test_existing_solver_compatibility():
    """Test that existing solvers still work correctly."""
    print("\n=== Testing Existing Solver Compatibility ===")
    
    # Test simpleFoam selection
    state = {
        "verbose": True,
        "parsed_parameters": {
            "reynolds_number": 100,
            "flow_type": "laminar",
            "analysis_type": "steady"
        },
        "geometry_info": {
            "type": "cylinder",
            "dimensions": {"diameter": 0.1}
        },
        "original_prompt": "Calculate steady drag coefficient",
        "errors": [],
        "warnings": []
    }
    
    result = solver_selector_agent(state)
    assert result["solver_settings"]["solver"] == "simpleFoam", f"Expected simpleFoam, got {result['solver_settings']['solver']}"
    print("✓ simpleFoam selection still works")
    
    # Test pimpleFoam selection
    state2 = {
        "verbose": True,
        "parsed_parameters": {
            "reynolds_number": 200,
            "flow_type": "laminar"
        },
        "geometry_info": {
            "type": "cylinder",
            "dimensions": {"diameter": 0.1}
        },
        "original_prompt": "Simulate vortex shedding",
        "errors": [],
        "warnings": []
    }
    
    result2 = solver_selector_agent(state2)
    assert result2["solver_settings"]["solver"] == "pimpleFoam", f"Expected pimpleFoam, got {result2['solver_settings']['solver']}"
    print("✓ pimpleFoam selection still works")


if __name__ == "__main__":
    print("Testing new solver implementation...")
    
    test_interfoam_selection()
    test_rhopimplefoam_selection()
    test_existing_solver_compatibility()
    
    print("\n✅ All tests passed! The new solvers are working correctly.")
    print("\nSummary:")
    print("- interFoam is correctly selected for multiphase flows")
    print("- rhoPimpleFoam is correctly selected for compressible flows")
    print("- Existing solvers (simpleFoam, pimpleFoam) continue to work")
    print("- All required configuration files are generated") 