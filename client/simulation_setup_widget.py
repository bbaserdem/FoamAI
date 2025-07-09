"""
Simulation Setup Widget for OpenFOAM Desktop Application
Main widget that replaces the chat interface with structured simulation setup
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLineEdit, QLabel, QFrame, QTextEdit, QMessageBox, QDialog)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
from PySide6.QtGui import QFont

from api_client import APIClient
from simulation_state import SimulationState, ComponentState, MeshData, SolverData, ParametersData
from simulation_cards import MeshCard, SolverCard, ParametersCard
from detail_dialogs import MeshDetailDialog, SolverDetailDialog, ParametersDetailDialog

logger = logging.getLogger(__name__)

class AIWorker(QObject):
    """Worker thread for AI API calls"""
    
    # Signals
    response_received = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, api_client: APIClient):
        super().__init__()
        self.api_client = api_client
    
    def process_scenario(self, scenario: str, current_state: dict):
        """Process scenario with AI"""
        try:
            # For now, return dummy responses
            # TODO: Replace with actual API calls
            response = self.generate_dummy_response(scenario, current_state)
            self.response_received.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def generate_dummy_response(self, scenario: str, current_state: dict) -> dict:
        """Generate dummy AI response for testing"""
        # Simulate processing time
        import time
        time.sleep(1)
        
        # Generate dummy mesh data
        mesh_data = {
            "description": f"Cube mesh for scenario: {scenario[:50]}...",
            "file_path": "/tmp/dummy_mesh.foam",
            "file_type": "foam",
            "content": "// Dummy OpenFOAM mesh content\n// Generated for: " + scenario,
            "generated_by_ai": True
        }
        
        # Generate dummy solver data
        solver_data = {
            "name": "simpleFoam",
            "description": "Steady-state solver for incompressible, turbulent flows",
            "justification": f"Selected simpleFoam for this scenario because it handles the wind flow around objects effectively.",
            "parameters": {"turbulence": "RAS", "scheme": "SIMPLE"},
            "generated_by_ai": True
        }
        
        # Generate dummy parameters data
        parameters_data = {
            "description": f"Wind simulation parameters for scenario: {scenario[:50]}...",
            "parameters": {
                "windSpeed": "10 m/s",
                "density": "1.2 kg/m³",
                "viscosity": "1.5e-5 m²/s",
                "iterations": "1000"
            },
            "generated_by_ai": True
        }
        
        return {
            "status": "success",
            "message": "Simulation components generated successfully!",
            "mesh": mesh_data,
            "solver": solver_data,
            "parameters": parameters_data
        }

class SimulationSetupWidget(QWidget):
    """Main simulation setup widget"""
    
    # Signals
    mesh_file_ready = Signal(str)
    results_ready = Signal(str)
    simulation_started = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize API client
        self.api_client = APIClient()
        
        # Initialize simulation state
        self.simulation_state = SimulationState()
        
        # Setup worker thread
        self.worker_thread = QThread()
        self.worker = AIWorker(self.api_client)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()
        
        # Connect worker signals
        self.worker.response_received.connect(self.handle_ai_response)
        self.worker.error_occurred.connect(self.handle_ai_error)
        
        # Setup UI
        self.setup_ui()
        
        # Connect signals
        self.connect_signals()
        
        # Update UI state
        self.update_ui_state()
    
    def setup_ui(self):
        """Setup the main UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("Simulation Setup")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Configure your CFD simulation components below")
        subtitle_label.setFont(QFont("Segoe UI", 10))
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(subtitle_label)
        
        # Mesh card
        self.mesh_card = MeshCard()
        layout.addWidget(self.mesh_card)
        
        # Solver card
        self.solver_card = SolverCard()
        layout.addWidget(self.solver_card)
        
        # Parameters card
        self.parameters_card = ParametersCard()
        layout.addWidget(self.parameters_card)
        
        # AI input area
        ai_group = QFrame()
        ai_group.setFrameStyle(QFrame.StyledPanel)
        ai_group.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        ai_layout = QVBoxLayout(ai_group)
        
        ai_label = QLabel("AI Assistant")
        ai_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        ai_layout.addWidget(ai_label)
        
        # AI input
        input_layout = QHBoxLayout()
        
        self.ai_input = QLineEdit()
        self.ai_input.setPlaceholderText("Describe your simulation scenario (e.g., '10 mph wind on a cube sitting on the ground')")
        self.ai_input.returnPressed.connect(self.process_ai_input)
        self.ai_input.setFont(QFont("Segoe UI", 10))
        self.ai_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 10px;
                font-size: 10pt;
            }
        """)
        input_layout.addWidget(self.ai_input)
        
        self.process_button = QPushButton("Process")
        self.process_button.clicked.connect(self.process_ai_input)
        self.process_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        input_layout.addWidget(self.process_button)
        
        ai_layout.addLayout(input_layout)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-size: 9pt; margin-top: 5px;")
        ai_layout.addWidget(self.status_label)
        
        layout.addWidget(ai_group)
        
        # Run simulation button
        self.run_button = QPushButton("Run Simulation")
        self.run_button.clicked.connect(self.run_simulation)
        self.run_button.setEnabled(False)
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px 30px;
                font-size: 14pt;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #0e6e0e;
            }
            QPushButton:pressed {
                background-color: #0c5d0c;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #666;
            }
        """)
        layout.addWidget(self.run_button)
        
        # Add stretch to push everything to the top
        layout.addStretch()
    
    def connect_signals(self):
        """Connect all signals"""
        # Card click signals
        self.mesh_card.clicked.connect(self.show_mesh_detail)
        self.solver_card.clicked.connect(self.show_solver_detail)
        self.parameters_card.clicked.connect(self.show_parameters_detail)
        
        # Lock change signals
        self.mesh_card.lock_changed.connect(self.on_mesh_lock_changed)
        self.solver_card.lock_changed.connect(self.on_solver_lock_changed)
        self.parameters_card.lock_changed.connect(self.on_parameters_lock_changed)
        
        # Upload signals
        self.mesh_card.upload_clicked.connect(self.upload_mesh_file)
        self.solver_card.upload_clicked.connect(self.show_solver_detail)
        self.parameters_card.upload_clicked.connect(self.upload_parameters_file)
    
    def update_ui_state(self):
        """Update UI based on simulation state"""
        # Update mesh card
        if self.simulation_state.mesh_state != ComponentState.EMPTY:
            self.mesh_card.set_description(self.simulation_state.mesh.description)
        self.mesh_card.set_state(self.simulation_state.mesh_state)
        self.mesh_card.lock_checkbox.setChecked(self.simulation_state.mesh_locked)
        
        # Update solver card
        if self.simulation_state.solver_state != ComponentState.EMPTY:
            self.solver_card.set_solver_info(
                self.simulation_state.solver.name,
                self.simulation_state.solver.description,
                self.simulation_state.solver.justification
            )
        self.solver_card.set_state(self.simulation_state.solver_state)
        self.solver_card.lock_checkbox.setChecked(self.simulation_state.solver_locked)
        
        # Update parameters card
        if self.simulation_state.parameters_state != ComponentState.EMPTY:
            self.parameters_card.set_parameters_info(
                self.simulation_state.parameters.description,
                self.simulation_state.parameters.parameters
            )
        self.parameters_card.set_state(self.simulation_state.parameters_state)
        self.parameters_card.lock_checkbox.setChecked(self.simulation_state.parameters_locked)
        
        # Update run button
        self.run_button.setEnabled(self.simulation_state.can_run_simulation())
        
        # Update process button
        self.process_button.setEnabled(not self.simulation_state.processing)
    
    def process_ai_input(self):
        """Process AI input"""
        scenario = self.ai_input.text().strip()
        if not scenario:
            return
        
        self.simulation_state.processing = True
        self.status_label.setText("Processing scenario...")
        self.update_ui_state()
        
        # Send to AI worker
        self.worker.process_scenario(scenario, self.simulation_state.to_dict())
        
        # Clear input
        self.ai_input.clear()
    
    def handle_ai_response(self, response: Dict[str, Any]):
        """Handle AI response"""
        try:
            if response.get("status") == "success":
                # Update unlocked components
                if "mesh" in response and not self.simulation_state.mesh_locked:
                    mesh_data = MeshData(**response["mesh"])
                    self.simulation_state.update_mesh(mesh_data)
                    
                    # Emit signal for visualization
                    if mesh_data.file_path:
                        self.mesh_file_ready.emit(mesh_data.file_path)
                
                if "solver" in response and not self.simulation_state.solver_locked:
                    solver_data = SolverData(**response["solver"])
                    self.simulation_state.update_solver(solver_data)
                
                if "parameters" in response and not self.simulation_state.parameters_locked:
                    parameters_data = ParametersData(**response["parameters"])
                    self.simulation_state.update_parameters(parameters_data)
                
                self.status_label.setText("Components updated successfully!")
                
            else:
                self.status_label.setText(f"Error: {response.get('message', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error handling AI response: {str(e)}")
            self.status_label.setText(f"Error processing response: {str(e)}")
        
        finally:
            self.simulation_state.processing = False
            self.update_ui_state()
    
    def handle_ai_error(self, error: str):
        """Handle AI error"""
        self.status_label.setText(f"AI Error: {error}")
        self.simulation_state.processing = False
        self.update_ui_state()
    
    def show_mesh_detail(self):
        """Show mesh detail dialog"""
        dialog = MeshDetailDialog(self.simulation_state.mesh, self)
        if dialog.exec() == QDialog.Accepted:
            updated_mesh = dialog.get_mesh_data()
            self.simulation_state.update_mesh(updated_mesh)
            self.update_ui_state()
            
            # Emit signal for visualization if file path changed
            if updated_mesh.file_path:
                self.mesh_file_ready.emit(updated_mesh.file_path)
    
    def show_solver_detail(self):
        """Show solver detail dialog"""
        dialog = SolverDetailDialog(self.simulation_state.solver, self)
        if dialog.exec() == QDialog.Accepted:
            updated_solver = dialog.get_solver_data()
            self.simulation_state.update_solver(updated_solver)
            self.update_ui_state()
    
    def show_parameters_detail(self):
        """Show parameters detail dialog"""
        dialog = ParametersDetailDialog(self.simulation_state.parameters, self)
        if dialog.exec() == QDialog.Accepted:
            updated_parameters = dialog.get_parameters_data()
            self.simulation_state.update_parameters(updated_parameters)
            self.update_ui_state()
    
    def on_mesh_lock_changed(self, locked: bool):
        """Handle mesh lock change"""
        self.simulation_state.set_mesh_locked(locked)
        self.update_ui_state()
    
    def on_solver_lock_changed(self, locked: bool):
        """Handle solver lock change"""
        self.simulation_state.set_solver_locked(locked)
        self.update_ui_state()
    
    def on_parameters_lock_changed(self, locked: bool):
        """Handle parameters lock change"""
        self.simulation_state.set_parameters_locked(locked)
        self.update_ui_state()
    
    def upload_mesh_file(self):
        """Upload mesh file"""
        from PySide6.QtWidgets import QFileDialog
        import os
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Mesh File",
            "",
            "Mesh Files (*.stl *.foam *.obj);;All Files (*)"
        )
        
        if file_path:
            # Update mesh data
            mesh_data = MeshData(
                description=f"Uploaded mesh: {os.path.basename(file_path)}",
                file_path=file_path,
                file_type=os.path.splitext(file_path)[1].lower(),
                generated_by_ai=False
            )
            self.simulation_state.update_mesh(mesh_data)
            self.update_ui_state()
            
            # Emit signal for visualization
            self.mesh_file_ready.emit(file_path)
    
    def upload_parameters_file(self):
        """Upload parameters file"""
        from PySide6.QtWidgets import QFileDialog
        import os
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Parameters File",
            "",
            "Parameter Files (*.json *.yaml *.yml *.txt);;All Files (*)"
        )
        
        if file_path:
            # Update parameters data
            parameters_data = ParametersData(
                description=f"Uploaded parameters: {os.path.basename(file_path)}",
                file_path=file_path,
                generated_by_ai=False
            )
            self.simulation_state.update_parameters(parameters_data)
            self.update_ui_state()
    
    def run_simulation(self):
        """Run simulation"""
        if not self.simulation_state.can_run_simulation():
            QMessageBox.warning(self, "Cannot Run Simulation", 
                              "Please ensure all components (mesh, solver, parameters) are configured.")
            return
        
        # Show confirmation dialog
        reply = QMessageBox.question(self, "Run Simulation", 
                                   "Are you sure you want to run the simulation with the current configuration?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.simulation_state.processing = True
            self.status_label.setText("Starting simulation...")
            self.update_ui_state()
            
            # TODO: Implement actual simulation API call
            # For now, just show a message
            QMessageBox.information(self, "Simulation Started", 
                                  "Simulation has been started! (This is a placeholder - actual implementation needed)")
            
            # Emit signal
            self.simulation_started.emit("dummy_simulation_id")
            
            self.simulation_state.processing = False
            self.update_ui_state()
    
    def test_server_connection(self):
        """Test connection to server"""
        try:
            return self.api_client.test_connection()
        except Exception as e:
            logger.error(f"Server connection test failed: {str(e)}")
            return False
    
    def reset_simulation(self):
        """Reset simulation to initial state"""
        self.simulation_state.reset()
        self.update_ui_state()
        self.status_label.setText("Ready")
        self.ai_input.clear()
    
    def closeEvent(self, event):
        """Handle widget close event"""
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.api_client.close()
        event.accept() 