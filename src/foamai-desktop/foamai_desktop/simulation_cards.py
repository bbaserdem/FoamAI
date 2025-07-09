"""
Simulation Cards for OpenFOAM Desktop Application
Visual components for mesh, solver, and parameters setup
"""
import os
from typing import Optional, Callable
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                               QCheckBox, QFrame, QFileDialog, QTextEdit, QGroupBox)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QPen, QBrush, QColor

from simulation_state import SimulationState, ComponentState, MeshData, SolverData, ParametersData

class SimulationCard(QFrame):
    """Base class for simulation component cards"""
    
    # Signals
    clicked = Signal()
    lock_changed = Signal(bool)
    upload_clicked = Signal()
    
    def __init__(self, title: str, component_type: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.component_type = component_type
        self.state = ComponentState.EMPTY
        self.locked = False
        
        self.setup_ui()
        self.setup_styling()
    
    def setup_ui(self):
        """Setup the card UI"""
        self.setFixedHeight(150)
        self.setFrameStyle(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header with title and lock checkbox
        header_layout = QHBoxLayout()
        
        # Title
        self.title_label = QLabel(self.title)
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        # Lock checkbox
        self.lock_checkbox = QCheckBox("🔒")
        self.lock_checkbox.setToolTip("Lock this component to prevent AI modifications")
        self.lock_checkbox.toggled.connect(self.on_lock_changed)
        header_layout.addWidget(self.lock_checkbox)
        
        layout.addLayout(header_layout)
        
        # Description area
        self.description_label = QLabel("Click to configure or drag files here")
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.description_label)
        
        # Status and buttons area
        bottom_layout = QHBoxLayout()
        
        # Status indicator
        self.status_label = QLabel("Empty")
        self.status_label.setStyleSheet("color: #888; font-size: 10pt;")
        bottom_layout.addWidget(self.status_label)
        
        bottom_layout.addStretch()
        
        # Action button (upload, select, etc.)
        self.action_button = QPushButton()
        self.action_button.setFixedSize(80, 25)
        self.action_button.clicked.connect(self.upload_clicked.emit)
        bottom_layout.addWidget(self.action_button)
        
        layout.addLayout(bottom_layout)
    
    def setup_styling(self):
        """Setup card styling"""
        self.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin: 2px;
            }
            QFrame:hover {
                border-color: #0078d4;
                background-color: #f5f5f5;
            }
        """)
    
    def mousePressEvent(self, event):
        """Handle mouse press event"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
    
    def on_lock_changed(self, locked: bool):
        """Handle lock state change"""
        self.locked = locked
        self.lock_changed.emit(locked)
        self.update_visual_state()
    
    def update_visual_state(self):
        """Update visual appearance based on current state"""
        if self.state == ComponentState.EMPTY:
            self.setStyleSheet("""
                QFrame {
                    background-color: #fafafa;
                    border: 2px dashed #ccc;
                    border-radius: 8px;
                    margin: 2px;
                }
                QFrame:hover {
                    border-color: #0078d4;
                    background-color: #f5f5f5;
                }
            """)
            self.status_label.setText("Empty")
            self.status_label.setStyleSheet("color: #888; font-size: 10pt;")
            
        elif self.state == ComponentState.POPULATED:
            self.setStyleSheet("""
                QFrame {
                    background-color: #f0f8ff;
                    border: 2px solid #0078d4;
                    border-radius: 8px;
                    margin: 2px;
                }
                QFrame:hover {
                    border-color: #106ebe;
                    background-color: #e8f4f8;
                }
            """)
            self.status_label.setText("Configured")
            self.status_label.setStyleSheet("color: #0078d4; font-size: 10pt; font-weight: bold;")
            
        elif self.state == ComponentState.LOCKED:
            self.setStyleSheet("""
                QFrame {
                    background-color: #f0f8f0;
                    border: 2px solid #107c10;
                    border-radius: 8px;
                    margin: 2px;
                }
                QFrame:hover {
                    border-color: #0e6e0e;
                    background-color: #e8f5e8;
                }
            """)
            self.status_label.setText("Locked")
            self.status_label.setStyleSheet("color: #107c10; font-size: 10pt; font-weight: bold;")
    
    def set_state(self, state: ComponentState):
        """Set the current state"""
        self.state = state
        self.update_visual_state()
    
    def set_description(self, description: str):
        """Set the description text"""
        if description:
            self.description_label.setText(description)
            self.description_label.setStyleSheet("color: #333; font-style: normal;")
        else:
            self.description_label.setText("Click to configure or drag files here")
            self.description_label.setStyleSheet("color: #666; font-style: italic;")

class MeshCard(SimulationCard):
    """Card for mesh component"""
    
    def __init__(self, parent=None):
        super().__init__("Mesh", "mesh", parent)
        self.action_button.setText("Upload")
        self.action_button.setToolTip("Upload mesh file (.stl, .foam, .obj)")
        
        # Enable drag and drop
        self.setAcceptDrops(True)
    
    def dragEnterEvent(self, event):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and any(url.toLocalFile().lower().endswith(('.stl', '.foam', '.obj')) for url in urls):
                event.acceptProposedAction()
    
    def dropEvent(self, event):
        """Handle drop event"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.stl', '.foam', '.obj')):
                self.handle_file_upload(file_path)
    
    def handle_file_upload(self, file_path: str):
        """Handle file upload"""
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1].lower()
        
        if file_ext == '.stl':
            self.set_description(f"STL file: {file_name}\n(Will be preprocessed into mesh)")
        elif file_ext == '.foam':
            self.set_description(f"OpenFOAM mesh: {file_name}")
        else:
            self.set_description(f"Mesh file: {file_name}")
        
        self.set_state(ComponentState.POPULATED)
        # TODO: Emit signal with file path

class SolverCard(SimulationCard):
    """Card for solver component"""
    
    def __init__(self, parent=None):
        super().__init__("Solver", "solver", parent)
        self.action_button.setText("Select")
        self.action_button.setToolTip("Select OpenFOAM solver")
    
    def set_solver_info(self, name: str, description: str, justification: str = ""):
        """Set solver information"""
        if name:
            display_text = f"{name}\n{description}"
            if justification:
                display_text += f"\n\nJustification: {justification}"
            self.set_description(display_text)
            self.set_state(ComponentState.POPULATED)
        else:
            self.set_description("Click to select solver")
            self.set_state(ComponentState.EMPTY)

class ParametersCard(SimulationCard):
    """Card for parameters component"""
    
    def __init__(self, parent=None):
        super().__init__("Parameters", "parameters", parent)
        self.action_button.setText("Upload")
        self.action_button.setToolTip("Upload parameters file or configure manually")
        
        # Enable drag and drop
        self.setAcceptDrops(True)
    
    def dragEnterEvent(self, event):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and any(url.toLocalFile().lower().endswith(('.json', '.yaml', '.yml', '.txt')) for url in urls):
                event.acceptProposedAction()
    
    def dropEvent(self, event):
        """Handle drop event"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.json', '.yaml', '.yml', '.txt')):
                self.handle_file_upload(file_path)
    
    def handle_file_upload(self, file_path: str):
        """Handle file upload"""
        file_name = os.path.basename(file_path)
        self.set_description(f"Parameters file: {file_name}")
        self.set_state(ComponentState.POPULATED)
        # TODO: Emit signal with file path
    
    def set_parameters_info(self, description: str, parameters: dict):
        """Set parameters information"""
        if description or parameters:
            display_text = description or "Custom parameters"
            if parameters:
                # Show a few key parameters
                param_preview = []
                for key, value in list(parameters.items())[:3]:
                    param_preview.append(f"{key}: {value}")
                if param_preview:
                    display_text += f"\n{', '.join(param_preview)}"
                    if len(parameters) > 3:
                        display_text += f"\n... and {len(parameters) - 3} more"
            self.set_description(display_text)
            self.set_state(ComponentState.POPULATED)
        else:
            self.set_description("Click to configure parameters")
            self.set_state(ComponentState.EMPTY) 