"""
Main Window for OpenFOAM Desktop Application
Integrates chat interface and ParaView visualization
"""
import logging
import sys
from typing import Optional
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QSplitter, QMenuBar, QMenu, QMessageBox, QStatusBar,
                               QLabel, QFrame, QApplication, QFileDialog, QDialog,
                               QDialogButtonBox, QFormLayout, QLineEdit, QPushButton)
from PySide6.QtCore import Qt, QTimer, Signal, QSettings
from PySide6.QtGui import QAction, QIcon, QFont

from simulation_setup_widget import SimulationSetupWidget
from paraview_widget import ParaViewWidget
from config import Config

logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    """Settings dialog for configuring server connections"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # Form layout for settings
        form_layout = QFormLayout()
        
        # Server settings
        self.server_host_input = QLineEdit()
        self.server_host_input.setText(Config.SERVER_HOST)
        form_layout.addRow("Server Host:", self.server_host_input)
        
        self.server_port_input = QLineEdit()
        self.server_port_input.setText(str(Config.SERVER_PORT))
        form_layout.addRow("Server Port:", self.server_port_input)
        
        # ParaView server settings
        self.paraview_host_input = QLineEdit()
        self.paraview_host_input.setText(Config.PARAVIEW_SERVER_HOST)
        form_layout.addRow("ParaView Server Host:", self.paraview_host_input)
        
        self.paraview_port_input = QLineEdit()
        self.paraview_port_input.setText(str(Config.PARAVIEW_SERVER_PORT))
        form_layout.addRow("ParaView Server Port:", self.paraview_port_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_settings(self):
        """Get the current settings"""
        return {
            'server_host': self.server_host_input.text(),
            'server_port': self.server_port_input.text(),
            'paraview_host': self.paraview_host_input.text(),
            'paraview_port': self.paraview_port_input.text()
        }

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize settings
        self.settings = QSettings('OpenFOAM', 'DesktopApp')
        
        # Initialize UI components
        self.simulation_setup = None
        self.paraview_widget = None
        
        # Setup UI
        self.setup_ui()
        self.setup_menu_bar()
        self.setup_status_bar()
        
        # Connect signals
        self.connect_signals()
        
        # Apply window settings
        self.apply_window_settings()
        
        # Test connections on startup
        QTimer.singleShot(1000, self.test_connections)
    
    def setup_ui(self):
        """Setup the main user interface"""
        # Set window properties
        self.setWindowTitle("OpenFOAM Desktop Assistant")
        self.setMinimumSize(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Create simulation setup interface
        self.simulation_setup = SimulationSetupWidget()
        setup_frame = QFrame()
        setup_frame.setFrameStyle(QFrame.StyledPanel)
        setup_layout = QVBoxLayout(setup_frame)
        setup_layout.addWidget(self.simulation_setup)
        splitter.addWidget(setup_frame)
        
        # Create ParaView widget
        self.paraview_widget = ParaViewWidget()
        paraview_frame = QFrame()
        paraview_frame.setFrameStyle(QFrame.StyledPanel)
        paraview_layout = QVBoxLayout(paraview_frame)
        
        # ParaView header
        paraview_header = QLabel("3D Visualization")
        paraview_header.setFont(QFont("Segoe UI", 12, QFont.Bold))
        paraview_header.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-bottom: 1px solid #ccc;")
        paraview_layout.addWidget(paraview_header)
        
        paraview_layout.addWidget(self.paraview_widget)
        splitter.addWidget(paraview_frame)
        
        # Set splitter proportions (40% chat, 60% visualization)
        splitter.setSizes([400, 600])
        
        # Style the application
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QFrame {
                border: 1px solid #ccc;
                border-radius: 5px;
                background-color: white;
            }
            QSplitter::handle {
                background-color: #ddd;
                width: 2px;
            }
            QSplitter::handle:hover {
                background-color: #bbb;
            }
        """)
    
    def setup_menu_bar(self):
        """Setup the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        # New session action
        new_action = QAction("New Session", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_session)
        file_menu.addAction(new_action)
        
        file_menu.addSeparator()
        
        # Settings action
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Connection menu
        connection_menu = menubar.addMenu("Connection")
        
        # Test connections action
        test_action = QAction("Test Connections", self)
        test_action.triggered.connect(self.test_connections)
        connection_menu.addAction(test_action)
        
        # Connect to ParaView action
        connect_pv_action = QAction("Connect to ParaView Server", self)
        connect_pv_action.triggered.connect(self.connect_paraview)
        connection_menu.addAction(connect_pv_action)
        
        # Disconnect from ParaView action
        disconnect_pv_action = QAction("Disconnect from ParaView Server", self)
        disconnect_pv_action.triggered.connect(self.disconnect_paraview)
        connection_menu.addAction(disconnect_pv_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        # About action
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        # User Guide action
        guide_action = QAction("User Guide", self)
        guide_action.triggered.connect(self.show_user_guide)
        help_menu.addAction(guide_action)
    
    def setup_status_bar(self):
        """Setup the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Connection status indicators
        self.server_status_label = QLabel("Server: Not connected")
        self.server_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.status_bar.addWidget(self.server_status_label)
        
        self.status_bar.addWidget(QLabel(" | "))
        
        self.paraview_status_label = QLabel("ParaView: Not connected")
        self.paraview_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.status_bar.addWidget(self.paraview_status_label)
        
        # Add permanent widget for app info
        self.status_bar.addPermanentWidget(QLabel("OpenFOAM Desktop Assistant v1.0"))
    
    def connect_signals(self):
        """Connect signals between components"""
        # Simulation setup signals
        self.simulation_setup.mesh_file_ready.connect(self.load_mesh_visualization)
        self.simulation_setup.results_ready.connect(self.load_results_visualization)
        self.simulation_setup.simulation_started.connect(self.on_simulation_started)
        
        # ParaView widget signals
        self.paraview_widget.visualization_loaded.connect(self.on_visualization_loaded)
        self.paraview_widget.visualization_error.connect(self.on_visualization_error)
    
    def apply_window_settings(self):
        """Apply saved window settings"""
        # Restore window geometry
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        # Restore window state
        state = self.settings.value("windowState")
        if state:
            self.restoreState(state)
    
    def test_connections(self):
        """Test connections to server and ParaView"""
        self.status_bar.showMessage("Testing connections...")
        
        # Test server connection
        if self.simulation_setup and self.simulation_setup.test_server_connection():
            self.server_status_label.setText("Server: Connected")
            self.server_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.server_status_label.setText("Server: Not connected")
            self.server_status_label.setStyleSheet("color: red; font-weight: bold;")
        
        # Test ParaView connection
        if self.paraview_widget and self.paraview_widget.is_connected():
            self.paraview_status_label.setText("ParaView: Connected")
            self.paraview_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.paraview_status_label.setText("ParaView: Not connected")
            self.paraview_status_label.setStyleSheet("color: red; font-weight: bold;")
        
        self.status_bar.showMessage("Connection test completed", 3000)
    
    def connect_paraview(self):
        """Connect to ParaView server"""
        if self.paraview_widget:
            self.paraview_widget.connect_to_server()
            QTimer.singleShot(1000, self.update_paraview_status)
    
    def disconnect_paraview(self):
        """Disconnect from ParaView server"""
        if self.paraview_widget:
            self.paraview_widget.disconnect_from_server()
            QTimer.singleShot(1000, self.update_paraview_status)
    
    def update_paraview_status(self):
        """Update ParaView connection status"""
        if self.paraview_widget and self.paraview_widget.is_connected():
            self.paraview_status_label.setText("ParaView: Connected")
            self.paraview_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.paraview_status_label.setText("ParaView: Not connected")
            self.paraview_status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def load_mesh_visualization(self, file_path: str):
        """Load mesh for visualization"""
        if self.paraview_widget:
            self.status_bar.showMessage(f"Loading mesh: {file_path}")
            self.paraview_widget.load_foam_file(file_path)
    
    def load_results_visualization(self, file_path: str):
        """Load simulation results for visualization"""
        if self.paraview_widget:
            self.status_bar.showMessage(f"Loading results: {file_path}")
            self.paraview_widget.load_foam_file(file_path)
    
    def on_visualization_loaded(self, file_path: str):
        """Handle visualization loaded event"""
        self.status_bar.showMessage(f"Visualization loaded: {file_path}", 5000)
    
    def on_visualization_error(self, error: str):
        """Handle visualization error event"""
        self.status_bar.showMessage(f"Visualization error: {error}", 10000)
        QMessageBox.warning(self, "Visualization Error", f"Failed to load visualization:\n{error}")
    
    def on_simulation_started(self, simulation_id: str):
        """Handle simulation started event"""
        self.status_bar.showMessage(f"Simulation started: {simulation_id}", 5000)
    
    def new_session(self):
        """Start a new session"""
        reply = QMessageBox.question(self, "New Session", 
                                   "Are you sure you want to start a new session? This will clear the current chat history.",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Reset simulation setup
            if self.simulation_setup:
                self.simulation_setup.reset_simulation()
            
            # Reset ParaView
            if self.paraview_widget:
                self.paraview_widget.disconnect_from_server()
                self.paraview_widget.connect_to_server()
            
            self.status_bar.showMessage("New session started", 3000)
    
    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            settings = dialog.get_settings()
            # Apply settings (would need to update Config class)
            self.status_bar.showMessage("Settings updated", 3000)
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
        <h3>OpenFOAM Desktop Assistant</h3>
        <p><b>Version:</b> 1.0</p>
        <p><b>Description:</b> A desktop application for simplified interaction with OpenFOAM CFD simulations through AI assistance and 3D visualization.</p>
        <p><b>Features:</b></p>
        <ul>
            <li>Conversational AI for simulation setup</li>
            <li>Automated mesh generation and validation</li>
            <li>Real-time 3D visualization with ParaView</li>
            <li>Time-step navigation and field visualization</li>
        </ul>
        <p><b>Requirements:</b></p>
        <ul>
            <li>OpenFOAM server with REST API</li>
            <li>ParaView server (pvserver)</li>
            <li>Python 3.7+ with required packages</li>
        </ul>
        """
        QMessageBox.about(self, "About", about_text)
    
    def show_user_guide(self):
        """Show user guide"""
        guide_text = """
        <h3>User Guide</h3>
        <p><b>Getting Started:</b></p>
        <ol>
            <li>Ensure the OpenFOAM server and ParaView server are running</li>
            <li>Use the Connection menu to test and establish connections</li>
            <li>Describe your simulation scenario in the chat area</li>
            <li>Review the generated mesh in the visualization area</li>
            <li>Approve or provide feedback on the mesh</li>
            <li>View simulation results with visualization controls</li>
        </ol>
        
        <p><b>Example Scenarios:</b></p>
        <ul>
            <li>"I want to see effects of 10 mph wind on a cube sitting on the ground"</li>
            <li>"Simulate airflow around a cylinder at 5 m/s"</li>
            <li>"Model heat transfer in a pipe with 80°C inlet temperature"</li>
        </ul>
        
        <p><b>Visualization Controls:</b></p>
        <ul>
            <li>Use mouse to rotate, zoom, and pan the 3D view</li>
            <li>Click field buttons to display pressure, velocity, or streamlines</li>
            <li>Use time step controls to navigate through simulation results</li>
        </ul>
        """
        QMessageBox.information(self, "User Guide", guide_text)
    
    def closeEvent(self, event):
        """Handle application close event"""
        # Save window settings
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        
        # Clean up components
        if self.simulation_setup:
            self.simulation_setup.close()
        
        if self.paraview_widget:
            self.paraview_widget.disconnect_from_server()
        
        event.accept()
        
        # Log application shutdown
        logger.info("Application shutting down") 