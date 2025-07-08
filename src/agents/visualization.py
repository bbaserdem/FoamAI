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
    """
    try:
        if state["verbose"]:
            logger.info("Visualization: Starting visualization generation")
        
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
            from foamai.config import get_settings
            settings = get_settings()
            
            if settings.paraview_path and Path(settings.paraview_path).exists():
                paraview_path = Path(settings.paraview_path)
                if platform.system() == "Windows":
                    paraview_exe = paraview_path / "bin" / "paraview.exe"
                elif platform.system() == "Darwin":  # macOS
                    if paraview_path.suffix == ".app":
                        paraview_exe = paraview_path / "Contents" / "MacOS" / "paraview"
                    else:
                        paraview_exe = paraview_path / "bin" / "paraview"
                else:
                    paraview_exe = paraview_path / "bin" / "paraview"
                
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
        
        with open(script_path, "w") as f:
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
    parsed_params = state["parsed_parameters"]
    flow_type = parsed_params.get("flow_type", "laminar")
    
    script = f'''
# ParaView Python script for {geometry_type} visualization
import paraview.simple as pv

# Disable automatic camera reset
pv._DisableFirstRenderCameraReset()

# Create OpenFOAM reader
foam_case = pv.OpenFOAMReader(FileName="{case_directory.as_posix()}/{case_directory.name}.foam")

# Update pipeline to read data
foam_case.UpdatePipeline()

# Get latest time step
time_values = foam_case.TimestepValues
if time_values:
    latest_time = max(time_values)
    foam_case.SMProxy.InvokeEvent('UserEvent', 'HideWidget')

# Create render view
render_view = pv.CreateView('RenderView')
render_view.ViewSize = [1200, 800]
render_view.Background = [1.0, 1.0, 1.0]  # White background

# Display the mesh
foam_display = pv.Show(foam_case, render_view)

# Set animation scene to latest time
animation_scene = pv.GetAnimationScene()
animation_scene.UpdateAnimationUsingDataTimeSteps()
if time_values:
    animation_scene.AnimationTime = latest_time
    
# Update the pipeline to load data at the correct time
pv.UpdatePipeline(time=latest_time, proxy=foam_case)

# Generate pressure visualization
try:
    # Color by pressure
    pv.ColorBy(foam_display, ('POINTS', 'p'))
    
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
    calculator = pv.Calculator(Input=foam_case)
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

# Generate streamlines for external flows
try:
    if "{geometry_type}" in ["cylinder", "airfoil", "sphere"]:
        # Create streamline tracer
        streamlines = pv.StreamTracer(Input=calculator)
        streamlines.Vectors = ['POINTS', 'U']
        streamlines.IntegrationDirection = 'FORWARD'
        streamlines.MaximumStreamlineLength = {parsed_params.get("geometry_dimensions", {}).get("domain_width", 2.0)}
        
        # Position seed points upstream
        streamlines.SeedType = 'Line'
        streamlines.SeedType.Point1 = [-1.0, -0.5, 0.0]
        streamlines.SeedType.Point2 = [-1.0, 0.5, 0.0]
        streamlines.SeedType.Resolution = 20
        
        # Display streamlines
        stream_display = pv.Show(streamlines, render_view)
        stream_display.ColorArrayName = ['POINTS', 'U_magnitude']
        
        # Reset camera and render
        render_view.ResetCamera()
        pv.Render()
        
        # Save streamlines image
        pv.SaveScreenshot("{case_directory.as_posix()}/visualization/streamlines.png")
except:
    print("Streamlines not available")

# Generate wall pressure distribution for bluff bodies
try:
    if "{geometry_type}" in ["cylinder", "airfoil", "sphere"]:
        # Extract surface
        extract_surface = pv.ExtractSurface(Input=foam_case)
        
        # Display surface colored by pressure
        surface_display = pv.Show(extract_surface, render_view)
        pv.ColorBy(surface_display, ('POINTS', 'p'))
        
        # Reset camera and render
        render_view.ResetCamera()
        pv.Render()
        
        # Save surface pressure image
        pv.SaveScreenshot("{case_directory.as_posix()}/visualization/surface_pressure.png")
except:
    print("Surface pressure not available")

print("Visualization generation completed successfully")
'''
    
    return script


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
        configured_path = os.environ.get("PARAVIEW_PATH")
    
    # Add common ParaView paths
    paraview_paths = [
        "/usr/bin",
        "/opt/paraview/bin",
        "/usr/local/bin",
        "/Applications/ParaView.app/Contents/MacOS"  # macOS default
    ]
    
    # Add configured ParaView path if it exists
    if configured_path:
        if configured_path.endswith(".app"):
            # Handle macOS .app bundle
            paraview_bin = os.path.join(configured_path, "Contents", "MacOS")
            if os.path.exists(paraview_bin):
                paraview_paths.insert(0, paraview_bin)
        elif not configured_path.startswith("/"):
            # Windows path - add bin directory
            paraview_bin = os.path.join(configured_path, "bin")
            if os.path.exists(paraview_bin):
                paraview_paths.insert(0, paraview_bin)
        else:
            # Linux/other path - add bin directory
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