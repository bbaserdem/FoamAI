"""
LangGraph Interface - Bridge between desktop client and LangGraph orchestrator.

This module provides a clean interface for the desktop client to interact
with the LangGraph CFD workflow, handling workflow execution, progress monitoring,
and result retrieval.
"""

import sys
import os
import time
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtWidgets import QApplication
import logging

# Add foamai-core to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "foamai-core"))

from foamai_core.orchestrator import (
    create_cfd_workflow, 
    create_initial_state, 
    create_remote_workflow_state,
    configure_remote_execution
)
from foamai_core.state import CFDState, CFDStep

logger = logging.getLogger(__name__)


class LangGraphInterface(QObject):
    """
    Interface class for integrating LangGraph CFD workflow with desktop client.
    
    This class provides a clean API for the desktop to interact with the
    LangGraph orchestrator, handling workflow execution and progress monitoring.
    """
    
    # Signals for progress updates
    step_changed = Signal(str, str)  # step_name, description
    progress_updated = Signal(int)  # progress_percentage
    log_message = Signal(str, str)  # level, message  
    workflow_completed = Signal(dict)  # final_state
    workflow_failed = Signal(str)  # error_message
    mesh_generated = Signal(dict)  # mesh_info
    simulation_started = Signal()
    simulation_progress = Signal(dict)  # progress_info
    simulation_completed = Signal(dict)  # results
    user_approval_required = Signal(dict)  # config_summary for UI approval
    
    def __init__(self, server_url: str, verbose: bool = True):
        """
        Initialize LangGraph interface.
        
        Args:
            server_url: URL of the remote OpenFOAM server
            verbose: Enable verbose logging
        """
        super().__init__()
        self.server_url = server_url
        self.verbose = verbose
        self.workflow = None
        self.current_state = None
        self.project_name = None
        self.is_running = False
        
        # Initialize workflow
        self._initialize_workflow()
        
        logger.info(f"LangGraphInterface initialized for server: {server_url}")
    
    def _initialize_workflow(self):
        """Initialize the LangGraph workflow."""
        try:
            self.workflow = create_cfd_workflow()
            logger.info("LangGraph CFD workflow initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LangGraph workflow: {str(e)}")
            raise
    
    def configure_remote_execution(self, project_name: str, test_connection: bool = True) -> Dict[str, Any]:
        """
        Configure remote execution for a specific project.
        
        Args:
            project_name: Name of the project on remote server
            test_connection: Whether to test the connection
            
        Returns:
            Configuration result
        """
        try:
            result = configure_remote_execution(
                server_url=self.server_url,
                project_name=project_name,
                test_connection=test_connection
            )
            
            if result["success"]:
                self.project_name = project_name
                logger.info(f"Remote execution configured for project: {project_name}")
            else:
                logger.error(f"Failed to configure remote execution: {result.get('error')}")
            
            return result
            
        except Exception as e:
            error_msg = f"Exception during remote execution configuration: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    def start_workflow(
        self, 
        user_prompt: str,
        project_name: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Start the CFD workflow.
        
        Args:
            user_prompt: User's simulation description
            project_name: Optional project name (uses configured one if not provided)
            **kwargs: Additional workflow parameters
            
        Returns:
            True if workflow started successfully, False otherwise
        """
        if self.is_running:
            logger.warning("Workflow is already running")
            return False
        
        try:
            # Use provided project name or fall back to configured one
            if project_name:
                self.project_name = project_name
            elif not self.project_name:
                # Generate a unique project name
                import time
                import hashlib
                timestamp = str(int(time.time()))
                prompt_hash = hashlib.md5(user_prompt.encode()).hexdigest()[:8]
                self.project_name = f"desktop_{timestamp}_{prompt_hash}"
                logger.info(f"Generated project name: {self.project_name}")
            
            # Create initial state for remote execution
            # Filter out conflicting kwargs
            filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ['verbose', 'server_url', 'project_name', 'user_prompt']}
            
            self.current_state = create_remote_workflow_state(
                user_prompt=user_prompt,
                server_url=self.server_url,
                project_name=self.project_name,
                verbose=self.verbose,
                **filtered_kwargs
            )
            
            # Start workflow in separate thread
            self.workflow_thread = WorkflowThread(self.workflow, self.current_state, self)
            self.workflow_thread.step_changed.connect(self.step_changed)
            self.workflow_thread.progress_updated.connect(self.progress_updated)
            self.workflow_thread.log_message.connect(self.log_message)
            self.workflow_thread.workflow_completed.connect(self._on_workflow_completed)
            self.workflow_thread.workflow_failed.connect(self._on_workflow_failed)
            self.workflow_thread.state_updated.connect(self._on_state_updated)
            
            self.workflow_thread.start()
            self.is_running = True
            
            logger.info(f"Started CFD workflow for project: {self.project_name}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to start workflow: {str(e)}"
            logger.error(error_msg)
            self.workflow_failed.emit(error_msg)
            return False
    
    def stop_workflow(self) -> bool:
        """
        Stop the running workflow.
        
        Returns:
            True if workflow stopped successfully, False otherwise
        """
        if not self.is_running:
            logger.warning("No workflow is currently running")
            return False
        
        try:
            if hasattr(self, 'workflow_thread') and self.workflow_thread.isRunning():
                self.workflow_thread.stop()
                self.workflow_thread.wait(5000)  # Wait up to 5 seconds
                
                if self.workflow_thread.isRunning():
                    self.workflow_thread.terminate()
                    logger.warning("Workflow thread terminated forcefully")
                else:
                    logger.info("Workflow stopped successfully")
            
            self.is_running = False
            return True
            
        except Exception as e:
            logger.error(f"Error stopping workflow: {str(e)}")
            return False
    
    def get_current_state(self) -> Optional[CFDState]:
        """Get the current workflow state."""
        return self.current_state
    
    def get_project_name(self) -> Optional[str]:
        """Get the current project name."""
        return self.project_name
    
    def is_workflow_running(self) -> bool:
        """Check if workflow is currently running."""
        return self.is_running
    
    def approve_configuration(self) -> bool:
        """
        Approve the current configuration and continue workflow.
        
        Returns:
            True if approval was successful, False otherwise
        """
        if not self.current_state or not self.current_state.get("awaiting_user_approval", False):
            logger.warning("No configuration approval pending")
            return False
        
        try:
            from foamai_core.orchestrator import approve_configuration_and_continue
            
            # Update state to approve configuration
            approved_state = approve_configuration_and_continue(self.current_state)
            
            # Start a new workflow execution with the approved state
            self.workflow_thread = WorkflowThread(self.workflow, approved_state, self)
            self.workflow_thread.step_changed.connect(self.step_changed)
            self.workflow_thread.progress_updated.connect(self.progress_updated)
            self.workflow_thread.log_message.connect(self.log_message)
            self.workflow_thread.workflow_completed.connect(self._on_workflow_completed)
            self.workflow_thread.workflow_failed.connect(self._on_workflow_failed)
            self.workflow_thread.state_updated.connect(self._on_state_updated)
            
            self.workflow_thread.start()
            self.current_state = approved_state
            
            logger.info("Configuration approved - workflow continuing")
            return True
            
        except Exception as e:
            logger.error(f"Failed to approve configuration: {str(e)}")
            return False
    
    def reject_configuration(self, feedback: str = "") -> bool:
        """
        Reject the current configuration and provide feedback.
        
        Args:
            feedback: User feedback on what to change
            
        Returns:
            True if rejection was successful, False otherwise
        """
        if not self.current_state or not self.current_state.get("awaiting_user_approval", False):
            logger.warning("No configuration approval pending")
            return False
        
        try:
            from foamai_core.orchestrator import reject_configuration
            
            # Update state to reject configuration
            rejected_state = reject_configuration(self.current_state, feedback)
            
            # Start a new workflow execution with the rejected state (will restart from solver selection)
            self.workflow_thread = WorkflowThread(self.workflow, rejected_state, self)
            self.workflow_thread.step_changed.connect(self.step_changed)
            self.workflow_thread.progress_updated.connect(self.progress_updated)
            self.workflow_thread.log_message.connect(self.log_message)
            self.workflow_thread.workflow_completed.connect(self._on_workflow_completed)
            self.workflow_thread.workflow_failed.connect(self._on_workflow_failed)
            self.workflow_thread.state_updated.connect(self._on_state_updated)
            
            self.workflow_thread.start()
            self.current_state = rejected_state
            
            logger.info(f"Configuration rejected with feedback: {feedback}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reject configuration: {str(e)}")
            return False
    
    def _on_workflow_completed(self, final_state: Dict[str, Any]):
        """Handle workflow completion."""
        self.current_state = final_state
        self.is_running = False
        self.workflow_completed.emit(final_state)
        logger.info("Workflow completed successfully")
    
    def _on_workflow_failed(self, error_message: str):
        """Handle workflow failure."""
        self.is_running = False
        self.workflow_failed.emit(error_message)
        logger.error(f"Workflow failed: {error_message}")
    
    def _on_state_updated(self, state: Dict[str, Any]):
        """Handle state updates during workflow execution."""
        self.current_state = state
        
        # Extract specific information and emit targeted signals
        current_step = state.get("current_step")
        
        # Check for user approval requirement
        if (current_step == CFDStep.USER_APPROVAL and 
            state.get("awaiting_user_approval", False) and 
            state.get("config_summary")):
            logger.info("User approval required - emitting signal to UI")
            self.user_approval_required.emit(state["config_summary"])
        
        # Check for mesh generation completion
        if current_step == CFDStep.BOUNDARY_CONDITIONS and state.get("mesh_config"):
            self.mesh_generated.emit(state["mesh_config"])
        
        # Check for simulation start
        if current_step == CFDStep.SIMULATION and not hasattr(self, '_simulation_started'):
            self._simulation_started = True
            self.simulation_started.emit()
        
        # Check for simulation progress
        if current_step == CFDStep.SIMULATION and state.get("simulation_results"):
            self.simulation_progress.emit(state["simulation_results"])
        
        # Check for simulation completion
        if current_step in [CFDStep.VISUALIZATION, CFDStep.RESULTS_REVIEW] and state.get("simulation_results"):
            if hasattr(self, '_simulation_started'):
                delattr(self, '_simulation_started')
                self.simulation_completed.emit(state["simulation_results"])


class WorkflowThread(QThread):
    """
    Thread for running the LangGraph workflow without blocking the UI.
    """
    
    step_changed = Signal(str, str)
    progress_updated = Signal(int)
    log_message = Signal(str, str)
    workflow_completed = Signal(dict)
    workflow_failed = Signal(str)
    state_updated = Signal(dict)
    
    def __init__(self, workflow, initial_state: CFDState, parent=None):
        super().__init__(parent)
        self.workflow = workflow
        self.initial_state = initial_state
        self.should_stop = False
        self.current_state = initial_state
    
    def run(self):
        """Run the workflow in the background thread."""
        try:
            logger.info("Starting workflow execution in background thread")
            
            # Execute workflow step by step with progress monitoring
            state = self.initial_state
            step_count = 0
            max_steps = 20  # Reasonable maximum to prevent infinite loops
            
            while not self.should_stop and step_count < max_steps:
                # Emit current step information
                current_step = state.get("current_step", CFDStep.START)
                step_name = current_step.value if hasattr(current_step, 'value') else str(current_step)
                
                self.step_changed.emit(step_name, self._get_step_description(current_step))
                
                # Update progress
                progress = self._calculate_progress(current_step)
                self.progress_updated.emit(progress)
                
                # Execute one workflow step
                try:
                    next_state = self.workflow.invoke(state)
                    
                    # Check if state actually changed
                    if next_state == state:
                        logger.warning("Workflow state did not change, may be stuck")
                        break
                    
                    state = next_state
                    self.current_state = state
                    self.state_updated.emit(state)
                    
                    # Check for completion or error
                    current_step = state.get("current_step", CFDStep.START)
                    if current_step in [CFDStep.COMPLETE, CFDStep.ERROR]:
                        break
                    
                    # Check for errors
                    if state.get("errors"):
                        self.log_message.emit("warning", f"Workflow errors: {state['errors']}")
                        # Don't fail immediately, let error handler try to recover
                    
                    step_count += 1
                    
                except Exception as e:
                    error_msg = f"Error during workflow step {step_name}: {str(e)}"
                    logger.error(error_msg)
                    self.workflow_failed.emit(error_msg)
                    return
            
            # Check final state
            final_step = state.get("current_step", CFDStep.ERROR)
            errors = state.get("errors", [])
            
            # Special case: workflow paused for user approval
            if (final_step == CFDStep.USER_APPROVAL and 
                state.get("awaiting_user_approval", False)):
                logger.info("Workflow paused for user review - waiting for approval")
                # Don't emit completion or failure - this is a pause state
                # The UI will handle this via the user_approval_required signal
                return
            
            # Check if there are errors even if step shows complete
            if errors and final_step != CFDStep.ERROR:
                logger.warning(f"Workflow completed with errors: {errors}")
                self.workflow_failed.emit(f"Workflow failed with errors: {errors}")
            elif final_step == CFDStep.COMPLETE and not errors:
                self.progress_updated.emit(100)
                self.workflow_completed.emit(state)
            elif final_step == CFDStep.ERROR:
                self.workflow_failed.emit(f"Workflow ended in error state: {errors}")
            else:
                self.workflow_failed.emit(f"Workflow stopped unexpectedly at step: {final_step}")
                
        except Exception as e:
            error_msg = f"Critical error in workflow thread: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.workflow_failed.emit(error_msg)
    
    def stop(self):
        """Stop the workflow execution."""
        self.should_stop = True
    
    def _get_step_description(self, step: CFDStep) -> str:
        """Get human-readable description for workflow step."""
        descriptions = {
            CFDStep.START: "Initializing workflow",
            CFDStep.NL_INTERPRETATION: "Interpreting simulation requirements",
            CFDStep.MESH_GENERATION: "Generating computational mesh",
            CFDStep.BOUNDARY_CONDITIONS: "Setting up boundary conditions",
            CFDStep.SOLVER_SELECTION: "Configuring solver settings",
            CFDStep.CASE_WRITING: "Writing simulation files",
            CFDStep.USER_APPROVAL: "Waiting for user approval",
            CFDStep.SIMULATION: "Running OpenFOAM simulation",
            CFDStep.VISUALIZATION: "Generating visualization",
            CFDStep.RESULTS_REVIEW: "Analyzing results",
            CFDStep.ERROR_HANDLER: "Handling errors and attempting recovery",
            CFDStep.COMPLETE: "Workflow completed successfully",
            CFDStep.ERROR: "Workflow failed"
        }
        return descriptions.get(step, f"Unknown step: {step}")
    
    def _calculate_progress(self, step: CFDStep) -> int:
        """Calculate progress percentage based on current step."""
        step_progress = {
            CFDStep.START: 0,
            CFDStep.NL_INTERPRETATION: 10,
            CFDStep.MESH_GENERATION: 20,
            CFDStep.BOUNDARY_CONDITIONS: 30,
            CFDStep.SOLVER_SELECTION: 40,
            CFDStep.CASE_WRITING: 50,
            CFDStep.USER_APPROVAL: 55,
            CFDStep.SIMULATION: 70,
            CFDStep.VISUALIZATION: 90,
            CFDStep.RESULTS_REVIEW: 95,
            CFDStep.COMPLETE: 100,
            CFDStep.ERROR: 0
        }
        return step_progress.get(step, 0) 