"""
Simulation Setup Widget for OpenFOAM Desktop Application
Main widget that replaces the chat interface with structured simulation setup
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLineEdit, QLabel, QFrame, QTextEdit, QMessageBox, QDialog,
                               QProgressBar)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
from PySide6.QtGui import QFont

from api_client import ProjectAPIClient
from simulation_state import SimulationState, ComponentState, MeshData, SolverData, ParametersData
from simulation_cards import MeshCard, SolverCard, ParametersCard
from langgraph_interface import LangGraphInterface

logger = logging.getLogger(__name__)


class SimulationSetupWidget(QWidget):
    """Main simulation setup widget with LangGraph integration."""
    
    # Signals
    workflow_started = Signal()
    workflow_completed = Signal(dict)
    workflow_failed = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = None
        self.current_project = None
        self.langgraph_interface = None
        self.simulation_state = SimulationState()
        
        self.setup_ui()
        self.setup_connections()
        
        logger.info("SimulationSetupWidget initialized")
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("CFD Simulation Setup")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Input section
        input_frame = QFrame()
        input_frame.setFrameStyle(QFrame.Shape.Box)
        input_frame.setStyleSheet("QFrame { border: 1px solid #ccc; border-radius: 5px; padding: 10px; }")
        input_layout = QVBoxLayout(input_frame)
        
        # Prompt input
        prompt_label = QLabel("Describe your simulation:")
        prompt_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        input_layout.addWidget(prompt_label)
        
        self.prompt_input = QTextEdit()
        self.prompt_input.setMaximumHeight(100)
        self.prompt_input.setPlaceholderText("e.g., 'Flow around a cylinder at 5 m/s with a diameter of 0.1m'")
        input_layout.addWidget(self.prompt_input)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Simulation Setup")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.stop_button.setEnabled(False)
        
        self.run_simulation_button = QPushButton("Run Simulation")
        self.run_simulation_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.run_simulation_button.setEnabled(False)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()
        button_layout.addWidget(self.run_simulation_button)
        
        input_layout.addLayout(button_layout)
        layout.addWidget(input_frame)
        
        # Progress section
        progress_frame = QFrame()
        progress_frame.setFrameStyle(QFrame.Shape.Box)
        progress_frame.setStyleSheet("QFrame { border: 1px solid #ccc; border-radius: 5px; padding: 10px; }")
        progress_layout = QVBoxLayout(progress_frame)
        
        self.progress_label = QLabel("Ready to start simulation setup")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addWidget(progress_frame)
        
        # Simulation cards
        cards_frame = QFrame()
        cards_layout = QVBoxLayout(cards_frame) # Changed to VBoxLayout
        cards_layout.setSpacing(15) # Reduced spacing
        
        # Mesh card
        self.mesh_card = MeshCard()
        cards_layout.addWidget(self.mesh_card)
        
        # Solver card  
        self.solver_card = SolverCard()
        cards_layout.addWidget(self.solver_card)
        
        # Parameters card
        self.parameters_card = ParametersCard()
        cards_layout.addWidget(self.parameters_card)
        
        layout.addWidget(cards_frame)
        
        # Log section
        log_frame = QFrame()
        log_frame.setFrameStyle(QFrame.Shape.Box)
        log_frame.setStyleSheet("QFrame { border: 1px solid #ccc; border-radius: 5px; padding: 5px; }")
        log_layout = QVBoxLayout(log_frame)
        
        log_label = QLabel("Workflow Log:")
        log_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        log_layout.addWidget(log_label)
        
        self.log_display = QTextEdit()
        self.log_display.setMaximumHeight(200) # Increased height
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("QTextEdit { background-color: #f5f5f5; }")
        log_layout.addWidget(self.log_display)
        
        layout.addWidget(log_frame)
    
    def setup_connections(self):
        """Set up signal-slot connections."""
        self.start_button.clicked.connect(self.start_workflow)
        self.stop_button.clicked.connect(self.stop_workflow)
        self.run_simulation_button.clicked.connect(self.run_simulation)
    
    def set_api_client(self, api_client: ProjectAPIClient):
        """Set the API client for server communication."""
        logger.info(f"SimulationSetupWidget.set_api_client called with: {api_client}")
        self.api_client = api_client
        
        # Initialize LangGraph interface with server URL
        if api_client and hasattr(api_client, 'base_url'):
            try:
                logger.info(f"Initializing LangGraph interface with URL: {api_client.base_url}")
                self.langgraph_interface = LangGraphInterface(api_client.base_url, verbose=True)
                self.setup_langgraph_connections()
                self.add_log_message("info", "LangGraph interface initialized successfully")
                logger.info("LangGraph interface initialized successfully")
                
                # If project was set before LangGraph interface was ready, configure it now
                if self.current_project:
                    logger.info(f"Configuring previously set project: {self.current_project}")
                    result = self.langgraph_interface.configure_remote_execution(self.current_project, test_connection=True)
                    if result["success"]:
                        self.add_log_message("info", f"Configured for project: {self.current_project}")
                    else:
                        self.add_log_message("error", f"Failed to configure project: {result.get('error')}")
            except Exception as e:
                logger.error(f"Failed to initialize LangGraph interface: {str(e)}")
                self.add_log_message("error", f"Failed to initialize LangGraph interface: {str(e)}")
        else:
            logger.warning("API client not available for LangGraph interface")
    
    def setup_langgraph_connections(self):
        """Set up connections to LangGraph interface signals."""
        if not self.langgraph_interface:
            return
        
        # Connect workflow signals
        self.langgraph_interface.step_changed.connect(self.on_step_changed)
        self.langgraph_interface.progress_updated.connect(self.on_progress_updated)
        self.langgraph_interface.log_message.connect(self.add_log_message)
        self.langgraph_interface.workflow_completed.connect(self.on_workflow_completed)
        self.langgraph_interface.workflow_failed.connect(self.on_workflow_failed)
        
        # Connect specific simulation signals
        self.langgraph_interface.mesh_generated.connect(self.on_mesh_generated)
        self.langgraph_interface.simulation_started.connect(self.on_simulation_started)
        self.langgraph_interface.simulation_progress.connect(self.on_simulation_progress)
        self.langgraph_interface.simulation_completed.connect(self.on_simulation_completed)
        self.langgraph_interface.user_approval_required.connect(self.on_user_approval_required)
    
    def set_current_project(self, project_name: str):
        """Set the current project for workflow execution."""
        logger.info(f"SimulationSetupWidget.set_current_project called with: {project_name}")
        self.current_project = project_name
        
        if self.langgraph_interface:
            # Configure remote execution for this project
            result = self.langgraph_interface.configure_remote_execution(project_name, test_connection=True)
            if result["success"]:
                self.add_log_message("info", f"Configured for project: {project_name}")
            else:
                self.add_log_message("error", f"Failed to configure project: {result.get('error')}")
        else:
            logger.info(f"Project set to: {project_name} (LangGraph interface not yet available)")
            self.add_log_message("info", f"Project set to: {project_name} (LangGraph interface not yet available)")
    
    def start_workflow(self):
        """Start the LangGraph CFD workflow."""
        logger.info(f"start_workflow called - current_project: {self.current_project}")
        
        if not self.langgraph_interface:
            QMessageBox.warning(self, "Error", "LangGraph interface not available")
            return
        
        if not self.current_project:
            logger.warning(f"No project selected - current_project is: {self.current_project}")
            QMessageBox.warning(self, "Error", "No project selected")
            return
        
        user_prompt = self.prompt_input.toPlainText().strip()
        if not user_prompt:
            QMessageBox.warning(self, "Error", "Please enter a simulation description")
            return
        
        # Reset UI state
        self.reset_cards()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_display.clear()
        
        # Update button states
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.run_simulation_button.setEnabled(False)
        
        # Start workflow
        try:
            success = self.langgraph_interface.start_workflow(
                user_prompt=user_prompt,
                project_name=self.current_project,
                verbose=True,
                export_images=True
            )
            
            if success:
                self.add_log_message("info", "Workflow started successfully")
                self.workflow_started.emit()
            else:
                self.add_log_message("error", "Failed to start workflow")
                self.reset_ui_state()
                
        except Exception as e:
            logger.error(f"Error starting workflow: {str(e)}")
            self.add_log_message("error", f"Error starting workflow: {str(e)}")
            self.reset_ui_state()
    
    def stop_workflow(self):
        """Stop the running workflow."""
        if not self.langgraph_interface:
            return
        
        try:
            success = self.langgraph_interface.stop_workflow()
            if success:
                self.add_log_message("info", "Workflow stopped")
            else:
                self.add_log_message("warning", "Failed to stop workflow gracefully")
        except Exception as e:
            logger.error(f"Error stopping workflow: {str(e)}")
            self.add_log_message("error", f"Error stopping workflow: {str(e)}")
        
        self.reset_ui_state()
    
    def run_simulation(self):
        """Approve configuration and run the OpenFOAM simulation."""
        if not self.langgraph_interface:
            QMessageBox.warning(self, "Error", "LangGraph interface not available")
            return
        
        # Check if we're waiting for user approval (configuration review)
        current_state = self.langgraph_interface.get_current_state()
        if current_state and current_state.get("awaiting_user_approval", False):
            # User ready to proceed - continue workflow with simulation
            success = self.langgraph_interface.approve_configuration()
            if success:
                self.add_log_message("info", "🚀 Starting OpenFOAM simulation on remote server...")
                self.run_simulation_button.setEnabled(False)
                self.run_simulation_button.setText("⏳ Running Simulation...")
                
                # Update card states to show simulation starting
                self.mesh_card.set_state(ComponentState.LOCKED)
                self.solver_card.set_state(ComponentState.LOCKED) 
                self.parameters_card.set_state(ComponentState.LOCKED)
            else:
                self.add_log_message("error", "Failed to start simulation")
        else:
            # No configuration review pending
            QMessageBox.information(self, "Info", "No simulation configuration ready for review.\nPlease run 'Start Simulation Setup' first.")
    
    def reset_ui_state(self):
        """Reset UI to initial state."""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Ready to start simulation setup")
    
    def reset_cards(self):
        """Reset all simulation cards to initial state."""
        self.mesh_card.set_state(ComponentState.EMPTY)
        self.solver_card.set_state(ComponentState.EMPTY)
        self.parameters_card.set_state(ComponentState.EMPTY)
        
        # Clear descriptions
        self.mesh_card.set_description("")
        self.solver_card.set_description("")
        self.parameters_card.set_description("")
    
    def add_log_message(self, level: str, message: str):
        """Add a message to the log display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {level.upper()}: {message}"
        
        # Add color based on level
        if level == "error":
            color = "red"
        elif level == "warning":
            color = "orange"
        elif level == "info":
            color = "blue"
        else:
            color = "black"
        
        self.log_display.append(f'<span style="color: {color};">{formatted_message}</span>')
        
        # Auto-scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    # LangGraph signal handlers
    def on_step_changed(self, step_name: str, description: str):
        """Handle workflow step changes."""
        self.progress_label.setText(f"Current step: {description}")
        self.add_log_message("info", f"Step: {step_name} - {description}")
        
        # Update card states based on step
        if step_name == "mesh_generation":
            self.mesh_card.set_state(ComponentState.PROCESSING)
        elif step_name == "boundary_conditions":
            self.mesh_card.set_state(ComponentState.COMPLETE)
            self.solver_card.set_state(ComponentState.PROCESSING)
        elif step_name == "solver_selection":
            self.solver_card.set_state(ComponentState.PROCESSING)
        elif step_name == "case_writing":
            self.solver_card.set_state(ComponentState.COMPLETE)
            self.parameters_card.set_state(ComponentState.PROCESSING)
        elif step_name == "simulation":
            self.parameters_card.set_state(ComponentState.COMPLETE)
    
    def on_progress_updated(self, progress: int):
        """Handle progress updates."""
        self.progress_bar.setValue(progress)
    
    def on_workflow_completed(self, final_state: Dict[str, Any]):
        """Handle workflow completion."""
        self.add_log_message("info", "Workflow completed successfully!")
        self.progress_label.setText("Workflow completed - ready to run simulation")
        self.progress_bar.setValue(100)
        
        # Enable run simulation button
        self.run_simulation_button.setEnabled(True)
        self.reset_ui_state()
        
        # Update all cards to complete
        self.mesh_card.set_state(ComponentState.COMPLETE)
        self.solver_card.set_state(ComponentState.COMPLETE)
        self.parameters_card.set_state(ComponentState.COMPLETE)
        
        self.workflow_completed.emit(final_state)
    
    def on_workflow_failed(self, error_message: str):
        """Handle workflow failure."""
        self.add_log_message("error", f"Workflow failed: {error_message}")
        self.progress_label.setText("Workflow failed")
        
        # Update cards to show error
        self.mesh_card.set_state(ComponentState.ERROR)
        self.solver_card.set_state(ComponentState.ERROR)
        self.parameters_card.set_state(ComponentState.ERROR)
        
        self.reset_ui_state()
        self.workflow_failed.emit(error_message)
    
    def on_mesh_generated(self, mesh_info: Dict[str, Any]):
        """Handle mesh generation completion."""
        self.add_log_message("info", "Mesh generation completed")
        
        # Update mesh card with real data
        mesh_data = MeshData(
            cell_count=mesh_info.get("total_cells", 0),
            mesh_type=mesh_info.get("type", "blockMesh"),
            quality_score=mesh_info.get("quality_score", 0.0)
        )
        # Update mesh card with mesh info
        mesh_info_text = f"Cells: {mesh_data.cell_count}\nType: {mesh_data.mesh_type}"
        if mesh_data.quality_score > 0:
            mesh_info_text += f"\nQuality: {mesh_data.quality_score:.2f}"
        self.mesh_card.set_description(mesh_info_text)
        self.mesh_card.set_state(ComponentState.COMPLETE)
    
    def on_simulation_started(self):
        """Handle simulation start."""
        self.add_log_message("info", "OpenFOAM simulation started")
    
    def on_simulation_progress(self, progress_info: Dict[str, Any]):
        """Handle simulation progress updates."""
        # Extract useful progress information
        steps = progress_info.get("steps", {})
        if "solver" in steps:
            solver_info = steps["solver"]
            if solver_info.get("success"):
                self.add_log_message("info", "Solver execution progressing...")
    
    def on_simulation_completed(self, results: Dict[str, Any]):
        """Handle simulation completion."""
        self.add_log_message("info", "OpenFOAM simulation completed")
        
        # Update solver card with results
        solver_name = results.get("solver", "Unknown")
        convergence = results.get("success", False)
        iterations = results.get("iterations", 0)
        
        solver_info_text = f"Solver: {solver_name}"
        if iterations > 0:
            solver_info_text += f"\nIterations: {iterations}"
        solver_info_text += f"\nConverged: {'Yes' if convergence else 'No'}"
        
        self.solver_card.set_solver_info(solver_name, solver_info_text)
    
    def on_user_approval_required(self, config_summary: Dict[str, Any]):
        """Handle configuration ready for review - update cards and enable Run Simulation button."""
        self.add_log_message("info", "✅ Configuration generated and ready for review")
        self.progress_label.setText("Review simulation setup below, then click 'Run Simulation' when ready")
        
        try:
            # Update mesh card
            mesh_info = config_summary.get("mesh_info", {})
            if mesh_info:
                mesh_text = f"Type: {mesh_info.get('mesh_type', 'Unknown')}\n"
                mesh_text += f"Cells: {mesh_info.get('total_cells', 0):,}\n"
                mesh_text += f"Quality: {mesh_info.get('quality_score', 0):.2f}"
                self.mesh_card.set_description(mesh_text)
                self.mesh_card.set_state(ComponentState.POPULATED)
            
            # Update solver card
            solver_info = config_summary.get("solver_info", {})
            if solver_info:
                solver_text = f"Solver: {solver_info.get('solver_name', 'Unknown')}\n"
                solver_text += f"End time: {solver_info.get('end_time', 0)} s\n"
                solver_text += f"Time step: {solver_info.get('time_step', 0)} s"
                self.solver_card.set_description(solver_text)
                self.solver_card.set_state(ComponentState.POPULATED)
            
            # Update parameters card
            sim_params = config_summary.get("simulation_parameters", {})
            if sim_params:
                param_text = f"Flow: {sim_params.get('flow_type', 'Unknown')}\n"
                param_text += f"Analysis: {sim_params.get('analysis_type', 'Unknown')}\n"
                if sim_params.get('velocity'):
                    param_text += f"Velocity: {sim_params['velocity']:.2f} m/s"
                self.parameters_card.set_description(param_text)
                self.parameters_card.set_state(ComponentState.POPULATED)
            
            # Auto-load mesh into ParaView for visualization
            self._auto_load_mesh_visualization(config_summary)
            
            # Enable Run Simulation button with clearer text
            self.run_simulation_button.setEnabled(True)
            self.run_simulation_button.setText("🚀 Run Simulation")
            
            # Log AI explanation if available
            ai_explanation = config_summary.get("ai_explanation", "")
            if ai_explanation:
                self.add_log_message("info", f"AI Analysis: {ai_explanation}")
                
        except Exception as e:
            logger.error(f"Error updating UI with config summary: {str(e)}")
            self.add_log_message("error", f"Error updating configuration display: {str(e)}")
    
    def _auto_load_mesh_visualization(self, config_summary: Dict[str, Any]):
        """Automatically load the generated mesh into ParaView for visualization."""
        try:
            # Check if we have a parent main window with ParaView widget
            main_window = self.parent()
            if not main_window or not hasattr(main_window, 'paraview_widget'):
                self.add_log_message("warning", "ParaView widget not available for mesh visualization")
                return
            
            paraview_widget = main_window.paraview_widget
            
            # Check if ParaView is connected
            if not paraview_widget.is_connected():
                self.add_log_message("info", "🔗 Connecting to ParaView server for mesh visualization...")
                # Try to connect to ParaView
                paraview_widget.connect_to_server()
                
                # Give it a moment to connect, then try to load
                QTimer.singleShot(2000, lambda: self._load_mesh_file(config_summary, paraview_widget))
            else:
                # Already connected, load immediately
                self._load_mesh_file(config_summary, paraview_widget)
                
        except Exception as e:
            logger.error(f"Error auto-loading mesh visualization: {str(e)}")
            self.add_log_message("error", f"Failed to auto-load mesh: {str(e)}")
    
    def _load_mesh_file(self, config_summary: Dict[str, Any], paraview_widget):
        """Load the mesh file into ParaView."""
        try:
            # Get the case path from config summary or construct it
            case_info = config_summary.get("case_info", {})
            foam_file_path = case_info.get("foam_file_path")
            
            if not foam_file_path and self.current_project:
                # Construct the .foam file path based on project name
                foam_file_path = f"/home/ubuntu/foam_projects/{self.current_project}/active_run/{self.current_project}.foam"
                self.add_log_message("info", f"Using constructed foam file path: {foam_file_path}")
            
            if foam_file_path:
                self.add_log_message("info", f"📊 Loading mesh visualization: {foam_file_path}")
                paraview_widget.load_foam_file(foam_file_path)
                self.add_log_message("info", "✅ Mesh loaded into ParaView - you can now review the geometry")
            else:
                self.add_log_message("warning", "No mesh file path available for visualization")
                
        except Exception as e:
            logger.error(f"Error loading mesh file: {str(e)}")
            self.add_log_message("error", f"Failed to load mesh file: {str(e)}") 