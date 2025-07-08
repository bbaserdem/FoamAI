"""System Orchestrator Agent - Central workflow controller."""

import uuid
from typing import Dict, Any
from loguru import logger

from langgraph.graph import StateGraph, END
from .state import CFDState, CFDStep


def orchestrator_agent(state: CFDState) -> CFDState:
    """
    Central orchestrator that manages workflow routing and error recovery.
    
    This agent analyzes the current state and determines the next step
    in the CFD workflow, including error recovery and quality checks.
    """
    if state["verbose"]:
        logger.info(f"Orchestrator: Current step = {state['current_step']}")
        logger.info(f"Orchestrator: Errors = {state['errors']}")
        logger.info(f"Orchestrator: Retry count = {state['retry_count']}")
    
    # Initialize error recovery tracking if not present
    if "error_recovery_attempts" not in state:
        state["error_recovery_attempts"] = {}
    
    # Handle maximum retries exceeded
    if state["retry_count"] >= state["max_retries"]:
        logger.error("Maximum retries exceeded")
        return {
            **state,
            "current_step": CFDStep.ERROR,
            "errors": state["errors"] + ["Maximum retries exceeded"]
        }
    
    # Handle errors first - determine recovery strategy
    # But not if we're already in ERROR state (terminal)
    if state["errors"] and state["current_step"] != CFDStep.ERROR:
        return handle_error_recovery(state)
    
    # Handle successful completion
    if state["current_step"] == CFDStep.SIMULATION and state.get("convergence_metrics", {}).get("converged", False):
        logger.info("Simulation completed successfully - proceeding to completion")
        # Check if visualization is requested
        if state.get("export_images", True):
            return {
                **state,
                "current_step": CFDStep.VISUALIZATION,
                "retry_count": 0
            }
        else:
            return {
                **state,
                "current_step": CFDStep.COMPLETE,
                "retry_count": 0
            }
    
    # Handle quality checks and refinement (only if simulation hasn't already succeeded)
    if state["current_step"] != CFDStep.COMPLETE and needs_refinement(state):
        return handle_refinement(state)
    
    # Normal workflow progression
    return handle_normal_progression(state)


def handle_error_recovery(state: CFDState) -> CFDState:
    """Handle error recovery routing."""
    last_error = state["errors"][-1].lower()
    
    logger.warning(f"Handling error: {last_error}")
    
    # Initialize error recovery tracking if not present
    if "error_recovery_attempts" not in state:
        state["error_recovery_attempts"] = {}
    
    # Check retry count first
    if state["retry_count"] >= state.get("max_retries", 3):
        logger.error("Maximum retries exceeded")
        return {
            **state,
            "current_step": CFDStep.ERROR,
            "errors": ["Maximum retries exceeded: " + state["errors"][-1] if state["errors"] else "Unknown error"],
        }
    
    # Check for OpenFOAM availability issues
    if "system cannot find the file specified" in last_error:
        logger.error("OpenFOAM not found - stopping execution")
        return {
            **state,
            "current_step": CFDStep.ERROR,
            "errors": state["errors"] + ["OpenFOAM not available - please install OpenFOAM first"],
        }
    
    # Parse error type and route to appropriate agent
    if any(keyword in last_error for keyword in ["mesh", "blockmesh", "geometry"]):
        next_step = CFDStep.MESH_GENERATION
    elif any(keyword in last_error for keyword in ["boundary", "inlet", "outlet", "wall", "patch type", "patchfield"]):
        next_step = CFDStep.BOUNDARY_CONDITIONS
    elif any(keyword in last_error for keyword in ["solver", "scheme", "solution", "diverged", "converged", "residual data"]):
        next_step = CFDStep.SOLVER_SELECTION
    elif any(keyword in last_error for keyword in ["case", "file", "directory"]):
        next_step = CFDStep.CASE_WRITING
    elif any(keyword in last_error for keyword in ["simulation", "execution", "foam", "failed with code"]):
        # For simulation failures, go back to boundary conditions or solver settings
        # to fix the underlying issue, not just retry the simulation
        if "patch" in last_error or "boundary" in last_error:
            next_step = CFDStep.BOUNDARY_CONDITIONS
        elif "residual" in last_error:
            next_step = CFDStep.SOLVER_SELECTION
        else:
            next_step = CFDStep.SOLVER_SELECTION
    else:
        # If error type is unclear, restart from interpretation
        next_step = CFDStep.NL_INTERPRETATION
    
    # Track which steps we've tried for this error
    error_key = f"{state['current_step']}_to_{next_step}"
    error_attempts = state.get("error_recovery_attempts", {})
    if error_attempts is None:
        error_attempts = {}
    
    if error_key in error_attempts:
        # We've already tried this recovery path
        logger.warning(f"Already attempted recovery path: {error_key}")
        # Count how many different recovery attempts we've made
        total_recovery_attempts = len(error_attempts)
        if total_recovery_attempts >= 3 or state["current_step"] == CFDStep.SIMULATION:
            # If we've tried 3 different recovery paths or simulation keeps failing, stop
            logger.error(f"Unable to recover after {total_recovery_attempts} different recovery attempts")
            return {
                **state,
                "current_step": CFDStep.ERROR,
                "errors": ["Unable to recover from error: " + last_error],
            }
    
    # Record this recovery attempt
    error_attempts[error_key] = True
    
    return {
        **state,
        "current_step": next_step,
        "retry_count": state["retry_count"] + 1,
        "errors": [],  # Clear errors for retry
        "error_recovery_attempts": error_attempts
    }


def needs_refinement(state: CFDState) -> bool:
    """Check if results need refinement."""
    # Don't refine if already completed or if we're in the middle of a retry
    if state["current_step"] == CFDStep.COMPLETE or state["retry_count"] > 0:
        return False
    
    # Check mesh quality - only if severely bad
    if state["mesh_quality"]:
        if state["mesh_quality"].get("quality_score", 1.0) < 0.5:
            return True
    
    # Check convergence - only if explicitly failed
    if state["convergence_metrics"]:
        if state["convergence_metrics"].get("converged", False) is False and state["convergence_metrics"].get("final_residuals"):
            # Only refine if residuals are extremely poor
            final_residuals = state["convergence_metrics"].get("final_residuals", {})
            if any(residual > 1e-1 for residual in final_residuals.values()):
                return True
    
    return False


def handle_refinement(state: CFDState) -> CFDState:
    """Handle refinement routing."""
    logger.info("Quality check indicates refinement needed")
    
    # Determine what needs refinement
    if state["mesh_quality"] and state["mesh_quality"].get("quality_score", 1.0) < 0.7:
        logger.info("Mesh quality low, requesting mesh refinement")
        return {
            **state,
            "current_step": CFDStep.MESH_GENERATION,
            "warnings": state["warnings"] + ["Mesh quality low, refining mesh"]
        }
    
    if state["convergence_metrics"] and not state["convergence_metrics"].get("converged", False):
        logger.info("Convergence poor, adjusting solver settings")
        return {
            **state,
            "current_step": CFDStep.SOLVER_SELECTION,
            "warnings": state["warnings"] + ["Poor convergence, adjusting solver"]
        }
    
    # Default to continuing workflow
    return handle_normal_progression(state)


def handle_normal_progression(state: CFDState) -> CFDState:
    """Handle normal workflow progression."""
    current_step = state["current_step"]
    
    # Determine next step based on current step
    next_step_map = {
        CFDStep.START: CFDStep.NL_INTERPRETATION,
        CFDStep.NL_INTERPRETATION: CFDStep.MESH_GENERATION,
        CFDStep.MESH_GENERATION: CFDStep.BOUNDARY_CONDITIONS,
        CFDStep.BOUNDARY_CONDITIONS: CFDStep.SOLVER_SELECTION,
        CFDStep.SOLVER_SELECTION: CFDStep.CASE_WRITING,
        CFDStep.CASE_WRITING: CFDStep.SIMULATION,
        CFDStep.SIMULATION: CFDStep.VISUALIZATION,
        CFDStep.VISUALIZATION: CFDStep.COMPLETE,
    }
    
    next_step = next_step_map.get(current_step, CFDStep.COMPLETE)
    
    if state["verbose"]:
        logger.info(f"Normal progression: {current_step} -> {next_step}")
    
    return {
        **state,
        "current_step": next_step,
        "retry_count": 0  # Reset retry count on successful progression
    }


def determine_next_agent(state: CFDState) -> str:
    """Determine which agent to call next based on current step."""
    step_to_agent = {
        CFDStep.NL_INTERPRETATION: "nl_interpreter",
        CFDStep.MESH_GENERATION: "mesh_generator",
        CFDStep.BOUNDARY_CONDITIONS: "boundary_condition",
        CFDStep.SOLVER_SELECTION: "solver_selector",
        CFDStep.CASE_WRITING: "case_writer",
        CFDStep.SIMULATION: "simulation_executor",
        CFDStep.VISUALIZATION: "visualization",
        CFDStep.COMPLETE: "end",
        CFDStep.ERROR: "end",
    }
    
    return step_to_agent.get(state["current_step"], "end")


def create_cfd_workflow():
    """Create and compile the CFD workflow graph."""
    from .nl_interpreter import nl_interpreter_agent
    from .mesh_generator import mesh_generator_agent
    from .boundary_condition import boundary_condition_agent
    from .solver_selector import solver_selector_agent
    from .case_writer import case_writer_agent
    from .simulation_executor import simulation_executor_agent
    from .visualization import visualization_agent
    
    # Create the state graph
    workflow = StateGraph(CFDState)
    
    # Add all agent nodes
    workflow.add_node("orchestrator", orchestrator_agent)
    workflow.add_node("nl_interpreter", nl_interpreter_agent)
    workflow.add_node("mesh_generator", mesh_generator_agent)
    workflow.add_node("boundary_condition", boundary_condition_agent)
    workflow.add_node("solver_selector", solver_selector_agent)
    workflow.add_node("case_writer", case_writer_agent)
    workflow.add_node("simulation_executor", simulation_executor_agent)
    workflow.add_node("visualization", visualization_agent)
    
    # Set entry point
    workflow.set_entry_point("orchestrator")
    
    # Add conditional edges from orchestrator to agents
    workflow.add_conditional_edges(
        "orchestrator",
        determine_next_agent,
        {
            "nl_interpreter": "nl_interpreter",
            "mesh_generator": "mesh_generator",
            "boundary_condition": "boundary_condition",
            "solver_selector": "solver_selector",
            "case_writer": "case_writer",
            "simulation_executor": "simulation_executor",
            "visualization": "visualization",
            "end": END,
        }
    )
    
    # All agents return to orchestrator for next step determination
    workflow.add_edge("nl_interpreter", "orchestrator")
    workflow.add_edge("mesh_generator", "orchestrator")
    workflow.add_edge("boundary_condition", "orchestrator")
    workflow.add_edge("solver_selector", "orchestrator")
    workflow.add_edge("case_writer", "orchestrator")
    workflow.add_edge("simulation_executor", "orchestrator")
    workflow.add_edge("visualization", "orchestrator")
    
    # Compile the workflow
    return workflow.compile()


def create_initial_state(
        user_prompt: str, 
        verbose: bool = False,
        export_images: bool = True,
        output_format: str = "images",
        max_retries: int = 3
    ) -> CFDState:
    """Create initial state for the CFD workflow."""
    return CFDState(
        user_prompt=user_prompt,
        parsed_parameters={},
        geometry_info={},
        mesh_config={},
        boundary_conditions={},
        solver_settings={},
        case_directory="",
        work_directory="",
        simulation_results={},
        visualization_path="",
        errors=[],
        warnings=[],
        current_step=CFDStep.START,
        retry_count=0,
        max_retries=max_retries,
        error_recovery_attempts=None,
        mesh_quality=None,
        convergence_metrics=None,
        verbose=verbose,
        export_images=export_images,
        output_format=output_format,
    ) 