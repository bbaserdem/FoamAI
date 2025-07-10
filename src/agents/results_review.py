"""Results Review Agent - Handles iterative workflow and conversation continuation."""

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


def results_review_agent(state: CFDState) -> CFDState:
    """
    Results Review Agent.
    
    Shows simulation results and asks user if they want to make changes
    for another iteration or complete the session.
    """
    try:
        if state["verbose"]:
            logger.info("Results Review: Displaying results and prompting for next action")
        
        # Display current results summary
        display_iteration_summary(state)
        
        # Ask user for next action
        user_choice = prompt_for_next_action(state)
        
        if user_choice == "continue":
            # User wants to make changes - prompt for new input
            new_prompt = get_new_user_prompt(state)
            
            if new_prompt:
                # Archive current results and start new iteration
                return start_new_iteration(state, new_prompt)
            else:
                # User canceled, complete the session
                return complete_session(state)
        else:
            # User is satisfied, complete the session
            return complete_session(state)
            
    except Exception as e:
        logger.error(f"Results Review: Error during results review: {str(e)}")
        return {
            **state,
            "errors": state["errors"] + [f"Results review failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        }


def display_iteration_summary(state: CFDState) -> None:
    """Display a summary of the current iteration results."""
    
    iteration_num = state.get("current_iteration", 0) + 1
    
    # Create results summary panel
    summary_lines = []
    summary_lines.append(f"[bold blue]Iteration {iteration_num} Complete![/bold blue]")
    summary_lines.append("")
    
    # Basic simulation info
    parsed_params = state.get("parsed_parameters", {})
    if parsed_params:
        summary_lines.append(f"[green]Geometry:[/green] {parsed_params.get('geometry_type', 'N/A')}")
        if parsed_params.get("velocity"):
            summary_lines.append(f"[green]Velocity:[/green] {parsed_params['velocity']:.2f} m/s")
        if parsed_params.get("reynolds_number"):
            summary_lines.append(f"[green]Reynolds Number:[/green] {parsed_params['reynolds_number']:.0f}")
    
    # Mesh info
    mesh_config = state.get("mesh_config", {})
    if mesh_config:
        total_cells = mesh_config.get("total_cells", 0)
        if total_cells > 0:
            summary_lines.append(f"[green]Mesh Cells:[/green] {total_cells:,}")
    
    # Quality metrics
    mesh_quality = state.get("mesh_quality", {})
    if mesh_quality:
        quality_score = mesh_quality.get("quality_score", 0)
        summary_lines.append(f"[green]Mesh Quality:[/green] {quality_score:.2f}/1.0")
    
    # Convergence
    convergence_metrics = state.get("convergence_metrics", {})
    if convergence_metrics:
        converged = convergence_metrics.get("converged", False)
        status_color = "green" if converged else "red"
        status_text = "✅ Converged" if converged else "❌ Not Converged"
        summary_lines.append(f"[{status_color}]Convergence:[/{status_color}] {status_text}")
        
        execution_time = convergence_metrics.get("execution_time", 0)
        if execution_time > 0:
            summary_lines.append(f"[green]Execution Time:[/green] {execution_time:.1f} seconds")
    
    # Visualization info
    visualization_path = state.get("visualization_path", "")
    if visualization_path:
        summary_lines.append(f"[green]Results Location:[/green] {visualization_path}")
    
    console.print(Panel(
        "\n".join(summary_lines),
        title=f"🎯 CFD Simulation Results - Iteration {iteration_num}",
        border_style="green"
    ))


def prompt_for_next_action(state: CFDState) -> str:
    """Prompt user for their next action."""
    
    console.print("\n🤔 What would you like to do next?")
    console.print()
    
    # Show previous iterations if any
    session_history = state.get("session_history", [])
    if session_history:
        console.print(f"📚 You have completed {len(session_history)} iteration(s) in this session:")
        for i, hist in enumerate(session_history, 1):
            prompt_preview = hist.get("user_prompt", "")[:50] + "..." if len(hist.get("user_prompt", "")) > 50 else hist.get("user_prompt", "")
            converged = hist.get("convergence_metrics", {}).get("converged", False)
            status = "✅" if converged else "❌"
            console.print(f"  {i}. {status} {prompt_preview}")
        console.print()
    
    # Prompt for choice
    console.print("Choose your next action:")
    console.print("  [bold green]1[/bold green] 🔄 Make changes and run another simulation")
    console.print("  [bold green]2[/bold green] 📊 I'm satisfied with the results")
    console.print("  [bold green]3[/bold green] 🚪 Exit the session")
    console.print()
    
    while True:
        choice = Prompt.ask("Enter your choice", choices=["1", "2", "3"], default="2")
        
        if choice == "1":
            return "continue"
        elif choice == "2":
            console.print("\n✅ Great! Your simulation results are ready for use.")
            return "complete"
        elif choice == "3":
            console.print("\n👋 Goodbye! Your simulation data has been saved.")
            return "complete"


def get_new_user_prompt(state: CFDState) -> str:
    """Get a new prompt from the user for the next iteration."""
    
    console.print("\n🔄 Starting New Iteration")
    console.print("=" * 50)
    
    # Show context from previous iteration
    current_prompt = state.get("user_prompt", "")
    console.print(f"[dim]Previous prompt: {current_prompt}[/dim]")
    console.print()
    
    # Provide suggestions based on current results
    suggestions = generate_improvement_suggestions(state)
    if suggestions:
        console.print("💡 [bold]Suggestions for improvements:[/bold]")
        for i, suggestion in enumerate(suggestions, 1):
            console.print(f"   {i}. {suggestion}")
        console.print()
    
    # Get new prompt
    console.print("Enter your new CFD problem description:")
    console.print("(You can modify parameters, change geometry, adjust conditions, etc.)")
    console.print("Type 'cancel' to return to the main menu.")
    console.print()
    
    new_prompt = Prompt.ask("New prompt", default="")
    
    if new_prompt.lower() == "cancel" or not new_prompt.strip():
        return ""
    
    return new_prompt.strip()


def generate_improvement_suggestions(state: CFDState) -> list:
    """Generate suggestions for improvements based on current results."""
    
    suggestions = []
    
    # Check convergence
    convergence_metrics = state.get("convergence_metrics", {})
    if convergence_metrics and not convergence_metrics.get("converged", False):
        suggestions.append("Try refining the mesh for better convergence")
        suggestions.append("Adjust solver settings or reduce time step")
    
    # Check mesh quality
    mesh_quality = state.get("mesh_quality", {})
    if mesh_quality:
        quality_score = mesh_quality.get("quality_score", 1.0)
        if quality_score < 0.7:
            suggestions.append("Improve mesh quality by using finer mesh settings")
    
    # Check execution time
    convergence_metrics = state.get("convergence_metrics", {})
    if convergence_metrics:
        execution_time = convergence_metrics.get("execution_time", 0)
        if execution_time > 300:  # More than 5 minutes
            suggestions.append("Use coarser mesh or steady-state solver to reduce computation time")
    
    # General suggestions
    suggestions.extend([
        "Change flow velocity or Reynolds number",
        "Try different geometry dimensions",
        "Experiment with laminar vs turbulent flow",
        "Adjust boundary conditions",
        "Test different solver types"
    ])
    
    return suggestions[:5]  # Limit to 5 suggestions


def start_new_iteration(state: CFDState, new_prompt: str) -> CFDState:
    """Start a new iteration with the given prompt."""
    
    # Archive current results to history
    current_results = {
        "iteration": state.get("current_iteration", 0),
        "user_prompt": state.get("user_prompt", ""),
        "parsed_parameters": state.get("parsed_parameters", {}),
        "mesh_config": state.get("mesh_config", {}),
        "convergence_metrics": state.get("convergence_metrics", {}),
        "mesh_quality": state.get("mesh_quality", {}),
        "visualization_path": state.get("visualization_path", ""),
        "execution_timestamp": state.get("convergence_metrics", {}).get("end_time", "")
    }
    
    # Add to session history
    session_history = state.get("session_history", [])
    session_history.append(current_results)
    
    logger.info(f"Results Review: Starting iteration {state.get('current_iteration', 0) + 1}")
    
    # Reset state for new iteration but keep history
    return {
        **state,
        "user_prompt": new_prompt,
        "parsed_parameters": {},
        "geometry_info": {},
        "mesh_config": {},
        "boundary_conditions": {},
        "solver_settings": {},
        "case_directory": "",
        "simulation_results": {},
        "visualization_path": "",
        "errors": [],
        "warnings": [],
        "current_step": CFDStep.NL_INTERPRETATION,
        "retry_count": 0,
        "user_approved": False,
        "mesh_quality": None,
        "convergence_metrics": None,
        "session_history": session_history,
        "current_iteration": state.get("current_iteration", 0) + 1,
        "previous_results": current_results,
        "conversation_active": True
    }


def complete_session(state: CFDState) -> CFDState:
    """Complete the current session."""
    
    # Archive final results
    if state.get("parsed_parameters") or state.get("convergence_metrics"):
        final_results = {
            "iteration": state.get("current_iteration", 0),
            "user_prompt": state.get("user_prompt", ""),
            "parsed_parameters": state.get("parsed_parameters", {}),
            "mesh_config": state.get("mesh_config", {}),
            "convergence_metrics": state.get("convergence_metrics", {}),
            "mesh_quality": state.get("mesh_quality", {}),
            "visualization_path": state.get("visualization_path", ""),
            "execution_timestamp": state.get("convergence_metrics", {}).get("end_time", "")
        }
        
        session_history = state.get("session_history", [])
        session_history.append(final_results)
        
        # Display final session summary
        display_session_summary(session_history)
        
        return {
            **state,
            "session_history": session_history,
            "conversation_active": False,
            "current_step": CFDStep.COMPLETE
        }
    else:
        return {
            **state,
            "conversation_active": False,
            "current_step": CFDStep.COMPLETE
        }


def display_session_summary(session_history: list) -> None:
    """Display a summary of the entire session."""
    
    if not session_history:
        return
    
    console.print("\n📊 Session Summary")
    console.print("=" * 50)
    
    # Create summary table
    table = Table(title="CFD Session Results")
    table.add_column("Iteration", style="cyan")
    table.add_column("Problem", style="yellow", max_width=30)
    table.add_column("Converged", style="green")
    table.add_column("Mesh Cells", style="blue")
    table.add_column("Time (s)", style="magenta")
    
    for i, result in enumerate(session_history, 1):
        prompt_preview = result.get("user_prompt", "")[:25] + "..." if len(result.get("user_prompt", "")) > 25 else result.get("user_prompt", "")
        converged = "✅" if result.get("convergence_metrics", {}).get("converged", False) else "❌"
        mesh_cells = f"{result.get('mesh_config', {}).get('total_cells', 0):,}" if result.get('mesh_config', {}).get('total_cells', 0) > 0 else "N/A"
        exec_time = f"{result.get('convergence_metrics', {}).get('execution_time', 0):.1f}" if result.get('convergence_metrics', {}).get('execution_time', 0) > 0 else "N/A"
        
        table.add_row(str(i), prompt_preview, converged, mesh_cells, exec_time)
    
    console.print(table)
    console.print(f"\n✅ Total iterations completed: {len(session_history)}")
    console.print("🎉 Thank you for using FoamAI!") 