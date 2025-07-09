"""
Chat Interface for OpenFOAM Desktop Application
Handles conversational AI interaction for simulation workflows
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QTextEdit, QLineEdit, QLabel, QScrollArea, QFrame)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject
from PySide6.QtGui import QTextCursor, QFont, QColor, QTextCharFormat

from api_client import APIClient

logger = logging.getLogger(__name__)

class APIWorker(QObject):
    """Worker thread for API calls to keep UI responsive"""
    
    # Signals
    response_received = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, api_client: APIClient):
        super().__init__()
        self.api_client = api_client
        self.task_id = None
    
    def submit_scenario(self, scenario: str):
        """Submit scenario in worker thread"""
        try:
            response = self.api_client.submit_scenario(scenario)
            self.response_received.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def approve_mesh(self, task_id: str):
        """Approve mesh in worker thread"""
        try:
            response = self.api_client.approve_mesh(task_id)
            self.response_received.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def reject_mesh(self, task_id: str, feedback: str):
        """Reject mesh in worker thread"""
        try:
            response = self.api_client.reject_mesh(task_id, feedback)
            self.response_received.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def run_simulation(self, task_id: str):
        """Run simulation in worker thread"""
        try:
            response = self.api_client.run_simulation(task_id)
            self.response_received.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def get_status(self, task_id: str):
        """Get status in worker thread"""
        try:
            response = self.api_client.get_status(task_id)
            self.response_received.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))

class ChatInterface(QWidget):
    """Chat interface widget for AI interaction"""
    
    # Signals
    scenario_submitted = Signal(str)           # Emitted when scenario is submitted
    mesh_approved = Signal(str)                # Emitted when mesh is approved
    mesh_rejected = Signal(str, str)           # Emitted when mesh is rejected (task_id, feedback)
    simulation_started = Signal(str)           # Emitted when simulation starts
    mesh_file_ready = Signal(str)             # Emitted when mesh file is ready for visualization
    results_ready = Signal(str)               # Emitted when simulation results are ready
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize API client
        self.api_client = APIClient()
        
        # Setup worker thread
        self.worker_thread = QThread()
        self.worker = APIWorker(self.api_client)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()
        
        # Connect worker signals
        self.worker.response_received.connect(self.handle_api_response)
        self.worker.error_occurred.connect(self.handle_api_error)
        
        # Current task state
        self.current_task_id = None
        self.current_state = "idle"  # idle, waiting_for_mesh, mesh_validation, simulation_running
        
        # Status polling timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.poll_status)
        
        # Initialize UI
        self.setup_ui()
        
        # Add welcome message
        self.add_ai_message("Welcome to OpenFOAM Assistant! 🌊\n\nDescribe your CFD simulation scenario and I'll help you set it up. For example:\n- 'I want to see effects of 10 mph wind on a cube sitting on the ground'\n- 'Simulate airflow around a cylinder at 5 m/s'\n- 'Model heat transfer in a pipe with 80°C inlet temperature'")
    
    def setup_ui(self):
        """Setup the chat interface UI"""
        layout = QVBoxLayout(self)
        
        # Chat history area
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setMinimumHeight(300)
        self.chat_area.setFont(QFont("Segoe UI", 10))
        self.chat_area.setAcceptRichText(True)  # Enable rich text formatting
        self.chat_area.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: #fafafa;
                padding: 10px;
            }
        """)
        layout.addWidget(self.chat_area)
        
        # Message input area
        input_layout = QHBoxLayout()
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.returnPressed.connect(self.send_message)
        self.message_input.setFont(QFont("Segoe UI", 10))
        self.message_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 8px;
                font-size: 10pt;
            }
        """)
        input_layout.addWidget(self.message_input)
        
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
        
        # Validation buttons (initially hidden)
        self.validation_frame = QFrame()
        self.validation_layout = QHBoxLayout(self.validation_frame)
        
        self.approve_button = QPushButton("✓ Yes, mesh looks correct")
        self.approve_button.clicked.connect(self.approve_mesh)
        self.approve_button.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0e6e0e;
            }
        """)
        self.validation_layout.addWidget(self.approve_button)
        
        self.reject_button = QPushButton("✗ No, needs adjustment")
        self.reject_button.clicked.connect(self.reject_mesh)
        self.reject_button.setStyleSheet("""
            QPushButton {
                background-color: #d13438;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #b92c30;
            }
        """)
        self.validation_layout.addWidget(self.reject_button)
        
        self.validation_frame.hide()
        layout.addWidget(self.validation_frame)
        
        # Status indicator
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 9pt;
                padding: 5px;
            }
        """)
        layout.addWidget(self.status_label)
    
    def add_user_message(self, message: str):
        """Add user message to chat"""
        timestamp = datetime.now().strftime("%H:%M")
        
        # Move to end and add a new line if there's existing content
        cursor = self.chat_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        if not self.chat_area.toPlainText().endswith('\n') and self.chat_area.toPlainText():
            cursor.insertText('\n')
        
        # Create format for user attribution (blue, bold)
        user_attr_format = QTextCharFormat()
        user_attr_format.setForeground(QColor(0, 120, 212))  # Blue
        user_attr_format.setFontWeight(QFont.Bold)
        
        # Create format for user message (slightly blue tinted)
        user_msg_format = QTextCharFormat()
        user_msg_format.setForeground(QColor(0, 80, 160))  # Darker blue
        
        # Insert attribution with formatting
        cursor.insertText('\n')
        cursor.setCharFormat(user_attr_format)
        cursor.insertText(f"You • {timestamp}")
        
        # Reset format and insert message
        cursor.insertText('\n')
        cursor.setCharFormat(user_msg_format)
        cursor.insertText(message)
        cursor.insertText('\n')
        
        # Reset to default format
        cursor.setCharFormat(QTextCharFormat())
        self.chat_area.setTextCursor(cursor)
        self.chat_area.ensureCursorVisible()
    
    def add_ai_message(self, message: str):
        """Add AI message to chat"""
        timestamp = datetime.now().strftime("%H:%M")
        
        # Move to end and add a new line if there's existing content
        cursor = self.chat_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        if not self.chat_area.toPlainText().endswith('\n') and self.chat_area.toPlainText():
            cursor.insertText('\n')
        
        # Create format for AI attribution (teal, bold)
        ai_attr_format = QTextCharFormat()
        ai_attr_format.setForeground(QColor(0, 150, 136))  # Teal
        ai_attr_format.setFontWeight(QFont.Bold)
        
        # Create format for AI message (dark gray)
        ai_msg_format = QTextCharFormat()
        ai_msg_format.setForeground(QColor(51, 51, 51))  # Dark gray
        
        # Insert attribution with formatting
        cursor.insertText('\n')
        cursor.setCharFormat(ai_attr_format)
        cursor.insertText(f"AI Assistant • {timestamp}")
        
        # Reset format and insert message
        cursor.insertText('\n')
        cursor.setCharFormat(ai_msg_format)
        cursor.insertText(message)
        cursor.insertText('\n')
        
        # Reset to default format
        cursor.setCharFormat(QTextCharFormat())
        self.chat_area.setTextCursor(cursor)
        self.chat_area.ensureCursorVisible()
    
    def add_system_message(self, message: str):
        """Add system message to chat"""
        timestamp = datetime.now().strftime("%H:%M")
        
        # Move to end and add a new line if there's existing content
        cursor = self.chat_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        if not self.chat_area.toPlainText().endswith('\n') and self.chat_area.toPlainText():
            cursor.insertText('\n')
        
        # Create format for system message (gray, italic)
        system_format = QTextCharFormat()
        system_format.setForeground(QColor(102, 102, 102))  # Gray
        system_format.setFontItalic(True)
        system_format.setFontWeight(QFont.Normal)
        
        # Insert system message with formatting
        cursor.insertText('\n')
        cursor.setCharFormat(system_format)
        cursor.insertText(f"[SYSTEM] {message} • {timestamp}")
        cursor.insertText('\n')
        
        # Reset to default format
        cursor.setCharFormat(QTextCharFormat())
        self.chat_area.setTextCursor(cursor)
        self.chat_area.ensureCursorVisible()
    
    def scroll_to_bottom(self):
        """Scroll chat area to bottom"""
        cursor = self.chat_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_area.setTextCursor(cursor)
        self.chat_area.ensureCursorVisible()
    
    def send_message(self):
        """Send user message"""
        message = self.message_input.text().strip()
        if not message:
            return
        
        # Add user message to chat
        self.add_user_message(message)
        self.message_input.clear()
        
        # Process based on current state
        if self.current_state == "idle":
            # This is a scenario submission
            self.current_state = "waiting_for_mesh"
            self.set_status("Submitting scenario...")
            self.worker.submit_scenario(message)
            self.scenario_submitted.emit(message)
            
        elif self.current_state == "mesh_validation" and self.reject_button.isEnabled():
            # This is feedback for mesh rejection
            self.set_status("Processing feedback...")
            self.worker.reject_mesh(self.current_task_id, message)
            self.mesh_rejected.emit(self.current_task_id, message)
            self.current_state = "waiting_for_mesh"
            self.hide_validation_buttons()
    
    def approve_mesh(self):
        """Approve the current mesh"""
        if self.current_task_id:
            self.set_status("Approving mesh...")
            self.worker.approve_mesh(self.current_task_id)
            self.mesh_approved.emit(self.current_task_id)
            self.current_state = "simulation_running"
            self.hide_validation_buttons()
            self.add_system_message("Mesh approved - Starting simulation...")
            # Restart polling to monitor simulation progress
            self.status_timer.start(3000)  # Poll every 3 seconds during simulation
    
    def reject_mesh(self):
        """Reject the current mesh"""
        self.add_ai_message("Please explain what needs to be adjusted with the mesh (e.g., 'too coarse near the cube', 'need finer boundary layer', etc.):")
        self.hide_validation_buttons()
        self.message_input.setFocus()
    
    def show_validation_buttons(self):
        """Show mesh validation buttons"""
        self.validation_frame.show()
        self.current_state = "mesh_validation"
    
    def hide_validation_buttons(self):
        """Hide mesh validation buttons"""
        self.validation_frame.hide()
    
    def handle_api_response(self, response: Dict[str, Any]):
        """Handle API response from worker"""
        try:
            if 'task_id' in response:
                self.current_task_id = response['task_id']
            
            if 'status' in response:
                status = response['status']
                
                if status == 'mesh_generated':
                    self.add_ai_message("Mesh generated successfully! 🎯\n\nPlease review the mesh in the visualization area.")
                    self.add_ai_message("Does this mesh look correct?")
                    self.show_validation_buttons()
                    self.set_status("Waiting for mesh validation...")
                    self.status_timer.stop()  # Stop polling when mesh is ready for validation
                    
                    # Emit signal for mesh file if provided
                    if 'mesh_file' in response:
                        self.mesh_file_ready.emit(response['mesh_file'])
                
                elif status == 'simulation_complete':
                    self.add_ai_message("Simulation completed successfully! 🎉\n\nResults are now available in the visualization area.")
                    self.current_state = "idle"
                    self.set_status("Ready")
                    self.status_timer.stop()  # Stop polling when simulation is complete
                    
                    # Emit signal for results if provided
                    if 'results_file' in response:
                        self.results_ready.emit(response['results_file'])
                
                elif status == 'processing':
                    self.add_ai_message("Processing your request... ⏳")
                    self.set_status("Processing...")
                    # Start polling for status updates
                    self.status_timer.start(2000)  # Poll every 2 seconds
                
                elif status == 'simulation_running':
                    self.set_status("Simulation running...")
                    # Continue polling during simulation
                    if not self.status_timer.isActive():
                        self.status_timer.start(3000)  # Poll every 3 seconds
                
                elif status == 'error':
                    error_msg = response.get('message', 'Unknown error occurred')
                    self.add_ai_message(f"Sorry, an error occurred: {error_msg} ❌")
                    self.current_state = "idle"
                    self.set_status("Ready")
                    self.hide_validation_buttons()
                    self.status_timer.stop()  # Stop polling on error
            
            if 'message' in response:
                message = response['message']
                if message and message not in ['Processing...', 'OK']:
                    self.add_ai_message(message)
                    
        except Exception as e:
            logger.error(f"Error handling API response: {str(e)}")
            self.handle_api_error(str(e))
    
    def handle_api_error(self, error: str):
        """Handle API error"""
        self.add_ai_message(f"Sorry, I encountered an error: {error} ❌\n\nPlease try again or check your connection.")
        self.current_state = "idle"
        self.set_status("Ready")
        self.hide_validation_buttons()
        self.status_timer.stop()
    
    def poll_status(self):
        """Poll for status updates"""
        if self.current_task_id:
            self.worker.get_status(self.current_task_id)
    
    def set_status(self, status: str):
        """Set status text"""
        self.status_label.setText(status)
    
    def test_server_connection(self):
        """Test connection to server"""
        try:
            if self.api_client.test_connection():
                self.add_system_message("Connected to server successfully")
                return True
            else:
                self.add_system_message("Failed to connect to server")
                return False
        except Exception as e:
            self.add_system_message(f"Connection error: {str(e)}")
            return False
    
    def closeEvent(self, event):
        """Handle widget close event"""
        self.status_timer.stop()
        self.worker_thread.quit()
        self.worker_thread.wait()
        self.api_client.close()
        event.accept() 