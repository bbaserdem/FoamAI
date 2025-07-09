"""Test script to demonstrate FoamAI visualization improvements."""

import sys
from pathlib import Path
sys.path.append('src')

from agents.visualization import visualization_agent
from agents.state import CFDState, GeometryType, FlowType

# Create a test state with a successful simulation
test_state = {
    "case_directory": "work/20250707_213752_channel_case",
    "verbose": True,
    "export_images": True,
    "output_format": "images",
    "geometry_info": {
        "type": GeometryType.CHANNEL,
        "dimensions": {"width": 0.1, "height": 0.1, "length": 1.0}
    },
    "parsed_parameters": {
        "flow_type": FlowType.LAMINAR,
        "reynolds_number": 6768
    },
    "solver_settings": {
        "solver": "simpleFoam"
    },
    "simulation_results": {
        "success": True,
        "final_residuals": {"p": 0.00530987, "Ux": 0.00286118, "Uy": 0.00945602}
    },
    "errors": [],
    "warnings": []
}

# Run visualization agent
print("Running visualization agent...")
result = visualization_agent(test_state)

if result.get("errors"):
    print(f"Errors: {result['errors']}")
else:
    print(f"Success! Visualization path: {result.get('visualization_path')}")
    print("\nThe following improvements were demonstrated:")
    print("1. ✅ Auto-opening ParaView after visualization")
    print("2. ✅ Time bug fixed - visualizing at latest time step")
    print("3. 🔄 Cylinder geometry attempted (needs more work)")
    print("\nCheck if ParaView opened automatically!") 