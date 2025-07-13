"""System Orchestrator Agent - Central workflow controller."""

import uuid
from typing import Dict, Any, Optional
from loguru import logger
from pathlib import Path

from langgraph.graph import StateGraph, END
from .state import CFDState, CFDStep
from .remote_executor import RemoteExecutor


def orchestrator_agent(state: CFDState) -> CFDState:
    """
    Central orchestrator that manages workflow routing and error recovery.
    
    This agent analyzes the current state and determines the next step
    in the CFD workflow, including error recovery and quality checks.
    Supports both local and remote execution modes.
    """
    logger.info("DEBUG: orchestrator_agent - FUNCTION START")
    
    if state["verbose"]:
        logger.info(f"Orchestrator: Current step = {state['current_step']}")
        logger.info(f"Orchestrator: Errors = {state['errors']}")
        logger.info(f"Orchestrator: Retry count = {state['retry_count']}")
        
        # Log execution mode
        execution_mode = state.get("execution_mode", "local")
        if execution_mode == "remote":
            project_name = state.get("project_name", "unknown")
            server_url = state.get("server_url", "unknown")
            logger.info(f"Orchestrator: Remote execution mode - project '{project_name}' on '{server_url}'")
    
    # DEBUG: Add explicit logging for config_only_mode in orchestrator
    logger.info(f"DEBUG: orchestrator_agent - current_step: {state['current_step']}")
    logger.info(f"DEBUG: orchestrator_agent - config_only_mode: {state.get('config_only_mode')}")
    logger.info(f"DEBUG: orchestrator_agent - awaiting_user_approval: {state.get('awaiting_user_approval')}")
    
    # DEBUG: Safely access simulation_results to prevent NoneType error
    simulation_results = state.get('simulation_results', {})
    logger.info(f"DEBUG: orchestrator_agent - simulation_results type: {type(simulation_results)}")
    logger.info(f"DEBUG: orchestrator_agent - simulation_results value: {simulation_results}")
    
    if simulation_results is not None and hasattr(simulation_results, 'get'):
        config_only = simulation_results.get('config_only')
        logger.info(f"DEBUG: orchestrator_agent - simulation_results config_only: {config_only}")
    else:
        logger.warning(f"DEBUG: orchestrator_agent - simulation_results is None or not a dict: {simulation_results}")
        config_only = None
    
    # Initialize error recovery tracking if not present
    logger.info("DEBUG: orchestrator_agent - About to check error_recovery_attempts")
    if "error_recovery_attempts" not in state:
        logger.info("DEBUG: orchestrator_agent - Setting error_recovery_attempts")
        state["error_recovery_attempts"] = {}
    logger.info("DEBUG: orchestrator_agent - Completed error_recovery_attempts setup")
    
    # Handle maximum retries exceeded
    logger.info("DEBUG: orchestrator_agent - About to check max retries")
    retry_count = state["retry_count"]
    max_retries = state["max_retries"]
    logger.info(f"DEBUG: orchestrator_agent - retry_count: {retry_count}, max_retries: {max_retries}")
    
    if retry_count >= max_retries:
        logger.error("Maximum retries exceeded")
        logger.info("DEBUG: orchestrator_agent - EARLY EXIT: max retries exceeded")
        return {
            **state,
            "current_step": CFDStep.ERROR,
            "errors": state["errors"] + ["Maximum retries exceeded"]
        }
    logger.info("DEBUG: orchestrator_agent - Passed max retries check")
    
    # Handle errors first - route to intelligent error handler
    # But not if we're already in ERROR state (terminal) or ERROR_HANDLER state
    logger.info("DEBUG: orchestrator_agent - About to check errors")
    errors = state["errors"]
    logger.info(f"DEBUG: orchestrator_agent - errors: {errors}")
    current_step = state["current_step"]
    logger.info(f"DEBUG: orchestrator_agent - current_step for error check: {current_step}")
    
    logger.info("DEBUG: orchestrator_agent - About to check if current_step not in ERROR states")
    step_check = current_step not in [CFDStep.ERROR, CFDStep.ERROR_HANDLER]
    logger.info(f"DEBUG: orchestrator_agent - step_check result: {step_check}")
    
    logger.info("DEBUG: orchestrator_agent - About to evaluate full error condition")
    if errors and step_check:
        logger.info("Orchestrator: Routing to intelligent error handler")
        logger.info("DEBUG: orchestrator_agent - EARLY EXIT: routing to error handler")
        return {
            **state,
            "current_step": CFDStep.ERROR_HANDLER
        }
    logger.info("DEBUG: orchestrator_agent - Passed error handling check")
    
    # Check if workflow should be paused for user approval
    if (state["current_step"] == CFDStep.USER_APPROVAL and 
        state.get("awaiting_user_approval", False)):
        if state["verbose"]:
            logger.info("Orchestrator: Workflow paused for user approval - stopping execution")
        logger.info("DEBUG: orchestrator_agent - EARLY EXIT: workflow paused for user approval")
        # Return current state without progression to pause workflow
        return state

    # Handle successful completion
    convergence_check = (state.get("convergence_metrics") or {}).get("converged", False)
    logger.info(f"DEBUG: orchestrator_agent - checking completion: current_step={state['current_step']}, convergence_check={convergence_check}")
    logger.info(f"DEBUG: orchestrator_agent - convergence_metrics: {state.get('convergence_metrics', {})}")
    
    if state["current_step"] == CFDStep.SIMULATION and convergence_check:
        logger.info("Simulation completed successfully - proceeding to completion")
        logger.info("DEBUG: orchestrator_agent - EARLY EXIT: simulation completed successfully")
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
    needs_refinement_check = needs_refinement(state)
    logger.info(f"DEBUG: orchestrator_agent - checking refinement: current_step={state['current_step']}, needs_refinement={needs_refinement_check}")
    
    if state["current_step"] != CFDStep.COMPLETE and needs_refinement_check:
        logger.info("DEBUG: orchestrator_agent - EARLY EXIT: routing to refinement")
        return handle_refinement(state)
    
    # Normal workflow progression
    logger.info("DEBUG: orchestrator_agent - REACHED normal workflow progression section")
    logger.info("DEBUG: orchestrator_agent - calling handle_normal_progression")
    result_state = handle_normal_progression(state)
    logger.info(f"DEBUG: orchestrator_agent - handle_normal_progression returned: {result_state is not None}")
    if result_state is not None:
        logger.info(f"DEBUG: orchestrator_agent - returned state current_step: {result_state.get('current_step')}")
    else:
        logger.error("DEBUG: orchestrator_agent - handle_normal_progression returned None!")
    return result_state


# Old error recovery system replaced by intelligent error handler agent


def needs_refinement(state: CFDState) -> bool:
    """Check if results need refinement."""
    # Don't refine if already completed or if we're in the middle of a retry
    if state["current_step"] == CFDStep.COMPLETE or state["retry_count"] > 0:
        return False
    
    # Check mesh quality - only if severely bad
    mesh_quality = state.get("mesh_quality") or {}
    if mesh_quality:
        if mesh_quality.get("quality_score", 1.0) < 0.5:
            return True
    
    # Check convergence - only if explicitly failed
    convergence_metrics = state.get("convergence_metrics") or {}
    if convergence_metrics:
        if convergence_metrics.get("converged", False) is False and convergence_metrics.get("final_residuals"):
            # Only refine if residuals are extremely poor
            final_residuals = convergence_metrics.get("final_residuals", {})
            if any(residual > 1e-1 for residual in final_residuals.values()):
                return True
    
    return False


def handle_refinement(state: CFDState) -> CFDState:
    """Handle refinement routing."""
    logger.info("Quality check indicates refinement needed")
    
    # Determine what needs refinement
    mesh_quality = state.get("mesh_quality") or {}
    if mesh_quality and mesh_quality.get("quality_score", 1.0) < 0.7:
        logger.info("Mesh quality low, requesting mesh refinement")
        return {
            **state,
            "current_step": CFDStep.MESH_GENERATION,
            "warnings": state["warnings"] + ["Mesh quality low, refining mesh"]
        }
    
    convergence_metrics = state.get("convergence_metrics") or {}
    if convergence_metrics and not convergence_metrics.get("converged", False):
        logger.info("Convergence poor, adjusting solver settings")
        return {
            **state,
            "current_step": CFDStep.SOLVER_SELECTION,
            "warnings": state["warnings"] + ["Poor convergence, adjusting solver"]
        }
    
    # Default to continuing workflow
    return handle_normal_progression(state)


def create_config_summary(state: CFDState) -> Dict[str, Any]:
    """Create a configuration summary for UI display during user approval."""
    logger.info("Creating config summary for user approval")
    
    config_summary = {}
    
    # Extract mesh information
    mesh_info = {}
    simulation_results = state.get("simulation_results", {})
    steps = simulation_results.get("steps", {})
    
    # Get mesh data from mesh generation step
    if "mesh_generation" in steps:
        mesh_step = steps["mesh_generation"]
        mesh_info = mesh_step.get("mesh_info", {})
    
    # If mesh_info not available, use mesh_config
    if not mesh_info:
        mesh_config = state.get("mesh_config", {})
        if mesh_config:
            mesh_info = {
                "mesh_type": mesh_config.get("type", "blockMesh"),
                "total_cells": mesh_config.get("total_cells", 0),
                "quality_score": mesh_config.get("quality_metrics", {}).get("quality_score", 0.0)
            }
    
    config_summary["mesh_info"] = mesh_info
    config_summary["mesh_config"] = state.get("mesh_config", {})
    
    # Extract solver information
    solver_settings = state.get("solver_settings", {})
    solver_info = {
        "solver_name": solver_settings.get("solver", "Unknown"),
        "end_time": solver_settings.get("end_time", 0),
        "time_step": solver_settings.get("time_step", 0),
        "write_control": solver_settings.get("write_control", "timeStep"),
        "write_interval": solver_settings.get("write_interval", 1)
    }
    config_summary["solver_info"] = solver_info
    
    # Extract simulation parameters
    parsed_params = state.get("parsed_parameters", {})
    sim_params = {
        "flow_type": parsed_params.get("flow_type", "incompressible"),
        "analysis_type": parsed_params.get("analysis_type", "steady"),
        "velocity": parsed_params.get("velocity", 0.0),
        "reynolds_number": parsed_params.get("reynolds_number", 0),
        "geometry_type": parsed_params.get("geometry_type", "custom")
    }
    config_summary["simulation_parameters"] = sim_params
    
    # Extract case information for ParaView loading
    case_info = {
        "case_directory": state.get("case_directory", ""),
        "project_name": state.get("project_name", ""),
        "foam_file_path": None  # Will be constructed by UI
    }
    
    # If we have project name, construct foam file path
    if case_info["project_name"]:
        case_info["foam_file_path"] = f"/home/ubuntu/foam_projects/{case_info['project_name']}/active_run/{case_info['project_name']}.foam"
    
    config_summary["case_info"] = case_info
    
    # Add boundary conditions summary
    boundary_conditions = state.get("boundary_conditions", {})
    if boundary_conditions:
        config_summary["boundary_conditions"] = boundary_conditions
    
    # Add geometry information
    geometry_info = state.get("geometry_info", {})
    if geometry_info:
        config_summary["geometry_info"] = geometry_info
    
    # Add AI explanation about the configuration
    ai_explanation = f"Configuration generated for {sim_params.get('flow_type', 'incompressible')} flow "
    ai_explanation += f"with {solver_info.get('solver_name', 'unknown')} solver. "
    ai_explanation += f"Mesh contains {mesh_info.get('total_cells', 0):,} cells. "
    ai_explanation += "Review the setup below and click 'Run Simulation' when ready."
    
    config_summary["ai_explanation"] = ai_explanation
    
    logger.info(f"Config summary created with keys: {list(config_summary.keys())}")
    logger.info(f"Mesh info: {mesh_info}")
    logger.info(f"Solver info: {solver_info}")
    logger.info(f"Simulation params: {sim_params}")
    logger.info(f"Case info: {case_info}")
    
    # Log available state data for debugging
    logger.info(f"Available state keys: {list(state.keys())}")
    logger.info(f"Simulation results structure: {list(simulation_results.keys()) if simulation_results else 'None'}")
    logger.info(f"Steps in simulation_results: {list(steps.keys()) if steps else 'None'}")
    
    return config_summary


def handle_normal_progression(state: CFDState) -> CFDState:
    """Handle normal workflow progression."""
    logger.info("DEBUG: handle_normal_progression - FUNCTION ENTRY")
    current_step = state["current_step"]
    logger.info(f"DEBUG: handle_normal_progression - current_step: {current_step}")
    
    # Check if user has explicitly approved (for resuming workflow)
    if current_step == CFDStep.USER_APPROVAL and state.get("user_approved", False):
        if state["verbose"]:
            logger.info("User approval received - proceeding to simulation")
        return {
            **state,
            "current_step": CFDStep.SIMULATION,
            "workflow_paused": False,
            "awaiting_user_approval": False,
            "config_only_mode": False,  # Full simulation mode after approval
            "retry_count": 0
        }
    
    # DEBUG: Add logging before step determination
    logger.info(f"DEBUG: handle_normal_progression - determining next step for current_step: {current_step}")
    logger.info(f"DEBUG: handle_normal_progression - config_only_mode: {state.get('config_only_mode')}")
    logger.info(f"DEBUG: handle_normal_progression - simulation_results config_only: {state.get('simulation_results', {}).get('config_only')}")
    
    # Determine next step based on current step  
    # Special case: handle simulation configuration vs full simulation
    if current_step == CFDStep.CASE_WRITING:
        if state.get("user_approval_enabled", True):
            # Run simulation in config-only mode first
            next_step = CFDStep.SIMULATION
            updated_state = {
                **state,
                "current_step": next_step,
                "config_only_mode": True,  # Configuration phase only
                "retry_count": 0
            }
            if state["verbose"]:
                logger.info("Normal progression: Running configuration phase (SIMULATION with config_only=True)")
            
            # DEBUG: Add explicit logging for config_only_mode being set
            logger.info(f"DEBUG: handle_normal_progression - SETTING config_only_mode=True in state")
            logger.info(f"DEBUG: handle_normal_progression - updated_state config_only_mode: {updated_state.get('config_only_mode')}")
            logger.info(f"DEBUG: handle_normal_progression - updated_state keys: {list(updated_state.keys())}")
            
            return updated_state
        else:
            # No user approval - go straight to full simulation
            next_step = CFDStep.SIMULATION
    elif current_step == CFDStep.SIMULATION and state.get("config_only_mode", False):
        # Configuration phase completed - now go to user approval
        logger.info("DEBUG: handle_normal_progression - ENTERED config-only SIMULATION transition branch")
        if state["verbose"]:
            logger.info("Normal progression: Configuration phase completed, moving to USER_APPROVAL")
        next_step = CFDStep.USER_APPROVAL
        
        # Create config summary for UI display
        config_summary = create_config_summary(state)
        
        # Clear config_only_mode as configuration phase is complete
        updated_state = {
            **state,
            "current_step": next_step,
            "config_only_mode": False,  # Config phase done
            "awaiting_user_approval": True,  # Set flag to pause workflow
            "workflow_paused": True,  # Set flag to pause workflow
            "config_summary": config_summary,  # Add config summary for UI
            "retry_count": 0
        }
        
        # DEBUG: Add explicit logging for transition from config-only SIMULATION to USER_APPROVAL
        logger.info(f"DEBUG: handle_normal_progression - TRANSITION from config-only SIMULATION to USER_APPROVAL")
        logger.info(f"DEBUG: handle_normal_progression - current state config_only_mode: {state.get('config_only_mode')}")
        logger.info(f"DEBUG: handle_normal_progression - simulation_results config_only: {state.get('simulation_results', {}).get('config_only')}")
        logger.info(f"DEBUG: handle_normal_progression - updated_state config_only_mode: {updated_state.get('config_only_mode')}")
        logger.info(f"DEBUG: handle_normal_progression - updated_state awaiting_user_approval: {updated_state.get('awaiting_user_approval')}")
        logger.info(f"DEBUG: handle_normal_progression - updated_state workflow_paused: {updated_state.get('workflow_paused')}")
        logger.info(f"DEBUG: handle_normal_progression - config_summary created: {config_summary is not None}")
        logger.info(f"DEBUG: handle_normal_progression - RETURNING updated_state for USER_APPROVAL")
        
        return updated_state
    else:
        # Normal step progression
        next_step_map = {
            CFDStep.START: CFDStep.NL_INTERPRETATION,
            CFDStep.NL_INTERPRETATION: CFDStep.MESH_GENERATION,
            CFDStep.MESH_GENERATION: CFDStep.BOUNDARY_CONDITIONS,
            CFDStep.BOUNDARY_CONDITIONS: CFDStep.SOLVER_SELECTION,
            CFDStep.SOLVER_SELECTION: CFDStep.CASE_WRITING,
            CFDStep.USER_APPROVAL: CFDStep.SIMULATION,  # After approval, run full simulation
            CFDStep.SIMULATION: CFDStep.VISUALIZATION,
            CFDStep.VISUALIZATION: CFDStep.RESULTS_REVIEW,
            CFDStep.RESULTS_REVIEW: CFDStep.COMPLETE,
        }
        next_step = next_step_map.get(current_step, CFDStep.COMPLETE)
    
    # Create updated state
    updated_state = {
        **state,
        "current_step": next_step,
        "retry_count": 0  # Reset retry count on successful progression
    }
    
    # If transitioning FROM user approval TO simulation, disable config_only mode
    if (current_step == CFDStep.USER_APPROVAL and 
        next_step == CFDStep.SIMULATION and 
        state.get("user_approved", False)):
        updated_state["config_only_mode"] = False  # Full simulation mode after approval
        if state["verbose"]:
            logger.info("Normal progression: Running full simulation after user approval")
    
    if state["verbose"]:
        logger.info(f"Normal progression: {current_step} -> {next_step}")
    
    logger.info(f"DEBUG: handle_normal_progression - FINAL RETURN with next_step: {next_step}")
    logger.info(f"DEBUG: handle_normal_progression - FINAL updated_state current_step: {updated_state.get('current_step')}")
    
    return updated_state


def determine_next_agent(state: CFDState) -> str:
    """Determine which agent to call next based on current step."""
    
    # DEBUG: Add explicit logging for determine_next_agent
    logger.info(f"DEBUG: determine_next_agent - current_step: {state['current_step']}")
    logger.info(f"DEBUG: determine_next_agent - awaiting_user_approval: {state.get('awaiting_user_approval', False)}")
    
    # Special case: if we're at user approval and awaiting approval, pause workflow
    if (state["current_step"] == CFDStep.USER_APPROVAL and 
        state.get("awaiting_user_approval", False)):
        logger.info("DEBUG: determine_next_agent - PAUSING workflow for user approval")
        return "end"  # Pause workflow until user approval
    
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
        force_validation: bool = False,

        mesh_convergence_active: bool = False,
        mesh_convergence_levels: int = 4,
        mesh_convergence_target_params: List[str] = None,
        mesh_convergence_threshold: float = 1.0,
        use_gpu: bool = False

        # Remote execution parameters
        execution_mode: str = "local",
        server_url: Optional[str] = None,
        project_name: Optional[str] = None

    ) -> CFDState:
    """
    Create initial state for the CFD workflow.
    
    Args:
        user_prompt: User's simulation description
        verbose: Enable verbose logging
        export_images: Enable image export
        output_format: Output format ("images", "data", etc.)
        max_retries: Maximum retry attempts
        user_approval_enabled: Enable user approval step
        stl_file: Optional STL file path
        force_validation: Force validation
        execution_mode: "local" or "remote"
        server_url: Server URL for remote execution
        project_name: Project name for remote execution
    """
    # Validate remote execution parameters
    if execution_mode == "remote":
        if not server_url:
            raise ValueError("server_url is required for remote execution")
        if not project_name:
            # Generate a unique project name if not provided
            import time
            import hashlib
            timestamp = str(int(time.time()))
            prompt_hash = hashlib.md5(user_prompt.encode()).hexdigest()[:8]
            project_name = f"foamai_{timestamp}_{prompt_hash}"
            logger.info(f"Generated project name for remote execution: {project_name}")
    
    initial_state = CFDState(
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
        mesh_convergence_active=mesh_convergence_active,
        mesh_convergence_levels=mesh_convergence_levels,
        mesh_convergence_target_params=mesh_convergence_target_params or [],
        mesh_convergence_threshold=mesh_convergence_threshold,
        mesh_convergence_results={},
        mesh_convergence_report={},
        recommended_mesh_level=0,
        use_gpu=use_gpu,
        gpu_info={
            "use_gpu": use_gpu,
            "gpu_explicit": False,
            "gpu_backend": "petsc"
        }
    ) 

        # Remote execution fields
        execution_mode=execution_mode,
        server_url=server_url,
        project_name=project_name,
        
        # User approval workflow fields
        awaiting_user_approval=False,
        workflow_paused=False,
        config_summary=None,
        config_only_mode=None
    )
    
    return initial_state


# Remote execution utility functions
def configure_remote_execution(
    server_url: str,
    project_name: str,
    test_connection: bool = True
) -> Dict[str, Any]:
    """
    Configure remote execution settings and optionally test the connection.
    
    Args:
        server_url: Remote server URL
        project_name: Project name on server
        test_connection: Whether to test the connection
        
    Returns:
        Configuration result with status and details
    """
    config_result = {
        "success": False,
        "server_url": server_url,
        "project_name": project_name,
        "tested": test_connection,
        "error": None
    }
    
    try:
        if test_connection:
            # Test server connection
            with RemoteExecutor(server_url, project_name) as remote:
                # Health check
                health = remote.health_check()
                
                # Ensure project exists or create it
                if not remote.ensure_project_exists():
                    remote.create_project_if_not_exists("LangGraph CFD workflow project")
                
                config_result["server_health"] = health
                config_result["project_created"] = True
        
        config_result["success"] = True
        logger.info(f"Remote execution configured successfully: {server_url} / {project_name}")
        
    except Exception as e:
        config_result["error"] = str(e)
        logger.error(f"Failed to configure remote execution: {str(e)}")
    
    return config_result


def create_remote_workflow_state(
    user_prompt: str,
    server_url: str,
    project_name: Optional[str] = None,
    **kwargs
) -> CFDState:
    """
    Convenience function to create a workflow state configured for remote execution.
    
    Args:
        user_prompt: User's simulation description
        server_url: Remote server URL
        project_name: Optional project name (auto-generated if not provided)
        **kwargs: Additional parameters for create_initial_state
        
    Returns:
        CFDState configured for remote execution
    """
    return create_initial_state(
        user_prompt=user_prompt,
        execution_mode="remote",
        server_url=server_url,
        project_name=project_name,
        **kwargs
    )


def get_remote_project_info(server_url: str, project_name: str) -> Dict[str, Any]:
    """
    Get information about a remote project.
    
    Args:
        server_url: Remote server URL
        project_name: Project name
        
    Returns:
        Project information including ParaView server status
    """
    try:
        import requests
        
        # Get project info
        response = requests.get(f"{server_url.rstrip('/')}/api/projects/{project_name}")
        response.raise_for_status()
        project_info = response.json()
        
        # Get ParaView server info
        try:
            pv_response = requests.get(f"{server_url.rstrip('/')}/api/projects/{project_name}/pvserver/info")
            pv_response.raise_for_status()
            pvserver_info = pv_response.json()
            project_info["pvserver_info"] = pvserver_info
        except Exception as e:
            logger.warning(f"Could not get ParaView server info: {e}")
            project_info["pvserver_info"] = {"status": "not_found"}
        
        return project_info
        
    except Exception as e:
        logger.error(f"Failed to get remote project info: {str(e)}")
        return {"error": str(e)}


def start_remote_paraview_server(server_url: str, project_name: str, port: Optional[int] = None) -> Dict[str, Any]:
    """
    Start ParaView server for a remote project using the project-based API.
    
    Args:
        server_url: Remote server URL
        project_name: Project name
        port: Optional specific port
        
    Returns:
        ParaView server information
    """
    try:
        import requests
        
        # Prepare request data
        data = {}
        if port:
            data["port"] = port
        
        # Start ParaView server using project-based API
        response = requests.post(
            f"{server_url.rstrip('/')}/api/projects/{project_name}/pvserver/start",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        result = response.json()
        
        # Extract connection info and format for widget
        formatted_result = {
            "success": True,
            "host": "localhost",  # ParaView server is accessible at localhost
            "port": result.get("port", 11111),
            "project_name": result.get("project_name", project_name),
            "connection_string": result.get("connection_string", f"localhost:{result.get('port', 11111)}"),
            "status": result.get("status", "running"),
            "pid": result.get("pid"),
            "case_path": result.get("case_path"),
            "started_at": result.get("started_at"),
            "message": result.get("message", "ParaView server started successfully")
        }
        
        logger.info(f"Started ParaView server for project '{project_name}': {formatted_result}")
        return formatted_result
        
    except Exception as e:
        logger.error(f"Failed to start remote ParaView server: {str(e)}")
        return {"error": str(e)}


def stop_remote_paraview_server(server_url: str, project_name: str) -> Dict[str, Any]:
    """
    Stop ParaView server for a remote project using the project-based API.
    
    Args:
        server_url: Remote server URL
        project_name: Project name
        
    Returns:
        Operation result
    """
    try:
        import requests
        
        # Stop ParaView server using project-based API
        response = requests.delete(f"{server_url.rstrip('/')}/api/projects/{project_name}/pvserver/stop")
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"Stopped ParaView server for project '{project_name}': {result}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to stop remote ParaView server: {str(e)}")
        return {"error": str(e)}


def approve_configuration_and_continue(state: CFDState) -> CFDState:
    """
    Approve the current configuration and continue the workflow.
    
    This function is called by the desktop UI when the user approves
    the configuration and wants to proceed with the simulation.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with approval and ready to continue
    """
    if state["verbose"]:
        logger.info("Configuration approved by user - continuing workflow")
    
    return {
        **state,
        "user_approved": True,
        "awaiting_user_approval": False,
        "workflow_paused": False,
        "current_step": CFDStep.USER_APPROVAL,  # Will progress to SIMULATION in next orchestrator call
        "retry_count": 0
    }


def reject_configuration(state: CFDState, feedback: str = "") -> CFDState:
    """
    Reject configuration and provide feedback for changes.
    
    Args:
        state: Current CFD state
        feedback: User feedback on what to change
        
    Returns:
        Updated CFD state routing back to solver selection
    """
    if state["verbose"]:
        logger.info(f"Configuration rejected with feedback: {feedback}")
    
    return {
        **state,
        "user_approved": False,
        "current_step": CFDStep.SOLVER_SELECTION,
        "awaiting_user_approval": False,
        "config_only_mode": False,
        "warnings": state.get("warnings", []) + [f"User requested changes: {feedback}"]
    }


def execute_solver_only(state: CFDState) -> CFDState:
    """
    Execute only the solver step after configuration is complete.
    
    This function is called when the user approves the configuration
    and wants to run the simulation with the prepared setup.
    
    Args:
        state: Current CFD state with complete configuration
        
    Returns:
        Updated CFD state with simulation results
    """
    try:
        if state["verbose"]:
            logger.info("Executing solver-only mode after user approval")
        
        # Import simulation executor functions
        from .simulation_executor import (
            run_solver_only_remote, 
            run_solver_only_local,
            parse_convergence_metrics
        )
        from .remote_executor import RemoteExecutor
        
        # Get execution parameters
        execution_mode = state.get("execution_mode", "local")
        server_url = state.get("server_url", "http://localhost:8000")
        project_name = state.get("project_name")
        solver = state.get("solver_settings", {}).get("solver", "simpleFoam")
        
        if execution_mode == "remote":
            if not project_name:
                raise ValueError("Project name is required for remote execution")
            
            # Execute solver remotely
            with RemoteExecutor(server_url, project_name) as remote:
                solver_results = run_solver_only_remote(remote, solver, state)
        else:
            # Execute solver locally
            case_directory = Path(state["case_directory"])
            solver_results = run_solver_only_local(case_directory, solver, state)
        
        # Check solver results
        if not solver_results["success"]:
            error_msg = f"Solver execution failed: {solver_results.get('error', 'Unknown error')}"
            logger.error(error_msg)
            return {
                **state,
                "errors": state.get("errors", []) + [error_msg],
                "current_step": CFDStep.ERROR
            }
        
        # Parse convergence metrics
        convergence_metrics = parse_convergence_metrics(solver_results)
        
        # Update state with solver results
        updated_state = {
            **state,
            "simulation_results": solver_results,
            "convergence_metrics": convergence_metrics,
            "current_step": CFDStep.VISUALIZATION if state.get("export_images", True) else CFDStep.RESULTS_REVIEW,
            "errors": []
        }
        
        if state["verbose"]:
            logger.info("Solver-only execution completed successfully")
            logger.info(f"Final residuals: {convergence_metrics.get('final_residuals', {})}")
        
        return updated_state
        
    except Exception as e:
        logger.error(f"Solver-only execution error: {str(e)}")
        return {
            **state,
            "errors": state.get("errors", []) + [f"Solver execution failed: {str(e)}"],
            "current_step": CFDStep.ERROR
        } 

