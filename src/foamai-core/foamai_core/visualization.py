"""Visualization Agent - Generates ParaView visualizations and exports images."""

import subprocess
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from loguru import logger

from .state import CFDState, CFDStep


def visualization_agent(state: CFDState) -> CFDState:
    """
    Visualization Agent.
    
    Generates visualizations using ParaView and exports images or data files
    based on simulation results and user preferences.
    
    For remote execution, visualization is delegated to the desktop UI.
    """
    try:
        if state["verbose"]:
            logger.info("Visualization: Starting visualization generation")
        
        # Check if running in remote execution mode
        if state.get("execution_mode") == "remote":
            logger.info("Remote execution detected - skipping LangGraph visualization (delegated to UI)")
            
            # For remote execution, visualization is handled by the desktop UI
            # Just mark this step as complete and proceed
            return {
                **state,
                "visualization_path": "remote://delegated_to_ui",
                "current_step": CFDStep.COMPLETE,
                "errors": []
            }
        
        case_directory = Path(state["case_directory"])
        output_format = state.get("output_format", "images")
        export_images = state.get("export_images", True)
        
        # Generate visualizations
        visualization_results = generate_visualizations(case_directory, state)
        
        # Export based on preferences
        if export_images or output_format == "images":
            image_results = export_visualization_images(case_directory, state, visualization_results)
            visualization_results.update(image_results)
        
        if output_format == "paraview":
            paraview_results = export_paraview_files(case_directory, state, visualization_results)
            visualization_results.update(paraview_results)
        
        if not visualization_results.get("success", False):
            error_msg = f"Visualization failed: {visualization_results.get('error', 'Unknown error')}"
            logger.error(error_msg)
            return {
                **state,
                "errors": state["errors"] + [error_msg],
                "visualization_path": "",
                "current_step": CFDStep.ERROR
            }
        
        visualization_path = visualization_results.get("output_directory", "")
        
        if state["verbose"]:
            logger.info(f"Visualization: Generated visualizations at {visualization_path}")
            logger.info(f"Visualization: Created {len(visualization_results.get('generated_files', []))} files")
        
        # Auto-open in ParaView if successful
        try:
            import sys
            import platform
            import subprocess
            
            # Create .foam file if it doesn't exist
            foam_file = Path(case_directory) / f"{Path(case_directory).name}.foam"
            if not foam_file.exists():
                foam_file.touch()
            
            # Get ParaView path from settings
            sys.path.append('src')
            from .config import get_settings
            settings = get_settings()
            
            if settings.paraview_path and Path(settings.paraview_path).exists():
                if platform.system() == "Windows":
                    paraview_exe = Path(settings.paraview_path) / "bin" / "paraview.exe"
                else:
                    paraview_exe = Path(settings.paraview_path) / "bin" / "paraview"
                
                if paraview_exe.exists():
                    logger.info(f"Opening results in ParaView...")
                    subprocess.Popen([str(paraview_exe), str(foam_file)])
                    logger.info(f"ParaView launched with case: {foam_file}")
        except Exception as e:
            logger.warning(f"Could not auto-open ParaView: {e}")
        
        return {
            **state,
            "visualization_path": str(visualization_path),
            "current_step": CFDStep.COMPLETE,
            "errors": []
        }
        
    except Exception as e:
        logger.error(f"Visualization error: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"Visualization failed: {str(e)}"],
            "visualization_path": "",
            "current_step": CFDStep.ERROR
        }


def generate_visualizations(case_directory: Path, state: CFDState) -> Dict[str, Any]:
    """Generate ParaView visualizations."""
    results = {
        "success": False,
        "generated_files": [],
        "output_directory": "",
        "error": None
    }
    
    try:
        # Create visualization output directory
        viz_dir = case_directory / "visualization"
        viz_dir.mkdir(exist_ok=True)
        results["output_directory"] = str(viz_dir)
        
        # Check if simulation results exist
        if not check_simulation_results(case_directory):
            results["error"] = "No simulation results found"
            return results
        
        # Generate ParaView Python script
        paraview_script = generate_paraview_script(case_directory, state)
        script_path = viz_dir / "visualization_script.py"
        
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(paraview_script)
        
        # Run ParaView in batch mode
        success = run_paraview_batch(script_path, state)
        
        if success:
            results["success"] = True
            results["generated_files"] = list(viz_dir.glob("*.png"))
            results["generated_files"].extend(list(viz_dir.glob("*.vtk")))
            results["generated_files"].extend(list(viz_dir.glob("*.vtu")))
        else:
            results["error"] = "ParaView batch execution failed"
        
    except Exception as e:
        results["error"] = str(e)
    
    return results


def check_simulation_results(case_directory: Path) -> bool:
    """Check if simulation results exist."""
    # Look for time directories (OpenFOAM results)
    time_dirs = [d for d in case_directory.iterdir() if d.is_dir() and d.name.replace(".", "").isdigit()]
    
    if not time_dirs:
        logger.warning("No time directories found - simulation may not have completed")
        return False
    
    # Check for field files in the latest time directory
    latest_time = max(time_dirs, key=lambda x: float(x.name))
    field_files = list(latest_time.glob("*"))
    
    if not field_files:
        logger.warning(f"No field files found in {latest_time}")
        return False
    
    logger.info(f"Found simulation results in {latest_time} with {len(field_files)} field files")
    return True


def generate_paraview_script(case_directory: Path, state: CFDState) -> str:
    """Generate ParaView Python script for visualization."""
    geometry_type = state["geometry_info"].get("type", "unknown")
    # Convert enum to string value if needed
    if hasattr(geometry_type, 'value'):
        geometry_type_str = geometry_type.value
    else:
        geometry_type_str = str(geometry_type)
    parsed_params = state["parsed_parameters"]
    flow_type = parsed_params.get("flow_type", "laminar")
    
    # Check if vortex shedding is expected
    reynolds_number = parsed_params.get("reynolds_number", 0)
    # Ensure Reynolds number is valid
    if reynolds_number is None:
        reynolds_number = 0
    expects_vortex_shedding = check_vortex_shedding_expected(geometry_type_str, reynolds_number)
    
    script = f'''# -*- coding: utf-8 -*-
# ParaView Python script for {geometry_type_str} visualization
import paraview.simple as pv
import numpy as np

# Disable automatic camera reset
pv._DisableFirstRenderCameraReset()

# Create OpenFOAM reader
foam_case = pv.OpenFOAMReader(FileName="{case_directory.as_posix()}/{case_directory.name}.foam")

# Update pipeline to read data
foam_case.UpdatePipeline()

# Get time information
time_values = foam_case.TimestepValues
if time_values:
    latest_time = max(time_values)
    initial_time = min(time_values)
    
    # For vortex shedding, use a representative time in the shedding cycle
    # Use 80% of the simulation time to ensure transients have settled
    if {expects_vortex_shedding} and len(time_values) > 10:
        target_time = initial_time + 0.8 * (latest_time - initial_time)
        # Find closest time step
        closest_time = min(time_values, key=lambda x: abs(x - target_time))
        # Set the animation time using proper ParaView API
        animation_scene = pv.GetAnimationScene()
        animation_scene.AnimationTime = closest_time
        # Update pipeline to load data at new time
        foam_case.UpdatePipeline(time=closest_time)
        print("Set time to", closest_time, "for vortex shedding analysis")
    else:
        # Set to latest time using proper ParaView API
        animation_scene = pv.GetAnimationScene()
        animation_scene.AnimationTime = latest_time
        # Update pipeline to load data at new time
        foam_case.UpdatePipeline(time=latest_time)
        print("Set time to", latest_time, "(latest available)")
else:
    # No time values available, use steady state
    print("No time values found, using steady state data")

# Create render view
render_view = pv.CreateView('RenderView')
render_view.ViewSize = [1200, 800]
render_view.Background = [1.0, 1.0, 1.0]  # White background

# Display the mesh
foam_display = pv.Show(foam_case, render_view)

# For custom STL geometries, configure display to show surfaces properly
try:
    if "{geometry_type_str}" == "custom":
        # For custom geometries, use extract surface to better show the geometry
        extract_surface = pv.ExtractSurface(Input=foam_case)
        visualization_source = extract_surface
    else:
        visualization_source = foam_case
except:
    visualization_source = foam_case

# Generate pressure visualization
try:
    # Display the visualization source
    if visualization_source != foam_case:
        source_display = pv.Show(visualization_source, render_view)
        pv.Hide(foam_case, render_view)
    else:
        source_display = foam_display
    
    # Color by pressure
    pv.ColorBy(source_display, ('POINTS', 'p'))
    
    # Get pressure lookup table
    p_lut = pv.GetColorTransferFunction('p')
    p_lut.ApplyPreset('Cool to Warm', True)
    
    # Add color bar
    p_colorbar = pv.GetScalarBar(p_lut, render_view)
    p_colorbar.Title = 'Pressure [Pa]'
    p_colorbar.ComponentTitle = ''
    
    # Reset camera and render
    render_view.ResetCamera()
    pv.Render()
    
    # Save pressure image
    pv.SaveScreenshot("{case_directory.as_posix()}/visualization/pressure_field.png")
except:
    print("Pressure field not available")

# Generate velocity visualization
try:
    # Color by velocity magnitude
    calculator = pv.Calculator(Input=visualization_source)
    calculator.ResultArrayName = 'U_magnitude'
    calculator.Function = 'mag(U)'
    
    # Display velocity magnitude
    calc_display = pv.Show(calculator, render_view)
    pv.ColorBy(calc_display, ('POINTS', 'U_magnitude'))
    
    # Get velocity lookup table
    u_lut = pv.GetColorTransferFunction('U_magnitude')
    u_lut.ApplyPreset('Rainbow', True)
    
    # Add color bar
    u_colorbar = pv.GetScalarBar(u_lut, render_view)
    u_colorbar.Title = 'Velocity Magnitude [m/s]'
    u_colorbar.ComponentTitle = ''
    
    # Reset camera and render
    render_view.ResetCamera()
    pv.Render()
    
    # Save velocity image
    pv.SaveScreenshot("{case_directory.as_posix()}/visualization/velocity_field.png")
except:
    print("Velocity field not available")

# Generate VORTICITY visualization (essential for vortex shedding)
try:
    if {expects_vortex_shedding}:
        # Calculate vorticity using curl of velocity
        vorticity_calc = pv.Calculator(Input=visualization_source)
        vorticity_calc.ResultArrayName = 'Vorticity'
        vorticity_calc.Function = 'curl(U)'
        
        # Calculate vorticity magnitude
        vorticity_mag = pv.Calculator(Input=vorticity_calc)
        vorticity_mag.ResultArrayName = 'Vorticity_Magnitude'
        vorticity_mag.Function = 'mag(Vorticity)'
        
        # Display vorticity magnitude
        vort_display = pv.Show(vorticity_mag, render_view)
        pv.ColorBy(vort_display, ('POINTS', 'Vorticity_Magnitude'))
        
        # Get vorticity lookup table with better color map for vortices
        vort_lut = pv.GetColorTransferFunction('Vorticity_Magnitude')
        vort_lut.ApplyPreset('Plasma', True)
        
        # Add color bar
        vort_colorbar = pv.GetScalarBar(vort_lut, render_view)
        vort_colorbar.Title = 'Vorticity Magnitude [1/s]'
        vort_colorbar.ComponentTitle = ''
        
        # Reset camera and render
        render_view.ResetCamera()
        pv.Render()
        
        # Save vorticity image
        pv.SaveScreenshot("{case_directory.as_posix()}/visualization/vorticity_field.png")
        
        # Hide vorticity display for next visualization
        pv.Hide(vorticity_mag, render_view)
        
        print("Vorticity field generated successfully")
except:
    print("Vorticity field not available")

# Generate Q-CRITERION visualization (advanced vortex identification)
try:
    if {expects_vortex_shedding}:
        # Calculate Q-criterion using velocity gradient tensor
        q_calc = pv.Calculator(Input=visualization_source)
        q_calc.ResultArrayName = 'Q_criterion'
        # Q = 0.5 * (Omega^2 - S^2) where Omega is vorticity and S is strain rate
        q_calc.Function = '0.5 * (mag(curl(U))^2 - 0.5 * (mag(grad(U)) + mag(grad(U))_T)^2)'
        
        # Create isosurface for Q-criterion to show vortex cores
        q_contour = pv.Contour(Input=q_calc)
        q_contour.ContourBy = ['POINTS', 'Q_criterion']
        
        # Get Q values and set appropriate contour level
        q_calc.UpdatePipeline()
        q_range = q_calc.GetDataInformation().GetPointDataInformation().GetArrayInformation('Q_criterion').GetComponentRange(0)
        if q_range[1] > 0:
            q_contour.Isosurfaces = [q_range[1] * 0.1]  # 10% of maximum Q value
            
            # Display Q-criterion contours
            q_display = pv.Show(q_contour, render_view)
            q_display.ColorArrayName = ['POINTS', 'U_magnitude']
            q_display.Opacity = 0.7
            
            # Color by velocity magnitude
            q_lut = pv.GetColorTransferFunction('U_magnitude')
            q_lut.ApplyPreset('Viridis', True)
            
            # Add color bar
            q_colorbar = pv.GetScalarBar(q_lut, render_view)
            q_colorbar.Title = 'Q-Criterion Isosurfaces [1/s^2]'
            q_colorbar.ComponentTitle = ''
            
            # Reset camera and render
            render_view.ResetCamera()
            pv.Render()
            
            # Save Q-criterion image
            pv.SaveScreenshot("{case_directory.as_posix()}/visualization/q_criterion.png")
            
            # Hide Q-criterion display for next visualization
            pv.Hide(q_contour, render_view)
            
            print("Q-criterion visualization generated successfully")
except:
    print("Q-criterion visualization not available")

# Generate ENHANCED STREAMLINES for vortex shedding
try:
    if "{geometry_type_str}" in ["cylinder", "airfoil", "sphere", "cube", "custom"]:
        # Create streamline tracer with better seeding for vortex shedding
        streamlines = pv.StreamTracer(Input=calculator)
        streamlines.Vectors = ['POINTS', 'U']
        streamlines.IntegrationDirection = 'FORWARD'
        streamlines.MaximumStreamlineLength = {parsed_params.get("geometry_dimensions", {}).get("domain_width", 2.0)}
        
        # Enhanced seeding for vortex shedding visualization
        if {expects_vortex_shedding}:
            # Create multiple seed lines to capture vortex shedding
            streamlines.SeedType = 'Point Cloud'
            
            # Get domain dimensions
            domain_upstream = {state.get("mesh_config", {}).get("dimensions", {}).get("domain_upstream", 1.0)}
            domain_height = {state.get("mesh_config", {}).get("dimensions", {}).get("domain_height", 1.0)}
            char_length = {parsed_params.get("geometry_dimensions", {}).get("diameter", 0.1)}
            
            # Seed points in the wake region where vortex shedding occurs
            seed_points = []
            # Upstream seeding
            for i in range(10):
                y = -domain_height * 0.4 + i * (domain_height * 0.8) / 9
                seed_points.append([-domain_upstream * 0.5, y, 0.0])
            
            # Wake seeding (downstream of object)
            for i in range(15):
                x = char_length * 0.5 + i * (char_length * 8) / 14
                for j in range(5):
                    y = -char_length * 2 + j * (char_length * 4) / 4
                    seed_points.append([x, y, 0.0])
            
            # Set the seed points
            streamlines.SeedType.Points = seed_points
        else:
            # Standard seeding for non-vortex shedding flows
            streamlines.SeedType = 'Line'
            domain_upstream = {state.get("mesh_config", {}).get("dimensions", {}).get("domain_upstream", 1.0)}
            domain_height = {state.get("mesh_config", {}).get("dimensions", {}).get("domain_height", 1.0)}
            
            seed_x = -domain_upstream * 0.8
            streamlines.SeedType.Point1 = [seed_x, -domain_height * 0.4, 0.0]
            streamlines.SeedType.Point2 = [seed_x, domain_height * 0.4, 0.0]
            streamlines.SeedType.Resolution = 20
        
        # Display streamlines
        stream_display = pv.Show(streamlines, render_view)
        stream_display.ColorArrayName = ['POINTS', 'U_magnitude']
        
        # Reset camera and render
        render_view.ResetCamera()
        pv.Render()
        
        # Save streamlines image
        pv.SaveScreenshot("{case_directory.as_posix()}/visualization/streamlines.png")
        
        # Hide streamlines for next visualization
        pv.Hide(streamlines, render_view)
        
        print("Enhanced streamlines generated successfully")
except:
    print("Streamlines not available")

# Generate surface pressure distribution for bluff bodies
try:
    if "{geometry_type_str}" in ["cylinder", "airfoil", "sphere", "cube", "custom"]:
        # For custom geometries, create a separate surface extraction for surface pressure
        if "{geometry_type_str}" == "custom":
            # Hide internal mesh and show only surfaces for better visualization
            foam_case.MeshRegions = []  # Hide internal mesh
            try:
                all_patches = foam_case.PatchArrays
                if all_patches:
                    foam_case.PatchArrays = all_patches  # Show all patches
            except AttributeError:
                # PatchArrays not available in this ParaView version
                # Try alternative approach using patch selection
                try:
                    if hasattr(foam_case, 'Patches'):
                        foam_case.Patches = ['.*']  # Show all patches using regex
                except:
                    pass  # Fallback: rely on default visualization
        
        # Extract surface
        extract_surface = pv.ExtractSurface(Input=foam_case)
        
        # Hide the previous visualization
        pv.Hide(visualization_source, render_view)
        
        # Display surface colored by pressure
        surface_display = pv.Show(extract_surface, render_view)
        surface_display.Representation = 'Surface'
        pv.ColorBy(surface_display, ('POINTS', 'p'))
        
        # Get pressure lookup table
        p_lut = pv.GetColorTransferFunction('p')
        p_lut.ApplyPreset('Cool to Warm', True)
        
        # Add color bar
        p_colorbar = pv.GetScalarBar(p_lut, render_view)
        p_colorbar.Title = 'Surface Pressure [Pa]'
        p_colorbar.ComponentTitle = ''
        
        # Reset camera and render
        render_view.ResetCamera()
        pv.Render()
        
        # Save surface pressure image
        pv.SaveScreenshot("{case_directory.as_posix()}/visualization/surface_pressure.png")
        
        print("Surface pressure visualization generated successfully")
except:
    print("Surface pressure not available")

# Generate TIME-AVERAGED FLOW visualization (for vortex shedding analysis)
try:
    if {str(expects_vortex_shedding).lower()} and len(time_values) > 20:
        # Create temporal statistics filter to compute time-averaged flow
        temporal_stats = pv.TemporalStatistics(Input=calculator)
        temporal_stats.ComputeMinimum = 0
        temporal_stats.ComputeMaximum = 0
        temporal_stats.ComputeAverage = 1
        temporal_stats.ComputeStandardDeviation = 0
        
        # Display time-averaged velocity magnitude
        avg_display = pv.Show(temporal_stats, render_view)
        pv.ColorBy(avg_display, ('POINTS', 'U_magnitude_average'))
        
        # Get lookup table for time-averaged velocity
        avg_lut = pv.GetColorTransferFunction('U_magnitude_average')
        avg_lut.ApplyPreset('Cool to Warm', True)
        
        # Add color bar
        avg_colorbar = pv.GetScalarBar(avg_lut, render_view)
        avg_colorbar.Title = 'Time-Averaged Velocity Magnitude [m/s]'
        avg_colorbar.ComponentTitle = ''
        
        # Reset camera and render
        render_view.ResetCamera()
        pv.Render()
        
        # Save time-averaged flow image
        pv.SaveScreenshot("{case_directory.as_posix()}/visualization/time_averaged_flow.png")
        
        print("Time-averaged flow visualization generated successfully")
except:
    print("Time-averaged flow visualization not available")

# Generate ANIMATION for vortex shedding (save state file for interactive viewing)
try:
    if {str(expects_vortex_shedding).lower()} and len(time_values) > 10:
        # Save the ParaView state file for interactive viewing of vortex shedding
        pv.SaveState("{case_directory.as_posix()}/visualization/vortex_shedding_animation.pvsm")
        
        # Create a simple animation setup
        # Set up the scene for animation
        scene = pv.GetAnimationScene()
        scene.UpdateAnimationUsingDataTimeSteps()
        
        # Write animation instructions to a text file
        with open("{case_directory.as_posix()}/visualization/animation_instructions.txt", "w", encoding="utf-8") as f:
            f.write("VORTEX SHEDDING ANIMATION INSTRUCTIONS\\n")
            f.write("=====================================\\n\\n")
            f.write("1. Open ParaView and load the state file: vortex_shedding_animation.pvsm\\n")
            f.write("2. Use the animation controls to play through time steps\\n")
            f.write("3. For best results, color by 'Vorticity_Magnitude' or 'U_magnitude'\\n")
            f.write("4. Enable the time annotation to see the temporal evolution\\n")
            f.write("5. Save as animation using File > Save Animation\\n\\n")
            f.write(f"Simulation contains {{len(time_values)}} time steps\\n")
            f.write(f"Time range: {{initial_time:.3f}} to {{latest_time:.3f}} seconds\\n")
            if reynolds_number > 0:
                f.write(f"Reynolds number: {{reynolds_number:.0f}}\\n")
                # Estimate Strouhal number for cylinder
                if geometry_type_str == "cylinder" and reynolds_number > 40:
                    strouhal = 0.198 * (1 - 19.7 / reynolds_number)
                    f.write(f"Estimated Strouhal number: {{strouhal:.3f}}\\n")
        
        print("Animation setup and instructions generated successfully")
except:
    print("Animation setup not available")

print("Enhanced vortex shedding visualization generation completed successfully")
'''
    
    return script


def check_vortex_shedding_expected(geometry_type_str: str, reynolds_number: float) -> bool:
    """Check if vortex shedding is expected based on geometry and Reynolds number."""
    # Handle None or invalid Reynolds number
    if reynolds_number is None or reynolds_number <= 0:
        logger.info(f"Invalid Reynolds number ({reynolds_number}), assuming no vortex shedding")
        return False
    
    # Geometry-specific vortex shedding thresholds
    vortex_thresholds = {
        "cylinder": 40,
        "sphere": 200,
        "cube": 50,
        "airfoil": 100000,  # Much higher for streamlined bodies
        "custom": 50,  # Conservative assumption
    }
    
    threshold = vortex_thresholds.get(geometry_type_str.lower(), 100)
    is_vortex_shedding = reynolds_number > threshold
    
    if is_vortex_shedding:
        logger.info(f"Vortex shedding expected for {geometry_type_str} at Re={reynolds_number} (threshold: {threshold})")
    else:
        logger.info(f"No vortex shedding expected for {geometry_type_str} at Re={reynolds_number} (threshold: {threshold})")
    
    return is_vortex_shedding


def run_paraview_batch(script_path: Path, state: CFDState) -> bool:
    """Run ParaView in batch mode to execute visualization script."""
    try:
        # Prepare environment
        env = prepare_paraview_env()
        
        # Get ParaView path from settings
        try:
            from ..foamai.config import get_settings
            settings = get_settings()
        except ImportError:
            # Fallback if import fails (e.g., when run from ParaView)
            class MockSettings:
                paraview_path = os.environ.get("PARAVIEW_PATH", "C:\\Program Files\\ParaView 6.0.0")
            settings = MockSettings()
        
        # Try configured ParaView path first
        paraview_executables = []
        
        if settings.paraview_path:
            if settings.paraview_path.startswith("/"):
                # WSL path
                paraview_executables.extend([
                    ["wsl", "-e", "bash", "-c", f"cd '{script_path.parent}' && pvpython '{script_path}'"],
                    ["wsl", "-e", "bash", "-c", f"cd '{script_path.parent}' && paraview --script '{script_path}'"]
                ])
            else:
                # Windows path
                paraview_exe = os.path.join(settings.paraview_path, "bin", "paraview.exe")
                pvpython_exe = os.path.join(settings.paraview_path, "bin", "pvpython.exe")
                
                if os.path.exists(pvpython_exe):
                    paraview_executables.append([pvpython_exe, str(script_path)])
                if os.path.exists(paraview_exe):
                    paraview_executables.append([paraview_exe, "--script", str(script_path)])
        
        # Fallback to system PATH
        paraview_executables.extend([
            ["pvpython", str(script_path)],
            ["paraview", "--script", str(script_path)],
            ["/usr/bin/pvpython", str(script_path)]
        ])
        
        for cmd in paraview_executables:
            try:
                if state["verbose"]:
                    logger.info(f"Trying ParaView command: {' '.join(cmd)}")
                
                result = subprocess.run(
                    cmd,
                    cwd=script_path.parent,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                if result.returncode == 0:
                    if state["verbose"]:
                        logger.info(f"ParaView visualization completed successfully")
                        logger.info(f"Command: {' '.join(cmd)}")
                    return True
                else:
                    logger.warning(f"ParaView failed with command '{' '.join(cmd)}': {result.stderr}")
                    
            except FileNotFoundError:
                continue
            except Exception as e:
                logger.warning(f"Error running ParaView command '{' '.join(cmd)}': {e}")
                continue
        
        logger.error("Could not find working ParaView executable")
        return False
        
    except Exception as e:
        logger.error(f"ParaView batch execution failed: {e}")
        return False


def prepare_paraview_env() -> Dict[str, str]:
    """Prepare ParaView environment variables."""
    env = os.environ.copy()
    
    # Get configured ParaView path
    try:
        from ..foamai.config import get_settings
        settings = get_settings()
        configured_path = settings.paraview_path
    except ImportError:
        # Fallback if import fails (e.g., when run from ParaView)
        configured_path = os.environ.get("PARAVIEW_PATH", "C:\\Program Files\\ParaView 6.0.0")
    
    # Add common ParaView paths
    paraview_paths = [
        "/usr/bin",
        "/opt/paraview/bin",
        "/usr/local/bin",
        "/Applications/ParaView.app/Contents/bin"  # macOS
    ]
    
    # Add configured ParaView path if it exists
    if configured_path and not configured_path.startswith("/"):
        # Windows path - add bin directory
        paraview_bin = os.path.join(configured_path, "bin")
        if os.path.exists(paraview_bin):
            paraview_paths.insert(0, paraview_bin)
    
    current_path = env.get("PATH", "")
    
    # Use appropriate separator based on OS
    path_separator = ";" if os.name == "nt" else ":"
    
    for path in paraview_paths:
        if path not in current_path:
            current_path = f"{path}{path_separator}{current_path}"
    
    env["PATH"] = current_path
    
    # Set display for headless rendering (Linux/WSL)
    if "DISPLAY" not in env and os.name != "nt":
        env["DISPLAY"] = ":0.0"
    
    return env


def export_visualization_images(case_directory: Path, state: CFDState, viz_results: Dict[str, Any]) -> Dict[str, Any]:
    """Export visualization images."""
    results = {
        "images_exported": [],
        "image_count": 0
    }
    
    viz_dir = Path(viz_results["output_directory"])
    
    # Look for generated images
    image_files = list(viz_dir.glob("*.png"))
    
    if image_files:
        results["images_exported"] = [str(f) for f in image_files]
        results["image_count"] = len(image_files)
        
        if state["verbose"]:
            logger.info(f"Exported {len(image_files)} visualization images")
    else:
        logger.warning("No visualization images were generated")
    
    return results


def export_paraview_files(case_directory: Path, state: CFDState, viz_results: Dict[str, Any]) -> Dict[str, Any]:
    """Export ParaView-compatible files."""
    results = {
        "paraview_files_exported": [],
        "paraview_file_count": 0
    }
    
    try:
        viz_dir = Path(viz_results["output_directory"])
        
        # Create .foam file for ParaView
        foam_file = case_directory / f"{case_directory.name}.foam"
        if not foam_file.exists():
            foam_file.touch()
        
        results["paraview_files_exported"].append(str(foam_file))
        
        # Look for VTK files
        vtk_files = list(viz_dir.glob("*.vtk"))
        vtu_files = list(viz_dir.glob("*.vtu"))
        
        all_files = vtk_files + vtu_files
        
        if all_files:
            results["paraview_files_exported"].extend([str(f) for f in all_files])
        
        results["paraview_file_count"] = len(results["paraview_files_exported"])
        
        if state["verbose"]:
            logger.info(f"Exported {results['paraview_file_count']} ParaView files")
    
    except Exception as e:
        logger.error(f"Error exporting ParaView files: {e}")
    
    return results


def generate_visualization_summary(case_directory: Path, state: CFDState, viz_results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate visualization summary report."""
    summary = {
        "case_name": case_directory.name,
        "geometry_type": state["geometry_info"].get("type", "unknown"),
        "flow_type": state["parsed_parameters"].get("flow_type", "unknown"),
        "solver": state["solver_settings"].get("solver", "unknown"),
        "visualization_files": viz_results.get("generated_files", []),
        "simulation_successful": state["simulation_results"].get("success", False),
        "convergence_achieved": state.get("convergence_metrics", {}).get("converged", False),
        "recommendations": []
    }
    
    # Add recommendations based on results
    if not summary["simulation_successful"]:
        summary["recommendations"].append("Simulation did not complete successfully")
    
    if not summary["convergence_achieved"]:
        summary["recommendations"].append("Solution did not converge - results may be inaccurate")
    
    mesh_quality = state.get("mesh_quality", {})
    if mesh_quality.get("quality_score", 1.0) < 0.7:
        summary["recommendations"].append("Poor mesh quality detected")
    
    # Export summary to JSON
    import json
    summary_file = case_directory / "visualization" / "summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    return summary 