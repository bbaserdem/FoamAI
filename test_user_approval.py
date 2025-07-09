#!/usr/bin/env python3
"""Test script for the user approval feature."""

import sys
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add src to path
sys.path.append('src')

from foamai.agents.orchestrator import create_initial_state, create_cfd_workflow
from foamai.agents.user_approval import user_approval_agent
from foamai.agents.state import CFDState, CFDStep

def test_user_approval_integration():
    """Test the user approval integration in the workflow."""
    
    # Test with user approval enabled
    print("Testing with user approval enabled...")
    
    state_with_approval = create_initial_state(
        user_prompt="Flow around cylinder at 10 m/s",
        verbose=True,
        user_approval_enabled=True
    )
    
    assert state_with_approval["user_approval_enabled"] == True
    assert state_with_approval["user_approved"] == False
    print("✅ Initial state with approval enabled created successfully")
    
    # Test with user approval disabled
    print("\nTesting with user approval disabled...")
    
    state_without_approval = create_initial_state(
        user_prompt="Flow around cylinder at 10 m/s",
        verbose=True,
        user_approval_enabled=False
    )
    
    assert state_without_approval["user_approval_enabled"] == False
    assert state_without_approval["user_approved"] == False
    print("✅ Initial state with approval disabled created successfully")
    
    # Test workflow creation
    print("\nTesting workflow creation...")
    
    try:
        workflow = create_cfd_workflow()
        print("✅ Workflow created successfully with user approval agent")
    except Exception as e:
        print(f"❌ Workflow creation failed: {e}")
        return False
    
    print("\n✅ All tests passed!")
    return True

def test_user_approval_agent():
    """Test the user approval agent with mock user input."""
    
    # Create a mock state with all required fields
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
            "geometry_type": "cylinder"
        },
        "boundary_conditions": {
            "U": {
                "boundaryField": {
                    "inlet": {"type": "fixedValue", "value": "(10 0 0)"},
                    "outlet": {"type": "zeroGradient"},
                    "walls": {"type": "noSlip"}
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
    
    print("Testing user approval agent...")
    
    # Test with approve decision
    print("\n1. Testing with 'approve' decision...")
    with patch('agents.user_approval.get_user_decision', return_value='approve'):
        with patch('agents.user_approval.display_configuration_summary'):
            result = user_approval_agent(test_state)
            assert result["user_approved"] == True
            print("✅ Approve decision handled correctly")
    
    # Test with changes decision
    print("\n2. Testing with 'changes' decision...")
    with patch('agents.user_approval.get_user_decision', return_value='changes'):
        with patch('agents.user_approval.get_change_requests', return_value='Make mesh finer'):
            with patch('agents.user_approval.display_configuration_summary'):
                result = user_approval_agent(test_state)
                assert result["user_approved"] == False
                assert result["current_step"] == CFDStep.SOLVER_SELECTION
                print("✅ Changes decision handled correctly")
    
    # Test with cancel decision
    print("\n3. Testing with 'cancel' decision...")
    with patch('agents.user_approval.get_user_decision', return_value='cancel'):
        with patch('agents.user_approval.display_configuration_summary'):
            result = user_approval_agent(test_state)
            assert result["user_approved"] == False
            assert result["current_step"] == CFDStep.ERROR
            print("✅ Cancel decision handled correctly")
    
    print("\n✅ All user approval agent tests passed!")
    return True

def main():
    """Run all tests."""
    print("="*60)
    print("TESTING USER APPROVAL FEATURE")
    print("="*60)
    
    try:
        # Run integration tests
        if not test_user_approval_integration():
            return False
            
        print("\n" + "="*60)
        
        # Run agent tests
        if not test_user_approval_agent():
            return False
            
        print("\n" + "="*60)
        print("🎉 ALL TESTS PASSED! User approval feature is working correctly.")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 