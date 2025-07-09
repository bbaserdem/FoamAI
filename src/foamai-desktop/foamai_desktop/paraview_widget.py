"""
ParaView Widget for OpenFOAM Desktop Application
Handles 3D visualization using ParaView server connection
"""
import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QMessageBox, QGroupBox, QSlider, QSpinBox, QGridLayout,
                               QDoubleSpinBox, QCheckBox, QStyle)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QImage

try:
    import paraview.simple as pv
    from paraview.simple import Connect, Disconnect, GetActiveSource, GetActiveView
    from paraview.simple import OpenFOAMReader, Show, Hide, Render
    from paraview.simple import CreateRenderView, ResetCamera
    PARAVIEW_AVAILABLE = True
except ImportError as e:
    PARAVIEW_AVAILABLE = False
    pv = None
    print(f"ParaView import error: {e}")

# Try to import VTK with Qt integration
VTK_AVAILABLE = False
VTK_QT_AVAILABLE = False
vtk = None
QVTKRenderWindowInteractor = None

# Initialize VTK-related variables
VTK_AVAILABLE = False
VTK_QT_AVAILABLE = False
vtk = None
QVTKRenderWindowInteractor = None

def initialize_vtk():
    """Initialize VTK in a robust way with minimal, targeted imports"""
    global VTK_AVAILABLE, VTK_QT_AVAILABLE, vtk, QVTKRenderWindowInteractor
    
    # Set up environment for PySide6 before importing VTK
    import os
    import sys
    os.environ['QT_API'] = 'pyside6'
    
    print("🔧 Initializing VTK with targeted imports...")
    
    try:
        # Import only the specific VTK modules we need, avoiding the full vtk package
        print("🔧 Importing specific VTK modules...")
        
        # Import essential VTK modules individually to avoid problematic dependencies
        try:
            # Import the core VTK modules we actually need
            import vtkmodules.vtkCommonCore as vtkCommonCore
            import vtkmodules.vtkCommonDataModel as vtkCommonDataModel
            import vtkmodules.vtkRenderingCore as vtkRenderingCore
            import vtkmodules.vtkRenderingOpenGL2 as vtkRenderingOpenGL2
            
            # Try to import additional rendering modules
            try:
                import vtkmodules.vtkRenderingAnnotation as vtkRenderingAnnotation
                print("✅ VTK rendering annotation module available")
            except ImportError:
                print("⚠️ VTK rendering annotation module not available")
            
            # Try to import the OpenFOAM reader from various possible modules
            vtkIOOther = None
            vtkIOGeometry = None
            vtkIOImport = None
            vtkIOLegacy = None
            
            try:
                import vtkmodules.vtkIOOther as vtkIOOther
                print("✅ VTK IO Other module available")
            except ImportError:
                print("⚠️ VTK IO Other module not available")
                
            try:
                import vtkmodules.vtkIOGeometry as vtkIOGeometry
                print("✅ VTK IO Geometry module available")
            except ImportError:
                print("⚠️ VTK IO Geometry module not available")
                
            try:
                import vtkmodules.vtkIOImport as vtkIOImport
                print("✅ VTK IO Import module available")
            except ImportError:
                print("⚠️ VTK IO Import module not available")
                
            try:
                import vtkmodules.vtkIOLegacy as vtkIOLegacy
                print("✅ VTK IO Legacy module available")
            except ImportError:
                print("⚠️ VTK IO Legacy module not available")
                vtkIOLegacy = None
            
            # Create a minimal VTK-like object with just the classes we need
            import types
            vtk = types.ModuleType('vtk')
            
            # Add the essential VTK classes to our minimal vtk module (with error handling)
            def safe_add_class(module, class_name, fallback_module=None):
                """Safely add a VTK class to our minimal vtk module"""
                try:
                    if hasattr(module, class_name):
                        setattr(vtk, class_name, getattr(module, class_name))
                        return True
                    elif fallback_module and hasattr(fallback_module, class_name):
                        setattr(vtk, class_name, getattr(fallback_module, class_name))
                        return True
                    else:
                        print(f"⚠️ {class_name} not found in expected modules")
                        return False
                except Exception as e:
                    print(f"⚠️ Failed to add {class_name}: {e}")
                    return False
            
            # Add core rendering classes
            safe_add_class(vtkRenderingCore, 'vtkRenderer')
            safe_add_class(vtkRenderingCore, 'vtkRenderWindow')
            safe_add_class(vtkRenderingCore, 'vtkRenderWindowInteractor')
            safe_add_class(vtkRenderingCore, 'vtkPolyDataMapper')
            safe_add_class(vtkRenderingCore, 'vtkActor')
            safe_add_class(vtkRenderingCore, 'vtkMapper')
            safe_add_class(vtkRenderingCore, 'vtkLookupTable')  # Add lookup table here
            
            # Add scalar bar actor (could be in different modules)
            if 'vtkRenderingAnnotation' in locals():
                safe_add_class(vtkRenderingAnnotation, 'vtkScalarBarActor', vtkRenderingCore)
            else:
                safe_add_class(vtkRenderingCore, 'vtkScalarBarActor')
            
            # Add data model classes
            safe_add_class(vtkCommonDataModel, 'vtkPolyData')
            safe_add_class(vtkCommonDataModel, 'vtkUnstructuredGrid')
            
            # Add VTK color support for lookup tables - try multiple modules
            lut_added = False
            try:
                import vtkmodules.vtkCommonColor as vtkCommonColor
                if safe_add_class(vtkCommonColor, 'vtkLookupTable'):
                    lut_added = True
                safe_add_class(vtkCommonColor, 'vtkColorTransferFunction')
                print("✅ VTK color support available")
            except ImportError:
                print("⚠️ VTK CommonColor not available - trying alternatives")
            
            # Try alternative modules for lookup table
            if not lut_added:
                try:
                    # Try Common module
                    import vtkmodules.vtkCommonCore as vtkCommonCore_alt
                    if safe_add_class(vtkCommonCore_alt, 'vtkLookupTable'):
                        lut_added = True
                        print("✅ VTK lookup table available via CommonCore")
                except ImportError:
                    pass
                    
            if not lut_added:
                try:
                    # Try DataModel module
                    if safe_add_class(vtkCommonDataModel, 'vtkLookupTable'):
                        lut_added = True
                        print("✅ VTK lookup table available via DataModel")
                except:
                    pass
                    
            if not lut_added:
                print("⚠️ VTK lookup table not available - will use default coloring")
            
            # Add VTK sources for basic geometry
            try:
                import vtkmodules.vtkFiltersSources as vtkFiltersSources
                safe_add_class(vtkFiltersSources, 'vtkSphereSource')
                safe_add_class(vtkFiltersSources, 'vtkCubeSource')
                safe_add_class(vtkFiltersSources, 'vtkConeSource')
                safe_add_class(vtkFiltersSources, 'vtkCylinderSource')
                print("✅ VTK basic sources available")
            except ImportError:
                print("⚠️ VTK sources not available - basic geometry will be limited")
            
            # Add VTK filters for data conversion
            try:
                import vtkmodules.vtkFiltersGeometry as vtkFiltersGeometry
                safe_add_class(vtkFiltersGeometry, 'vtkGeometryFilter')
                print("✅ VTK geometry filters available")
            except ImportError:
                print("⚠️ VTK geometry filters not available - data conversion will be limited")
            
            # Add file readers - try to find OpenFOAM reader in multiple modules
            openfoam_reader_found = False
            
            # Try to find OpenFOAM reader in different modules
            for module_name, module in [('vtkIOOther', vtkIOOther), ('vtkIOGeometry', vtkIOGeometry), ('vtkIOImport', vtkIOImport)]:
                if module and safe_add_class(module, 'vtkOpenFOAMReader'):
                    print(f"✅ OpenFOAM reader found in {module_name}")
                    openfoam_reader_found = True
                    break
            
            if not openfoam_reader_found:
                print("⚠️ OpenFOAM reader not found - adding alternative file readers")
                # Add alternative readers for common formats
                if 'vtkIOLegacy' in locals() and vtkIOLegacy:
                    safe_add_class(vtkIOLegacy, 'vtkPolyDataReader')
                    safe_add_class(vtkIOLegacy, 'vtkUnstructuredGridReader')
                if vtkIOGeometry:
                    safe_add_class(vtkIOGeometry, 'vtkSTLReader')
                    safe_add_class(vtkIOGeometry, 'vtkPLYReader')
                
                # Create a custom OpenFOAM reader that suggests alternatives
                def openfoam_reader_fallback(*args, **kwargs):
                    raise ImportError(
                        "OpenFOAM reader not available in this VTK build.\n"
                        "Alternative solutions:\n"
                        "1. Convert OpenFOAM data to VTK format using foamToVTK\n"
                        "2. Use ParaView server mode instead\n"
                        "3. Install a VTK build with OpenFOAM support"
                    )
                vtk.vtkOpenFOAMReader = openfoam_reader_fallback
            
            # Add version info
            vtk.vtkVersion = vtkCommonCore.vtkVersion
            
            # Add OpenGL settings if available
            safe_add_class(vtkRenderingOpenGL2, 'vtkOpenGLRenderWindow')
            
            VTK_AVAILABLE = True
            print(f"✅ VTK modules loaded successfully: {vtk.vtkVersion.GetVTKVersion()}")
            
        except ImportError as targeted_error:
            print(f"❌ Targeted VTK import failed: {targeted_error}")
            print("🔧 Falling back to full VTK import with error handling...")
            
            # Fallback: try the full VTK import with patching as last resort
            original_import = __builtins__['__import__']
            
            def patched_import(name, *args, **kwargs):
                if 'vtkTestingSerialization' in name:
                    print(f"🚫 Skipping problematic import: {name}")
                    # Return a dummy module
                    import types
                    dummy_module = types.ModuleType(name)
                    return dummy_module
                return original_import(name, *args, **kwargs)
            
            # Apply the patch
            __builtins__['__import__'] = patched_import
            
            try:
                # Try importing full VTK with the patch
                import vtk as vtk_module
                vtk = vtk_module
                VTK_AVAILABLE = True
                print(f"✅ VTK version (patched): {vtk.vtkVersion.GetVTKVersion()}")
                
            except Exception as patched_error:
                print(f"❌ VTK import still failed after patch: {patched_error}")
                VTK_AVAILABLE = False
                vtk = None
                
            finally:
                # Restore original import
                __builtins__['__import__'] = original_import
                
        if VTK_AVAILABLE and vtk:
            # Try to import VTK-Qt integration with minimal dependencies
            try:
                print("🔧 Importing VTK-Qt integration...")
                # Try the working VTK-Qt integration without importing heavy modules
                from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
                VTK_QT_AVAILABLE = True
                print("✅ VTK-Qt integration loaded successfully!")
                
                # Set VTK to use software rendering if hardware OpenGL fails
                try:
                    # Try to force compatible OpenGL settings (only if we have the classes)
                    if hasattr(vtk, 'vtkOpenGLRenderWindow'):
                        vtk.vtkOpenGLRenderWindow.SetGlobalMaximumNumberOfMultiSamples(0)
                    if hasattr(vtk, 'vtkMapper'):
                        vtk.vtkMapper.SetResolveCoincidentTopologyToPolygonOffset()
                except Exception as settings_error:
                    print(f"⚠️ VTK OpenGL settings failed: {settings_error}")
                    pass  # Ignore if these settings aren't available
                
            except Exception as qt_error:
                print(f"⚠️ VTK-Qt (vtkmodules) failed: {qt_error}")
                # Fallback to vtk.qt if vtkmodules doesn't work
                try:
                    print("🔧 Trying VTK-Qt fallback...")
                    from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
                    VTK_QT_AVAILABLE = True
                    print("✅ VTK-Qt integration loaded successfully (fallback method)!")
                except Exception as qt_fallback_error:
                    print(f"❌ VTK-Qt integration failed: {qt_fallback_error}")
                    print("❌ VTK-Qt integration failed - embedded visualization disabled")
                    VTK_QT_AVAILABLE = False
        else:
            print("❌ VTK not available - skipping Qt integration")
            VTK_QT_AVAILABLE = False
                
    except Exception as e:
        print(f"❌ VTK initialization error: {e}")
        print("VTK not available - visualization will be limited")
        VTK_AVAILABLE = False
        VTK_QT_AVAILABLE = False
        vtk = None
        
    print(f"🔧 VTK initialization complete: VTK_AVAILABLE={VTK_AVAILABLE}, VTK_QT_AVAILABLE={VTK_QT_AVAILABLE}")
    return VTK_AVAILABLE, VTK_QT_AVAILABLE

# Don't initialize VTK immediately - defer until needed
print("🔧 Deferring VTK initialization until needed...")

from config import Config

logger = logging.getLogger(__name__)

class ParaViewWidget(QWidget):
    """Widget for displaying ParaView visualizations"""
    
    # Signals
    visualization_loaded = Signal(str)  # Emitted when visualization is loaded
    visualization_error = Signal(str)   # Emitted when visualization fails
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_source = None
        self.time_steps = []
        self.time_directories = []
        
        # Initialize field button tracking
        self.field_buttons = {}
        self.available_fields = []
        self.current_field = None  # Track currently selected field
        
        # Connection state
        self.connected = False
        
        # Initialize UI
        self.setup_ui()
        
        # Connection timer for retry logic
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.retry_connection)
        
        # Note: VTK initialization is deferred until UI setup
        # Auto-connect logic will be handled after UI setup
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        
        # Initialize VTK when UI is being set up (deferred initialization)
        global VTK_AVAILABLE, VTK_QT_AVAILABLE, vtk, QVTKRenderWindowInteractor
        if not VTK_AVAILABLE:
            print("🔄 Initializing VTK (deferred)...")
            try:
                vtk_result, vtk_qt_result = initialize_vtk()
                print(f"🔄 Initialization result: VTK_AVAILABLE={VTK_AVAILABLE}, VTK_QT_AVAILABLE={VTK_QT_AVAILABLE}")
            except Exception as e:
                print(f"VTK initialization failed: {e}")
                import traceback
                traceback.print_exc()
        
        # Connection status
        if VTK_QT_AVAILABLE and QVTKRenderWindowInteractor:
            if PARAVIEW_AVAILABLE:
                self.connection_label = QLabel("VTK + ParaView available - best performance")
            else:
                self.connection_label = QLabel("Embedded VTK rendering ready")
            self.connection_label.setStyleSheet("color: orange; font-weight: bold;")
        elif PARAVIEW_AVAILABLE:
            self.connection_label = QLabel("ParaView server mode - connect to view")
            self.connection_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.connection_label = QLabel("Visualization not available")
            self.connection_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.connection_label)
        
        # Create horizontal layout for view buttons and visualization area
        viz_horizontal_layout = QHBoxLayout()
        
        # View orientation buttons column
        self.setup_view_buttons(viz_horizontal_layout)
        
        # Visualization area - VTK widget for embedded rendering or ParaView for server rendering
        if VTK_QT_AVAILABLE and QVTKRenderWindowInteractor:
            try:
                # Use embedded VTK rendering with proper OpenGL context setup
                from PySide6.QtCore import Qt
                
                # Create VTK widget with explicit OpenGL context
                self.vtk_widget = QVTKRenderWindowInteractor(self)
                self.vtk_widget.setMinimumSize(600, 400)
                
                # Set format for OpenGL context
                from PySide6.QtGui import QSurfaceFormat
                format = QSurfaceFormat()
                format.setRenderableType(QSurfaceFormat.OpenGL)
                format.setProfile(QSurfaceFormat.CoreProfile)
                format.setVersion(3, 2)  # OpenGL 3.2
                format.setDepthBufferSize(24)
                format.setStencilBufferSize(8)
                format.setSamples(4)  # Anti-aliasing
                format.setSwapBehavior(QSurfaceFormat.DoubleBuffer)
                
                # Apply format before getting render window
                if hasattr(self.vtk_widget, 'setFormat'):
                    self.vtk_widget.setFormat(format)
                
                # Get render window and set up OpenGL backend
                self.render_window = self.vtk_widget.GetRenderWindow()
                
                # Force VTK to use OpenGL2 backend (more compatible)
                self.render_window.SetMultiSamples(0)  # Disable multisampling if problematic
                
                # Create renderer
                self.renderer = vtk.vtkRenderer()
                self.render_window.AddRenderer(self.renderer)
                
                # Set background color
                self.renderer.SetBackground(0.1, 0.1, 0.2)  # Dark blue background
                
                viz_horizontal_layout.addWidget(self.vtk_widget)
                
                # Initialize the interactor with proper context
                self.vtk_widget.Initialize()
                self.vtk_widget.Start()
                
                # Set up custom mouse interaction
                self.setup_custom_mouse_interaction()
                
                # Test render to check if OpenGL context works
                try:
                    self.render_window.Render()
                    self.use_embedded_vtk = True
                    print("✅ Embedded VTK widget ready with OpenGL context!")
                except Exception as render_error:
                    print(f"⚠️ OpenGL context test failed: {render_error}")
                    print("⚠️ Falling back to software rendering...")
                    
                    # Try software rendering fallback
                    self.render_window.SetOffScreenRendering(1)
                    self.render_window.Render()
                    self.use_embedded_vtk = True
                    print("✅ Embedded VTK widget ready with software rendering!")
                
            except Exception as e:
                print(f"❌ Failed to initialize VTK-Qt widget: {e}")
                import traceback
                traceback.print_exc()
                print("⚠️ Falling back to ParaView server mode")
                self.vtk_widget = None
                self.use_embedded_vtk = False
                # Fall through to ParaView fallback
                
        if not hasattr(self, 'use_embedded_vtk') or not self.use_embedded_vtk:
            if PARAVIEW_AVAILABLE:
                # Fallback to ParaView server connection with image display
                self.visualization_area = QLabel("Connect to ParaView server to view visualizations")
                self.visualization_area.setMinimumSize(600, 400)
                self.visualization_area.setStyleSheet("""
                    QLabel {
                        border: 2px solid #ccc;
                        border-radius: 5px;
                        background-color: #f0f0f0;
                        text-align: center;
                    }
                """)
                viz_horizontal_layout.addWidget(self.visualization_area)
                self.vtk_widget = None
                self.use_embedded_vtk = False
                
            else:
                # No visualization available
                self.visualization_area = QLabel("Visualization not available.\n\nInstall options:\n• pip install vtk (for embedded rendering)\n• Install ParaView (for server rendering)")
                self.visualization_area.setMinimumSize(600, 400)
                self.visualization_area.setStyleSheet("""
                    QLabel {
                        border: 2px solid #ccc;
                        border-radius: 5px;
                        background-color: #f0f0f0;
                        text-align: center;
                        color: red;
                        font-weight: bold;
                    }
                """)
                viz_horizontal_layout.addWidget(self.visualization_area)
                self.vtk_widget = None
                self.use_embedded_vtk = False
        
        # Add the horizontal layout to the main layout
        layout.addLayout(viz_horizontal_layout)
        
        # Control buttons
        self.setup_controls(layout)
        
        # Auto-connect if embedded VTK is available (after UI setup)
        if VTK_QT_AVAILABLE and hasattr(self, 'vtk_widget') and self.vtk_widget:
            # Auto-initialize embedded VTK rendering
            logger.info("✅ Embedded VTK rendering available - auto-connecting")
            QTimer.singleShot(100, self.connect_to_server)
        elif VTK_AVAILABLE:
            logger.info("⚠️ VTK available but no Qt integration - standalone windows will be used")
        elif PARAVIEW_AVAILABLE:
            logger.info("⚠️ ParaView server mode available - manual connection required")
        else:
            logger.warning("❌ No visualization system available. Please install VTK or ParaView.")
    
    def setup_controls(self, layout):
        """Setup control buttons and widgets"""
        # Visualization controls group
        viz_group = QGroupBox("Visualization Controls")
        viz_layout = QVBoxLayout(viz_group)
        
        # Create a container for dynamic field buttons
        self.field_buttons_container = QWidget()
        self.field_buttons_layout = QGridLayout(self.field_buttons_container)
        self.field_buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a label to show current field info
        self.field_info_label = QLabel("No fields detected - load data first")
        self.field_info_label.setStyleSheet("color: gray; font-style: italic;")
        viz_layout.addWidget(self.field_info_label)
        
        # Add the dynamic field buttons container
        viz_layout.addWidget(self.field_buttons_container)
        
        # Store field buttons for later management
        self.field_buttons = {}
        self.available_fields = []
        self.current_field = None  # Track currently selected field
        
        layout.addWidget(viz_group)
        
        # Enhanced time controls group
        time_group = QGroupBox("Time Controls")
        time_layout = QVBoxLayout(time_group)
        
        # Top row with main time controls
        time_controls_layout = QHBoxLayout()
        
        # Get Qt style for standard icons
        style = self.style()
        
        # First frame button
        self.first_frame_btn = QPushButton()
        self.first_frame_btn.setIcon(style.standardIcon(QStyle.SP_MediaSkipBackward))
        self.first_frame_btn.clicked.connect(self.first_time_step)
        self.first_frame_btn.setEnabled(False)
        self.first_frame_btn.setToolTip("Go to first time step")
        self.first_frame_btn.setMaximumWidth(40)
        time_controls_layout.addWidget(self.first_frame_btn)
        
        # Previous frame button  
        self.prev_time_btn = QPushButton()
        self.prev_time_btn.setIcon(style.standardIcon(QStyle.SP_MediaSeekBackward))
        self.prev_time_btn.clicked.connect(self.previous_time_step)
        self.prev_time_btn.setEnabled(False)
        self.prev_time_btn.setToolTip("Previous time step")
        self.prev_time_btn.setMaximumWidth(40)
        time_controls_layout.addWidget(self.prev_time_btn)
        
        # Play/Pause button
        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setIcon(style.standardIcon(QStyle.SP_MediaPlay))
        self.play_pause_btn.clicked.connect(self.play_pause_toggle)
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.setToolTip("Play/Pause animation")
        self.play_pause_btn.setMaximumWidth(40)
        time_controls_layout.addWidget(self.play_pause_btn)
        
        # Next frame button
        self.next_time_btn = QPushButton()
        self.next_time_btn.setIcon(style.standardIcon(QStyle.SP_MediaSeekForward))
        self.next_time_btn.clicked.connect(self.next_time_step)
        self.next_time_btn.setEnabled(False)
        self.next_time_btn.setToolTip("Next time step")
        self.next_time_btn.setMaximumWidth(40)
        time_controls_layout.addWidget(self.next_time_btn)
        
        # Last frame button
        self.last_frame_btn = QPushButton()
        self.last_frame_btn.setIcon(style.standardIcon(QStyle.SP_MediaSkipForward))
        self.last_frame_btn.clicked.connect(self.last_time_step)
        self.last_frame_btn.setEnabled(False)
        self.last_frame_btn.setToolTip("Go to last time step")
        self.last_frame_btn.setMaximumWidth(40)
        time_controls_layout.addWidget(self.last_frame_btn)
        
        # Time slider
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.valueChanged.connect(self.set_time_step)
        self.time_slider.setEnabled(False)
        time_controls_layout.addWidget(self.time_slider)
        
        # Time label
        self.time_label = QLabel("Time: 0.0")
        self.time_label.setMinimumWidth(80)
        time_controls_layout.addWidget(self.time_label)
        
        time_layout.addLayout(time_controls_layout)
        
        # Bottom row with playback settings
        playback_settings_layout = QHBoxLayout()
        
        # Speed control
        speed_label = QLabel("Speed:")
        playback_settings_layout.addWidget(speed_label)
        
        self.speed_control = QDoubleSpinBox()
        self.speed_control.setRange(0.1, 2.0)
        self.speed_control.setValue(1.0)
        self.speed_control.setSingleStep(0.1)
        self.speed_control.setSuffix(" s/frame")
        self.speed_control.setToolTip("Animation speed in seconds per frame")
        self.speed_control.setMaximumWidth(120)
        self.speed_control.valueChanged.connect(self.update_playback_speed)
        playback_settings_layout.addWidget(self.speed_control)
        
        # Loop checkbox
        self.loop_checkbox = QCheckBox("Loop")
        self.loop_checkbox.setChecked(False)
        self.loop_checkbox.setToolTip("Loop animation when it reaches the end")
        playback_settings_layout.addWidget(self.loop_checkbox)
        
        # Add stretch to push controls to the left
        playback_settings_layout.addStretch()
        
        time_layout.addLayout(playback_settings_layout)
        
        # Initialize playback system
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.advance_frame)
        self.is_playing = False
        
        layout.addWidget(time_group)
        
        # Connection controls
        conn_group = QGroupBox("Connection Controls")
        conn_layout = QHBoxLayout(conn_group)
        
        if VTK_QT_AVAILABLE:
            if PARAVIEW_AVAILABLE:
                self.connect_btn = QPushButton("Connect to ParaView Server")
            else:
                self.connect_btn = QPushButton("Initialize Visualization")
        elif PARAVIEW_AVAILABLE:
            self.connect_btn = QPushButton("Connect to ParaView Server")
        else:
            self.connect_btn = QPushButton("Visualization Unavailable")
            self.connect_btn.setEnabled(False)
            
        self.connect_btn.clicked.connect(self.connect_to_server)
        conn_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self.disconnect_from_server)
        self.disconnect_btn.setEnabled(False)
        conn_layout.addWidget(self.disconnect_btn)
        
        layout.addWidget(conn_group)
    
    def connect_to_server(self):
        """Connect to visualization (embedded VTK or ParaView server)"""
        if not PARAVIEW_AVAILABLE and not VTK_QT_AVAILABLE:
            self.show_error("No visualization system available")
            return
        
        try:
            if self.use_embedded_vtk and self.vtk_widget:
                # Use embedded VTK rendering
                logger.info("Initializing embedded VTK rendering")
                
                self.connected = True
                self.connection_label.setText("Embedded VTK rendering active")
                self.connection_label.setStyleSheet("color: green; font-weight: bold;")
                
                logger.info("Successfully initialized embedded VTK rendering")
                
            elif PARAVIEW_AVAILABLE:
                # Use ParaView server connection
                server_info = Config.get_paraview_server_info()
                host = server_info['host']
                port = server_info['port']
                
                logger.info(f"Connecting to ParaView server at {host}:{port}")
                
                # Connect to pvserver using lower-level API to avoid automatic view creation
                try:
                    import paraview.servermanager as sm
                    
                    # Connect without creating default views
                    if not sm.ActiveConnection:
                        connection = sm.Connect(host, port)
                        logger.info("Connected to ParaView server using servermanager")
                    else:
                        logger.info("Using existing ParaView server connection")
                    
                    # Only create render view as fallback if embedded VTK is not available
                    if not self.use_embedded_vtk:
                        # For fallback only - when no embedded VTK is available
                        from paraview.simple import CreateRenderView
                        self.current_view = CreateRenderView()
                        logger.info("Created fallback render view for ParaView server")
                    else:
                        logger.info("Using embedded VTK widget for ParaView server data - no render view needed")
                    
                    self.connected = True
                    self.connection_label.setText(f"Connected to ParaView server ({host}:{port})")
                    self.connection_label.setStyleSheet("color: green; font-weight: bold;")
                    
                    logger.info("Successfully connected to ParaView server")
                    
                except Exception as e:
                    logger.error(f"Failed to connect with servermanager: {str(e)}")
                    # Fallback to simple Connect
                    try:
                        Connect(host, port)
                        logger.info("Connected using paraview.simple fallback")
                        
                        self.connected = True
                        self.connection_label.setText(f"Connected to ParaView server ({host}:{port})")
                        self.connection_label.setStyleSheet("color: green; font-weight: bold;")
                        
                    except Exception as e2:
                        logger.error(f"Both connection methods failed: {str(e2)}")
                        raise e2
                
            else:
                self.show_error("No visualization system available")
                return
            
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            
        except Exception as e:
            logger.error(f"Failed to initialize visualization: {str(e)}")
            self.show_error(f"Failed to initialize visualization: {str(e)}")
            self.connected = False
    
    def disconnect_from_server(self):
        """Disconnect from visualization"""
        try:
            if self.use_embedded_vtk and hasattr(self, 'renderer') and self.renderer:
                # Clear embedded VTK renderer
                self.renderer.RemoveAllViewProps()
                if self.vtk_widget:
                    self.vtk_widget.GetRenderWindow().Render()
                logger.info("Cleared embedded VTK rendering")
                
            elif PARAVIEW_AVAILABLE:
                # Disconnect from ParaView server
                try:
                    import paraview.servermanager as sm
                    
                    # Clean up render view if it exists
                    if hasattr(self, 'current_view') and self.current_view:
                        # Import here to avoid automatic view creation
                        from paraview.simple import Delete
                        Delete(self.current_view)
                        self.current_view = None
                        logger.info("Cleaned up ParaView render view")
                    
                    # Disconnect from server
                    if sm.ActiveConnection:
                        sm.Disconnect()
                        logger.info("Disconnected from ParaView server using servermanager")
                    else:
                        logger.info("No active ParaView connection to disconnect")
                        
                except Exception as e:
                    logger.error(f"Error disconnecting via servermanager: {str(e)}")
                    # Fallback to simple Disconnect
                    try:
                        Disconnect()
                        logger.info("Disconnected using paraview.simple fallback")
                    except Exception as e2:
                        logger.error(f"Both disconnect methods failed: {str(e2)}")
                
                logger.info("Disconnected from ParaView server")
            
            # Clean up any remaining temporary case directories if they exist
            if hasattr(self, '_temp_case_dirs') and self._temp_case_dirs:
                try:
                    import shutil
                    for temp_dir in self._temp_case_dirs:
                        try:
                            shutil.rmtree(temp_dir)
                            logger.info(f"Cleaned up temporary case directory: {temp_dir}")
                        except Exception as e:
                            logger.error(f"Failed to cleanup temporary case {temp_dir}: {e}")
                    self._temp_case_dirs = []
                except Exception as e:
                    logger.error(f"Failed to cleanup temporary cases: {e}")
            
            self.connected = False
            self.current_source = None
            
            # Stop any running playback
            if hasattr(self, 'is_playing') and self.is_playing:
                self.pause_playback()
            
            if VTK_QT_AVAILABLE:
                self.connection_label.setText("Embedded VTK rendering ready")
            elif PARAVIEW_AVAILABLE:
                self.connection_label.setText("ParaView server mode - connect to view")
            else:
                self.connection_label.setText("Visualization not available")
                
            self.connection_label.setStyleSheet("color: orange; font-weight: bold;")
            
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            
            # Disable all visualization controls
            self.disable_controls()
            
        except Exception as e:
            logger.error(f"Error disconnecting from visualization: {str(e)}")
    
    def load_foam_file(self, file_path: str):
        """Load an OpenFOAM file for visualization"""
        if not self.connected:
            self.show_error("Not connected to visualization system")
            return
        
        try:
            # Convert to absolute path and fix separators for cross-platform compatibility
            from pathlib import Path
            abs_path = Path(file_path).resolve()
            normalized_path = str(abs_path).replace('\\', '/')
            
            logger.info(f"Loading OpenFOAM file: {normalized_path}")
            
            # Debug logging
            logger.info(f"DEBUG: VTK_AVAILABLE={VTK_AVAILABLE}, vtk={vtk}, PARAVIEW_AVAILABLE={PARAVIEW_AVAILABLE}")
            logger.info(f"DEBUG: self.connected={self.connected}, self.use_embedded_vtk={self.use_embedded_vtk}")
            logger.info(f"DEBUG: hasattr(self, 'current_view')={hasattr(self, 'current_view')}")
            if hasattr(self, 'current_view'):
                logger.info(f"DEBUG: self.current_view={self.current_view}")
            
            # Determine which loading method to use - prioritize embedded rendering
            print(f"🔍 LOADING PATH DEBUG:")
            print(f"   VTK_QT_AVAILABLE: {VTK_QT_AVAILABLE}")
            print(f"   hasattr(self, 'vtk_widget'): {hasattr(self, 'vtk_widget')}")
            print(f"   self.vtk_widget: {getattr(self, 'vtk_widget', 'None')}")
            print(f"   PARAVIEW_AVAILABLE: {PARAVIEW_AVAILABLE}")
            print(f"   self.connected: {self.connected}")
            
            if VTK_QT_AVAILABLE and hasattr(self, 'vtk_widget') and self.vtk_widget:
                # Best case: Embedded VTK rendering in Qt widget
                if PARAVIEW_AVAILABLE and self.connected:
                    print("🎯 USING: ParaView server data with embedded VTK widget")
                    logger.info("Using ParaView server data with embedded VTK widget")
                    self._load_with_paraview_embedded(normalized_path)
                else:
                    print("🎯 USING: Direct VTK rendering in embedded widget")
                    logger.info("Using direct VTK rendering in embedded widget")
                    self._load_with_vtk_embedded(normalized_path)
            elif VTK_AVAILABLE and vtk is not None:
                # Fallback: VTK available but no Qt integration - use standalone windows
                if PARAVIEW_AVAILABLE and self.connected:
                    print("🎯 USING: ParaView server data with standalone VTK window")
                    logger.info("Using ParaView server data with standalone VTK window")
                    self._load_with_paraview(normalized_path)
                else:
                    print("🎯 USING: Direct VTK rendering in standalone window")
                    logger.info("Using direct VTK rendering in standalone window")
                    self._load_with_vtk(normalized_path)
            elif PARAVIEW_AVAILABLE and self.connected:
                # Last resort: ParaView server rendering (separate ParaView window)
                print("🎯 USING: ParaView server fallback rendering - no VTK available")
                logger.info("Using ParaView server fallback rendering - no VTK available")
                self._load_with_paraview_fallback(normalized_path)
            else:
                print("❌ NO LOADING PATH FOUND")
                error_msg = "No active visualization system available.\n\n"
                error_msg += "VTK Status: " + ("Available" if VTK_AVAILABLE else "Not Available") + "\n"
                error_msg += "VTK-Qt Status: " + ("Available" if VTK_QT_AVAILABLE else "Not Available") + "\n"
                error_msg += "ParaView Status: " + ("Available" if PARAVIEW_AVAILABLE else "Not Available") + "\n\n"
                error_msg += "For embedded visualization, install VTK with Qt support:\n"
                error_msg += "  pip install vtk pyside6\n\n"
                self.show_error(error_msg)
                return
            
            # Enable controls
            self.enable_controls()
            
            # Setup time steps if available
            self.setup_time_steps()
            
            # Create dynamic field buttons based on available data
            self.create_field_buttons()
            
            self.visualization_loaded.emit(file_path)
            logger.info(f"Successfully loaded: {normalized_path}")
            
        except Exception as e:
            logger.error(f"Failed to load OpenFOAM file: {str(e)}")
            self.show_error(f"Failed to load file: {str(e)}")
            self.visualization_error.emit(str(e))
    
    def _load_with_vtk(self, file_path: str):
        """Load file using VTK"""
        # Use the global VTK instance
        if not VTK_AVAILABLE or vtk is None:
            logger.error("VTK not available for file loading")
            self.show_error("VTK not available")
            return
        
        vtk_local = vtk
        
        # Create VTK OpenFOAM reader
        reader = vtk_local.vtkOpenFOAMReader()
        reader.SetFileName(file_path)
        reader.CreateCellToPointOn()
        reader.ReadZonesOn()
        reader.Update()
        
        self.current_source = reader
        
        # Create mapper and actor for the mesh
        mapper = vtk_local.vtkPolyDataMapper()
        mapper.SetInputConnection(reader.GetOutputPort())
        
        # Set up scalar field coloring
        try:
            # Try to use pressure field first, then velocity
            reader.Update()
            output = reader.GetOutput()
            if output and output.GetCellData().GetArray('p'):
                print("🎨 Using pressure field (p) for coloring")
                mapper.SetScalarModeToUseCellFieldData()
                mapper.SelectColorArray('p')
                mapper.SetColorModeToMapScalars()
            elif output and output.GetCellData().GetArray('U'):
                print("🎨 Using velocity field (U) for coloring")
                mapper.SetScalarModeToUseCellFieldData()
                mapper.SelectColorArray('U')
                mapper.SetColorModeToMapScalars()
            else:
                print("⚠️ No recognized scalar fields - using solid color")
                
        except Exception as e:
            print(f"⚠️ Failed to set up scalar coloring: {e}")
        
        actor = vtk_local.vtkActor()
        actor.SetMapper(mapper)
        
        # Set basic properties but don't override scalar coloring
        actor.GetProperty().SetOpacity(0.8)
        # Don't set solid color - let the scalar mapping handle coloring
        
        # Check if we have embedded rendering available
        if hasattr(self, 'vtk_widget') and self.vtk_widget and hasattr(self, 'renderer'):
            # Use embedded Qt widget
            self.renderer.RemoveAllViewProps()
            self.renderer.AddActor(actor)
            self.renderer.ResetCamera()
            self.vtk_widget.GetRenderWindow().Render()
            logger.info("Successfully loaded VTK data into embedded widget")
        else:
            # Create standalone VTK window
            logger.info("Creating standalone VTK window for direct VTK visualization")
            
            # Create render window
            render_window = vtk_local.vtkRenderWindow()
            render_window.SetSize(800, 600)
            render_window.SetWindowName("OpenFOAM Visualization - Direct VTK")
            
            # Create renderer
            renderer = vtk_local.vtkRenderer()
            renderer.SetBackground(0.1, 0.1, 0.2)  # Dark blue background
            render_window.AddRenderer(renderer)
            
            # Add actor to renderer
            renderer.AddActor(actor)
            renderer.ResetCamera()
            
            # Create interactor
            interactor = vtk_local.vtkRenderWindowInteractor()
            interactor.SetRenderWindow(render_window)
            
            # Start the visualization
            render_window.Render()
            interactor.Start()
            
            logger.info("Created standalone VTK visualization window")
            
            # Update the visualization area to show a message
            if hasattr(self, 'visualization_area'):
                self.visualization_area.setText(
                    "Visualization opened in standalone VTK window.\n\n"
                    "Data loaded successfully using direct VTK " + vtk_local.vtkVersion.GetVTKVersion() + "\n\n"
                    "To embed visualization in this window:\n"
                    "Install VTK with Qt support:\n"
                    "pip install vtk[qt] or pip install PyQt5"
                )
    
    def _load_with_paraview(self, file_path: str):
        """Load file using ParaView server but render with VTK"""
        # Validate VTK availability
        if not self.validate_vtk():
            logger.error("VTK validation failed - cannot render ParaView data locally")
            self.show_error("VTK is not available for visualization")
            return
        
        # Use the global VTK instance
        if not VTK_AVAILABLE or vtk is None:
            logger.error("VTK not available for ParaView rendering")
            self.show_error("VTK not available")
            return
        
        vtk_local = vtk
        
        # Use lower-level ParaView API to avoid automatic view creation
        try:
            # Import ParaView servermanager for lower-level access
            import paraview.servermanager as sm
            
            # Create OpenFOAM reader without automatic view creation
            reader = sm.sources.OpenFOAMReader(FileName=file_path)
            
            # Update the pipeline to get data
            reader.UpdateVTKObjects()
            reader.UpdatePipeline()
            
            # Get the VTK data object from ParaView server
            vtk_data = reader.GetClientSideObject().GetOutput()
            
            # Store for later use
            self.current_source = reader
            
            # Check if we got valid VTK data
            if vtk_data is None:
                logger.error("No VTK data received from ParaView server")
                self.show_error("No data received from ParaView server")
                return
            
            # Create VTK visualization even without Qt widget integration
            if hasattr(self, 'vtk_widget') and self.vtk_widget and hasattr(self, 'renderer'):
                # We have a Qt widget - use it
                self.renderer.RemoveAllViewProps()
                
                # Create VTK pipeline for local rendering
                mapper = vtk_local.vtkPolyDataMapper()
                mapper.SetInputData(vtk_data)
                
                actor = vtk_local.vtkActor()
                actor.SetMapper(mapper)
                
                # Set some basic properties
                actor.GetProperty().SetOpacity(0.8)
                actor.GetProperty().SetColor(0.8, 0.8, 0.9)  # Light blue
                
                self.renderer.AddActor(actor)
                self.renderer.ResetCamera()
                self.vtk_widget.GetRenderWindow().Render()
                
                logger.info("Successfully loaded ParaView data into embedded VTK widget")
                
            else:
                # No Qt widget available - create standalone VTK visualization window
                logger.info("Creating standalone VTK window for visualization")
                
                # Create render window
                render_window = vtk_local.vtkRenderWindow()
                render_window.SetSize(800, 600)
                render_window.SetWindowName("OpenFOAM Visualization")
                
                # Create renderer
                renderer = vtk_local.vtkRenderer()
                renderer.SetBackground(0.1, 0.1, 0.2)  # Dark blue background
                render_window.AddRenderer(renderer)
                
                # Create VTK pipeline
                mapper = vtk_local.vtkPolyDataMapper()
                mapper.SetInputData(vtk_data)
                
                actor = vtk_local.vtkActor()
                actor.SetMapper(mapper)
                actor.GetProperty().SetOpacity(0.8)
                actor.GetProperty().SetColor(0.8, 0.8, 0.9)  # Light blue
                
                renderer.AddActor(actor)
                renderer.ResetCamera()
                
                # Create interactor
                interactor = vtk_local.vtkRenderWindowInteractor()
                interactor.SetRenderWindow(render_window)
                
                # Start the visualization
                render_window.Render()
                interactor.Start()
                
                logger.info("Created standalone VTK visualization window")
                
                # Update the visualization area to show a message
                if hasattr(self, 'visualization_area'):
                    self.visualization_area.setText(
                        "Visualization opened in standalone VTK window.\n\n"
                        "Data loaded successfully using VTK " + vtk_local.vtkVersion.GetVTKVersion() + "\n\n"
                        "To embed visualization in this window:\n"
                        "Install VTK with Qt support:\n"
                        "pip install vtk[qt] or pip install PyQt5"
                    )
                
        except Exception as e:
            logger.error(f"Failed to load with ParaView servermanager: {str(e)}")
            # Try the original simple approach as absolute last resort
            logger.info("Attempting fallback to direct VTK loading")
            try:
                self._load_with_vtk(file_path)
            except Exception as e2:
                logger.error(f"VTK fallback also failed: {str(e2)}")
                self.show_error(f"Failed to load visualization: {str(e)}")
    
    def _load_with_vtk_embedded(self, file_path: str):
        """Load file using VTK with embedded Qt widget"""
        # Use the global VTK instance
        if not VTK_AVAILABLE or vtk is None:
            logger.error("VTK not available for embedded rendering")
            self.show_error("VTK not available")
            return
        
        vtk_local = vtk
        
        # Clear previous visualization
        if hasattr(self, 'renderer') and self.renderer:
            self.renderer.RemoveAllViewProps()
        
        try:
            # Create VTK OpenFOAM reader
            reader = vtk_local.vtkOpenFOAMReader()
            reader.SetFileName(file_path)
            reader.CreateCellToPointOn()
            reader.ReadZonesOn()
            reader.Update()
            
            self.current_source = reader
            # Store the file path for time step navigation
            self._foam_file_path = file_path
            
            # Create mapper and actor for the mesh
            mapper = vtk_local.vtkPolyDataMapper()
            mapper.SetInputConnection(reader.GetOutputPort())
            
            actor = vtk_local.vtkActor()
            actor.SetMapper(mapper)
            
            # Set some basic properties
            actor.GetProperty().SetOpacity(0.8)
            actor.GetProperty().SetColor(0.8, 0.8, 0.9)  # Light blue
            
            # Add to embedded renderer
            self.renderer.AddActor(actor)
            self.renderer.ResetCamera()
            
            # Try to render - this is where OpenGL errors occur
            try:
                self.vtk_widget.GetRenderWindow().Render()
                logger.info("✅ Successfully loaded VTK data into embedded Qt widget")
                print("✅ Embedded visualization working!")
                
                # Setup time steps after successful loading
                self.setup_time_steps()
                
            except Exception as render_error:
                logger.error(f"OpenGL rendering failed in embedded widget: {render_error}")
                print(f"❌ OpenGL rendering failed: {render_error}")
                print("🔄 Falling back to standalone VTK window...")
                
                # Fall back to standalone VTK window
                self._create_standalone_vtk_window(reader)
                
        except Exception as e:
            logger.error(f"Failed to load VTK data: {e}")
            print(f"❌ Failed to load VTK data: {e}")
            self.show_error(f"Failed to load visualization: {e}")
    
    def _create_standalone_vtk_window(self, reader):
        """Create standalone VTK window when embedded rendering fails"""
        if not VTK_AVAILABLE or vtk is None:
            logger.error("VTK not available for standalone window")
            self.show_error("VTK not available")
            return
        
        vtk_local = vtk
        
        try:
            
            # Create standalone render window
            render_window = vtk_local.vtkRenderWindow()
            render_window.SetSize(800, 600)
            render_window.SetWindowName("OpenFOAM Visualization (Standalone)")
            
            # Create renderer
            renderer = vtk_local.vtkRenderer()
            renderer.SetBackground(0.1, 0.1, 0.2)  # Dark blue background
            render_window.AddRenderer(renderer)
            
            # Create mapper and actor
            mapper = vtk_local.vtkPolyDataMapper()
            mapper.SetInputConnection(reader.GetOutputPort())
            
            actor = vtk_local.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetOpacity(0.8)
            actor.GetProperty().SetColor(0.8, 0.8, 0.9)  # Light blue
            
            # Add to renderer
            renderer.AddActor(actor)
            renderer.ResetCamera()
            
            # Create interactor
            interactor = vtk_local.vtkRenderWindowInteractor()
            interactor.SetRenderWindow(render_window)
            
            # Show the window
            render_window.Render()
            interactor.Start()
            
            logger.info("Created standalone VTK window as fallback")
            print("✅ Standalone VTK window created successfully")
            
            # Update UI to show message
            if hasattr(self, 'visualization_area'):
                self.visualization_area.setText(
                    "Visualization opened in standalone window due to OpenGL issues.\n\n"
                    "Your graphics drivers may need updating for embedded visualization.\n\n"
                    "Data loaded successfully!"
                )
            
        except Exception as e:
            logger.error(f"Standalone VTK window creation also failed: {e}")
            self.show_error(f"All visualization methods failed: {e}")
    
    def _load_with_paraview_embedded(self, file_path: str):
        """Load file using ParaView server but render in embedded Qt widget"""
        # Validate VTK availability
        if not self.validate_vtk():
            logger.error("VTK validation failed - cannot render ParaView data locally")
            self.show_error("VTK is not available for visualization")
            return
        
        # Use the global VTK instance
        if not VTK_AVAILABLE or vtk is None:
            logger.error("VTK not available for embedded rendering")
            self.show_error("VTK not available")
            return
        
        vtk_local = vtk
        
        # Clear previous visualization
        if hasattr(self, 'renderer') and self.renderer:
            self.renderer.RemoveAllViewProps()
        
        # Use ParaView API properly to get data
        try:
            # Import ParaView modules
            import paraview.servermanager as sm
            from paraview.simple import OpenFOAMReader, servermanager
            
            # Create OpenFOAM reader using paraview.simple
            reader = OpenFOAMReader(FileName=file_path)
            
            # Configure reader for time-dependent data
            try:
                # Enable time-dependent reading options
                if hasattr(reader, 'CreateCellToPointOn'):
                    reader.CreateCellToPointOn()
                if hasattr(reader, 'ReadZonesOn'):
                    reader.ReadZonesOn()
                if hasattr(reader, 'CacheMeshOn'):
                    reader.CacheMeshOn()
                if hasattr(reader, 'DecomposePolyhedraOn'):
                    reader.DecomposePolyhedraOn()
                if hasattr(reader, 'ReadFieldsOn'):
                    reader.ReadFieldsOn()
                
                # Critical: Enable time step information
                if hasattr(reader, 'RefreshTimes'):
                    reader.RefreshTimes()
                
                # Force refresh of time step information
                reader.UpdateVTKObjects()
                    
                print("🔧 Configured OpenFOAM reader for time-dependent data")
                
                # Check if time steps are detected
                if hasattr(reader, 'TimestepValues'):
                    time_values = reader.TimestepValues
                    if time_values:
                        print(f"📊 ParaView reader detected {len(time_values)} time steps: {time_values}")
                    else:
                        print("⚠️ No time step values detected by ParaView reader")
                else:
                    print("⚠️ Reader does not have TimestepValues attribute")
                    
            except Exception as config_error:
                print(f"⚠️ Failed to configure reader: {config_error}")
            
            # Update the pipeline to get data
            reader.UpdateVTKObjects()
            reader.UpdatePipeline()
            
            # Store for later use
            self.current_source = reader
            # Store the file path for time step navigation in the widget
            self._foam_file_path = file_path
            
            # Get the VTK data object from ParaView server - use the proper API
            try:
                # Method 1: Try to get VTK data via client-side object
                client_side_object = reader.GetClientSideObject()
                if client_side_object:
                    vtk_data = client_side_object.GetOutput()
                    print(f"📊 Got VTK data via client-side object: {vtk_data}")
                else:
                    print("⚠️ No client-side object available")
                    vtk_data = None
                    
            except Exception as e1:
                print(f"⚠️ Client-side method failed: {e1}")
                vtk_data = None
            
            # Method 2: If client-side failed, try to fetch data differently
            if vtk_data is None:
                try:
                    # Use servermanager to fetch data
                    reader.UpdatePipeline()
                    output_port = reader.GetOutputPort(0)
                    
                    # Create a temporary mapper to get the data
                    vtk_data = reader.GetOutputData(0)
                    print(f"📊 Got VTK data via output port: {vtk_data}")
                    
                except Exception as e2:
                    print(f"⚠️ Output port method failed: {e2}")
                    vtk_data = None
            
            # Method 3: If still no data, try another approach
            if vtk_data is None:
                try:
                    # Force update and try again
                    reader.UpdatePipeline()
                    
                    # Try to get the algorithm output directly
                    algorithm = reader.GetAlgorithm()
                    if algorithm:
                        vtk_data = algorithm.GetOutputData(0)
                        print(f"📊 Got VTK data via algorithm: {vtk_data}")
                    else:
                        print("⚠️ No algorithm available")
                        
                except Exception as e3:
                    print(f"⚠️ Algorithm method failed: {e3}")
                    vtk_data = None
            
            # Check if we got valid VTK data
            if vtk_data is None:
                logger.error("No VTK data received from ParaView server")
                print("❌ All methods to get VTK data failed")
                
                # Try to create a simple test geometry instead
                print("🔄 Creating test geometry as fallback...")
                
                # Create a simple test sphere
                sphere = vtk_local.vtkSphereSource()
                sphere.SetRadius(1.0)
                sphere.SetThetaResolution(20)
                sphere.SetPhiResolution(20)
                sphere.Update()
                
                vtk_data = sphere.GetOutput()
                print(f"✅ Using test sphere geometry: {vtk_data}")
                
                # Update the message
                self.show_error("ParaView data extraction failed - showing test geometry")
            
            # Create VTK pipeline for embedded rendering
            # Handle multi-block datasets from ParaView
            if vtk_data.GetClassName() == 'vtkMultiBlockDataSet':
                print(f"🔄 Processing multi-block dataset with {vtk_data.GetNumberOfBlocks()} blocks")
                
                # Extract the first block (usually the internal mesh)
                if vtk_data.GetNumberOfBlocks() > 0:
                    block = vtk_data.GetBlock(0)
                    if block:
                        print(f"📊 Using block 0: {block.GetClassName()} with {block.GetNumberOfPoints()} points")
                        
                        # Convert unstructured grid to polydata if needed
                        if block.GetClassName() == 'vtkUnstructuredGrid':
                            geom_filter = vtk_local.vtkGeometryFilter()
                            geom_filter.SetInputData(block)
                            geom_filter.Update()
                            vtk_data = geom_filter.GetOutput()
                            print(f"✅ Converted to polydata: {vtk_data.GetNumberOfPoints()} points")
                        else:
                            vtk_data = block
                    else:
                        print("⚠️ Block 0 is None")
                        vtk_data = None
                else:
                    print("⚠️ No blocks in multi-block dataset")
                    vtk_data = None
            
            # Final check for valid data
            if vtk_data is None:
                print("❌ No valid VTK data available")
                return
            
            # Use the unified visualization method with blue-gray-red colors
            self._display_vtk_data(vtk_data)
            
            logger.info("Successfully loaded ParaView data into embedded Qt widget")
            print("✅ ParaView data successfully rendered in embedded widget")
            
        except Exception as e:
            logger.error(f"Failed to load with ParaView servermanager: {str(e)}")
            print(f"❌ ParaView embedded loading failed: {e}")
            # Try fallback to embedded VTK
            logger.info("Attempting fallback to embedded VTK loading")
            try:
                self._load_with_vtk_embedded(file_path)
            except Exception as e2:
                logger.error(f"Embedded VTK fallback also failed: {str(e2)}")
                self.show_error(f"Failed to load visualization: {str(e)}")
    
    def _load_with_paraview_fallback(self, file_path: str):
        """Load file using ParaView server with native rendering (separate window fallback)"""
        logger.warning("Using ParaView fallback mode - visualization will open in separate window")
        logger.warning("To fix this, install VTK: pip install vtk")
        
        try:
            # Use the original paraview.simple approach as fallback
            from paraview.simple import OpenFOAMReader, Show, ResetCamera, Render
            
            # Create OpenFOAM reader
            self.current_source = OpenFOAMReader(FileName=file_path)
            
            # Show the data (this will create a separate window)
            if hasattr(self, 'current_view') and self.current_view:
                display = Show(self.current_source, self.current_view)
                ResetCamera(self.current_view)
                Render(self.current_view)
            else:
                # Create a view if none exists
                from paraview.simple import CreateRenderView
                self.current_view = CreateRenderView()
                display = Show(self.current_source, self.current_view)
                ResetCamera(self.current_view)
                Render(self.current_view)
                
            logger.info("Loaded with ParaView fallback mode - separate window created")
            
            # Update the visualization area to show a message
            if hasattr(self, 'visualization_area'):
                self.visualization_area.setText(
                    "Visualization opened in separate ParaView window.\n\n"
                    "To embed visualization in this window:\n"
                    "1. Install VTK: pip install vtk\n"
                    "2. Restart the application\n\n"
                    "Or run: python diagnose_vtk.py"
                )
            
        except Exception as e:
            logger.error(f"ParaView fallback also failed: {str(e)}")
            self.show_error(f"All visualization methods failed: {str(e)}")
    
    def show_field(self, field_name: str):
        """Show a specific field in the visualization"""
        if not self.current_source or not hasattr(self, 'renderer'):
            print("⚠️ No data source or renderer available")
            return
        
        try:
            print(f"🎨 Showing field: {field_name}")
            
            # Get field info
            field_info = None
            for field in self.available_fields:
                if field['name'] == field_name:
                    field_info = field
                    break
            
            if not field_info:
                print(f"⚠️ Field '{field_name}' not found in available fields")
                return
            
            # Track the current field for time step navigation
            self.current_field = field_name
            print(f"🎯 Current field set to: {field_name}")
            
            # Clear current visualization
            if hasattr(self, 'renderer') and self.renderer:
                self.renderer.RemoveAllViewProps()
            
            # Save current camera position
            if hasattr(self, 'renderer') and self.renderer:
                try:
                    camera = self.renderer.GetActiveCamera()
                    self._saved_camera_position = camera.GetPosition()
                    self._saved_camera_focal_point = camera.GetFocalPoint()
                    self._saved_camera_view_up = camera.GetViewUp()
                except Exception as cam_error:
                    print(f"⚠️ Could not save camera position: {cam_error}")
                    self._saved_camera_position = None
            
            # Get VTK data
            vtk_data = None
            if hasattr(self.current_source, 'GetClientSideObject'):
                # ParaView server source
                self.current_source.UpdatePipeline()
                vtk_data = self.current_source.GetClientSideObject().GetOutput()
            elif hasattr(self.current_source, 'GetOutput'):
                # Direct VTK source
                self.current_source.Update()
                vtk_data = self.current_source.GetOutput()
            
            if not vtk_data:
                print("⚠️ No VTK data available for field visualization")
                return
            
            # Display with specific field
            self._display_vtk_data_with_field(vtk_data, field_info)
            
            print(f"✅ Successfully displayed field: {field_info['display_name']}")
            
        except Exception as e:
            print(f"❌ Error showing field {field_name}: {e}")
            import traceback
            traceback.print_exc()
    
    def _display_vtk_data_with_field(self, vtk_data, field_info):
        """Display VTK data with specific field coloring"""
        try:
            from paraview_widget import VTK_AVAILABLE, vtk
            if not VTK_AVAILABLE or vtk is None:
                print("❌ VTK not available for field visualization")
                return
            
            vtk_local = vtk
            
            # Handle multi-block datasets
            if vtk_data.GetClassName() == 'vtkMultiBlockDataSet':
                if vtk_data.GetNumberOfBlocks() > 0:
                    block = vtk_data.GetBlock(0)
                    if block:
                        if block.GetClassName() == 'vtkUnstructuredGrid':
                            geom_filter = vtk_local.vtkGeometryFilter()
                            geom_filter.SetInputData(block)
                            geom_filter.Update()
                            vtk_data = geom_filter.GetOutput()
                        else:
                            vtk_data = block
                    else:
                        print("⚠️ Block 0 is None")
                        return
                else:
                    print("⚠️ No blocks in multi-block dataset")
                    return
            
            # Create mapper
            mapper = vtk_local.vtkPolyDataMapper()
            mapper.SetInputData(vtk_data)
            
            # Get the field array
            field_array = None
            if field_info['type'] == 'cell':
                cell_data = vtk_data.GetCellData()
                field_array = cell_data.GetArray(field_info['name'])
                if field_array:
                    mapper.SetScalarModeToUseCellFieldData()
                    mapper.SelectColorArray(field_info['name'])
                    mapper.SetColorModeToMapScalars()
                    print(f"🎨 Using cell field: {field_info['name']}")
            elif field_info['type'] == 'point':
                point_data = vtk_data.GetPointData()
                field_array = point_data.GetArray(field_info['name'])
                if field_array:
                    mapper.SetScalarModeToUsePointFieldData()
                    mapper.SelectColorArray(field_info['name'])
                    mapper.SetColorModeToMapScalars()
                    print(f"🎨 Using point field: {field_info['name']}")
            
            if not field_array:
                print(f"⚠️ Field array '{field_info['name']}' not found")
                return
            
            # Get data range
            data_range = field_array.GetRange()
            print(f"📊 Field '{field_info['name']}' range: {data_range}")
            
            # Create custom lookup table based on field type
            lut = self._create_field_lookup_table(field_info, data_range)
            
            # Apply lookup table to mapper
            mapper.SetLookupTable(lut)
            mapper.SetScalarRange(data_range)
            
            # Create actor
            actor = vtk_local.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetOpacity(0.8)
            
            # Create color bar
            scalar_bar = vtk_local.vtkScalarBarActor()
            scalar_bar.SetLookupTable(lut)
            scalar_bar.SetTitle(field_info['display_name'])
            scalar_bar.SetWidth(0.12)
            scalar_bar.SetHeight(0.8)
            scalar_bar.SetPosition(0.85, 0.1)
            scalar_bar.SetNumberOfLabels(7)
            
            # Style the color bar
            scalar_bar.GetTitleTextProperty().SetFontSize(12)
            scalar_bar.GetLabelTextProperty().SetFontSize(10)
            scalar_bar.GetTitleTextProperty().SetColor(1.0, 1.0, 1.0)
            scalar_bar.GetLabelTextProperty().SetColor(1.0, 1.0, 1.0)
            
            # Add to renderer
            self.renderer.AddActor(actor)
            self.renderer.AddActor2D(scalar_bar)
            
            # Restore camera position
            if hasattr(self, '_saved_camera_position') and self._saved_camera_position:
                try:
                    camera = self.renderer.GetActiveCamera()
                    camera.SetPosition(self._saved_camera_position)
                    camera.SetFocalPoint(self._saved_camera_focal_point)
                    camera.SetViewUp(self._saved_camera_view_up)
                    print("📷 Restored camera position")
                except Exception as cam_error:
                    print(f"⚠️ Could not restore camera position: {cam_error}")
                    self.renderer.ResetCamera()
            else:
                self.renderer.ResetCamera()
            
            # Render
            if hasattr(self, 'vtk_widget') and self.vtk_widget:
                self.vtk_widget.GetRenderWindow().Render()
            
            print(f"✅ Field visualization complete for: {field_info['display_name']}")
            
        except Exception as e:
            print(f"❌ Failed to display field data: {e}")
            import traceback
            traceback.print_exc()
    
    def _create_field_lookup_table(self, field_info, data_range):
        """Create appropriate lookup table based on field type"""
        from paraview_widget import vtk
        
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(256)
        lut.SetRange(data_range)
        
        field_name = field_info['name']
        
        print(f"🎨 Creating color scheme for field: {field_name}")
        
        # Different color schemes for different field types
        if field_name == 'p':
            # Pressure: Blue (low) -> White (zero) -> Red (high)
            self._create_pressure_colormap(lut, data_range)
        elif field_name == 'U':
            # Velocity: Blue (low) -> Green -> Yellow -> Red (high)
            self._create_velocity_colormap(lut)
        elif field_name == 'k':
            # Kinetic Energy: Purple (low) -> Blue -> Green -> Yellow -> Red (high)
            self._create_kinetic_energy_colormap(lut)
        elif field_name in ['epsilon', 'omega']:
            # Dissipation rates: Cool colors (blue to cyan)
            self._create_dissipation_colormap(lut)
        elif field_name in ['nut', 'nuTilda']:
            # Viscosity: Green spectrum
            self._create_viscosity_colormap(lut)
        else:
            # Default: Rainbow color scheme
            self._create_rainbow_colormap(lut)
        
        lut.Build()
        return lut
    
    def _create_pressure_colormap(self, lut, data_range):
        """Create pressure-specific colormap (blue-white-red)"""
        min_val, max_val = data_range
        
        for i in range(256):
            pos = i / 255.0
            
            # Find normalized position relative to zero
            if min_val < 0 and max_val > 0:
                zero_pos = -min_val / (max_val - min_val)
                if pos < zero_pos:
                    # Below zero: blue to white
                    factor = pos / zero_pos
                    r = factor
                    g = factor
                    b = 1.0
                else:
                    # Above zero: white to red
                    factor = (pos - zero_pos) / (1.0 - zero_pos)
                    r = 1.0
                    g = 1.0 - factor
                    b = 1.0 - factor
            else:
                # All positive or all negative
                r = pos
                g = 0.5 * (1.0 - pos)
                b = 1.0 - pos
            
            lut.SetTableValue(i, r, g, b, 1.0)
    
    def _create_velocity_colormap(self, lut):
        """Create velocity-specific colormap (blue-green-yellow-red)"""
        for i in range(256):
            pos = i / 255.0
            
            if pos <= 0.33:
                # Blue to green
                factor = pos / 0.33
                r = 0.0
                g = factor
                b = 1.0 - factor
            elif pos <= 0.66:
                # Green to yellow
                factor = (pos - 0.33) / 0.33
                r = factor
                g = 1.0
                b = 0.0
            else:
                # Yellow to red
                factor = (pos - 0.66) / 0.34
                r = 1.0
                g = 1.0 - factor
                b = 0.0
            
            lut.SetTableValue(i, r, g, b, 1.0)
    
    def _create_kinetic_energy_colormap(self, lut):
        """Create kinetic energy colormap (purple-blue-green-yellow-red)"""
        for i in range(256):
            pos = i / 255.0
            
            if pos <= 0.25:
                # Purple to blue
                factor = pos / 0.25
                r = 0.5 - 0.5 * factor
                g = 0.0
                b = 0.5 + 0.5 * factor
            elif pos <= 0.5:
                # Blue to green
                factor = (pos - 0.25) / 0.25
                r = 0.0
                g = factor
                b = 1.0 - factor
            elif pos <= 0.75:
                # Green to yellow
                factor = (pos - 0.5) / 0.25
                r = factor
                g = 1.0
                b = 0.0
            else:
                # Yellow to red
                factor = (pos - 0.75) / 0.25
                r = 1.0
                g = 1.0 - factor
                b = 0.0
            
            lut.SetTableValue(i, r, g, b, 1.0)
    
    def _create_dissipation_colormap(self, lut):
        """Create dissipation colormap (cool colors)"""
        for i in range(256):
            pos = i / 255.0
            
            # Cool colors: dark blue to cyan
            r = 0.0
            g = pos
            b = 1.0
            
            lut.SetTableValue(i, r, g, b, 1.0)
    
    def _create_viscosity_colormap(self, lut):
        """Create viscosity colormap (green spectrum)"""
        for i in range(256):
            pos = i / 255.0
            
            # Green spectrum: dark green to bright green
            r = pos * 0.5
            g = 0.5 + pos * 0.5
            b = pos * 0.3
            
            lut.SetTableValue(i, r, g, b, 1.0)
    
    def _create_rainbow_colormap(self, lut):
        """Create rainbow colormap (default)"""
        for i in range(256):
            pos = i / 255.0
            
            # HSV to RGB conversion for rainbow
            h = pos * 300.0  # Hue from 0 to 300 degrees
            s = 1.0          # Full saturation
            v = 1.0          # Full value
            
            # Convert HSV to RGB
            c = v * s
            x = c * (1 - abs(((h / 60.0) % 2) - 1))
            m = v - c
            
            if h < 60:
                r, g, b = c, x, 0
            elif h < 120:
                r, g, b = x, c, 0
            elif h < 180:
                r, g, b = 0, c, x
            elif h < 240:
                r, g, b = 0, x, c
            elif h < 300:
                r, g, b = x, 0, c
            else:
                r, g, b = c, 0, x
            
            lut.SetTableValue(i, r + m, g + m, b + m, 1.0)
    
    def setup_time_steps(self):
        """Setup time step controls by scanning available time directories"""
        if not self.current_source:
            return
        
        try:
            # Get the base directory path from the OpenFOAM file
            foam_file_path = None
            
            # Try different ways to get the file path
            if hasattr(self.current_source, 'FileName'):
                # VTK sources have FileName attribute
                foam_file_path = self.current_source.FileName
            elif hasattr(self.current_source, 'GetFileName'):
                # Some VTK sources have GetFileName method
                try:
                    foam_file_path = self.current_source.GetFileName()
                except:
                    pass
            
            # Fallback to widget-stored path
            if not foam_file_path:
                foam_file_path = getattr(self, '_foam_file_path', None)
            
            if not foam_file_path:
                logger.info("No file path available for time step detection")
                print("⚠️ No file path found for time step detection")
                return
                
            # Get the directory containing the .foam file
            from pathlib import Path
            base_dir = Path(foam_file_path).parent
            
            # Scan for time directories (numeric folder names)
            time_dirs = []
            for item in base_dir.iterdir():
                if item.is_dir():
                    try:
                        # Try to convert directory name to float (time value)
                        time_value = float(item.name)
                        time_dirs.append((time_value, item))
                    except ValueError:
                        # Skip non-numeric directories (like 'constant', 'system', etc.)
                        continue
            
            # Sort by time value
            time_dirs.sort(key=lambda x: x[0])
            
            if time_dirs:
                self.time_steps = [time_val for time_val, _ in time_dirs]
                self.time_directories = [str(path) for _, path in time_dirs]
                
                # Store the original file path for reloading
                self._foam_file_path = foam_file_path
                
                # CRITICAL FIX: Filter time steps to match what the reader actually has
                if hasattr(self.current_source, 'TimestepValues'):
                    reader_time_values = list(self.current_source.TimestepValues)
                    print(f"🔍 DEBUG: Reader has time values: {reader_time_values}")
                    print(f"🔍 DEBUG: UI detected time steps: {self.time_steps}")
                    
                    # Only keep time steps that the reader actually has
                    filtered_time_steps = [t for t in self.time_steps if t in reader_time_values]
                    if filtered_time_steps != self.time_steps:
                        print(f"⚠️ Time step mismatch detected - filtering to match reader")
                        print(f"🔧 Filtered time steps: {filtered_time_steps}")
                        self.time_steps = filtered_time_steps
                
                # Enable time controls
                self.time_slider.setRange(0, len(self.time_steps) - 1)
                self.time_slider.setValue(0)
                self.time_slider.setEnabled(True)
                self.prev_time_btn.setEnabled(True)
                self.next_time_btn.setEnabled(True)
                self.update_time_label()
                
                logger.info(f"Found {len(self.time_steps)} time steps: {self.time_steps}")
                print(f"🕐 Time steps available: {self.time_steps}")
            else:
                logger.info("No time directories found")
                print("⚠️ No time directories found in the data")
                        
        except Exception as e:
            logger.error(f"Failed to setup time steps: {str(e)}")
            print(f"⚠️ Time step setup failed: {e}")
    
    def set_time_step(self, step: int):
        """Set the current time step using proper ParaView client-server time navigation"""
        if not self.time_steps or step >= len(self.time_steps) or not self.current_source:
            return
        
        # Prevent rapid successive calls to the same time step
        if hasattr(self, '_current_time_step') and self._current_time_step == step:
            print(f"⚠️ Already at time step {step}, skipping update")
            return
        
        # Simple debouncing
        import time
        current_time = time.time()
        if hasattr(self, '_last_time_change') and (current_time - self._last_time_change) < 0.2:
            print(f"⚠️ Time step change too frequent, ignoring")
            return
        
        self._last_time_change = current_time
        
        try:
            self._current_time_step = step
            time_value = self.time_steps[step]
            
            print(f"🕐 Setting time step {step}: t = {time_value}")
            
            # Save current camera position to prevent view reset
            if hasattr(self, 'renderer') and self.renderer:
                try:
                    camera = self.renderer.GetActiveCamera()
                    self._saved_camera_position = camera.GetPosition()
                    self._saved_camera_focal_point = camera.GetFocalPoint()
                    self._saved_camera_view_up = camera.GetViewUp()
                    print("📷 Saved camera position")
                except Exception as cam_error:
                    print(f"⚠️ Could not save camera position: {cam_error}")
                    self._saved_camera_position = None
            
            # CLEAN APPROACH: Use ParaView's proper client-server time navigation
            print("🔄 Using proper ParaView client-server time navigation...")
            
            # Method 1: Set time using animation scene and force server update
            try:
                from paraview.simple import GetAnimationScene, GetTimeKeeper, UpdatePipeline
                
                # Set the animation time
                scene = GetAnimationScene()
                scene.AnimationTime = time_value
                print(f"🕐 Set animation scene time to: {time_value}")
                
                # Set the time keeper
                time_keeper = GetTimeKeeper()
                time_keeper.Time = time_value
                print(f"🕐 Set time keeper to: {time_value}")
                
                # CRITICAL: Force server to update pipeline for this specific time
                try:
                    # Try ParaView's UpdatePipeline with explicit time
                    UpdatePipeline(time=time_value, proxy=self.current_source)
                    print(f"✅ Updated pipeline with explicit time: {time_value}")
                except Exception as update_error:
                    print(f"⚠️ UpdatePipeline with time failed: {update_error}")
                    # Fallback to standard pipeline update
                    self.current_source.UpdatePipeline()
                    print("🔄 Used standard pipeline update")
                
                # Get the updated data from server
                vtk_data = self.current_source.GetClientSideObject().GetOutput()
                
                if vtk_data and vtk_data.GetNumberOfPoints() > 0:
                    print(f"📊 Received data with {vtk_data.GetNumberOfPoints()} points")
                    
                    # Verify we got the correct time step data
                    try:
                        if vtk_data.GetClassName() == 'vtkMultiBlockDataSet' and vtk_data.GetNumberOfBlocks() > 0:
                            block = vtk_data.GetBlock(0)
                            if block and hasattr(block, 'GetCellData'):
                                cell_data = block.GetCellData()
                                if cell_data.GetArray('p'):
                                    pressure_array = cell_data.GetArray('p')
                                    data_range = pressure_array.GetRange()
                                    if pressure_array.GetNumberOfTuples() > 10:
                                        sample_values = [pressure_array.GetValue(i) for i in [0, 100, 1000, 5000]]
                                        print(f"🔍 Pressure range for t={time_value}: {data_range}")
                                        print(f"🔍 Sample pressure values: {sample_values}")
                    except Exception as verify_error:
                        print(f"⚠️ Could not verify data: {verify_error}")
                    
                    # Clear current visualization
                    if hasattr(self, 'renderer') and self.renderer:
                        self.renderer.RemoveAllViewProps()
                    
                    # Display the updated data with current field selection
                    if hasattr(self, 'current_field') and self.current_field:
                        # Find the field info for the current field
                        field_info = None
                        for field in self.available_fields:
                            if field['name'] == self.current_field:
                                field_info = field
                                break
                        
                        if field_info:
                            print(f"🎯 Preserving current field: {self.current_field}")
                            self._display_vtk_data_with_field(vtk_data, field_info)
                        else:
                            print(f"⚠️ Current field {self.current_field} not found, using default display")
                            self._display_vtk_data(vtk_data)
                    else:
                        print("🔄 No current field set, using default display")
                        self._display_vtk_data(vtk_data)
                    
                    # Restore camera position
                    if hasattr(self, '_saved_camera_position') and self._saved_camera_position:
                        try:
                            camera = self.renderer.GetActiveCamera()
                            camera.SetPosition(self._saved_camera_position)
                            camera.SetFocalPoint(self._saved_camera_focal_point)
                            camera.SetViewUp(self._saved_camera_view_up)
                            print("📷 Restored camera position")
                        except Exception as restore_error:
                            print(f"⚠️ Could not restore camera position: {restore_error}")
                            self.renderer.ResetCamera()
                    else:
                        self.renderer.ResetCamera()
                    
                    # Render the updated visualization
                    if hasattr(self, 'vtk_widget') and self.vtk_widget:
                        self.vtk_widget.GetRenderWindow().Render()
                    
                    print(f"✅ Successfully updated visualization for t={time_value}")
                    self.update_time_label()
                    return
                    
                else:
                    print("⚠️ No data received from server")
                    
            except Exception as e1:
                print(f"⚠️ Client-server time navigation failed: {e1}")
                import traceback
                traceback.print_exc()
                
                # Method 2: Alternative approach - Direct time step setting
                try:
                    print("🔄 Fallback: Direct time step approach...")
                    
                    # Try to find the time step index
                    if hasattr(self.current_source, 'TimestepValues'):
                        time_values = list(self.current_source.TimestepValues)
                        if time_value in time_values:
                            time_index = time_values.index(time_value)
                            print(f"🎯 Setting reader to time index {time_index} for time {time_value}")
                            
                            # Set time step directly on the source
                            if hasattr(self.current_source, 'UpdateTimeStep'):
                                self.current_source.UpdateTimeStep(time_value)
                                print(f"🕐 Called UpdateTimeStep({time_value})")
                            elif hasattr(self.current_source, 'SetTimeStep'):
                                self.current_source.SetTimeStep(time_index)
                                print(f"🕐 Called SetTimeStep({time_index})")
                            
                            # Force pipeline update
                            self.current_source.UpdateVTKObjects()
                            self.current_source.UpdatePipeline()
                            
                            # Get the data
                            vtk_data = self.current_source.GetClientSideObject().GetOutput()
                            
                            if vtk_data and vtk_data.GetNumberOfPoints() > 0:
                                print(f"📊 Fallback received data with {vtk_data.GetNumberOfPoints()} points")
                                
                                # Clear and display
                                if hasattr(self, 'renderer') and self.renderer:
                                    self.renderer.RemoveAllViewProps()
                                
                                # Display the updated data with current field selection
                                if hasattr(self, 'current_field') and self.current_field:
                                    # Find the field info for the current field
                                    field_info = None
                                    for field in self.available_fields:
                                        if field['name'] == self.current_field:
                                            field_info = field
                                            break
                                    
                                    if field_info:
                                        print(f"🎯 Fallback preserving current field: {self.current_field}")
                                        self._display_vtk_data_with_field(vtk_data, field_info)
                                    else:
                                        print(f"⚠️ Current field {self.current_field} not found, using default display")
                                        self._display_vtk_data(vtk_data)
                                else:
                                    print("🔄 No current field set, using default display")
                                    self._display_vtk_data(vtk_data)
                                
                                # Restore camera
                                if hasattr(self, '_saved_camera_position') and self._saved_camera_position:
                                    try:
                                        camera = self.renderer.GetActiveCamera()
                                        camera.SetPosition(self._saved_camera_position)
                                        camera.SetFocalPoint(self._saved_camera_focal_point)
                                        camera.SetViewUp(self._saved_camera_view_up)
                                        print("📷 Restored camera position")
                                    except:
                                        self.renderer.ResetCamera()
                                else:
                                    self.renderer.ResetCamera()
                                
                                if hasattr(self, 'vtk_widget') and self.vtk_widget:
                                    self.vtk_widget.GetRenderWindow().Render()
                                
                                print(f"✅ Fallback successfully updated visualization for t={time_value}")
                                self.update_time_label()
                                return
                        else:
                            print(f"⚠️ Time {time_value} not found in reader time values: {time_values}")
                    else:
                        print("⚠️ Reader has no TimestepValues property")
                        
                except Exception as e2:
                    print(f"⚠️ Fallback approach also failed: {e2}")
                    import traceback
                    traceback.print_exc()
            
            # Update time label regardless of success/failure
            self.update_time_label()
            
        except Exception as e:
            logger.error(f"Failed to set time step: {str(e)}")
            print(f"❌ Time step change failed: {e}")
            import traceback
            traceback.print_exc()
            self.update_time_label()
    
    def _display_vtk_data(self, vtk_data):
        """Display VTK data with blue-gray-red color scheme"""
        try:
            from paraview_widget import VTK_AVAILABLE, vtk
            if not VTK_AVAILABLE or vtk is None:
                print("❌ VTK not available for visualization")
                return
                
            vtk_local = vtk
            
            # Handle multi-block datasets from ParaView
            if vtk_data.GetClassName() == 'vtkMultiBlockDataSet':
                print(f"🔄 Processing multi-block dataset with {vtk_data.GetNumberOfBlocks()} blocks")
                
                if vtk_data.GetNumberOfBlocks() > 0:
                    block = vtk_data.GetBlock(0)
                    if block:
                        print(f"📊 Using block 0: {block.GetClassName()} with {block.GetNumberOfPoints()} points")
                        
                        # Convert unstructured grid to polydata if needed
                        if block.GetClassName() == 'vtkUnstructuredGrid':
                            geom_filter = vtk_local.vtkGeometryFilter()
                            geom_filter.SetInputData(block)
                            geom_filter.Update()
                            vtk_data = geom_filter.GetOutput()
                            print(f"✅ Converted to polydata: {vtk_data.GetNumberOfPoints()} points")
                        else:
                            vtk_data = block
                    else:
                        print("⚠️ Block 0 is None")
                        return
                else:
                    print("⚠️ No blocks in multi-block dataset")
                    return
            
            # Create mapper and set up pressure field coloring
            mapper = vtk_local.vtkPolyDataMapper()
            mapper.SetInputData(vtk_data)
            
            # Set up pressure field coloring
            cell_data = vtk_data.GetCellData()
            if cell_data.GetArray('p'):
                print("🎨 Using pressure field (p) for coloring")
                mapper.SetScalarModeToUseCellFieldData()
                mapper.SelectColorArray('p')
                mapper.SetColorModeToMapScalars()
            elif cell_data.GetArray('U'):
                print("🎨 Using velocity field (U) for coloring")
                mapper.SetScalarModeToUseCellFieldData()
                mapper.SelectColorArray('U')
                mapper.SetColorModeToMapScalars()
            
            # Get the actual data range for proper color mapping
            data_range = None
            try:
                # Debug: Check what arrays are available
                cell_data = vtk_data.GetCellData()
                print(f"🔍 Available cell data arrays:")
                for i in range(cell_data.GetNumberOfArrays()):
                    array = cell_data.GetArray(i)
                    array_name = array.GetName() if array else "Unknown"
                    print(f"   [{i}] {array_name}")
                
                # Try to get the pressure field array
                pressure_array = None
                if cell_data.GetArray('p'):
                    pressure_array = cell_data.GetArray('p')
                    print(f"✅ Found pressure array 'p'")
                elif cell_data.GetNumberOfArrays() > 0:
                    # If 'p' not found, look for any array that might be pressure
                    for i in range(cell_data.GetNumberOfArrays()):
                        array = cell_data.GetArray(i)
                        array_name = array.GetName() if array else ""
                        if 'p' in array_name.lower() or i == 4:  # 'p' is usually array 4 in OpenFOAM
                            pressure_array = array
                            print(f"✅ Found pressure-like array: '{array_name}' at index {i}")
                            break
                
                if pressure_array:
                    data_range = pressure_array.GetRange()
                    print(f"📊 Pressure data range: {data_range}")
                    
                    # Force the mapper to use this specific array
                    mapper.SetScalarModeToUseCellFieldData()
                    mapper.SelectColorArray(pressure_array.GetName())
                    mapper.SetColorModeToMapScalars()
                    print(f"🎯 Forced mapper to use array: {pressure_array.GetName()}")
                else:
                    print(f"⚠️ No pressure field found, using fallback")
                    # Force mapper to use cell data and update
                    mapper.SetInputData(vtk_data)
                    mapper.Update()
                    data_range = mapper.GetInput().GetScalarRange()
                    print(f"📊 Fallback data range: {data_range}")
                    
            except Exception as range_error:
                print(f"⚠️ Could not get data range: {range_error}")
                data_range = (0.0, 1.0)  # Safe fallback

            # Create custom blue-gray-red lookup table
            try:
                lut = vtk_local.vtkLookupTable()
                lut.SetNumberOfTableValues(256)
                
                # CRITICAL: Set the range to the actual data range
                if data_range and data_range[0] != data_range[1]:
                    lut.SetRange(data_range)
                    print(f"🎨 Setting lookup table range to: {data_range}")
                else:
                    # If uniform data, use a small range around the value
                    center_val = data_range[0] if data_range else 0.0
                    lut.SetRange(center_val - 0.1, center_val + 0.1)
                    data_range = (center_val - 0.1, center_val + 0.1)
                    print(f"🎨 Uniform data detected, using range around: {center_val}")
                
                print("🎨 Creating blue-gray-red color scheme...")
                
                # Define the color gradient: blue -> gray -> red
                for i in range(256):
                    pos = i / 255.0  # Normalize position (0.0 to 1.0)
                    
                    if pos <= 0.5:
                        # Blue to gray (first half)
                        factor = pos * 2.0  # 0.0 to 1.0
                        r = 0.0 + factor * 0.5  # 0.0 to 0.5
                        g = 0.0 + factor * 0.5  # 0.0 to 0.5  
                        b = 1.0 - factor * 0.5  # 1.0 to 0.5
                    else:
                        # Gray to red (second half)
                        factor = (pos - 0.5) * 2.0  # 0.0 to 1.0
                        r = 0.5 + factor * 0.5  # 0.5 to 1.0
                        g = 0.5 - factor * 0.5  # 0.5 to 0.0
                        b = 0.5 - factor * 0.5  # 0.5 to 0.0
                    
                    lut.SetTableValue(i, r, g, b, 1.0)
                
                lut.Build()
                
                # CRITICAL: Set both the lookup table AND the mapper's scalar range
                mapper.SetLookupTable(lut)
                mapper.SetScalarRange(data_range)  # This is the key fix!
                print(f"🎨 Set mapper scalar range to: {data_range}")
                print("✅ Applied custom blue-gray-red color scheme")
                
            except Exception as lut_error:
                print(f"⚠️ Custom color scheme failed: {lut_error}")
                print("⚠️ Using default VTK coloring")
            
            # Create actor
            actor = vtk_local.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetOpacity(0.8)
            
            # Create color bar
            scalar_bar = None
            try:
                scalar_bar = vtk_local.vtkScalarBarActor()
                scalar_bar.SetLookupTable(mapper.GetLookupTable())
                scalar_bar.SetTitle("Pressure")
                scalar_bar.SetWidth(0.1)
                scalar_bar.SetHeight(0.8)
                scalar_bar.SetPosition(0.85, 0.1)
                scalar_bar.SetNumberOfLabels(7)
                print("🎨 Added color bar legend")
                
            except Exception as bar_error:
                print(f"⚠️ Color bar creation failed: {bar_error}")
                scalar_bar = None
            
            # Add to renderer
            self.renderer.AddActor(actor)
            if scalar_bar:
                self.renderer.AddActor2D(scalar_bar)
            
            # Restore camera position if it was saved, otherwise reset camera
            if hasattr(self, '_saved_camera_position') and self._saved_camera_position:
                try:
                    camera = self.renderer.GetActiveCamera()
                    camera.SetPosition(self._saved_camera_position)
                    camera.SetFocalPoint(self._saved_camera_focal_point)
                    camera.SetViewUp(self._saved_camera_view_up)
                    print("📷 Restored camera position")
                except Exception as cam_error:
                    print(f"⚠️ Could not restore camera position: {cam_error}")
                    self.renderer.ResetCamera()
            else:
                self.renderer.ResetCamera()
            
            self.vtk_widget.GetRenderWindow().Render()
            
            print("✅ Visualization updated with new time step data")
                
        except Exception as e:
            print(f"❌ Failed to display VTK data: {e}")
            import traceback
            traceback.print_exc()
    
    def previous_time_step(self):
        """Go to previous time step"""
        current_step = getattr(self, '_current_time_step', 0)
        if current_step > 0:
            self.time_slider.setValue(current_step - 1)
    
    def next_time_step(self):
        """Go to next time step"""
        current_step = getattr(self, '_current_time_step', 0)
        if current_step < len(self.time_steps) - 1:
            self.time_slider.setValue(current_step + 1)
    
    def update_time_label(self):
        """Update the time label"""
        if self.time_steps and hasattr(self, '_current_time_step') and self._current_time_step < len(self.time_steps):
            time_value = self.time_steps[self._current_time_step]
            self.time_label.setText(f"Time: {time_value:.3f}")
    
    def enable_controls(self):
        """Enable visualization controls"""
        # Enable dynamic field buttons
        if hasattr(self, 'field_buttons'):
            for button in self.field_buttons.values():
                button.setEnabled(True)
        
        # Enable view orientation buttons
        if hasattr(self, 'view_pos_x_btn'):
            for btn in [self.view_pos_x_btn, self.view_neg_x_btn, self.view_pos_y_btn, 
                        self.view_neg_y_btn, self.view_pos_z_btn, self.view_neg_z_btn,
                        self.rotate_cw_btn, self.rotate_ccw_btn]:
                btn.setEnabled(True)
        
        # Enable time controls
        if hasattr(self, 'time_steps') and self.time_steps:
            self.first_frame_btn.setEnabled(True)
            self.prev_time_btn.setEnabled(True)
            self.play_pause_btn.setEnabled(True)
            self.next_time_btn.setEnabled(True)
            self.last_frame_btn.setEnabled(True)
            self.time_slider.setEnabled(True)
        
        print("✅ Visualization controls enabled")
    
    def disable_controls(self):
        """Disable visualization controls"""
        # Disable dynamic field buttons
        if hasattr(self, 'field_buttons'):
            for button in self.field_buttons.values():
                button.setEnabled(False)
        
        # Disable view orientation buttons
        if hasattr(self, 'view_pos_x_btn'):
            for btn in [self.view_pos_x_btn, self.view_neg_x_btn, self.view_pos_y_btn, 
                        self.view_neg_y_btn, self.view_pos_z_btn, self.view_neg_z_btn,
                        self.rotate_cw_btn, self.rotate_ccw_btn]:
                btn.setEnabled(False)
        
        # Disable time controls and stop playback
        if hasattr(self, 'is_playing') and self.is_playing:
            self.pause_playback()
        
        if hasattr(self, 'first_frame_btn'):
            self.first_frame_btn.setEnabled(False)
        if hasattr(self, 'prev_time_btn'):
            self.prev_time_btn.setEnabled(False)
        if hasattr(self, 'play_pause_btn'):
            self.play_pause_btn.setEnabled(False)
        if hasattr(self, 'next_time_btn'):
            self.next_time_btn.setEnabled(False)
        if hasattr(self, 'last_frame_btn'):
            self.last_frame_btn.setEnabled(False)
        if hasattr(self, 'time_slider'):
            self.time_slider.setEnabled(False)
        
        print("⚠️ Visualization controls disabled")
    
    def show_error(self, message: str):
        """Show error message"""
        QMessageBox.critical(self, "ParaView Error", message)
    
    def retry_connection(self):
        """Retry connection to ParaView server"""
        if not self.connected:
            self.connect_to_server()
    
    def is_connected(self) -> bool:
        """Check if connected to ParaView server"""
        return self.connected
    
    def validate_vtk(self) -> bool:
        """Validate VTK availability at runtime"""
        global vtk, VTK_AVAILABLE, VTK_QT_AVAILABLE
        
        logger.info(f"VTK Validation: VTK_AVAILABLE={VTK_AVAILABLE}")
        logger.info(f"VTK Validation: VTK_QT_AVAILABLE={VTK_QT_AVAILABLE}")
        logger.info(f"VTK Validation: vtk module={vtk}")
        logger.info(f"VTK Validation: vtk is None={vtk is None}")
        
        if vtk is None or not VTK_AVAILABLE:
            logger.error("VTK module is None or not available - attempting to re-initialize")
            try:
                # Try to reinitialize VTK
                initialize_vtk()
                if VTK_AVAILABLE and vtk is not None:
                    # Test if we can create a VTK object
                    test_mapper = vtk.vtkPolyDataMapper()
                    logger.info(f"VTK re-initialization and validation successful")
                    return True
                else:
                    logger.error("VTK re-initialization failed")
                    return False
            except Exception as e:
                logger.error(f"VTK re-initialization failed: {e}")
                return False
        else:
            try:
                # Test if we can create a VTK object
                test_mapper = vtk.vtkPolyDataMapper()
                logger.info("VTK validation successful - can create objects")
                return True
            except Exception as e:
                logger.error(f"VTK object creation failed: {e}")
                return False
    
    def detect_available_fields(self):
        """Detect available fields from the current data source"""
        if not self.current_source:
            print("⚠️ No data source available for field detection")
            return []
        
        available_fields = []
        
        try:
            print("🔍 Detecting available fields from server data...")
            
            # Get the VTK data from the current source
            vtk_data = None
            if hasattr(self.current_source, 'GetClientSideObject'):
                # ParaView server source
                self.current_source.UpdatePipeline()
                vtk_data = self.current_source.GetClientSideObject().GetOutput()
            elif hasattr(self.current_source, 'GetOutput'):
                # Direct VTK source
                self.current_source.Update()
                vtk_data = self.current_source.GetOutput()
            
            if not vtk_data:
                print("⚠️ No VTK data available for field detection")
                return []
            
            # Handle multi-block datasets
            if vtk_data.GetClassName() == 'vtkMultiBlockDataSet':
                if vtk_data.GetNumberOfBlocks() > 0:
                    block = vtk_data.GetBlock(0)
                    if block:
                        vtk_data = block
                    else:
                        print("⚠️ Block 0 is None in multi-block dataset")
                        return []
                else:
                    print("⚠️ No blocks in multi-block dataset")
                    return []
            
            # Check cell data arrays
            cell_data = vtk_data.GetCellData()
            if cell_data:
                print(f"📊 Found {cell_data.GetNumberOfArrays()} cell data arrays:")
                for i in range(cell_data.GetNumberOfArrays()):
                    array = cell_data.GetArray(i)
                    if array:
                        array_name = array.GetName()
                        array_size = array.GetNumberOfTuples()
                        array_components = array.GetNumberOfComponents()
                        data_range = array.GetRange()
                        
                        # Create field info
                        field_info = {
                            'name': array_name,
                            'display_name': self._get_field_display_name(array_name),
                            'type': 'cell',
                            'size': array_size,
                            'components': array_components,
                            'range': data_range,
                            'array_index': i
                        }
                        
                        available_fields.append(field_info)
                        print(f"   [{i}] {array_name} ({array_components} components, range: {data_range})")
            
            # Check point data arrays
            point_data = vtk_data.GetPointData()
            if point_data:
                print(f"📊 Found {point_data.GetNumberOfArrays()} point data arrays:")
                for i in range(point_data.GetNumberOfArrays()):
                    array = point_data.GetArray(i)
                    if array:
                        array_name = array.GetName()
                        array_size = array.GetNumberOfTuples()
                        array_components = array.GetNumberOfComponents()
                        data_range = array.GetRange()
                        
                        # Create field info
                        field_info = {
                            'name': array_name,
                            'display_name': self._get_field_display_name(array_name),
                            'type': 'point',
                            'size': array_size,
                            'components': array_components,
                            'range': data_range,
                            'array_index': i
                        }
                        
                        available_fields.append(field_info)
                        print(f"   [{i}] {array_name} ({array_components} components, range: {data_range})")
            
            # Sort fields by importance (pressure, velocity, etc.)
            available_fields.sort(key=lambda x: self._get_field_priority(x['name']))
            
            print(f"✅ Detected {len(available_fields)} available fields")
            return available_fields
            
        except Exception as e:
            print(f"❌ Failed to detect fields: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_field_display_name(self, field_name):
        """Get user-friendly display name for a field"""
        display_names = {
            'p': 'Pressure',
            'U': 'Velocity',
            'k': 'Kinetic Energy',
            'epsilon': 'Dissipation Rate',
            'omega': 'Specific Dissipation Rate',
            'nut': 'Turbulent Viscosity',
            'nuTilda': 'Modified Viscosity',
            'v2': 'Velocity Scale',
            'f': 'Elliptic Relaxation'
        }
        return display_names.get(field_name, field_name.capitalize())
    
    def _get_field_priority(self, field_name):
        """Get priority for field ordering (lower number = higher priority)"""
        priorities = {
            'p': 1,        # Pressure (most important)
            'U': 2,        # Velocity
            'k': 3,        # Kinetic energy
            'epsilon': 4,  # Dissipation rate
            'omega': 5,    # Specific dissipation rate
            'nut': 6,      # Turbulent viscosity
            'nuTilda': 7,  # Modified viscosity
            'v2': 8,       # Velocity scale
            'f': 9         # Elliptic relaxation
        }
        return priorities.get(field_name, 100)  # Unknown fields get low priority
    
    def create_field_buttons(self):
        """Create dynamic field buttons based on detected fields"""
        if not hasattr(self, 'field_buttons_container'):
            print("⚠️ Field buttons container not initialized")
            return
        
        # Clear existing field buttons
        for field_name, button in self.field_buttons.items():
            button.setParent(None)
            button.deleteLater()
        
        self.field_buttons = {}
        
        # Detect available fields
        self.available_fields = self.detect_available_fields()
        
        if not self.available_fields:
            self.field_info_label.setText("No fields detected in current data")
            self.field_info_label.setStyleSheet("color: orange; font-style: italic;")
            return
        
        # Update info label
        field_count = len(self.available_fields)
        self.field_info_label.setText(f"Found {field_count} field{'s' if field_count != 1 else ''} in data")
        self.field_info_label.setStyleSheet("color: green; font-style: normal;")
        
        # Create buttons for each field
        row = 0
        col = 0  # Start from column 0 since no default view button
        max_cols = 3
        
        for field_info in self.available_fields:
            field_name = field_info['name']
            display_name = field_info['display_name']
            components = field_info['components']
            data_range = field_info['range']
            
            # Create button
            button = QPushButton(display_name)
            button.clicked.connect(lambda checked, fn=field_name: self.show_field(fn))
            button.setEnabled(True)
            
            # Style button based on field type
            button_style = self._get_field_button_style(field_name)
            button.setStyleSheet(button_style)
            
            # Add tooltip with field info
            tooltip = f"Field: {field_name}\n"
            tooltip += f"Components: {components}\n"
            tooltip += f"Range: {data_range[0]:.3f} to {data_range[1]:.3f}"
            button.setToolTip(tooltip)
            
            # Add to layout
            self.field_buttons_layout.addWidget(button, row, col)
            self.field_buttons[field_name] = button
            
            # Move to next position
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        print(f"✅ Created {len(self.field_buttons)} field buttons")
        
        # Set pressure as the initial field if available
        if 'p' in self.field_buttons:
            print("🎯 Setting pressure as initial field")
            self.show_field('p')
        elif self.available_fields:
            # If no pressure field, use the first available field
            first_field = self.available_fields[0]['name']
            print(f"🎯 Setting {first_field} as initial field (no pressure found)")
            self.show_field(first_field)
    
    def _get_field_button_style(self, field_name):
        """Get button style based on field type"""
        styles = {
            'p': "background-color: #2196F3; color: white; font-weight: bold;",  # Blue for pressure
            'U': "background-color: #FF9800; color: white; font-weight: bold;",  # Orange for velocity
            'k': "background-color: #9C27B0; color: white; font-weight: bold;",  # Purple for kinetic energy
            'epsilon': "background-color: #607D8B; color: white;",               # Blue-gray for dissipation
            'omega': "background-color: #795548; color: white;",                 # Brown for omega
            'nut': "background-color: #009688; color: white;",                   # Teal for viscosity
            'nuTilda': "background-color: #4CAF50; color: white;",               # Green for modified viscosity
            'v2': "background-color: #FF5722; color: white;",                    # Deep orange for v2
            'f': "background-color: #E91E63; color: white;"                      # Pink for f
        }
        return styles.get(field_name, "background-color: #757575; color: white;")  # Default gray
    
    def setup_view_buttons(self, parent_layout):
        """Setup view orientation buttons column"""
        # Create a vertical layout for view buttons
        view_buttons_widget = QWidget()
        view_buttons_widget.setMaximumWidth(80)
        view_buttons_layout = QVBoxLayout(view_buttons_widget)
        view_buttons_layout.setContentsMargins(5, 5, 5, 5)
        view_buttons_layout.setSpacing(5)
        
        # View orientation buttons
        self.view_pos_x_btn = QPushButton("+X")
        self.view_pos_x_btn.clicked.connect(self.view_pos_x)
        self.view_pos_x_btn.setToolTip("View along positive X axis")
        view_buttons_layout.addWidget(self.view_pos_x_btn)
        
        self.view_neg_x_btn = QPushButton("-X")
        self.view_neg_x_btn.clicked.connect(self.view_neg_x)
        self.view_neg_x_btn.setToolTip("View along negative X axis")
        view_buttons_layout.addWidget(self.view_neg_x_btn)
        
        self.view_pos_y_btn = QPushButton("+Y")
        self.view_pos_y_btn.clicked.connect(self.view_pos_y)
        self.view_pos_y_btn.setToolTip("View along positive Y axis")
        view_buttons_layout.addWidget(self.view_pos_y_btn)
        
        self.view_neg_y_btn = QPushButton("-Y")
        self.view_neg_y_btn.clicked.connect(self.view_neg_y)
        self.view_neg_y_btn.setToolTip("View along negative Y axis")
        view_buttons_layout.addWidget(self.view_neg_y_btn)
        
        self.view_pos_z_btn = QPushButton("+Z")
        self.view_pos_z_btn.clicked.connect(self.view_pos_z)
        self.view_pos_z_btn.setToolTip("View along positive Z axis")
        view_buttons_layout.addWidget(self.view_pos_z_btn)
        
        self.view_neg_z_btn = QPushButton("-Z")
        self.view_neg_z_btn.clicked.connect(self.view_neg_z)
        self.view_neg_z_btn.setToolTip("View along negative Z axis")
        view_buttons_layout.addWidget(self.view_neg_z_btn)
        
        # Add separator
        view_buttons_layout.addSpacing(10)
        
        # Rotation buttons
        self.rotate_cw_btn = QPushButton("↻")
        self.rotate_cw_btn.clicked.connect(self.rotate_clockwise_90)
        self.rotate_cw_btn.setToolTip("Rotate view 90° clockwise")
        view_buttons_layout.addWidget(self.rotate_cw_btn)
        
        self.rotate_ccw_btn = QPushButton("↺")
        self.rotate_ccw_btn.clicked.connect(self.rotate_counterclockwise_90)
        self.rotate_ccw_btn.setToolTip("Rotate view 90° counterclockwise")
        view_buttons_layout.addWidget(self.rotate_ccw_btn)
        
        # Add stretch to push buttons to top
        view_buttons_layout.addStretch()
        
        # Style the buttons
        button_style = """
            QPushButton {
                font-size: 12px;
                font-weight: bold;
                min-height: 30px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """
        
        # Apply style to all view buttons
        for btn in [self.view_pos_x_btn, self.view_neg_x_btn, self.view_pos_y_btn, 
                    self.view_neg_y_btn, self.view_pos_z_btn, self.view_neg_z_btn,
                    self.rotate_cw_btn, self.rotate_ccw_btn]:
            btn.setStyleSheet(button_style)
            btn.setEnabled(False)  # Disabled until visualization is loaded
        
        # Add to parent layout
        parent_layout.addWidget(view_buttons_widget)
    
    def setup_custom_mouse_interaction(self):
        """Setup custom mouse interaction for Blender-like behavior"""
        if not hasattr(self, 'vtk_widget') or not self.vtk_widget:
            return
        
        # Initialize mouse interaction state
        self.mouse_dragging = False
        self.last_mouse_pos = None
        self.camera_rotation_speed = 0.5
        
        # Install event filter to capture mouse events
        self.vtk_widget.installEventFilter(self)
    
    def eventFilter(self, source, event):
        """Custom event filter for mouse interaction"""
        if source == self.vtk_widget and hasattr(self, 'renderer') and self.renderer:
            from PySide6.QtCore import QEvent
            from PySide6.QtGui import QMouseEvent
            
            if event.type() == QEvent.MouseButtonPress:
                if isinstance(event, QMouseEvent) and event.button() == Qt.LeftButton:
                    self.last_mouse_pos = event.position()
                    self.mouse_dragging = True
                    return True
                    
            elif event.type() == QEvent.MouseMove:
                if isinstance(event, QMouseEvent) and self.mouse_dragging:
                    current_pos = event.position()
                    if self.last_mouse_pos is not None:
                        delta_x = current_pos.x() - self.last_mouse_pos.x()
                        delta_y = current_pos.y() - self.last_mouse_pos.y()
                        self.rotate_camera(delta_x, delta_y)
                    self.last_mouse_pos = current_pos
                    return True
                    
            elif event.type() == QEvent.MouseButtonRelease:
                if isinstance(event, QMouseEvent) and event.button() == Qt.LeftButton:
                    self.mouse_dragging = False
                    self.last_mouse_pos = None
                    return True
        
        # Pass event to parent
        return super().eventFilter(source, event)
    
    def rotate_camera(self, delta_x, delta_y):
        """Rotate camera based on mouse movement (Blender-like behavior)"""
        if not hasattr(self, 'renderer') or not self.renderer:
            return
        
        camera = self.renderer.GetActiveCamera()
        
        # Get current camera parameters
        focal_point = camera.GetFocalPoint()
        position = camera.GetPosition()
        view_up = camera.GetViewUp()
        
        # Calculate rotation angles based on mouse movement
        azimuth = -delta_x * self.camera_rotation_speed
        elevation = delta_y * self.camera_rotation_speed
        
        # Apply azimuth rotation (horizontal mouse movement)
        camera.Azimuth(azimuth)
        
        # Apply elevation rotation (vertical mouse movement)
        camera.Elevation(elevation)
        
        # Ensure camera maintains proper orientation
        camera.OrthogonalizeViewUp()
        
        # Render the updated view
        if hasattr(self, 'vtk_widget') and self.vtk_widget:
            self.vtk_widget.GetRenderWindow().Render()
    
    def view_pos_x(self):
        """View along positive X axis"""
        if not hasattr(self, 'renderer') or not self.renderer:
            return
        
        camera = self.renderer.GetActiveCamera()
        # Position camera along positive X axis looking toward origin
        camera.SetPosition(10, 0, 0)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 0, 1)  # Z is up
        self.renderer.ResetCamera()
        
        if hasattr(self, 'vtk_widget') and self.vtk_widget:
            self.vtk_widget.GetRenderWindow().Render()
    
    def view_neg_x(self):
        """View along negative X axis"""
        if not hasattr(self, 'renderer') or not self.renderer:
            return
        
        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(-10, 0, 0)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 0, 1)  # Z is up
        self.renderer.ResetCamera()
        
        if hasattr(self, 'vtk_widget') and self.vtk_widget:
            self.vtk_widget.GetRenderWindow().Render()
    
    def view_pos_y(self):
        """View along positive Y axis"""
        if not hasattr(self, 'renderer') or not self.renderer:
            return
        
        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(0, 10, 0)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 0, 1)  # Z is up
        self.renderer.ResetCamera()
        
        if hasattr(self, 'vtk_widget') and self.vtk_widget:
            self.vtk_widget.GetRenderWindow().Render()
    
    def view_neg_y(self):
        """View along negative Y axis"""
        if not hasattr(self, 'renderer') or not self.renderer:
            return
        
        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(0, -10, 0)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 0, 1)  # Z is up
        self.renderer.ResetCamera()
        
        if hasattr(self, 'vtk_widget') and self.vtk_widget:
            self.vtk_widget.GetRenderWindow().Render()
    
    def view_pos_z(self):
        """View along positive Z axis"""
        if not hasattr(self, 'renderer') or not self.renderer:
            return
        
        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(0, 0, 10)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 1, 0)  # Y is up when looking down Z
        self.renderer.ResetCamera()
        
        if hasattr(self, 'vtk_widget') and self.vtk_widget:
            self.vtk_widget.GetRenderWindow().Render()
    
    def view_neg_z(self):
        """View along negative Z axis"""
        if not hasattr(self, 'renderer') or not self.renderer:
            return
        
        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(0, 0, -10)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 1, 0)  # Y is up when looking up Z
        self.renderer.ResetCamera()
        
        if hasattr(self, 'vtk_widget') and self.vtk_widget:
            self.vtk_widget.GetRenderWindow().Render()
    
    def rotate_clockwise_90(self):
        """Rotate view 90 degrees clockwise"""
        if not hasattr(self, 'renderer') or not self.renderer:
            return
        
        camera = self.renderer.GetActiveCamera()
        camera.Roll(-90)  # Negative roll for clockwise rotation
        
        if hasattr(self, 'vtk_widget') and self.vtk_widget:
            self.vtk_widget.GetRenderWindow().Render()
    
    def rotate_counterclockwise_90(self):
        """Rotate view 90 degrees counterclockwise"""
        if not hasattr(self, 'renderer') or not self.renderer:
            return
        
        camera = self.renderer.GetActiveCamera()
        camera.Roll(90)  # Positive roll for counterclockwise rotation
        
        if hasattr(self, 'vtk_widget') and self.vtk_widget:
            self.vtk_widget.GetRenderWindow().Render()
    
    def first_time_step(self):
        """Go to first time step"""
        if self.time_steps:
            self.time_slider.setValue(0)
    
    def last_time_step(self):
        """Go to last time step"""
        if self.time_steps:
            self.time_slider.setValue(len(self.time_steps) - 1)
    
    def play_pause_toggle(self):
        """Toggle play/pause for animation"""
        if self.is_playing:
            self.pause_playback()
        else:
            self.start_playback()
    
    def start_playback(self):
        """Start playback animation"""
        if not self.time_steps or len(self.time_steps) <= 1:
            return
        
        self.is_playing = True
        
        # Update button icon to pause
        style = self.style()
        self.play_pause_btn.setIcon(style.standardIcon(QStyle.SP_MediaPause))
        self.play_pause_btn.setToolTip("Pause animation")
        
        # Start timer with current speed
        interval = int(self.speed_control.value() * 1000)  # Convert to milliseconds
        self.playback_timer.start(interval)
        
        print(f"🎬 Started playback at {self.speed_control.value()} s/frame")
    
    def pause_playback(self):
        """Pause playback animation"""
        self.is_playing = False
        
        # Update button icon to play
        style = self.style()
        self.play_pause_btn.setIcon(style.standardIcon(QStyle.SP_MediaPlay))
        self.play_pause_btn.setToolTip("Play animation")
        
        # Stop timer
        self.playback_timer.stop()
        
        print("⏸️ Paused playback")
    
    def advance_frame(self):
        """Advance to next frame during playback"""
        if not self.time_steps:
            self.pause_playback()
            return
        
        current_step = self.time_slider.value()
        max_step = len(self.time_steps) - 1
        
        if current_step < max_step:
            # Go to next frame
            self.time_slider.setValue(current_step + 1)
        else:
            # At the end
            if self.loop_checkbox.isChecked():
                # Loop back to start
                self.time_slider.setValue(0)
                print("🔄 Looping back to start")
            else:
                # Stop playback
                self.pause_playback()
                print("⏹️ Reached end of animation")
    
    def update_playback_speed(self):
        """Update playback speed when spinner value changes"""
        if self.is_playing:
            # Update timer interval while playing
            interval = int(self.speed_control.value() * 1000)
            self.playback_timer.start(interval)
            print(f"🎬 Updated playback speed to {self.speed_control.value()} s/frame")