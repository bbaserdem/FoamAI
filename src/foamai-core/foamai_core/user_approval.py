"""User Approval Agent - Shows configuration and waits for user approval."""

import json
from pathlib import Path
from typing import Dict, Any
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm

from .state import CFDState, CFDStep

console = Console()


def user_approval_agent(state: CFDState) -> CFDState:
    """
    User Approval Agent.
    
    Displays the selected solver, mesh configuration, and hyperparameters
    to the user and waits for approval or change requests.
    
    In remote execution mode, this creates a summary for the UI and
    waits for user approval through the desktop interface.
    """
    try:
        if state["verbose"]:
            logger.info("User Approval: Displaying configuration for user review")
        
        # Check if we're in remote execution mode (desktop UI)
        execution_mode = state.get("execution_mode", "local")
        
        if execution_mode == "remote":
            # Remote execution - prepare data for desktop UI
            if state["verbose"]:
                logger.info("User Approval: Remote execution mode - preparing configuration for UI")
            
            # Generate configuration summary for UI
            config_summary = generate_configuration_summary(state)
            
            # Extract mesh and simulation information from config-only results
            mesh_info = {}
            simulation_results = state.get("simulation_results", {})
            
            # Get mesh information from the configuration phase results
            if simulation_results.get("steps", {}).get("mesh_generation"):
                mesh_gen_result = simulation_results["steps"]["mesh_generation"]
                mesh_info = {
                    "mesh_type": state.get("mesh_config", {}).get("type", "blockMesh"),
                    "total_cells": mesh_gen_result.get("mesh_info", {}).get("total_cells", 0),
                    "quality_score": mesh_gen_result.get("mesh_info", {}).get("quality_score", 0.0)
                }
                if state["verbose"]:
                    logger.info(f"User Approval: Extracted mesh info from config results: {mesh_info}")
            else:
                # Fallback to mesh_config if simulation_results not available
                mesh_config = state.get("mesh_config", {})
                if mesh_config:
                    mesh_info = {
                        "mesh_type": mesh_config.get("type", "blockMesh"),
                        "total_cells": mesh_config.get("total_cells", 0),
                        "quality_score": 0.0  # Default if not available
                    }
                    if state["verbose"]:
                        logger.info(f"User Approval: Using fallback mesh info from config: {mesh_info}")
            
            # Add case file information if available
            case_info = {}
            if state.get("project_name"):
                case_info = {
                    "project_name": state["project_name"],
                    "foam_file_path": f"/home/ubuntu/foam_projects/{state['project_name']}/active_run/{state['project_name']}.foam"
                }
            
            # Update config summary with mesh and case info
            config_summary.update({
                "mesh_info": mesh_info,
                "case_info": case_info
            })
            
            if state["verbose"]:
                logger.info(f"User Approval: Generated config summary with keys: {list(config_summary.keys())}")
                logger.info("User Approval: Workflow will pause for user review in desktop UI")
            
            # Set state to indicate waiting for user approval
            # This will pause the workflow until the user clicks "Run Simulation"
            return {
                **state,
                "user_approved": False,
                "awaiting_user_approval": True,
                "config_summary": config_summary,
                "current_step": CFDStep.USER_APPROVAL,
                "workflow_paused": True,
                "errors": []
            }
        else:
            # Local execution - use CLI interface
            display_configuration_summary(state)
            
            # Get user input
            user_decision = get_user_decision()
            
            if user_decision == "approve":
                if state["verbose"]:
                    logger.info("User Approval: Configuration approved, proceeding to simulation")
                
                return {
                    **state,
                    "user_approved": True,
                    "config_only_mode": False,  # Full simulation mode after approval
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


def generate_configuration_explanation(state: CFDState) -> str:
    """Generate explanatory text about defaults and decisions made using OpenAI."""
    try:
        # Import OpenAI dependencies
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
        
        # Get settings for API key
        import sys
        sys.path.append('src')
        from .config import get_settings
        settings = get_settings()
        
        # Create LLM
        llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=400
        )
        
        # Extract relevant information for explanation
        parsed_params = state.get("parsed_parameters", {})
        mesh_config = state.get("mesh_config", {})
        solver_settings = state.get("solver_settings", {})
        geometry_info = state.get("geometry_info", {})
        original_prompt = state.get("user_prompt", "")
        
        # Create context for OpenAI
        context = {
            "original_prompt": original_prompt,
            "geometry_type": str(geometry_info.get("type", "Unknown")),
            "dimensions": geometry_info.get("dimensions", {}),
            "solver": solver_settings.get("solver", "Unknown"),
            "flow_type": str(parsed_params.get("flow_type", "Unknown")),
            "analysis_type": str(parsed_params.get("analysis_type", "Unknown")),
            "mesh_type": mesh_config.get("type", "Unknown"),
            "total_cells": mesh_config.get("total_cells", 0),
            "velocity": parsed_params.get("velocity"),
            "reynolds_number": parsed_params.get("reynolds_number"),
            "density": parsed_params.get("density"),
            "viscosity": parsed_params.get("viscosity"),
            "time_step": solver_settings.get("controlDict", {}).get("deltaT"),
            "end_time": solver_settings.get("controlDict", {}).get("endTime"),
            "domain_size_multiplier": geometry_info.get("flow_context", {}).get("domain_size_multiplier")
        }
        
        # Create prompt for OpenAI
        system_message = SystemMessage(content="""You are an expert CFD engineer explaining simulation configuration decisions to users. 
        
        Your task is to write a brief, clear explanation (2-3 sentences) of the key assumptions, defaults, and decisions made in setting up this CFD simulation that weren't explicitly specified by the user.
        
        Focus on:
        - Important default values that were used (like fluid properties, domain size, time stepping)
        - Key assumptions made about the physics (steady vs unsteady, laminar vs turbulent)
        - Mesh and solver choices that were made automatically
        
        Write in a friendly, professional tone as if explaining to a colleague. Start with "Based on your prompt, I made the following key decisions:" and be specific about the values used.""")
        
        human_message = HumanMessage(content=f"""
        User's original prompt: "{original_prompt}"
        
        Configuration details:
        - Geometry: {context['geometry_type']} with dimensions {context['dimensions']}
        - Solver: {context['solver']} for {context['flow_type']} {context['analysis_type']} analysis
        - Mesh: {context['mesh_type']} with {context['total_cells']:,} cells
        - Flow properties: velocity={context['velocity']} m/s, Re={context['reynolds_number']}, density={context['density']} kg/m³, viscosity={context['viscosity']} Pa·s
        - Time settings: dt={context['time_step']} s, end_time={context['end_time']} s
        - Domain size: {context['domain_size_multiplier']}x object size
        
        Explain the key defaults and decisions made that the user didn't explicitly specify.
        """)
        
        # Get response from OpenAI
        response = llm.invoke([system_message, human_message])
        
        return response.content.strip()
        
    except Exception as e:
        logger.warning(f"Could not generate configuration explanation: {e}")
        return "Configuration explanation unavailable (OpenAI API error)."


def generate_configuration_summary(state: CFDState) -> Dict[str, Any]:
    """Generate a structured configuration summary for the desktop UI."""
    summary = {
        "solver_info": {},
        "mesh_info": {},
        "boundary_conditions": {},
        "simulation_parameters": {},
        "file_locations": {},
        "ai_explanation": ""
    }
    
    try:
        # Generate AI explanation
        summary["ai_explanation"] = generate_configuration_explanation(state)
        
        # Solver information
        solver_settings = state.get("solver_settings", {})
        if solver_settings:
            control_dict = solver_settings.get("controlDict", {})
            turbulence_props = solver_settings.get("turbulenceProperties", {})
            
            summary["solver_info"] = {
                "solver_name": solver_settings.get("solver", "Unknown"),
                "solver_type": solver_settings.get("solver_type", "Unknown"),
                "start_time": control_dict.get("startTime", 0),
                "end_time": control_dict.get("endTime", 10),
                "time_step": control_dict.get("deltaT", 0.001),
                "write_interval": control_dict.get("writeInterval", 1),
                "turbulence_model": turbulence_props.get("simulationType", "Unknown")
            }
        
        # Mesh information
        mesh_config = state.get("mesh_config", {})
        mesh_quality = state.get("mesh_quality", {})
        if mesh_config:
            summary["mesh_info"] = {
                "mesh_type": mesh_config.get("type", "Unknown"),
                "total_cells": mesh_config.get("total_cells", 0),
                "geometry_type": str(mesh_config.get("geometry_type", "Unknown")),
                "dimensions": mesh_config.get("dimensions", {}),
                "quality_score": mesh_quality.get("quality_score", 0) if mesh_quality else 0
            }
        
        # Boundary conditions
        boundary_conditions = state.get("boundary_conditions", {})
        if boundary_conditions:
            summary["boundary_conditions"] = boundary_conditions
        
        # Simulation parameters
        parsed_params = state.get("parsed_parameters", {})
        if parsed_params:
            summary["simulation_parameters"] = {
                "flow_type": str(parsed_params.get("flow_type", "Unknown")),
                "analysis_type": str(parsed_params.get("analysis_type", "Unknown")),
                "velocity": parsed_params.get("velocity"),
                "reynolds_number": parsed_params.get("reynolds_number"),
                "pressure": parsed_params.get("pressure"),
                "density": parsed_params.get("density"),
                "viscosity": parsed_params.get("viscosity")
            }
        
        # File locations
        case_directory = state.get("case_directory", "")
        if case_directory:
            summary["file_locations"] = {
                "case_directory": case_directory
            }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating configuration summary: {str(e)}")
        return {
            "error": f"Failed to generate configuration summary: {str(e)}",
            "ai_explanation": "Configuration summary unavailable due to error."
        }


def display_configuration_summary(state: CFDState) -> None:
    """Display a comprehensive summary of the configuration."""
    
    console.print("\n" + "="*80)
    console.print(
        Panel(
            "[bold blue]SIMULATION CONFIGURATION REVIEW[/bold blue]\n"
            "Please review the following configuration before proceeding with the simulation.",
            title="Configuration Review",
            border_style="blue"
        )
    )
    
    # Display AI explanation of defaults and decisions
    display_ai_explanation(state)
    
    # Display solver information
    display_solver_info(state)
    
    # Display mesh information
    display_mesh_info(state)
    
    # Display STL rotation if applicable
    display_stl_rotation_info(state)
    
    # Display boundary conditions
    display_boundary_conditions(state)
    
    # Display simulation parameters
    display_simulation_parameters(state)
    
    # Display file locations
    display_file_locations(state)


def display_ai_explanation(state: CFDState) -> None:
    """Display AI-generated explanation of configuration decisions."""
    console.print("\n")
    
    # Generate explanation
    explanation = generate_configuration_explanation(state)
    
    # Display the explanation
    console.print(
        Panel(
            f"[bold yellow]🤖 Configuration Explanation[/bold yellow]\n\n"
            f"[white]{explanation}[/white]",
            title="AI Analysis",
            border_style="yellow",
            padding=(1, 2)
        )
    )


def display_solver_info(state: CFDState) -> None:
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


def display_mesh_info(state: CFDState) -> None:
    """Display mesh configuration."""
    mesh_config = state.get("mesh_config", {})
    mesh_quality = state.get("mesh_quality", {})
    
    if mesh_config:
        table = Table(title="🔲 Mesh Configuration", show_header=True, header_style="bold cyan")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="green")
        
        # Basic mesh info
        mesh_type = mesh_config.get("type", "Unknown")
        table.add_row("Mesh Type", str(mesh_type) if mesh_type is not None else "Unknown")
        
        total_cells = mesh_config.get("total_cells", 0)
        table.add_row("Total Cells", f"{total_cells:,}" if total_cells is not None else "N/A")
        
        # Geometry info
        geometry_type = mesh_config.get("geometry_type", "Unknown")
        if hasattr(geometry_type, 'value'):
            geometry_type = geometry_type.value
        table.add_row("Geometry Type", str(geometry_type) if geometry_type is not None else "Unknown")
        
        # Dimensions
        dimensions = mesh_config.get("dimensions", {})
        if dimensions:
            for key, value in dimensions.items():
                if isinstance(value, (int, float)) and value is not None:
                    table.add_row(f"  {key.replace('_', ' ').title()}", f"{value:.3f} m")
                elif value is not None:
                    table.add_row(f"  {key.replace('_', ' ').title()}", str(value))
        
        # Mesh quality
        if mesh_quality:
            quality_score = mesh_quality.get("quality_score", 0)
            if quality_score is not None:
                table.add_row("Quality Score", f"{quality_score:.2f}/1.0")
            
            aspect_ratio = mesh_quality.get("aspect_ratio", 0)
            if aspect_ratio is not None and aspect_ratio > 0:
                table.add_row("Aspect Ratio", f"{aspect_ratio:.2f}")
        
        console.print(table)
    else:
        console.print("[yellow]⚠️  No mesh configuration available[/yellow]")


def display_stl_rotation_info(state: CFDState) -> None:
    """Display STL rotation information if applicable."""
    geometry_info = state.get("geometry_info", {})
    parsed_params = state.get("parsed_parameters", {})
    mesh_config = state.get("mesh_config", {})
    
    # Check if this is an STL file
    if not geometry_info.get("is_custom_geometry") or not geometry_info.get("stl_file"):
        return
    
    # Get rotation info from either parsed parameters or mesh config
    rotation_info = parsed_params.get("rotation_info", {}) or mesh_config.get("rotation_info", {})
    
    table = Table(title="🔄 STL Geometry Rotation", show_header=True, header_style="bold cyan")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")
    
    # Display STL file
    stl_file = geometry_info.get("stl_file", "Unknown")
    table.add_row("STL File", str(stl_file))
    
    # Display rotation status
    if rotation_info.get("rotate", False):
        angle = rotation_info.get("rotation_angle", 0)
        axis = rotation_info.get("rotation_axis", "z")
        table.add_row("Rotation Angle", f"{angle}°")
        table.add_row("Rotation Axis", axis.upper())
        table.add_row("Rotation Center", "Origin (0, 0, 0)")
    else:
        table.add_row("Rotation", "No rotation applied")
        table.add_row("", "[dim]Tip: Add 'rotate 90 degrees' to your prompt[/dim]")
    
    console.print(table)
    
    # Add warning about orientation
    console.print(
        Panel(
            "[yellow]⚠️  STL Orientation Check[/yellow]\n\n"
            "Please verify that your geometry is oriented correctly:\n"
            "• The inlet (red wall in ParaView) should face the front of your object\n"
            "• For vehicles, the front should face the inlet for proper aerodynamic simulation\n"
            "• Use rotation to adjust orientation if needed (e.g., 'rotate 90 degrees')",
            border_style="yellow"
        )
    )


def display_boundary_conditions(state: CFDState) -> None:
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


def display_simulation_parameters(state: CFDState) -> None:
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


def display_file_locations(state: CFDState) -> None:
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
    console.print("\n" + "="*80)
    console.print(
        Panel(
            "[bold yellow]What would you like to do?[/bold yellow]\n\n"
            "[green]1. [bold]Approve[/bold] - Proceed with simulation using this configuration[/green]\n"
            "[blue]2. [bold]Request Changes[/bold] - Modify the configuration[/blue]\n"
            "[red]3. [bold]Cancel[/bold] - Cancel the simulation[/red]",
            title="User Decision",
            border_style="yellow"
        )
    )
    
    while True:
        choice = Prompt.ask(
            "\nEnter your choice",
            choices=["1", "2", "3", "approve", "changes", "cancel"],
            default="1"
        )
        
        if choice in ["1", "approve"]:
            return "approve"
        elif choice in ["2", "changes"]:
            return "changes"
        elif choice in ["3", "cancel"]:
            return "cancel"


def get_change_requests() -> str:
    """Get change requests from the user."""
    console.print(
        Panel(
            "[bold blue]Describe the changes you'd like to make:[/bold blue]\n\n"
            "You can request changes to:\n"
            "• Solver selection (e.g., 'use transient solver instead')\n"
            "• Mesh resolution (e.g., 'make mesh finer')\n"
            "• Boundary conditions (e.g., 'increase inlet velocity')\n"
            "• Simulation parameters (e.g., 'run for longer time')\n"
            "• STL rotation (e.g., 'rotate 90 degrees around z-axis')\n\n"
            "Be as specific as possible about what you want to change.",
            title="Change Requests",
            border_style="blue"
        )
    )
    
    change_requests = Prompt.ask(
        "\nDescribe your requested changes",
        default="No specific changes"
    )
    
    return change_requests 