"""
Simulation Setup Widget for OpenFOAM Desktop Application
Main widget that replaces the chat interface with structured simulation setup
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLineEdit, QLabel, QFrame, QTextEdit, QMessageBox, QDialog,
                               QProgressBar, QScrollArea, QApplication)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
from PySide6.QtGui import QFont

from .api_client import ProjectAPIClient
from .simulation_state import SimulationState, ComponentState, MeshData, SolverData, ParametersData
from .simulation_cards import MeshCard, SolverCard, ParametersCard
from .langgraph_interface import LangGraphInterface
from .detail_dialogs import MeshDetailDialog, SolverDetailDialog, ParametersDetailDialog

logger = logging.getLogger(__name__)


class SimulationSetupWidget(QWidget):
    """Main simulation setup widget with LangGraph integration."""
    
    # Signals
    workflow_started = Signal()
    workflow_completed = Signal(dict)
    workflow_failed = Signal(str)
    
    # New signals for ParaView integration
    paraview_connect_requested = Signal(str, str)  # server_url, project_name
    paraview_disconnect_requested = Signal()
    paraview_load_mesh_requested = Signal(str)  # file_path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_client = None
        self.current_project = None
        self.langgraph_interface = None
        self.simulation_state = SimulationState()
        self.current_config_summary = None  # Store current configuration for editing
        self.paraview_was_connected = False  # Track if ParaView was connected before project switch
        
        self.setup_ui()
        self.setup_connections()
        
        logger.info("SimulationSetupWidget initialized")
    
    def get_screen_height_class(self):
        """Determine screen height class for responsive design"""
        screen = QApplication.primaryScreen()
        if screen:
            screen_height = screen.size().height()
            if screen_height < 768:
                return "small"
            elif screen_height < 1080:
                return "medium"
            else:
                return "large"
        return "medium"  # default fallback
    
    def get_responsive_spacing(self, base_spacing=20):
        """Get responsive spacing based on screen height - prioritize content over spacing"""
        height_class = self.get_screen_height_class()
        if height_class == "small":
            return int(base_spacing * 0.5)  # 50% reduction
        elif height_class == "medium":
            return int(base_spacing * 0.75)  # 25% reduction
        else:
            return int(base_spacing * 0.85)  # 15% reduction even on large screens to save space
    
    def get_responsive_font_size(self, base_size=18):
        """Get responsive font size based on screen height"""
        height_class = self.get_screen_height_class()
        if height_class == "small":
            return max(12, int(base_size * 0.67))  # Significantly smaller for small screens
        elif height_class == "medium":
            return max(14, int(base_size * 0.83))  # Moderately smaller
        else:
            return base_size
    
    def get_responsive_log_height(self):
        """Get adaptive log display height based on screen size - prioritize simulation cards"""
        screen = QApplication.primaryScreen()
        if screen:
            height_class = self.get_screen_height_class()
            
            if height_class == "small":
                return 80  # Fixed small height for small screens
            elif height_class == "medium":
                return 100  # Fixed moderate height for medium screens
            else:
                return 120  # Fixed reasonable height for large screens - don't scale with screen size
        return 100  # fallback
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Use responsive spacing and margins
        responsive_spacing = self.get_responsive_spacing(20)
        layout.setSpacing(responsive_spacing)
        layout.setContentsMargins(responsive_spacing, responsive_spacing, responsive_spacing, responsive_spacing)
        
        # Title with responsive font size
        title = QLabel("CFD Simulation Setup")
        title_font_size = self.get_responsive_font_size(18)
        title.setFont(QFont("Arial", title_font_size, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Input section with consolidated action buttons in header
        input_frame = QFrame()
        input_frame.setFrameStyle(QFrame.Shape.Box)
        input_frame.setStyleSheet("QFrame { border: 1px solid #ccc; border-radius: 5px; padding: 10px; }")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setSpacing(self.get_responsive_spacing(10))
        
        # Header row with prompt label and action buttons
        header_layout = QHBoxLayout()
        
        prompt_label = QLabel("Describe your simulation:")
        prompt_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        header_layout.addWidget(prompt_label)
        
        header_layout.addStretch()  # Push buttons to the right
        
        # Action buttons in header (consolidated to save vertical space)
        self.start_button = QPushButton("Start Setup")
        self.start_button.setMaximumHeight(30)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
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
        self.stop_button.setMaximumHeight(30)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.stop_button.setEnabled(False)
        
        self.run_simulation_button = QPushButton("Run Simulation")
        self.run_simulation_button.setMaximumHeight(30)
        self.run_simulation_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 11px;
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
        
        header_layout.addWidget(self.start_button)
        header_layout.addWidget(self.stop_button)
        header_layout.addWidget(self.run_simulation_button)
        
        input_layout.addLayout(header_layout)
        
        # Prompt input
        self.prompt_input = QTextEdit()
        
        # Responsive input height - prioritize simulation cards over prompt area
        height_class = self.get_screen_height_class()
        input_height = 60 if height_class == "small" else 75 if height_class == "medium" else 80
        self.prompt_input.setMaximumHeight(input_height)
        self.prompt_input.setPlaceholderText("e.g., 'Flow around a cylinder at 5 m/s with a diameter of 0.1m'")
        input_layout.addWidget(self.prompt_input)
        
        layout.addWidget(input_frame)
        
        # Progress section (hidden to save vertical space, but kept for functionality)
        progress_frame = QFrame()
        progress_frame.setFrameStyle(QFrame.Shape.Box)
        progress_frame.setStyleSheet("QFrame { border: 1px solid #ccc; border-radius: 5px; padding: 8px; }")
        progress_layout = QVBoxLayout(progress_frame)
        progress_layout.setSpacing(5)
        
        # Combine progress label and bar in one compact section
        progress_header = QHBoxLayout()
        self.progress_label = QLabel("Ready to start simulation setup")
        self.progress_label.setFont(QFont("Arial", 9))
        progress_header.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setVisible(False)
        progress_header.addWidget(self.progress_bar)
        
        progress_layout.addLayout(progress_header)
        
        # Hide the entire progress section to save vertical space
        progress_frame.setVisible(False)
        
        layout.addWidget(progress_frame)
        
        # Simulation cards section - scroll area for small/medium screens, direct layout for large screens
        height_class = self.get_screen_height_class()
        
        if height_class in ["small", "medium"]:
            # Use scroll area for constrained screens
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameStyle(QFrame.NoFrame)
            
            cards_widget = QWidget()
            cards_layout = QVBoxLayout(cards_widget)
            
            # More compact spacing for smaller screens
            cards_spacing = 5 if height_class == "small" else 8
            cards_layout.setSpacing(cards_spacing)
            
            # Mesh card (fixed height for scrolling)
            self.mesh_card = MeshCard()
            cards_layout.addWidget(self.mesh_card)
            
            # Solver card (fixed height for scrolling)
            self.solver_card = SolverCard()
            cards_layout.addWidget(self.solver_card)
            
            # Parameters card (fixed height for scrolling)
            self.parameters_card = ParametersCard()
            cards_layout.addWidget(self.parameters_card)
            
            cards_layout.addStretch()  # Push cards to top
            scroll_area.setWidget(cards_widget)
            layout.addWidget(scroll_area, 1)
            
        else:
            # Use direct layout for large screens - no scrolling, cards expand to fill space
            cards_frame = QFrame()
            cards_frame.setFrameStyle(QFrame.NoFrame)
            cards_layout = QVBoxLayout(cards_frame)
            
            cards_spacing = self.get_responsive_spacing(15)  # Normal spacing on large screens
            cards_layout.setSpacing(cards_spacing)
            
            # Mesh card with expansion
            self.mesh_card = MeshCard()
            cards_layout.addWidget(self.mesh_card, 1)  # Give equal stretch to all cards
            
            # Solver card with expansion
            self.solver_card = SolverCard()
            cards_layout.addWidget(self.solver_card, 1)  # Give equal stretch to all cards
            
            # Parameters card with expansion
            self.parameters_card = ParametersCard()
            cards_layout.addWidget(self.parameters_card, 1)  # Give equal stretch to all cards
            
            layout.addWidget(cards_frame, 1)  # Give simulation cards area more weight in layout
        
        # Log section with adaptive height
        log_frame = QFrame()
        log_frame.setFrameStyle(QFrame.Shape.Box)
        log_frame.setStyleSheet("QFrame { border: 1px solid #ccc; border-radius: 5px; padding: 5px; }")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setSpacing(5)
        
        log_label = QLabel("Workflow Log:")
        log_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        log_layout.addWidget(log_label)
        
        self.log_display = QTextEdit()
        
        # Use adaptive height instead of fixed height
        adaptive_log_height = self.get_responsive_log_height()
        self.log_display.setMaximumHeight(adaptive_log_height)
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("QTextEdit { background-color: #f5f5f5; }")
        log_layout.addWidget(self.log_display)
        
        layout.addWidget(log_frame)
    
    def setup_connections(self):
        """Set up signal-slot connections."""
        self.start_button.clicked.connect(self.start_workflow)
        self.stop_button.clicked.connect(self.stop_workflow)
        self.run_simulation_button.clicked.connect(self.run_simulation)
        
        # Connect card edit signals
        self.mesh_card.edit_requested.connect(self.on_edit_requested)
        self.solver_card.edit_requested.connect(self.on_edit_requested)
        self.parameters_card.edit_requested.connect(self.on_edit_requested)
    
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
        
        # Check if we're switching to a different project and ParaView is connected
        if self.current_project != project_name and self.current_project is not None:
            # Check if ParaView is currently connected
            main_window = self.parent()
            if main_window and hasattr(main_window, 'paraview_widget'):
                paraview_widget = main_window.paraview_widget
                # Check the connection status using the internal connected flag to avoid API calls during switching
                self.paraview_was_connected = getattr(paraview_widget, 'connected', False)
                
                if self.paraview_was_connected:
                    self.add_log_message("info", f"📡 Disconnecting from ParaView before switching to project: {project_name}")
                    self.paraview_disconnect_requested.emit()
        
        self.current_project = project_name
        
        if self.langgraph_interface:
            # Configure remote execution for this project
            result = self.langgraph_interface.configure_remote_execution(project_name, test_connection=True)
            if result["success"]:
                self.add_log_message("info", f"Configured for project: {project_name}")
                
                # If ParaView was connected before switching, reconnect to new project
                if self.paraview_was_connected and self.api_client:
                    self.add_log_message("info", f"📡 Reconnecting to ParaView for new project: {project_name}")
                    # Give more time for the disconnection and project configuration to settle
                    QTimer.singleShot(2000, lambda: self.paraview_connect_requested.emit(self.api_client.base_url, project_name))
                    self.paraview_was_connected = False  # Reset flag
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
            # Check if configuration has been modified by user
            if current_state.get("user_modified_config", False):
                self.add_log_message("info", "🔄 Using user-modified configuration for simulation")
            
            # Debug: Show what solver will be used
            solver_settings = current_state.get("solver_settings", {})
            solver_name = solver_settings.get("solver", "Unknown")
            logger.info(f"DEBUG: About to run simulation with solver: {solver_name}")
            logger.info(f"DEBUG: Full solver_settings: {solver_settings}")
            self.add_log_message("info", f"🔧 Running simulation with solver: {solver_name}")
            
            # Disconnect from ParaView before starting simulation to prevent freezing
            self.add_log_message("info", "📡 Disconnecting from ParaView server before simulation...")
            self.paraview_disconnect_requested.emit()
            
            # User ready to proceed - run solver only
            success = self.langgraph_interface.run_solver_only()
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
    
    def on_edit_requested(self, component_type: str):
        """Handle edit request from a simulation card."""
        logger.info(f"Edit requested for component: {component_type}")
        
        if component_type == "mesh":
            self.open_mesh_detail_dialog()
        elif component_type == "solver":
            self.open_solver_detail_dialog()
        elif component_type == "parameters":
            self.open_parameters_detail_dialog()
    
    def open_mesh_detail_dialog(self):
        """Open mesh detail dialog for editing."""
        # Create mesh data from current state
        mesh_data = self._create_mesh_data_from_config()
        
        dialog = MeshDetailDialog(mesh_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get updated data and validate
            updated_mesh_data = dialog.get_mesh_data()
            
            # Show validation preview if there are issues
            if not self._show_validation_preview("mesh", updated_mesh_data):
                return  # User chose not to continue with invalid data
            
            # Update mesh card with new data
            self.mesh_card.set_description(updated_mesh_data.description)
            self.mesh_card.set_state(ComponentState.POPULATED)
            
            # Send updated configuration back to LangGraph
            self._send_config_update("mesh", updated_mesh_data)
            self.add_log_message("info", "Mesh configuration updated")
            
            # Add visual indicator that this component has been modified
            self._mark_component_as_modified("mesh")
    
    def open_solver_detail_dialog(self):
        """Open solver detail dialog for editing."""
        # Create solver data from current state
        solver_data = self._create_solver_data_from_config()
        
        dialog = SolverDetailDialog(solver_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get updated data and validate
            updated_solver_data = dialog.get_solver_data()
            
            # Show validation preview if there are issues
            if not self._show_validation_preview("solver", updated_solver_data):
                return  # User chose not to continue with invalid data
            
            # Update solver card with new data
            self.solver_card.set_solver_info(
                updated_solver_data.name,
                updated_solver_data.description,
                updated_solver_data.justification
            )
            
            # Send updated configuration back to LangGraph
            self._send_config_update("solver", updated_solver_data)
            self.add_log_message("info", "Solver configuration updated")
            
            # Add visual indicator that this component has been modified
            self._mark_component_as_modified("solver")
    
    def open_parameters_detail_dialog(self):
        """Open parameters detail dialog for editing."""
        # Create parameters data from current state
        parameters_data = self._create_parameters_data_from_config()
        
        dialog = ParametersDetailDialog(parameters_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get updated data and validate
            updated_parameters_data = dialog.get_parameters_data()
            
            # Show validation preview if there are issues
            if not self._show_validation_preview("parameters", updated_parameters_data):
                return  # User chose not to continue with invalid data
            
            # Update parameters card with new data
            self.parameters_card.set_parameters_info(
                updated_parameters_data.description,
                updated_parameters_data.parameters
            )
            
            # Send updated configuration back to LangGraph
            self._send_config_update("parameters", updated_parameters_data)
            self.add_log_message("info", "Parameters configuration updated")
            
            # Add visual indicator that this component has been modified
            self._mark_component_as_modified("parameters")
    
    def _create_mesh_data_from_config(self) -> MeshData:
        """Create mesh data from current configuration summary."""
        if not self.current_config_summary:
            return MeshData(
                description=self.mesh_card.description_label.text(),
                generated_by_ai=True
            )
        
        mesh_info = self.current_config_summary.get("mesh_info", {})
        mesh_config = self.current_config_summary.get("mesh_config", {})
        
        return MeshData(
            description=mesh_info.get("description", mesh_config.get("description", self.mesh_card.description_label.text())),
            file_path=mesh_info.get("file_path", mesh_config.get("file_path")),
            file_type=mesh_info.get("mesh_type", mesh_config.get("type", "blockMesh")),
            content=mesh_info.get("content", mesh_config.get("content")),
            generated_by_ai=True
        )
    
    def _create_solver_data_from_config(self) -> SolverData:
        """Create solver data from current configuration summary."""
        if not self.current_config_summary:
            return SolverData(
                name="Current Solver",
                description=self.solver_card.description_label.text(),
                generated_by_ai=True
            )
        
        solver_info = self.current_config_summary.get("solver_info", {})
        solver_config = self.current_config_summary.get("solver_config", {})
        
        return SolverData(
            name=solver_info.get("solver_name", solver_config.get("name", "simpleFoam")),
            description=solver_info.get("description", solver_config.get("description", self.solver_card.description_label.text())),
            justification=solver_info.get("justification", solver_config.get("justification", "")),
            parameters=solver_info.get("parameters", solver_config.get("parameters", {})),
            generated_by_ai=True
        )
    
    def _create_parameters_data_from_config(self) -> ParametersData:
        """Create parameters data from current configuration summary."""
        if not self.current_config_summary:
            return ParametersData(
                description=self.parameters_card.description_label.text(),
                generated_by_ai=True
            )
        
        sim_params = self.current_config_summary.get("simulation_parameters", {})
        
        return ParametersData(
            description=sim_params.get("description", self.parameters_card.description_label.text()),
            parameters=sim_params.get("parameters", sim_params),  # Use entire sim_params as parameters
            generated_by_ai=True
        )
    
    def _send_config_update(self, component: str, data):
        """Send configuration update to LangGraph interface."""
        if not self.langgraph_interface:
            logger.warning("LangGraph interface not available for configuration update")
            return
        
        try:
            # Validate the configuration before sending
            validation_result = self._validate_component_config(component, data)
            if not validation_result["valid"]:
                logger.error(f"Configuration validation failed for {component}: {validation_result['errors']}")
                self.add_log_message("error", f"❌ {component.capitalize()} configuration validation failed: {', '.join(validation_result['errors'])}")
                return
            
            # Convert the data to a format suitable for the workflow
            config_update = {component: self._convert_data_to_config_format(component, data)}
            
            # Add debug logging for solver updates
            if component == "solver":
                solver_name = getattr(data, 'name', 'Unknown')
                logger.info(f"DEBUG: Sending solver update - name: {solver_name}")
                logger.info(f"DEBUG: Full solver data: {data}")
                logger.info(f"DEBUG: Converted config update: {config_update}")
            
            # Send the update to the LangGraph interface
            success = self.langgraph_interface.update_configuration(config_update)
            
            if success:
                logger.info(f"Successfully updated {component} configuration")
                if component == "solver":
                    solver_name = getattr(data, 'name', 'Unknown')
                    self.add_log_message("info", f"✅ Solver updated to: {solver_name}")
                else:
                    self.add_log_message("info", f"✅ {component.capitalize()} configuration sent to workflow")
                
                # Update the local configuration summary to reflect changes
                self._update_local_config_summary(component, data)
            else:
                logger.error(f"Failed to update {component} configuration")
                self.add_log_message("error", f"❌ Failed to update {component} configuration")
                
        except Exception as e:
            logger.error(f"Error sending {component} configuration update: {str(e)}")
            self.add_log_message("error", f"❌ Error updating {component} configuration: {str(e)}")
    
    def _convert_data_to_config_format(self, component: str, data) -> Dict[str, Any]:
        """Convert UI data to configuration format expected by LangGraph."""
        if component == "mesh":
            return {
                "description": data.description,
                "file_path": data.file_path,
                "file_type": data.file_type,
                "content": data.content,
                "user_modified": True
            }
        elif component == "solver":
            return {
                "name": data.name,
                "description": data.description,
                "justification": data.justification,
                "parameters": data.parameters,
                "user_modified": True
            }
        elif component == "parameters":
            return {
                "description": data.description,
                "parameters": data.parameters,
                "content": data.content,
                "user_modified": True
            }
        else:
            return {"user_modified": True}
    
    def _validate_component_config(self, component: str, data) -> Dict[str, Any]:
        """Validate component configuration before sending to LangGraph."""
        errors = []
        
        try:
            if component == "mesh":
                errors.extend(self._validate_mesh_config(data))
            elif component == "solver":
                errors.extend(self._validate_solver_config(data))
            elif component == "parameters":
                errors.extend(self._validate_parameters_config(data))
            
            return {
                "valid": len(errors) == 0,
                "errors": errors
            }
            
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"]
            }
    
    def _validate_mesh_config(self, mesh_data: MeshData) -> List[str]:
        """Validate mesh configuration."""
        errors = []
        
        if not mesh_data.description and not mesh_data.content:
            errors.append("Mesh must have either a description or content")
        
        if mesh_data.file_path and not mesh_data.file_type:
            errors.append("Mesh file must have a file type")
        
        if mesh_data.file_type and mesh_data.file_type not in ['.stl', '.foam', '.obj', 'blockMesh', 'snappyHexMesh']:
            errors.append(f"Unsupported mesh file type: {mesh_data.file_type}")
        
        return errors
    
    def _validate_solver_config(self, solver_data: SolverData) -> List[str]:
        """Validate solver configuration."""
        errors = []
        
        if not solver_data.name:
            errors.append("Solver name is required")
        
        # Check if solver name is valid OpenFOAM solver
        valid_solvers = [
            "simpleFoam", "pimpleFoam", "icoFoam", "buoyantSimpleFoam", 
            "rhoPimpleFoam", "potentialFoam", "interFoam", "reactingFoam",
            "chtMultiRegionFoam", "rhoSimpleFoam", "sonicFoam"
        ]
        if solver_data.name not in valid_solvers:
            errors.append(f"Unknown solver: {solver_data.name}. Valid solvers: {', '.join(valid_solvers)}")
        
        if not solver_data.description:
            errors.append("Solver description is required")
        
        return errors
    
    def _validate_parameters_config(self, parameters_data: ParametersData) -> List[str]:
        """Validate parameters configuration."""
        errors = []
        
        if not parameters_data.description and not parameters_data.parameters:
            errors.append("Parameters must have either a description or parameter values")
        
        # Validate parameter values if present
        if parameters_data.parameters:
            for key, value in parameters_data.parameters.items():
                if not key.strip():
                    errors.append("Parameter names cannot be empty")
                if isinstance(value, str) and not value.strip():
                    errors.append(f"Parameter '{key}' has empty value")
        
        return errors
    
    def _update_local_config_summary(self, component: str, data):
        """Update the local configuration summary with user changes."""
        if not self.current_config_summary:
            self.current_config_summary = {}
        
        if component == "mesh":
            if "mesh_info" not in self.current_config_summary:
                self.current_config_summary["mesh_info"] = {}
            self.current_config_summary["mesh_info"].update({
                "description": data.description,
                "file_path": data.file_path,
                "mesh_type": data.file_type,
                "content": data.content,
                "user_modified": True
            })
            
        elif component == "solver":
            if "solver_info" not in self.current_config_summary:
                self.current_config_summary["solver_info"] = {}
            self.current_config_summary["solver_info"].update({
                "solver_name": data.name,
                "description": data.description,
                "justification": data.justification,
                "parameters": data.parameters,
                "user_modified": True
            })
            
        elif component == "parameters":
            if "simulation_parameters" not in self.current_config_summary:
                self.current_config_summary["simulation_parameters"] = {}
            self.current_config_summary["simulation_parameters"].update({
                "description": data.description,
                "parameters": data.parameters,
                "user_modified": True
            })
        
        # Mark the entire configuration as user-modified
        self.current_config_summary["user_modified"] = True
        
        logger.info(f"Updated local config summary for {component}")
    
    def _mark_component_as_modified(self, component: str):
        """Add visual indicator that a component has been modified by the user."""
        if component == "mesh":
            card = self.mesh_card
        elif component == "solver":
            card = self.solver_card
        elif component == "parameters":
            card = self.parameters_card
        else:
            return
        
        # Update the status label to show modification
        current_status = card.status_label.text()
        if "Modified" not in current_status:
            card.status_label.setText(f"{current_status} - Modified")
            card.status_label.setStyleSheet("color: #ff8c00; font-size: 10pt; font-weight: bold;")
        
        # Add visual border to indicate modification
        card.setStyleSheet(card.styleSheet() + """
            QFrame {
                border: 3px solid #ff8c00 !important;
                box-shadow: 0 0 10px rgba(255, 140, 0, 0.3);
            }
        """)
        
        logger.info(f"Marked {component} as modified with visual indicators")
    
    def _show_validation_preview(self, component: str, data) -> bool:
        """Show a preview of validation results before applying changes."""
        validation_result = self._validate_component_config(component, data)
        
        if not validation_result["valid"]:
            # Show validation errors in a message box
            error_message = f"Configuration validation failed for {component}:\n\n"
            error_message += "\n".join(f"• {error}" for error in validation_result["errors"])
            
            reply = QMessageBox.question(
                self,
                "Validation Errors",
                f"{error_message}\n\nDo you want to continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            return reply == QMessageBox.StandardButton.Yes
        
        return True
    
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
        
        # Re-enable run simulation button and reset text
        self.run_simulation_button.setEnabled(True)
        self.run_simulation_button.setText("🚀 Run Simulation")
        
        # Reconnect to ParaView to view results
        if self.api_client and self.current_project:
            self.add_log_message("info", "📡 Reconnecting to ParaView server to view results...")
            self.paraview_connect_requested.emit(self.api_client.base_url, self.current_project)
    
    def on_user_approval_required(self, config_summary: Dict[str, Any]):
        """Handle configuration ready for review - update cards and enable Run Simulation button."""
        logger.info(f"on_user_approval_required called with config_summary keys: {list(config_summary.keys()) if config_summary else 'None'}")
        self.add_log_message("info", "✅ Configuration generated and ready for review")
        self.progress_label.setText("Review simulation setup below, then click 'Run Simulation' when ready")
        
        # Store the configuration summary for editing
        self.current_config_summary = config_summary
        
        try:
            # Update mesh card
            mesh_info = config_summary.get("mesh_info", {})
            if mesh_info and mesh_info.get("total_cells", 0) > 0:
                mesh_text = f"Type: {mesh_info.get('mesh_type', 'Unknown')}\n"
                mesh_text += f"Cells: {mesh_info.get('total_cells', 0):,}\n"
                if mesh_info.get('quality_score', 0) > 0:
                    mesh_text += f"Quality: {mesh_info.get('quality_score', 0):.2f}"
                self.mesh_card.set_description(mesh_text)
                self.mesh_card.set_state(ComponentState.POPULATED)
            else:
                # Fallback to mesh config if mesh_info not available
                mesh_config = config_summary.get("mesh_config", {})
                if mesh_config:
                    mesh_text = f"Type: {mesh_config.get('type', 'Unknown')}\n"
                    mesh_text += f"Cells: {mesh_config.get('total_cells', 0):,}"
                    self.mesh_card.set_description(mesh_text)
                    self.mesh_card.set_state(ComponentState.POPULATED)
                else:
                    # Last resort - show basic info
                    self.mesh_card.set_description("Mesh configuration generated")
                    self.mesh_card.set_state(ComponentState.POPULATED)
            
            # Update solver card
            solver_info = config_summary.get("solver_info", {})
            if solver_info and solver_info.get("solver_name"):
                solver_text = f"Solver: {solver_info.get('solver_name', 'Unknown')}\n"
                solver_text += f"End time: {solver_info.get('end_time', 0)} s\n"
                solver_text += f"Time step: {solver_info.get('time_step', 0)} s"
                self.solver_card.set_description(solver_text)
                self.solver_card.set_state(ComponentState.POPULATED)
            else:
                # Fallback - show basic info
                self.solver_card.set_description("Solver configuration generated")
                self.solver_card.set_state(ComponentState.POPULATED)
            
            # Update parameters card
            sim_params = config_summary.get("simulation_parameters", {})
            if sim_params and sim_params.get("flow_type"):
                param_text = f"Flow: {sim_params.get('flow_type', 'Unknown')}\n"
                param_text += f"Analysis: {sim_params.get('analysis_type', 'Unknown')}\n"
                if sim_params.get('velocity'):
                    param_text += f"Velocity: {sim_params['velocity']:.2f} m/s"
                self.parameters_card.set_description(param_text)
                self.parameters_card.set_state(ComponentState.POPULATED)
            else:
                # Fallback - show basic info
                self.parameters_card.set_description("Simulation parameters configured")
                self.parameters_card.set_state(ComponentState.POPULATED)
            
            # Auto-load mesh into ParaView for visualization
            self._auto_load_mesh_visualization(config_summary)
            
        except Exception as e:
            logger.error(f"Error updating UI with config summary: {str(e)}")
            self.add_log_message("error", f"Error updating configuration display: {str(e)}")
            
        finally:
            # Always enable Run Simulation button and reset UI state
            self.run_simulation_button.setEnabled(True)
            self.run_simulation_button.setText("🚀 Run Simulation")
            
            # Mark workflow as stopped at this point
            self.reset_ui_state()
            
            # Log AI explanation if available
            ai_explanation = config_summary.get("ai_explanation", "")
            if ai_explanation:
                self.add_log_message("info", f"AI Analysis: {ai_explanation}")
            else:
                self.add_log_message("info", "Configuration review complete. Ready to run simulation!")
    
    def _auto_load_mesh_visualization(self, config_summary: Dict[str, Any]):
        """Automatically load the generated mesh into ParaView for visualization."""
        try:
            # Check if we have a parent main window with ParaView widget
            main_window = self.parent()
            if not main_window or not hasattr(main_window, 'paraview_widget'):
                self.add_log_message("warning", "ParaView widget not available for mesh visualization")
                return
            
            paraview_widget = main_window.paraview_widget
            
            # Get the case path from config summary or construct it
            case_info = config_summary.get("case_info", {})
            foam_file_path = case_info.get("foam_file_path")
            
            if not foam_file_path and self.current_project:
                # Construct the .foam file path based on project name
                foam_file_path = f"/home/ubuntu/foam_projects/{self.current_project}/active_run/{self.current_project}.foam"
                self.add_log_message("info", f"Using constructed foam file path: {foam_file_path}")
            
            if not foam_file_path:
                self.add_log_message("warning", "No mesh file path available for visualization")
                return
            
            # Always trigger ParaView connection when setup is finished (it will check server status internally)
            self.add_log_message("info", "🔗 Connecting to ParaView server for mesh visualization...")
            if self.api_client and self.current_project:
                # Emit the connection request signal
                self.paraview_connect_requested.emit(self.api_client.base_url, self.current_project)
                
                # Schedule mesh loading after connection (give it time to connect and start server if needed)
                QTimer.singleShot(5000, lambda: self.paraview_load_mesh_requested.emit(foam_file_path))
                self.add_log_message("info", "✅ ParaView connection requested - mesh will load automatically")
            else:
                self.add_log_message("error", "API client or project not available for ParaView connection")
                
        except Exception as e:
            logger.error(f"Error auto-loading mesh visualization: {str(e)}")
            self.add_log_message("error", f"Failed to auto-load mesh: {str(e)}") 