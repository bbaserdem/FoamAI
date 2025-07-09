"""User Approval Agent - Shows configuration and waits for user approval."""

import json
import sys
from pathlib import Path
from typing import Dict, Any
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .state import CFDState, CFDStep

# Use the same console instance as the CLI
console = Console(file=sys.stdout)


def user_approval_agent(state: CFDState) -> CFDState:
    """
    User Approval Agent.
    
    Displays the selected solver, mesh configuration, and hyperparameters
    to the user and waits for approval or change requests.
    """
    try:
        if state["verbose"]:
            logger.info("User Approval: Displaying configuration for user review")
        
        # Display configuration summary
        display_configuration_summary(state)
        
        # Get user input
        user_decision = get_user_decision()
        
        if user_decision == "approve":
            if state["verbose"]:
                logger.info("User Approval: Configuration approved, proceeding to simulation")
            
            return {
                **state,
                "user_approved": True,
                "errors": []
            }
        elif user_decision == "changes":
            # User wants to make changes - collect feedback
            change_requests = get_change_requests()
            
            if state["verbose"]:
                logger.info(f"User Approval: Change requests received: {change_requests}")
            
            # For now, we'll go back to solver selection to re-process
            # In a more sophisticated implementation, we could route to specific agents
            # based on the type of change requested
            return {
                **state,
                "user_approved": False,
                "current_step": CFDStep.SOLVER_SELECTION,
                "warnings": state["warnings"] + [f"User requested changes: {change_requests}"],
                "errors": []
            }
        else:
            # User cancelled
            return {
                **state,
                "user_approved": False,
                "current_step": CFDStep.ERROR,
                "errors": state["errors"] + ["User cancelled the simulation"]
            }
        
    except Exception as e:
        logger.error(f"User Approval error: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"User approval failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        }


def display_configuration_summary(state: CFDState) -> None:
    """Display comprehensive configuration summary using rich tables."""
    
    # Create stderr console to avoid stdout interference
    stderr_console = Console(file=sys.stderr)
    
    # Display solver configuration
    display_solver_config(state, stderr_console)
    
    # Display mesh configuration
    display_mesh_config(state, stderr_console)
    
    # Display STL geometry if present
    if state.get("geometry_source") == "stl":
        display_stl_geometry(state, stderr_console)
    
    # Display boundary conditions
    display_boundary_conditions(state, stderr_console)
    
    # Display simulation parameters
    display_simulation_parameters(state, stderr_console)
    
    # Display generated files
    display_generated_files(state, stderr_console)


def display_solver_config(state: CFDState, console: Console) -> None:
    """Display solver selection and settings."""
    solver_settings = state.get("solver_settings", {})
    
    if solver_settings:
        table = Table(title="🔧 Solver Configuration", show_header=True, header_style="bold cyan")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="green")
        
        # Basic solver info
        solver_name = solver_settings.get("solver", "Unknown")
        table.add_row("Selected Solver", f"[bold]{solver_name}[/bold]")
        
        # Solver type and description
        solver_type = solver_settings.get("solver_type", "Unknown")
        table.add_row("Solver Type", str(solver_type))
        
        # Time stepping
        control_dict = solver_settings.get("controlDict", {})
        if control_dict:
            start_time = control_dict.get("startTime", 0)
            end_time = control_dict.get("endTime", 10)
            delta_t = control_dict.get("deltaT", 0.001)
            write_interval = control_dict.get("writeInterval", 1)
            
            table.add_row("Start Time", f"{start_time} s" if start_time is not None else "N/A")
            table.add_row("End Time", f"{end_time} s" if end_time is not None else "N/A")
            table.add_row("Time Step", f"{delta_t} s" if delta_t is not None else "N/A")
            table.add_row("Write Interval", f"{write_interval} s" if write_interval is not None else "N/A")
        
        # Turbulence model
        turbulence_props = solver_settings.get("turbulenceProperties", {})
        if turbulence_props:
            simulation_type = turbulence_props.get("simulationType", "Unknown")
            table.add_row("Turbulence Model", str(simulation_type) if simulation_type is not None else "N/A")
        
        console.print(table)
    else:
        console.print("[yellow]⚠️  No solver settings available[/yellow]")


def display_mesh_config(state: CFDState, console: Console) -> None:
    """Display mesh configuration."""
    
    mesh_config = state.get("mesh_config", {})
    if not mesh_config:
        return
    
    # Create mesh table
    mesh_table = Table(title="🔲 Mesh Configuration", show_header=True)
    mesh_table.add_column("Property", style="cyan", min_width=20)
    mesh_table.add_column("Value", style="white", min_width=30)
    
    # Basic mesh info
    mesh_type = mesh_config.get("type", "N/A")
    mesh_table.add_row("Mesh Type", mesh_type)
    
    geometry_type = mesh_config.get("geometry_type", "N/A")
    mesh_table.add_row("Geometry Type", str(geometry_type))
    
    # Handle both STL and parametric mesh configurations
    if geometry_type == "stl":
        # STL mesh configuration
        background_mesh = mesh_config.get("background_mesh", {})
        if background_mesh:
            n_cells_x = background_mesh.get("n_cells_x", 0)
            n_cells_y = background_mesh.get("n_cells_y", 0) 
            n_cells_z = background_mesh.get("n_cells_z", 0)
            mesh_table.add_row("Background Cells", f"{n_cells_x} × {n_cells_y} × {n_cells_z}")
            
            base_size = background_mesh.get("base_cell_size", 0)
            if base_size > 0:
                mesh_table.add_row("Base Cell Size", f"{base_size:.6f} m")
        
        # Refinement settings
        snappy_settings = mesh_config.get("snappy_settings", {})
        if snappy_settings:
            refinement_levels = snappy_settings.get("refinement_levels", {})
            if refinement_levels:
                min_level = refinement_levels.get("min", 0)
                max_level = refinement_levels.get("max", 0)
                mesh_table.add_row("Refinement Levels", f"{min_level} - {max_level}")
            
            add_layers = snappy_settings.get("add_layers", False)
            mesh_table.add_row("Boundary Layers", "✓ Yes" if add_layers else "✗ No")
        
        # STL file path
        stl_file_path = mesh_config.get("stl_file_path")
        if stl_file_path:
            mesh_table.add_row("STL File", str(stl_file_path))
    
    else:
        # Parametric mesh configuration (existing logic)
        is_2d = mesh_config.get("is_2d", False)
        mesh_table.add_row("Dimension", "2D" if is_2d else "3D")
        
        is_external = mesh_config.get("is_external_flow", False)
        mesh_table.add_row("Flow Type", "External" if is_external else "Internal")
        
        # Cell counts
        total_cells = mesh_config.get("total_cells", 0)
        if total_cells > 0:
            mesh_table.add_row("Total Cells", f"{total_cells:,}")
        
        # Domain dimensions
        dimensions = mesh_config.get("dimensions", {})
        if dimensions:
            domain_length = dimensions.get("domain_length", 0)
            domain_height = dimensions.get("domain_height", 0)
            if domain_length > 0 and domain_height > 0:
                mesh_table.add_row("Domain Size", f"{domain_length:.2f} × {domain_height:.2f} m")
        
        # Resolution
        resolution = mesh_config.get("resolution", {})
        if resolution:
            background_res = resolution.get("background", 0)
            if background_res > 0:
                mesh_table.add_row("Background Resolution", str(background_res))
    
    # Quality metrics (common to both)
    quality_metrics = mesh_config.get("quality_metrics", {})
    if quality_metrics:
        aspect_ratio = quality_metrics.get("aspect_ratio", 0)
        if aspect_ratio > 0:
            mesh_table.add_row("Aspect Ratio", f"{aspect_ratio:.2f}")
        
        quality_score = quality_metrics.get("quality_score", 0)
        if quality_score > 0:
            mesh_table.add_row("Quality Score", f"{quality_score:.2f}")
    
    console.print(mesh_table)
    console.print()


def display_stl_geometry(state: CFDState, console: Console) -> None:
    """Display STL geometry information."""
    
    stl_geometry = state.get("stl_geometry", {})
    geometry_info = state.get("geometry_info", {})
    
    if not stl_geometry:
        return
    
    # Create STL geometry table
    stl_table = Table(title="🔷 STL Geometry Information", show_header=True)
    stl_table.add_column("Property", style="cyan", min_width=20)
    stl_table.add_column("Value", style="white", min_width=30)
    
    # Basic geometry info
    stl_table.add_row("File Path", str(stl_geometry.get("file_path", "N/A")))
    stl_table.add_row("Triangles", str(stl_geometry.get("num_triangles", 0)))
    stl_table.add_row("Vertices", str(stl_geometry.get("num_vertices", 0)))
    
    # Dimensions
    bbox = stl_geometry.get("bounding_box", {})
    if bbox:
        dimensions = bbox.get("dimensions", [0, 0, 0])
        stl_table.add_row("Dimensions (L×W×H)", f"{dimensions[0]:.3f} × {dimensions[1]:.3f} × {dimensions[2]:.3f} m")
    
    char_length = stl_geometry.get("characteristic_length", 0)
    if char_length > 0:
        stl_table.add_row("Characteristic Length", f"{char_length:.3f} m")
    
    surface_area = stl_geometry.get("surface_area", 0)
    if surface_area > 0:
        stl_table.add_row("Surface Area", f"{surface_area:.6f} m²")
    
    volume = stl_geometry.get("volume")
    if volume:
        stl_table.add_row("Volume", f"{volume:.6f} m³")
    
    # Mesh quality
    is_watertight = stl_geometry.get("is_watertight", False)
    stl_table.add_row("Watertight", "✓ Yes" if is_watertight else "✗ No")
    
    # Flow context
    flow_context = geometry_info.get("flow_context", {})
    if flow_context:
        is_external = flow_context.get("is_external_flow", True)
        stl_table.add_row("Flow Type", "External" if is_external else "Internal")
        
        flow_direction = flow_context.get("flow_direction", "x")
        stl_table.add_row("Flow Direction", f"{flow_direction.upper()}-axis")
    
    # Mesh recommendations
    mesh_rec = stl_geometry.get("mesh_recommendations", {})
    if mesh_rec:
        base_size = mesh_rec.get("base_cell_size", 0)
        if base_size > 0:
            stl_table.add_row("Base Cell Size", f"{base_size:.6f} m")
        
        estimated_cells = mesh_rec.get("estimated_cells", 0)
        if estimated_cells > 0:
            stl_table.add_row("Estimated Cells", f"{estimated_cells:,}")
    
    console.print(stl_table)
    console.print()
    
    # Display STL surfaces if available
    stl_surfaces = geometry_info.get("stl_surfaces", [])
    if stl_surfaces:
        surfaces_table = Table(title="🔷 STL Surfaces & Boundary Conditions", show_header=True)
        surfaces_table.add_column("Surface", style="cyan", min_width=15)
        surfaces_table.add_column("Type", style="green", min_width=15)
        surfaces_table.add_column("Triangles", style="white", min_width=10)
        surfaces_table.add_column("Recommended BC", style="yellow", min_width=15)
        surfaces_table.add_column("Description", style="white", min_width=20)
        
        for surface in stl_surfaces:
            name = surface.get("name", "Unknown")
            triangle_count = surface.get("triangle_count", 0)
            bc_info = surface.get("recommended_bc", {})
            bc_type = bc_info.get("U", "N/A")
            description = bc_info.get("description", "N/A")
            
            surfaces_table.add_row(
                name,
                name.replace("_", " ").title(),
                str(triangle_count),
                bc_type,
                description
            )
        
        console.print(surfaces_table)
        console.print()


def display_boundary_conditions(state: CFDState, console: Console) -> None:
    """Display boundary conditions."""
    boundary_conditions = state.get("boundary_conditions", {})
    
    if boundary_conditions:
        table = Table(title="🔄 Boundary Conditions", show_header=True, header_style="bold cyan")
        table.add_column("Boundary", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Value", style="green")
        
        # Process each field (U, p, etc.)
        for field, field_data in boundary_conditions.items():
            if isinstance(field_data, dict) and "boundaryField" in field_data:
                boundary_field = field_data["boundaryField"]
                
                # Add field header
                table.add_row(f"[bold]{field.upper()} Field[/bold]", "", "")
                
                # Add each boundary
                for boundary_name, boundary_config in boundary_field.items():
                    boundary_type = boundary_config.get("type", "Unknown")
                    
                    # Get value information
                    value_info = ""
                    if "value" in boundary_config:
                        value = boundary_config["value"]
                        if value is not None:
                            if isinstance(value, str):
                                value_info = value
                            elif isinstance(value, (list, tuple)):
                                value_info = f"({', '.join(str(v) for v in value)})"
                            else:
                                value_info = str(value)
                    elif "uniformValue" in boundary_config:
                        uniform_value = boundary_config["uniformValue"]
                        value_info = str(uniform_value) if uniform_value is not None else ""
                    
                    table.add_row(f"  {boundary_name}", str(boundary_type), value_info)
        
        console.print(table)
    else:
        console.print("[yellow]⚠️  No boundary conditions available[/yellow]")


def display_simulation_parameters(state: CFDState, console: Console) -> None:
    """Display key simulation parameters."""
    parsed_params = state.get("parsed_parameters", {})
    
    if parsed_params:
        table = Table(title="⚙️ Simulation Parameters", show_header=True, header_style="bold cyan")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="green")
        
        # Flow parameters
        flow_type = parsed_params.get("flow_type", "Unknown")
        table.add_row("Flow Type", str(flow_type) if flow_type is not None else "Unknown")
        
        analysis_type = parsed_params.get("analysis_type", "Unknown")
        table.add_row("Analysis Type", str(analysis_type) if analysis_type is not None else "Unknown")
        
        # Physical properties
        velocity = parsed_params.get("velocity")
        if velocity is not None:
            table.add_row("Velocity", f"{velocity:.2f} m/s")
        
        reynolds_number = parsed_params.get("reynolds_number")
        if reynolds_number is not None:
            table.add_row("Reynolds Number", f"{reynolds_number:.0f}")
        
        pressure = parsed_params.get("pressure")
        if pressure is not None:
            table.add_row("Reference Pressure", f"{pressure:.2f} Pa")
        
        # Fluid properties
        density = parsed_params.get("density")
        if density is not None:
            table.add_row("Density", f"{density:.3f} kg/m³")
        
        viscosity = parsed_params.get("viscosity")
        if viscosity is not None:
            table.add_row("Viscosity", f"{viscosity:.6f} kg/(m·s)")
        
        console.print(table)
    else:
        console.print("[yellow]⚠️  No simulation parameters available[/yellow]")


def display_generated_files(state: CFDState, console: Console) -> None:
    """Display file locations."""
    case_directory = state.get("case_directory", "")
    
    if case_directory:
        console.print(f"\n📁 [bold]Case Directory:[/bold] {case_directory}")
        
        # List key files
        case_path = Path(case_directory)
        if case_path.exists():
            key_files = [
                "system/blockMeshDict",
                "system/snappyHexMeshDict",
                "system/controlDict",
                "system/fvSchemes",
                "system/fvSolution",
                "0/U",
                "0/p",
                "constant/turbulenceProperties",
                "constant/transportProperties"
            ]
            
            existing_files = []
            for file_path in key_files:
                full_path = case_path / file_path
                if full_path.exists():
                    existing_files.append(f"  ✅ {file_path}")
            
            if existing_files:
                console.print("\n[bold]Generated Files:[/bold]")
                for file_info in existing_files:
                    console.print(file_info)


def get_user_decision() -> str:
    """Get user decision on whether to proceed, make changes, or cancel."""
    # Create a console that outputs to stderr to avoid interference with progress
    stderr_console = Console(file=sys.stderr)
    
    stderr_console.print("\n" + "="*80)
    stderr_console.print(
        Panel(
            "[bold yellow]What would you like to do?[/bold yellow]\n\n"
            "[green]1. [bold]Approve[/bold] - Proceed with simulation using this configuration[/green]\n"
            "[blue]2. [bold]Request Changes[/bold] - Modify the configuration[/blue]\n"
            "[red]3. [bold]Cancel[/bold] - Cancel the simulation[/red]",
            title="User Decision",
            border_style="yellow"
        )
    )
    
    # Force console output to be displayed
    stderr_console.file.flush()
    
    while True:
        try:
            # Use regular input() for more reliable user interaction
            print("\nEnter your choice [1/2/3/approve/changes/cancel] (default: 1): ", end="", file=sys.stderr)
            sys.stderr.flush()
            choice = input().strip()
            
            # Handle empty input (use default)
            if not choice:
                choice = "1"
            
            # Process the choice
            if choice.lower() in ["1", "approve"]:
                return "approve"
            elif choice.lower() in ["2", "changes"]:
                return "changes"
            elif choice.lower() in ["3", "cancel"]:
                return "cancel"
            else:
                print("Invalid choice. Please enter 1, 2, 3, or approve/changes/cancel.", file=sys.stderr)
                continue
                
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled by user.", file=sys.stderr)
            return "cancel"
        except Exception as e:
            print(f"Error reading input: {e}", file=sys.stderr)
            return "cancel"


def get_change_requests() -> str:
    """Get change requests from the user."""
    # Create a console that outputs to stderr to avoid interference with progress
    stderr_console = Console(file=sys.stderr)
    
    stderr_console.print(
        Panel(
            "[bold blue]Describe the changes you'd like to make:[/bold blue]\n\n"
            "You can request changes to:\n"
            "• Solver selection (e.g., 'use transient solver instead')\n"
            "• Mesh resolution (e.g., 'make mesh finer')\n"
            "• Boundary conditions (e.g., 'increase inlet velocity')\n"
            "• Simulation parameters (e.g., 'run for longer time')\n\n"
            "Be as specific as possible about what you want to change.",
            title="Change Requests",
            border_style="blue"
        )
    )
    
    # Force console output to be displayed
    stderr_console.file.flush()
    
    try:
        print("\nDescribe your requested changes (press Enter for default): ", end="", file=sys.stderr)
        sys.stderr.flush()
        change_requests = input().strip()
        
        if not change_requests:
            change_requests = "No specific changes"
            
        return change_requests
        
    except (KeyboardInterrupt, EOFError):
        print("\nOperation cancelled by user.", file=sys.stderr)
        return "User cancelled"
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        return "Error reading input" 