"""
DeLorean Vortex Shedding Test - pimpleFoam
Test STL support with DeLorean for vortex shedding simulation using pimpleFoam
"""

import sys
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agents.stl_processor import STLProcessor, validate_stl_file, process_stl_file
from agents.orchestrator import create_initial_state
from agents.nl_interpreter import nl_interpreter_agent
from agents.mesh_generator import mesh_generator_agent
from agents.boundary_condition import boundary_condition_agent
from agents.solver_selector import solver_selector_agent
from agents.case_writer import case_writer_agent
from agents.state import CFDState


def test_delorean_vortex_shedding():
    """Test complete workflow for DeLorean vortex shedding with pimpleFoam."""
    print("🚗 TESTING DELOREAN VORTEX SHEDDING - PIMPLEFOAM")
    print("="*60)
    
    stl_path = Path("stl") / "DeLorean.STL"
    
    # Test prompt for vortex shedding
    prompt = "Simulate vortex shedding around a DeLorean car at 25 m/s using pimpleFoam for unsteady turbulent flow analysis"
    
    print(f"📁 STL File: {stl_path}")
    print(f"💭 Prompt: {prompt}")
    print()
    
    try:
        # Step 1: Create initial state
        print("1️⃣ Creating initial state...")
        initial_state = create_initial_state(
            user_prompt=prompt,
            verbose=True,
            export_images=False,
            user_approval_enabled=False,
            stl_file=stl_path
        )
        
        print("✅ Initial state created successfully")
        print(f"   - Geometry source: {initial_state.get('geometry_source')}")
        print(f"   - STL file path: {initial_state.get('stl_file_path')}")
        print()
        
        # Step 2: NL Interpreter
        print("2️⃣ Running NL interpreter...")
        interpreted_state = nl_interpreter_agent(initial_state)
        
        if interpreted_state.get("errors"):
            print("❌ NL interpreter failed:")
            for error in interpreted_state["errors"]:
                print(f"   - {error}")
            return False
        
        print("✅ NL interpreter completed")
        
        # Check STL geometry processing
        stl_geometry = interpreted_state.get("stl_geometry", {})
        geometry_info = interpreted_state.get("geometry_info", {})
        
        if stl_geometry:
            print(f"   - STL triangles: {stl_geometry.get('num_triangles', 0):,}")
            print(f"   - Characteristic length: {stl_geometry.get('characteristic_length', 0):.3f} m")
            print(f"   - Surface area: {stl_geometry.get('surface_area', 0):.6f} m²")
            print(f"   - Volume: {stl_geometry.get('volume', 0):.6f} m³")
            print(f"   - Watertight: {stl_geometry.get('is_watertight', False)}")
            
            # Check flow context
            flow_context = geometry_info.get("flow_context", {})
            if flow_context:
                print(f"   - Flow type: {'External' if flow_context.get('is_external_flow', False) else 'Internal'}")
                print(f"   - Flow direction: {flow_context.get('flow_direction', 'Unknown')}")
        
        # Check parsed parameters
        parsed_params = interpreted_state.get("parsed_parameters", {})
        if parsed_params:
            print(f"   - Velocity: {parsed_params.get('velocity', 'Not specified')} m/s")
            print(f"   - Flow type: {parsed_params.get('flow_type', 'Not specified')}")
            print(f"   - Analysis type: {parsed_params.get('analysis_type', 'Not specified')}")
        
        print()
        
        # Step 3: Mesh Generator
        print("3️⃣ Running mesh generator...")
        mesh_state = mesh_generator_agent(interpreted_state)
        
        if mesh_state.get("errors"):
            print("❌ Mesh generator failed:")
            for error in mesh_state["errors"]:
                print(f"   - {error}")
            return False
        
        print("✅ Mesh generator completed")
        
        # Check mesh configuration
        mesh_config = mesh_state.get("mesh_config", {})
        if mesh_config:
            print(f"   - Mesh type: {mesh_config.get('type', 'Unknown')}")
            print(f"   - Geometry type: {mesh_config.get('geometry_type', 'Unknown')}")
            print(f"   - Estimated cells: {mesh_config.get('total_cells', 0):,}")
            print(f"   - External flow: {mesh_config.get('is_external_flow', False)}")
            
            # STL specific info
            if mesh_config.get('geometry_type') == 'stl':
                background_mesh = mesh_config.get('background_mesh', {})
                if background_mesh:
                    print(f"   - Background cells: {background_mesh.get('n_cells_x', 0)} × {background_mesh.get('n_cells_y', 0)} × {background_mesh.get('n_cells_z', 0)}")
                    print(f"   - Base cell size: {background_mesh.get('base_cell_size', 0):.6f} m")
        
        print()
        
        # Step 4: Boundary Condition Generator
        print("4️⃣ Running boundary condition generator...")
        bc_state = boundary_condition_agent(mesh_state)
        
        if bc_state.get("errors"):
            print("❌ Boundary condition generator failed:")
            for error in bc_state["errors"]:
                print(f"   - {error}")
            return False
        
        print("✅ Boundary condition generator completed")
        
        # Check boundary conditions
        boundary_conditions = bc_state.get("boundary_conditions", {})
        if boundary_conditions:
            print(f"   - Generated fields: {', '.join(boundary_conditions.keys())}")
            
            # Check for STL boundary conditions
            if 'U' in boundary_conditions:
                u_field = boundary_conditions['U']
                boundary_field = u_field.get('boundaryField', {})
                stl_patches = [name for name in boundary_field.keys() if name.startswith('stl_')]
                print(f"   - STL boundary patches: {len(stl_patches)}")
                
                # Show external flow boundaries
                external_patches = [name for name in boundary_field.keys() if name in ['inlet', 'outlet', 'sides', 'top', 'bottom']]
                print(f"   - External flow patches: {len(external_patches)}")
        
        print()
        
        # Step 5: Solver Selection
        print("5️⃣ Running solver selector...")
        solver_state = solver_selector_agent(bc_state)
        
        if solver_state.get("errors"):
            print("❌ Solver selector failed:")
            for error in solver_state["errors"]:
                print(f"   - {error}")
            return False
        
        print("✅ Solver selector completed")
        
        # Check solver settings
        solver_settings = solver_state.get("solver_settings", {})
        if solver_settings:
            print(f"   - Selected solver: {solver_settings.get('solver_name', 'Unknown')}")
            print(f"   - Solver type: {solver_settings.get('solver_type', 'Unknown')}")
            print(f"   - Analysis type: {solver_settings.get('analysis_type', 'Unknown')}")
            print(f"   - Unsteady: {solver_settings.get('unsteady', False)}")
            
            # Check if pimpleFoam was selected
            if solver_settings.get('solver_name') == 'pimpleFoam':
                print("✅ pimpleFoam correctly selected for vortex shedding")
            else:
                print(f"⚠️  Expected pimpleFoam but got {solver_settings.get('solver_name', 'Unknown')}")
        
        print()
        
        # Step 6: Case Writer
        print("6️⃣ Running case writer...")
        case_state = case_writer_agent(solver_state)
        
        if case_state.get("errors"):
            print("❌ Case writer failed:")
            for error in case_state["errors"]:
                print(f"   - {error}")
            return False
        
        print("✅ Case writer completed")
        
        # Check case directory
        case_directory = case_state.get("case_directory", "")
        if case_directory:
            print(f"   - Case directory: {case_directory}")
            
            # Check if key files exist
            case_path = Path(case_directory)
            if case_path.exists():
                print("   - Generated files:")
                
                # Check system files
                system_files = ["controlDict", "fvSchemes", "fvSolution", "decomposeParDict"]
                for file in system_files:
                    file_path = case_path / "system" / file
                    if file_path.exists():
                        print(f"     ✅ system/{file}")
                    else:
                        print(f"     ❌ system/{file} (missing)")
                
                # Check constant files
                constant_files = ["turbulenceProperties", "transportProperties"]
                for file in constant_files:
                    file_path = case_path / "constant" / file
                    if file_path.exists():
                        print(f"     ✅ constant/{file}")
                    else:
                        print(f"     ❌ constant/{file} (missing)")
                
                # Check 0 directory files
                zero_dir = case_path / "0"
                if zero_dir.exists():
                    zero_files = list(zero_dir.glob("*"))
                    print(f"     ✅ 0/ directory with {len(zero_files)} field files")
                    for file in zero_files:
                        print(f"       - {file.name}")
                else:
                    print("     ❌ 0/ directory (missing)")
        
        print()
        print("🎉 DELOREAN VORTEX SHEDDING TEST COMPLETED SUCCESSFULLY!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error in DeLorean vortex shedding test: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cli_direct():
    """Test the CLI directly with the DeLorean vortex shedding case."""
    print("\n🚗 TESTING CLI DIRECT - DELOREAN VORTEX SHEDDING")
    print("="*60)
    
    stl_path = Path("stl") / "DeLorean.STL"
    prompt = "Simulate vortex shedding around a DeLorean car at 25 m/s using pimpleFoam for unsteady turbulent flow analysis"
    
    print(f"📁 STL File: {stl_path}")
    print(f"💭 Prompt: {prompt}")
    print()
    
    try:
        import subprocess
        
        # Test CLI command
        cmd = [
            "uv", "run", "python", "src/foamai/cli.py", "solve",
            prompt,
            "--stl-file", str(stl_path),
            "--verbose",
            "--no-user-approval",
            "--no-export-images"
        ]
        
        print("🔧 Running CLI command...")
        print(f"   Command: {' '.join(cmd)}")
        print()
        
        # Run with timeout
        try:
            result = subprocess.run(
                cmd,
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                print("✅ CLI command completed successfully")
                print()
                print("📋 Output summary:")
                lines = result.stdout.split('\n')
                for line in lines[-20:]:  # Show last 20 lines
                    if line.strip():
                        print(f"   {line}")
                
                return True
            else:
                print(f"❌ CLI command failed with return code {result.returncode}")
                print()
                print("📋 Error output:")
                lines = result.stderr.split('\n')
                for line in lines[-20:]:  # Show last 20 lines
                    if line.strip():
                        print(f"   {line}")
                
                return False
                
        except subprocess.TimeoutExpired:
            print("⏱️ CLI command timed out after 5 minutes")
            return False
            
    except Exception as e:
        print(f"❌ Error in CLI test: {e}")
        return False


if __name__ == "__main__":
    print("🚀 STARTING DELOREAN VORTEX SHEDDING TESTS")
    print("="*60)
    
    start_time = time.time()
    
    # Test workflow components
    workflow_success = test_delorean_vortex_shedding()
    
    # Test CLI if workflow succeeded
    if workflow_success:
        cli_success = test_cli_direct()
    else:
        cli_success = False
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\n🏁 TESTS COMPLETED IN {duration:.2f} SECONDS")
    print("="*60)
    
    if workflow_success and cli_success:
        print("🎉 ALL TESTS PASSED - STL SUPPORT IS WORKING!")
    elif workflow_success:
        print("⚠️  WORKFLOW TESTS PASSED, CLI TESTS FAILED")
    else:
        print("❌ WORKFLOW TESTS FAILED")
    
    print("="*60) 