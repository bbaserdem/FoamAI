#!/usr/bin/env python3
"""
Test script to demonstrate the user approval feature working correctly.
This script shows how to test the user approval without full simulation.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.append('src')

from agents.user_approval import display_configuration_summary, get_user_decision, get_change_requests
from agents.state import CFDState, CFDStep

def test_user_approval_display():
    """Test the user approval display functionality."""
    
    print("="*80)
    print("TESTING USER APPROVAL DISPLAY")
    print("="*80)
    
    # Create a realistic test state
    test_state = {
        "user_prompt": "Flow around cylinder at 10 m/s",
        "parsed_parameters": {
            "flow_type": "incompressible",
            "analysis_type": "steady",
            "velocity": 10.0,
            "reynolds_number": 1000,
            "density": 1.225,
            "viscosity": 1.5e-5
        },
        "geometry_info": {
            "type": "cylinder",
            "dimensions": {"diameter": 0.1, "length": 0.01}
        },
        "mesh_config": {
            "type": "snappyHexMesh",
            "total_cells": 50000,
            "geometry_type": "cylinder",
            "dimensions": {"diameter": 0.1, "length": 0.01}
        },
        "boundary_conditions": {
            "U": {
                "boundaryField": {
                    "inlet": {"type": "fixedValue", "value": "(10 0 0)"},
                    "outlet": {"type": "zeroGradient"},
                    "walls": {"type": "noSlip"}
                }
            },
            "p": {
                "boundaryField": {
                    "inlet": {"type": "zeroGradient"},
                    "outlet": {"type": "fixedValue", "value": "0"},
                    "walls": {"type": "zeroGradient"}
                }
            }
        },
        "solver_settings": {
            "solver": "simpleFoam",
            "solver_type": "SIMPLE_FOAM",
            "controlDict": {
                "startTime": 0,
                "endTime": 100,
                "deltaT": 0.1,
                "writeInterval": 10
            },
            "turbulenceProperties": {
                "simulationType": "laminar"
            }
        },
        "case_directory": "/tmp/test_case",
        "work_directory": "/tmp",
        "simulation_results": {},
        "visualization_path": "",
        "errors": [],
        "warnings": [],
        "current_step": CFDStep.USER_APPROVAL,
        "retry_count": 0,
        "max_retries": 3,
        "error_recovery_attempts": None,
        "user_approved": False,
        "user_approval_enabled": True,
        "mesh_quality": {"quality_score": 0.85, "aspect_ratio": 1.2},
        "convergence_metrics": None,
        "verbose": True,
        "export_images": True,
        "output_format": "images"
    }
    
    try:
        # Display the configuration summary
        display_configuration_summary(test_state)
        
        # Get user decision
        print("\n" + "="*80)
        print("🎯 Now testing user decision functionality...")
        print("The user approval display should appear above.")
        print("Try entering different options to test the functionality.")
        print("="*80)
        
        decision = get_user_decision()
        print(f"\n✅ User decision: {decision}")
        
        if decision == "changes":
            changes = get_change_requests()
            print(f"✅ Change requests: {changes}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test."""
    print("This script tests the user approval feature display and interaction.")
    print("It should display the configuration review and wait for your input.")
    print("You can test different options (approve, changes, cancel).")
    print("\nPress Enter to continue...")
    input()
    
    success = test_user_approval_display()
    
    if success:
        print("\n🎉 User approval feature is working correctly!")
        print("The display should now work properly in the main CLI without interference.")
    else:
        print("\n❌ User approval test failed.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 