"""
Comprehensive STL Support Test Script

Tests STL file processing and simulation workflow using DeLorean and 747 plane files.
"""

import sys
import tempfile
import shutil
from pathlib import Path
import subprocess
import json
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Test imports
from agents.stl_processor import STLProcessor, validate_stl_file, process_stl_file
from agents.orchestrator import create_initial_state, create_cfd_workflow
from agents.nl_interpreter import nl_interpreter_agent
from agents.mesh_generator import mesh_generator_agent
from agents.boundary_condition import boundary_condition_agent
from agents.state import CFDState


def test_stl_file_processing():
    """Test STL file processing for both files."""
    print("="*60)
    print("TESTING STL FILE PROCESSING")
    print("="*60)
    
    stl_files = [
        ("DeLorean.STL", "DeLorean"),
        ("747-400.stl", "747 Plane")
    ]
    
    for stl_file, description in stl_files:
        print(f"\n🔍 Testing {description}: {stl_file}")
        print("-" * 40)
        
        stl_path = Path("stl") / stl_file
        
        # Test file validation
        print("1. Validating STL file...")
        is_valid, warnings = validate_stl_file(str(stl_path))
        
        if is_valid:
            print("✅ STL file is valid")
            if warnings:
                print("⚠️  Warnings:")
                for warning in warnings:
                    print(f"   - {warning}")
        else:
            print("❌ STL file validation failed:")
            for warning in warnings:
                print(f"   - {warning}")
            continue
        
        # Test STL processing
        print("2. Processing STL geometry...")
        try:
            stl_processor = STLProcessor(str(stl_path))
            if stl_processor.load_stl():
                print("✅ STL file loaded successfully")
                print(f"   - Triangles: {len(stl_processor.normals):,}")
                print(f"   - Vertices: {len(stl_processor.vertices):,}")
                
                # Analyze geometry
                geometry_info = stl_processor.analyze_geometry()
                if geometry_info:
                    print("✅ Geometry analysis complete")
                    print(f"   - Characteristic length: {geometry_info['characteristic_length']:.3f} m")
                    print(f"   - Surface area: {geometry_info['surface_area']:.6f} m²")
                    
                    if geometry_info.get('volume'):
                        print(f"   - Volume: {geometry_info['volume']:.6f} m³")
                    
                    print(f"   - Watertight: {geometry_info['is_watertight']}")
                    print(f"   - Surfaces detected: {len(geometry_info.get('surfaces', []))}")
                    
                    # Show estimated mesh size
                    mesh_rec = geometry_info.get('mesh_recommendations', {})
                    if mesh_rec:
                        print(f"   - Estimated cells: {mesh_rec.get('estimated_cells', 0):,}")
                        print(f"   - Base cell size: {mesh_rec.get('base_cell_size', 0):.6f} m")
                    
                else:
                    print("❌ Geometry analysis failed")
                    
            else:
                print("❌ Failed to load STL file")
                
        except Exception as e:
            print(f"❌ Error processing STL: {e}")
    
    print("\n" + "="*60)


def test_workflow_integration():
    """Test complete workflow integration with STL files."""
    print("TESTING WORKFLOW INTEGRATION")
    print("="*60)
    
    test_cases = [
        {
            "file": "DeLorean.STL",
            "description": "DeLorean Aerodynamics",
            "prompt": "Simulate airflow around a DeLorean car at 30 m/s to analyze aerodynamic drag and lift",
            "expected_flow": "external"
        },
        {
            "file": "747-400.stl", 
            "description": "747 Plane Aerodynamics",
            "prompt": "Analyze the aerodynamic flow around a 747 plane at 200 m/s for lift and drag calculations",
            "expected_flow": "external"
        }
    ]
    
    for case in test_cases:
        print(f"\n🔍 Testing {case['description']}")
        print("-" * 40)
        
        stl_path = Path("stl") / case["file"]
        
        try:
            # Create initial state
            print("1. Creating initial state...")
            initial_state = create_initial_state(
                user_prompt=case["prompt"],
                verbose=True,
                export_images=False,
                user_approval_enabled=False,
                stl_file=stl_path
            )
            
            print("✅ Initial state created")
            print(f"   - Geometry source: {initial_state.get('geometry_source')}")
            print(f"   - STL file path: {initial_state.get('stl_file_path')}")
            
            # Test NL interpreter
            print("2. Testing NL interpreter...")
            interpreted_state = nl_interpreter_agent(initial_state)
            
            if interpreted_state.get("errors"):
                print("❌ NL interpreter errors:")
                for error in interpreted_state["errors"]:
                    print(f"   - {error}")
                continue
            
            print("✅ NL interpreter completed")
            
            # Check STL geometry processing
            stl_geometry = interpreted_state.get("stl_geometry", {})
            if stl_geometry:
                print(f"   - STL triangles: {stl_geometry.get('num_triangles', 0):,}")
                print(f"   - Characteristic length: {stl_geometry.get('characteristic_length', 0):.3f} m")
                
                # Check flow context
                geometry_info = interpreted_state.get("geometry_info", {})
                flow_context = geometry_info.get("flow_context", {})
                if flow_context:
                    is_external = flow_context.get("is_external_flow", False)
                    expected_external = case["expected_flow"] == "external"
                    if is_external == expected_external:
                        print(f"✅ Flow context correct: {case['expected_flow']}")
                    else:
                        print(f"❌ Flow context mismatch: got {'external' if is_external else 'internal'}, expected {case['expected_flow']}")
                
                # Check surfaces
                stl_surfaces = geometry_info.get("stl_surfaces", [])
                print(f"   - STL surfaces detected: {len(stl_surfaces)}")
                for surface in stl_surfaces:
                    print(f"     - {surface.get('name', 'Unknown')}: {surface.get('triangle_count', 0)} triangles")
            
            # Test mesh generator
            print("3. Testing mesh generator...")
            mesh_state = mesh_generator_agent(interpreted_state)
            
            if mesh_state.get("errors"):
                print("❌ Mesh generator errors:")
                for error in mesh_state["errors"]:
                    print(f"   - {error}")
                continue
            
            print("✅ Mesh generator completed")
            
            # Check mesh config
            mesh_config = mesh_state.get("mesh_config", {})
            if mesh_config:
                print(f"   - Mesh type: {mesh_config.get('type', 'Unknown')}")
                print(f"   - Geometry type: {mesh_config.get('geometry_type', 'Unknown')}")
                print(f"   - Estimated cells: {mesh_config.get('total_cells', 0):,}")
                
                # Check STL specific settings
                if mesh_config.get('geometry_type') == 'stl':
                    print(f"   - STL file path: {mesh_config.get('stl_file_path', 'Not set')}")
                    
                    background_mesh = mesh_config.get('background_mesh', {})
                    if background_mesh:
                        print(f"   - Background cells: {background_mesh.get('n_cells_x', 0)} × {background_mesh.get('n_cells_y', 0)} × {background_mesh.get('n_cells_z', 0)}")
                        print(f"   - Base cell size: {background_mesh.get('base_cell_size', 0):.6f} m")
            
            # Test boundary condition generator
            print("4. Testing boundary condition generator...")
            bc_state = boundary_condition_agent(mesh_state)
            
            if bc_state.get("errors"):
                print("❌ Boundary condition errors:")
                for error in bc_state["errors"]:
                    print(f"   - {error}")
                continue
            
            print("✅ Boundary condition generator completed")
            
            # Check boundary conditions
            boundary_conditions = bc_state.get("boundary_conditions", {})
            if boundary_conditions:
                print(f"   - Generated fields: {', '.join(boundary_conditions.keys())}")
                
                # Check for STL surface boundary conditions
                if 'U' in boundary_conditions:
                    u_field = boundary_conditions['U']
                    boundary_field = u_field.get('boundaryField', {})
                    stl_patches = [name for name in boundary_field.keys() if name.startswith('stl_')]
                    
                    if stl_patches:
                        print(f"   - STL boundary patches: {len(stl_patches)}")
                        for patch in stl_patches:
                            print(f"     - {patch}")
                    else:
                        print("   - No STL boundary patches found")
            
            print(f"✅ {case['description']} workflow test completed successfully")
            
        except Exception as e:
            print(f"❌ Error in {case['description']} workflow: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)


def test_cli_integration():
    """Test CLI integration with STL files."""
    print("TESTING CLI INTEGRATION")
    print("="*60)
    
    test_cases = [
        {
            "file": "DeLorean.STL",
            "description": "DeLorean CLI Test",
            "prompt": "Simulate airflow around a DeLorean car at 30 m/s",
            "expected_success": True
        },
        {
            "file": "747-400.stl",
            "description": "747 CLI Test", 
            "prompt": "Analyze aerodynamic flow around a 747 plane at 200 m/s",
            "expected_success": True
        }
    ]
    
    for case in test_cases:
        print(f"\n🔍 Testing {case['description']}")
        print("-" * 40)
        
        stl_path = Path("stl") / case["file"]
        
        try:
            # Test CLI command
            cmd = [
                "uv", "run", "python", "src/foamai/cli.py", "solve",
                case["prompt"],
                "--stl-file", str(stl_path),
                "--verbose",
                "--no-user-approval",
                "--no-export-images"
            ]
            
            print("1. Running CLI command...")
            print(f"   Command: {' '.join(cmd)}")
            
            # Run with timeout
            try:
                result = subprocess.run(
                    cmd,
                    cwd=Path.cwd(),
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minute timeout
                )
                
                if result.returncode == 0:
                    print("✅ CLI command completed successfully")
                    print("   Output preview:")
                    lines = result.stdout.split('\n')
                    for line in lines[-10:]:  # Show last 10 lines
                        if line.strip():
                            print(f"   {line}")
                else:
                    print(f"❌ CLI command failed with return code {result.returncode}")
                    print("   Error output:")
                    lines = result.stderr.split('\n')
                    for line in lines[-10:]:  # Show last 10 lines
                        if line.strip():
                            print(f"   {line}")
                
            except subprocess.TimeoutExpired:
                print("⏱️ CLI command timed out after 2 minutes")
                
        except Exception as e:
            print(f"❌ Error in {case['description']} CLI test: {e}")
    
    print("\n" + "="*60)


def test_error_handling():
    """Test error handling for STL files."""
    print("TESTING ERROR HANDLING")
    print("="*60)
    
    print("\n🔍 Testing non-existent STL file")
    print("-" * 40)
    
    try:
        # Test with non-existent file
        fake_path = Path("fake_file.stl")
        initial_state = create_initial_state(
            user_prompt="Test prompt",
            verbose=True,
            stl_file=fake_path
        )
        
        interpreted_state = nl_interpreter_agent(initial_state)
        
        if interpreted_state.get("errors"):
            print("✅ Error handling working correctly")
            print("   Errors caught:")
            for error in interpreted_state["errors"]:
                print(f"   - {error}")
        else:
            print("❌ Error handling failed - should have caught missing file")
            
    except Exception as e:
        print(f"✅ Exception caught correctly: {e}")
    
    print("\n" + "="*60)


def run_all_tests():
    """Run all STL support tests."""
    print("🚀 STARTING STL SUPPORT TESTS")
    print("="*60)
    
    start_time = time.time()
    
    # Run tests
    test_stl_file_processing()
    test_workflow_integration()
    test_cli_integration()
    test_error_handling()
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"🏁 ALL TESTS COMPLETED IN {duration:.2f} SECONDS")
    print("="*60)


if __name__ == "__main__":
    run_all_tests() 