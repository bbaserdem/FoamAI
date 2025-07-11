"""System Orchestrator Agent - Central workflow controller."""

import uuid
from typing import Dict, Any, Optional
from loguru import logger

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
                "retry_count": 0
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
    
    # Check if user has explicitly approved (for resuming workflow)
    if current_step == CFDStep.USER_APPROVAL and state.get("user_approved", False):
        if state["verbose"]:
            logger.info("User approval received - proceeding to simulation")
        return {
            **state,
            "current_step": CFDStep.SIMULATION,
            "workflow_paused": False,
            "awaiting_user_approval": False,
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
    
    return {
        **state,
        "current_step": next_step,
        "retry_count": 0  # Reset retry count on successful progression
    }


def determine_next_agent(state: CFDState) -> str:
    """Determine which agent to call next based on current step."""
    
    # Special case: if we're at user approval and awaiting approval, pause workflow
    if (state["current_step"] == CFDStep.USER_APPROVAL and 
        state.get("awaiting_user_approval", False)):
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
        # Remote execution fields
        execution_mode=execution_mode,
        server_url=server_url,
        project_name=project_name,
        
        # User approval workflow fields
        awaiting_user_approval=False,
        workflow_paused=False,
        config_summary=None
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
    Reject the current configuration and provide feedback.
    
    This function is called by the desktop UI when the user wants
    to modify the configuration.
    
    Args:
        state: Current workflow state
        feedback: User feedback on what to change
        
    Returns:
        Updated state to restart from solver selection
    """
    if state["verbose"]:
        logger.info(f"Configuration rejected by user with feedback: {feedback}")
    
    return {
        **state,
        "user_approved": False,
        "awaiting_user_approval": False,
        "workflow_paused": False,
        "current_step": CFDStep.SOLVER_SELECTION,  # Restart from solver selection
        "warnings": state["warnings"] + [f"User requested changes: {feedback}"] if feedback else state["warnings"],
        "retry_count": 0
    } 