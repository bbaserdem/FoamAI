"""
Main Window for OpenFOAM Desktop Application
Integrates chat interface, project management, and ParaView visualization
"""
import logging
import sys
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QSplitter, QMenuBar, QMenu, QMessageBox, QStatusBar,
                               QLabel, QFrame, QApplication, QFileDialog, QDialog,
                               QDialogButtonBox, QFormLayout, QLineEdit, QPushButton,
                               QComboBox, QTextEdit, QGroupBox)
from PySide6.QtCore import Qt, QTimer, Signal, QSettings, QThread
from PySide6.QtGui import QAction, QIcon, QFont

from simulation_setup_widget import SimulationSetupWidget
from paraview_widget import ParaViewWidget
from api_client import ProjectAPIClient
from config import Config

logger = logging.getLogger(__name__)

class ProjectCreationDialog(QDialog):
    """Dialog for creating new projects"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setModal(True)
        self.resize(400, 200)
        
        layout = QVBoxLayout(self)
        
        # Form layout for project details
        form_layout = QFormLayout()
        
        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("e.g., airflow_simulation")
        form_layout.addRow("Project Name:", self.project_name_input)
        
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Optional description of your simulation project...")
        self.description_input.setMaximumHeight(80)
        form_layout.addRow("Description:", self.description_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Connect enter key to accept
        self.project_name_input.returnPressed.connect(self.accept)
    
    def get_project_data(self):
        """Get the project data"""
        return {
            'name': self.project_name_input.text().strip(),
            'description': self.description_input.toPlainText().strip()
        }
    
    def accept(self):
        """Validate before accepting"""
        if not self.project_name_input.text().strip():
            QMessageBox.warning(self, "Invalid Input", "Project name is required.")
            return
        super().accept()

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

class AdvancedProjectDialog(QDialog):
    """Advanced project creation dialog with more options"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project (Advanced)")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Form layout for project details
        form_layout = QFormLayout()
        
        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("e.g., airflow_simulation")
        form_layout.addRow("Project Name:", self.project_name_input)
        
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Optional description of your simulation project...")
        self.description_input.setMaximumHeight(100)
        form_layout.addRow("Description:", self.description_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_project_data(self):
        """Get the project data"""
        return {
            'name': self.project_name_input.text().strip(),
            'description': self.description_input.toPlainText().strip()
        }

class CloneProjectDialog(QDialog):
    """Dialog for cloning projects"""
    
    def __init__(self, source_project, parent=None):
        super().__init__(parent)
        self.source_project = source_project
        self.setWindowTitle(f"Clone Project: {source_project}")
        self.setModal(True)
        self.resize(400, 150)
        
        layout = QVBoxLayout(self)
        
        # Form layout
        form_layout = QFormLayout()
        
        self.new_name_input = QLineEdit()
        self.new_name_input.setPlaceholderText(f"{source_project}_copy")
        form_layout.addRow("New Project Name:", self.new_name_input)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_new_name(self):
        """Get the new project name"""
        return self.new_name_input.text().strip()

class ConnectionTestThread(QThread):
    """Thread for testing connections without blocking UI"""
    connection_tested = Signal(str, bool)  # service, success
    
    def __init__(self, api_client, paraview_widget):
        super().__init__()
        self.api_client = api_client
        self.paraview_widget = paraview_widget
    
    def run(self):
        """Test connections in background"""
        # Test server connection
        try:
            server_ok = self.api_client.test_connection()
            self.connection_tested.emit("server", server_ok)
        except Exception:
            self.connection_tested.emit("server", False)
        
        # Test ParaView connection
        try:
            paraview_ok = self.paraview_widget.is_connected() if self.paraview_widget else False
            self.connection_tested.emit("paraview", paraview_ok)
        except Exception:
            self.connection_tested.emit("paraview", False)

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize settings
        self.settings = QSettings('OpenFOAM', 'DesktopApp')
        
        # Initialize API client
        self.api_client = ProjectAPIClient()
        
        # Initialize UI components
        self.simulation_widget = None
        self.paraview_widget = None
        self.project_combo = None
        self.connection_test_thread = None
        self.current_project = None
        
        # Setup UI
        self.setup_ui()
        self.setup_menu_bar()
        self.setup_status_bar()
        
        # Connect signals
        self.connect_signals()
        
        # Apply window settings
        self.apply_window_settings()
        
        # Load projects and test connections on startup
        QTimer.singleShot(1000, self.load_projects)
        QTimer.singleShot(2000, self.test_connections)
    
    def setup_ui(self):
        """Setup the main user interface"""
        # Set window properties
        self.setWindowTitle("OpenFOAM Desktop Assistant")
        self.setMinimumSize(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Add project selection bar
        self.setup_project_bar(main_layout)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Create and set up simulation widget
        self.simulation_widget = SimulationSetupWidget()
        logger.info("Setting API client on simulation widget")
        self.simulation_widget.set_api_client(self.api_client)
        
        # Connect simulation widget signals
        self.simulation_widget.workflow_started.connect(self.on_workflow_started)
        self.simulation_widget.workflow_completed.connect(self.on_workflow_completed)
        self.simulation_widget.workflow_failed.connect(self.on_workflow_failed)
        
        splitter.addWidget(self.simulation_widget)

        # Create ParaView widget
        self.paraview_widget = ParaViewWidget()
        
        # Configure ParaView widget for remote server
        server_url = self.api_client.base_url if self.api_client else None
        if server_url and self.current_project:
            self.paraview_widget.set_remote_server(server_url, self.current_project)
        
        splitter.addWidget(self.paraview_widget)
        
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
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
    
    def setup_project_bar(self, main_layout):
        """Setup the project selection and management bar"""
        project_frame = QGroupBox("Project Management")
        project_frame.setMaximumHeight(80)  # Constrain height to be compact
        project_layout = QHBoxLayout(project_frame)
        project_layout.setContentsMargins(10, 5, 10, 5)  # Tighter margins
        project_layout.setSpacing(10)  # Consistent spacing
        
        # Project selection
        project_layout.addWidget(QLabel("Current Project:"))
        
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(200)
        self.project_combo.currentTextChanged.connect(self.on_project_changed)
        project_layout.addWidget(self.project_combo)
        
        # Project management buttons
        self.new_project_btn = QPushButton("New Project")
        self.new_project_btn.clicked.connect(self.create_new_project)
        project_layout.addWidget(self.new_project_btn)
        
        self.delete_project_btn = QPushButton("Delete Project")
        self.delete_project_btn.clicked.connect(self.delete_current_project)
        self.delete_project_btn.setEnabled(False)
        project_layout.addWidget(self.delete_project_btn)
        
        self.refresh_projects_btn = QPushButton("Refresh")
        self.refresh_projects_btn.clicked.connect(self.load_projects)
        project_layout.addWidget(self.refresh_projects_btn)
        
        project_layout.addStretch()  # Push everything to the left
        
        main_layout.addWidget(project_frame)
    
    def setup_menu_bar(self):
        """Setup the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        # New project action
        new_project_action = QAction("New Project...", self)
        new_project_action.setShortcut("Ctrl+N")
        new_project_action.triggered.connect(self.create_new_project)
        file_menu.addAction(new_project_action)
        
        # New session action
        new_session_action = QAction("New Session", self)
        new_session_action.setShortcut("Ctrl+Shift+N")
        new_session_action.triggered.connect(self.new_session)
        file_menu.addAction(new_session_action)
        
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
        
        # Project menu
        project_menu = menubar.addMenu("Project")
        
        # Refresh projects action
        refresh_action = QAction("Refresh Projects", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.load_projects)
        project_menu.addAction(refresh_action)
        
        # Delete project action
        delete_action = QAction("Delete Current Project...", self)
        delete_action.triggered.connect(self.delete_current_project)
        project_menu.addAction(delete_action)
        
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
        
        self.status_bar.addWidget(QLabel(" | "))
        
        self.project_status_label = QLabel("Project: None")
        self.project_status_label.setStyleSheet("color: gray; font-weight: bold;")
        self.status_bar.addWidget(self.project_status_label)
        
        # Add permanent widget for app info
        self.status_bar.addPermanentWidget(QLabel("OpenFOAM Desktop Assistant v1.0"))
    
    def connect_signals(self):
        """Connect signals between components"""
        # Simulation setup signals
        if hasattr(self.simulation_widget, 'mesh_file_ready'):
            self.simulation_widget.mesh_file_ready.connect(self.load_mesh_visualization)
        if hasattr(self.simulation_widget, 'results_ready'):
            self.simulation_widget.results_ready.connect(self.load_results_visualization)
        if hasattr(self.simulation_widget, 'simulation_started'):
            self.simulation_widget.simulation_started.connect(self.on_simulation_started)
        
        # ParaView widget signals
        if hasattr(self.paraview_widget, 'visualization_loaded'):
            self.paraview_widget.visualization_loaded.connect(self.on_visualization_loaded)
        if hasattr(self.paraview_widget, 'visualization_error'):
            self.paraview_widget.visualization_error.connect(self.on_visualization_error)
        if hasattr(self.paraview_widget, 'connection_status_changed'):
            self.paraview_widget.connection_status_changed.connect(self.on_paraview_connection_changed)
    
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
        
        # Restore last project
        last_project = self.settings.value("lastProject")
        if last_project:
            # Will be set when projects are loaded
            pass
    
    # Project Management Methods
    def load_projects(self):
        """Load available projects from server"""
        try:
            response = self.api_client.list_projects()
            projects = response.get('projects', [])
            
            # Update combo box
            self.project_combo.blockSignals(True)
            self.project_combo.clear()
            self.project_combo.addItem("-- Select Project --")
            
            for project in projects:
                # Handle both string format and object format
                if isinstance(project, str):
                    # Server returns simple strings: ["project1", "project2"]
                    project_name = project
                else:
                    # Server returns objects: [{"project_name": "project1", ...}]
                    project_name = project.get('project_name', str(project))
                
                self.project_combo.addItem(project_name)
            
            self.project_combo.blockSignals(False)
            
            # Restore last project if available
            last_project = self.settings.value("lastProject")
            if last_project:
                index = self.project_combo.findText(last_project)
                if index >= 0:
                    self.project_combo.setCurrentIndex(index)
            
            self.status_bar.showMessage(f"Loaded {len(projects)} projects", 3000)
            
        except Exception as e:
            logger.error(f"Failed to load projects: {str(e)}")
            self.status_bar.showMessage(f"Failed to load projects: {str(e)}", 5000)
    
    def create_new_project(self):
        """Create a new project"""
        dialog = ProjectCreationDialog(self)
        if dialog.exec() == QDialog.Accepted:
            project_data = dialog.get_project_data()
            try:
                response = self.api_client.create_project(
                    project_data['name'], 
                    project_data['description']
                )
                
                # Reload projects and select the new one
                self.load_projects()
                index = self.project_combo.findText(project_data['name'])
                if index >= 0:
                    self.project_combo.setCurrentIndex(index)
                
                self.status_bar.showMessage(f"Created project: {project_data['name']}", 5000)
                
            except Exception as e:
                logger.error(f"Failed to create project: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to create project:\n{str(e)}")
    
    def delete_current_project(self):
        """Delete the currently selected project"""
        current_project = self.api_client.get_current_project()
        if not current_project:
            QMessageBox.warning(self, "Warning", "No project selected.")
            return
        
        reply = QMessageBox.question(
            self, "Delete Project",
            f"Are you sure you want to delete the project '{current_project}'?\n\n"
            f"This will permanently delete all project files and cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.api_client.delete_project(current_project)
                
                # Reload projects
                self.load_projects()
                self.project_combo.setCurrentIndex(0)  # Select "-- Select Project --"
                
                self.status_bar.showMessage(f"Deleted project: {current_project}", 5000)
                
            except Exception as e:
                logger.error(f"Failed to delete project: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to delete project:\n{str(e)}")
    
    def on_project_changed(self, project_name: str):
        """Handle project selection change"""
        if project_name and project_name != "-- Select Project --":
            # Set current project in API client
            if self.api_client.set_current_project(project_name):
                self.current_project = project_name  # Update local current_project
                self.project_status_label.setText(f"Project: {project_name}")
                self.project_status_label.setStyleSheet("color: green; font-weight: bold;")
                self.delete_project_btn.setEnabled(True)
                
                # Save last project
                self.settings.setValue("lastProject", project_name)
                
                # Update simulation setup with new project
                if hasattr(self.simulation_widget, 'set_current_project'):
                    logger.info(f"Calling simulation_widget.set_current_project with: {project_name}")
                    self.simulation_widget.set_current_project(project_name)
                else:
                    logger.warning("simulation_widget does not have set_current_project method")
                
                # Configure ParaView widget for remote server
                if hasattr(self, 'paraview_widget') and self.api_client:
                    self.paraview_widget.set_remote_server(self.api_client.base_url, project_name)
                
                self.status_bar.showMessage(f"Selected project: {project_name}", 3000)
            else:
                QMessageBox.warning(self, "Error", f"Failed to set project: {project_name}")
        else:
            self.api_client.current_project = None
            self.current_project = None
            self.project_status_label.setText("Project: None")
            self.project_status_label.setStyleSheet("color: gray; font-weight: bold;")
            self.delete_project_btn.setEnabled(False)
    
    def on_project_selected(self, project_name: str):
        """Handle project selection."""
        logger.info(f"Project selected: {project_name}")
        self.current_project = project_name
        
        # Update window title
        self.setWindowTitle(f"OpenFOAM Desktop - {project_name}")
        
        # Update status bar
        self.project_status_label.setText(f"Project: {project_name}")
        
        # Configure simulation widget for the project
        if hasattr(self, 'simulation_widget'):
            self.simulation_widget.set_current_project(project_name)
        
        # Configure ParaView widget for remote server
        if hasattr(self, 'paraview_widget') and self.api_client:
            self.paraview_widget.set_remote_server(self.api_client.base_url, project_name)
        
        # Save last project
        self.settings.setValue("lastProject", project_name)
    
    def on_workflow_started(self):
        """Handle workflow start."""
        logger.info("Workflow started")
        self.status_bar.showMessage("CFD workflow started...", 5000)
        
        # Update UI state
        if hasattr(self, 'project_combo'):
            self.project_combo.setEnabled(False)  # Prevent project switching during workflow
    
    def on_workflow_completed(self, final_state: Dict[str, Any]):
        """Handle workflow completion."""
        logger.info("Workflow completed successfully")
        self.status_bar.showMessage("CFD workflow completed successfully!", 10000)
        
        # Re-enable UI elements
        if hasattr(self, 'project_combo'):
            self.project_combo.setEnabled(True)
        
        # Check if ParaView visualization is available
        if final_state.get("visualization_path"):
            self.status_bar.showMessage("Workflow complete - visualization ready for ParaView", 5000)
        
        # Show completion message
        QMessageBox.information(
            self,
            "Workflow Complete",
            "The CFD workflow has completed successfully!\n\n"
            "You can now:\n"
            "• View results in the ParaView widget\n"
            "• Start a new simulation\n"
            "• Modify parameters and re-run"
        )
    
    def on_workflow_failed(self, error_message: str):
        """Handle workflow failure."""
        logger.error(f"Workflow failed: {error_message}")
        self.status_bar.showMessage(f"Workflow failed: {error_message}", 10000)
        
        # Re-enable UI elements
        if hasattr(self, 'project_combo'):
            self.project_combo.setEnabled(True)
        
        # Show error message
        QMessageBox.critical(
            self,
            "Workflow Failed",
            f"The CFD workflow encountered an error:\n\n{error_message}\n\n"
            "Please check the log for more details and try again."
        )
    
    def create_new_project_advanced(self):
        """Create a new project with advanced options."""
        dialog = AdvancedProjectDialog(self)
        if dialog.exec() == QDialog.Accepted:
            project_data = dialog.get_project_data()
            
            try:
                response = self.api_client.create_project(
                    project_name=project_data["name"],
                    description=project_data["description"]
                )
                
                if response.get("success"):
                    logger.info(f"Advanced project created: {project_data['name']}")
                    self.load_projects()
                    
                    # Select the new project
                    index = self.project_combo.findText(project_data["name"])
                    if index >= 0:
                        self.project_combo.setCurrentIndex(index)
                    
                    self.status_bar.showMessage(f"Created project: {project_data['name']}", 3000)
                else:
                    QMessageBox.warning(self, "Error", f"Failed to create project: {response.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"Error creating advanced project: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to create project: {str(e)}")
    
    def clone_current_project(self):
        """Clone the current project."""
        if not self.current_project:
            QMessageBox.warning(self, "Error", "No project selected to clone")
            return
        
        dialog = CloneProjectDialog(self.current_project, self)
        if dialog.exec() == QDialog.Accepted:
            new_name = dialog.get_new_name()
            
            try:
                # Create new project
                response = self.api_client.create_project(
                    project_name=new_name,
                    description=f"Clone of {self.current_project}"
                )
                
                if response.get("success"):
                    logger.info(f"Project cloned: {self.current_project} -> {new_name}")
                    self.load_projects()
                    
                    # Select the new project
                    index = self.project_combo.findText(new_name)
                    if index >= 0:
                        self.project_combo.setCurrentIndex(index)
                    
                    self.status_bar.showMessage(f"Cloned project: {new_name}", 3000)
                else:
                    QMessageBox.warning(self, "Error", f"Failed to clone project: {response.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"Error cloning project: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to clone project: {str(e)}")
    
    # Connection Testing
    def test_connections(self):
        """Test connections to server and ParaView"""
        self.status_bar.showMessage("Testing connections...")
        
        # Use background thread to avoid blocking UI
        if self.connection_test_thread and self.connection_test_thread.isRunning():
            return
        
        self.connection_test_thread = ConnectionTestThread(self.api_client, self.paraview_widget)
        self.connection_test_thread.connection_tested.connect(self.on_connection_tested)
        self.connection_test_thread.start()
    
    def on_connection_tested(self, service: str, success: bool):
        """Handle connection test results"""
        if service == "server":
            if success:
                self.server_status_label.setText("Server: Connected")
                self.server_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.server_status_label.setText("Server: Not connected")
                self.server_status_label.setStyleSheet("color: red; font-weight: bold;")
        
        elif service == "paraview":
            if success:
                self.paraview_status_label.setText("ParaView: Connected")
                self.paraview_status_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.paraview_status_label.setText("ParaView: Not connected")
                self.paraview_status_label.setStyleSheet("color: red; font-weight: bold;")
        
        # Update status when both tests complete
        if self.connection_test_thread and self.connection_test_thread.isFinished():
            self.status_bar.showMessage("Connection test completed", 3000)
    
    def connect_paraview(self):
        """Connect to ParaView server"""
        # First check if current project has a PVServer
        current_project = self.api_client.get_current_project()
        if current_project:
            try:
                # Try to get existing PVServer info
                pv_info = self.api_client.get_pvserver_info(current_project)
                if pv_info.get('status') == 'running':
                    connection_string = pv_info.get('connection_string')
                    if connection_string and self.paraview_widget:
                        host, port = connection_string.split(':')
                        self.paraview_widget.connect_to_server(host, int(port))
                        QTimer.singleShot(1000, self.update_paraview_status)
                        return
                else:
                    # Start a new PVServer for the project
                    response = self.api_client.start_pvserver(project_name=current_project)
                    if response.get('status') == 'running':
                        connection_string = response.get('connection_string')
                        if connection_string and self.paraview_widget:
                            host, port = connection_string.split(':')
                            self.paraview_widget.connect_to_server(host, int(port))
                            QTimer.singleShot(1000, self.update_paraview_status)
                            return
            except Exception as e:
                logger.error(f"Failed to connect to project PVServer: {str(e)}")
        
        # Fallback to default connection
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
    
    def on_paraview_connection_changed(self, connected: bool):
        """Handle ParaView connection status changes from the widget"""
        if connected:
            self.paraview_status_label.setText("ParaView: Connected")
            self.paraview_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.paraview_status_label.setText("ParaView: Not connected")
            self.paraview_status_label.setStyleSheet("color: red; font-weight: bold;")
    
    # ... rest of existing methods (load_mesh_visualization, etc.) remain the same
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
            if self.simulation_widget and hasattr(self.simulation_widget, 'reset_simulation'):
                self.simulation_widget.reset_simulation()
            
            # Reset ParaView
            if self.paraview_widget:
                self.paraview_widget.disconnect_from_server()
                # Try to reconnect to project PVServer if available
                self.connect_paraview()
            
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
            <li>Project-based workflow management</li>
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
            <li>Create a new project or select an existing one</li>
            <li>Describe your simulation scenario in the chat area</li>
            <li>Review the generated mesh in the visualization area</li>
            <li>Approve or provide feedback on the mesh</li>
            <li>View simulation results with visualization controls</li>
        </ol>
        
        <p><b>Project Management:</b></p>
        <ul>
            <li>Use "New Project" to create a simulation project</li>
            <li>Select projects from the dropdown to switch between them</li>
            <li>Each project maintains its own files and ParaView server</li>
        </ul>
        
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
        if self.simulation_widget:
            self.simulation_widget.close()
        
        if self.paraview_widget:
            self.paraview_widget.disconnect_from_server()
        
        if self.api_client:
            self.api_client.close()
        
        event.accept()
        
        # Log application shutdown
        logger.info("Application shutting down") 