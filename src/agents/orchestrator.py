"""System Orchestrator Agent - Central workflow controller."""

import uuid
from typing import Dict, Any, Optional
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
            "errors": state["errors"] + ["Maximum retries exceeded"],
            "conversation_active": False
        }
    
    # Handle errors first - route to intelligent error handler
    # But not if we're already in ERROR state (terminal) or ERROR_HANDLER state
    if state["errors"] and state["current_step"] not in [CFDStep.ERROR, CFDStep.ERROR_HANDLER]:
        logger.info("Orchestrator: Routing to intelligent error handler")
        return {
            **state,
            "current_step": CFDStep.ERROR_HANDLER
        }
    
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
                "retry_count": 0,
                "conversation_active": False
            }
    
    # Handle quality checks and refinement (only if simulation hasn't already succeeded)
    if state["current_step"] != CFDStep.COMPLETE and needs_refinement(state):
        return handle_refinement(state)
    
    # Normal workflow progression
    return handle_normal_progression(state)


# Old error recovery system replaced by intelligent error handler agent


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
            "warnings": state["warnings"] + ["Mesh quality low, refining mesh"],
            "retry_count": state["retry_count"] + 1
        }
    
    if state["convergence_metrics"] and not state["convergence_metrics"].get("converged", False):
        logger.info("Convergence poor, adjusting solver settings")
        return {
            **state,
            "current_step": CFDStep.SOLVER_SELECTION,
            "warnings": state["warnings"] + ["Poor convergence, adjusting solver"],
            "retry_count": state["retry_count"] + 1
        }
    
    # Default to continuing workflow
    return handle_normal_progression(state)


def handle_normal_progression(state: CFDState) -> CFDState:
    """Handle normal workflow progression."""
    current_step = state["current_step"]
    
    # If we're already at COMPLETE, ensure we terminate properly
    if current_step == CFDStep.COMPLETE:
        return {
            **state,
            "conversation_active": False,
            "retry_count": 0
        }
    
    # Determine next step based on current step
    next_step_map = {
        CFDStep.START: CFDStep.NL_INTERPRETATION,
        CFDStep.NL_INTERPRETATION: CFDStep.MESH_GENERATION,
        CFDStep.MESH_GENERATION: CFDStep.BOUNDARY_CONDITIONS,
        CFDStep.BOUNDARY_CONDITIONS: CFDStep.SOLVER_SELECTION,
        CFDStep.SOLVER_SELECTION: CFDStep.CASE_WRITING,
        CFDStep.CASE_WRITING: CFDStep.USER_APPROVAL if state.get("user_approval_enabled", True) else CFDStep.SIMULATION,
        CFDStep.USER_APPROVAL: CFDStep.SIMULATION,
        CFDStep.SIMULATION: CFDStep.VISUALIZATION,
        CFDStep.VISUALIZATION: CFDStep.RESULTS_REVIEW,
        CFDStep.RESULTS_REVIEW: CFDStep.COMPLETE,  # Will be overridden by results_review_agent if continuing
    }
    
    next_step = next_step_map.get(current_step, CFDStep.COMPLETE)
    
    if state["verbose"]:
        logger.info(f"Normal progression: {current_step} -> {next_step}")
    
    # If next step is COMPLETE, set conversation_active to False
    if next_step == CFDStep.COMPLETE:
        return {
            **state,
            "current_step": next_step,
            "conversation_active": False,
            "retry_count": 0
        }
    
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
        CFDStep.USER_APPROVAL: "user_approval",
        CFDStep.SIMULATION: "simulation_executor",
        CFDStep.VISUALIZATION: "visualization",
        CFDStep.RESULTS_REVIEW: "results_review",
        CFDStep.ERROR_HANDLER: "error_handler",
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
    from .user_approval import user_approval_agent
    from .simulation_executor import simulation_executor_agent
    from .visualization import visualization_agent
    from .results_review import results_review_agent
    from .error_handler import error_handler_agent
    
    # Create the state graph
    workflow = StateGraph(CFDState)
    
    # Add all agent nodes
    workflow.add_node("orchestrator", orchestrator_agent)
    workflow.add_node("nl_interpreter", nl_interpreter_agent)
    workflow.add_node("mesh_generator", mesh_generator_agent)
    workflow.add_node("boundary_condition", boundary_condition_agent)
    workflow.add_node("solver_selector", solver_selector_agent)
    workflow.add_node("case_writer", case_writer_agent)
    workflow.add_node("user_approval", user_approval_agent)
    workflow.add_node("simulation_executor", simulation_executor_agent)
    workflow.add_node("visualization", visualization_agent)
    workflow.add_node("results_review", results_review_agent)
    workflow.add_node("error_handler", error_handler_agent)
    
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
            "user_approval": "user_approval",
            "simulation_executor": "simulation_executor",
            "visualization": "visualization",
            "results_review": "results_review",
            "error_handler": "error_handler",
            "end": END,
        }
    )
    
    # All agents return to orchestrator for next step determination
    workflow.add_edge("nl_interpreter", "orchestrator")
    workflow.add_edge("mesh_generator", "orchestrator")
    workflow.add_edge("boundary_condition", "orchestrator")
    workflow.add_edge("solver_selector", "orchestrator")
    workflow.add_edge("case_writer", "orchestrator")
    workflow.add_edge("user_approval", "orchestrator")
    workflow.add_edge("simulation_executor", "orchestrator")
    workflow.add_edge("visualization", "orchestrator")
    workflow.add_edge("results_review", "orchestrator")
    workflow.add_edge("error_handler", "orchestrator")
    
    # Compile the workflow
    return workflow.compile()


def create_initial_state(
        user_prompt: str, 
        verbose: bool = False,
        export_images: bool = True,
        output_format: str = "images",
        max_retries: int = 3,
        user_approval_enabled: bool = True,
        stl_file: Optional[str] = None,
        force_validation: bool = False
    ) -> CFDState:
    """Create initial state for the CFD workflow."""
    return CFDState(
        user_prompt=user_prompt,
        stl_file=stl_file,
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
        user_approved=False,
        user_approval_enabled=user_approval_enabled,
        mesh_quality=None,
        convergence_metrics=None,
        verbose=verbose,
        export_images=export_images,
        output_format=output_format,
        force_validation=force_validation,
        session_history=[],
        current_iteration=0,
        conversation_active=True,
        previous_results=None,
    ) 