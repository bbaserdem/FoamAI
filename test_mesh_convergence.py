#!/usr/bin/env python3
"""
Test script for mesh convergence functionality.
"""

import sys
import os
sys.path.append('src')

from agents.mesh_convergence import (
    generate_mesh_convergence_levels,
    assess_mesh_convergence,
    calculate_gci,
    calculate_richardson_extrapolation,
    recommend_optimal_mesh_level
)

def test_mesh_level_generation():
    """Test mesh level generation."""
    print("🔍 Testing mesh level generation...")
    
    base_mesh_config = {
        "cells_per_diameter": 20,
        "refinement_level": 2,
        "total_cells": 100000
    }
    
    geometry_info = {
        "domain_width": 2.0,
        "domain_height": 2.0,
        "domain_depth": 0.1,
        "characteristic_length": 0.1
    }
    
    mesh_levels = generate_mesh_convergence_levels(
        base_mesh_config, 
        geometry_info, 
        num_levels=4
    )
    
    print(f"✅ Generated {len(mesh_levels)} mesh levels:")
    for level in mesh_levels:
        print(f"  Level {level['level']}: {level['estimated_cells']:,} cells ({level['description']})")
    
    return mesh_levels

def test_convergence_assessment():
    """Test convergence assessment."""
    print("\n🔍 Testing convergence assessment...")
    
    # Mock convergence results
    convergence_results = [
        {
            "level": 0,
            "mesh_level": {"estimated_cells": 100000, "description": "Coarse"},
            "convergence_parameters": {"drag_coefficient": 1.25, "pressure_drop": 145.0}
        },
        {
            "level": 1,
            "mesh_level": {"estimated_cells": 400000, "description": "Medium"},
            "convergence_parameters": {"drag_coefficient": 1.21, "pressure_drop": 138.0}
        },
        {
            "level": 2,
            "mesh_level": {"estimated_cells": 1600000, "description": "Fine"},
            "convergence_parameters": {"drag_coefficient": 1.20, "pressure_drop": 137.0}
        },
        {
            "level": 3,
            "mesh_level": {"estimated_cells": 6400000, "description": "Very Fine"},
            "convergence_parameters": {"drag_coefficient": 1.199, "pressure_drop": 136.8}
        }
    ]
    
    target_params = ["drag_coefficient", "pressure_drop"]
    threshold = 1.0
    
    assessment = assess_mesh_convergence(convergence_results, target_params, threshold)
    
    print("✅ Convergence assessment results:")
    for param, param_assessment in assessment.items():
        status = "CONVERGED" if param_assessment["is_converged"] else "NOT CONVERGED"
        final_change = param_assessment["relative_changes"][-1] if param_assessment["relative_changes"] else 0
        gci = param_assessment.get("gci", {})
        print(f"  {param}: {status} ({final_change:.2f}% change, GCI: {gci.get('gci', 0):.2f}%)")
    
    return assessment

def test_gci_calculation():
    """Test GCI calculation."""
    print("\n🔍 Testing GCI calculation...")
    
    values = [1.25, 1.21, 1.20, 1.199]
    mesh_sizes = [100000, 400000, 1600000, 6400000]
    
    gci = calculate_gci(values, mesh_sizes)
    
    print(f"✅ GCI calculation:")
    print(f"  GCI: {gci.get('gci', 0):.2f}%")
    print(f"  Uncertainty: ±{gci.get('uncertainty', 0):.2f}%")
    print(f"  Order of convergence: {gci.get('order_of_convergence', 0):.2f}")
    
    return gci

def test_richardson_extrapolation():
    """Test Richardson extrapolation."""
    print("\n🔍 Testing Richardson extrapolation...")
    
    values = [1.25, 1.21, 1.20, 1.199]
    mesh_sizes = [100000, 400000, 1600000, 6400000]
    
    extrapolated = calculate_richardson_extrapolation(values, mesh_sizes)
    
    print(f"✅ Richardson extrapolation:")
    print(f"  Extrapolated value: {extrapolated:.4f}")
    print(f"  Finest mesh value: {values[-1]:.4f}")
    print(f"  Difference: {abs(extrapolated - values[-1]):.4f}")
    
    return extrapolated

def test_mesh_recommendation():
    """Test mesh level recommendation."""
    print("\n🔍 Testing mesh recommendation...")
    
    # Mock data from previous tests
    convergence_results = [
        {"level": 0, "mesh_level": {"estimated_cells": 100000}},
        {"level": 1, "mesh_level": {"estimated_cells": 400000}},
        {"level": 2, "mesh_level": {"estimated_cells": 1600000}},
        {"level": 3, "mesh_level": {"estimated_cells": 6400000}}
    ]
    
    assessment = {
        "drag_coefficient": {
            "is_converged": True,
            "relative_changes": [3.2, 0.8, 0.1]
        },
        "pressure_drop": {
            "is_converged": True,
            "relative_changes": [5.1, 0.7, 0.2]
        }
    }
    
    recommended_level = recommend_optimal_mesh_level(convergence_results, assessment)
    
    print(f"✅ Mesh recommendation:")
    print(f"  Recommended level: {recommended_level}")
    print(f"  Estimated cells: {convergence_results[recommended_level]['mesh_level']['estimated_cells']:,}")
    
    return recommended_level

def main():
    """Run all tests."""
    print("🚀 Starting mesh convergence tests...\n")
    
    try:
        # Run tests
        mesh_levels = test_mesh_level_generation()
        assessment = test_convergence_assessment()
        gci = test_gci_calculation()
        extrapolated = test_richardson_extrapolation()
        recommended = test_mesh_recommendation()
        
        print("\n✅ All tests completed successfully!")
        print("\n📊 Summary:")
        print(f"  Generated {len(mesh_levels)} mesh levels")
        print(f"  Assessed {len(assessment)} parameters")
        print(f"  Recommended mesh level: {recommended}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 