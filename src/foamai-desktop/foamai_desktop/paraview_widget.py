"""
ParaView Widget for OpenFOAM Desktop Application
Handles 3D visualization using ParaView server connection
"""
import logging
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QMessageBox, QGroupBox, QSlider, QSpinBox, QGridLayout,
                               QDoubleSpinBox, QCheckBox, QStyle, QFrame)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QImage

# Import remote ParaView server management
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "foamai-core"))

try:
    from foamai_core.orchestrator import start_remote_paraview_server, stop_remote_paraview_server, get_remote_project_info
    REMOTE_PARAVIEW_AVAILABLE = True
except ImportError as e:
    REMOTE_PARAVIEW_AVAILABLE = False
    print(f"Remote ParaView management not available: {e}")

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

from .config import Config

logger = logging.getLogger(__name__)

class ParaViewWidget(QWidget):
    """Widget for displaying ParaView visualizations"""
    
    # Signals
    visualization_loaded = Signal(str)  # Emitted when visualization is loaded
    visualization_error = Signal(str)   # Emitted when visualization fails
    connection_status_changed = Signal(bool)  # Emitted when connection status changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_source = None
        self.time_steps = []
        self.time_directories = []
        
        # Initialize field button tracking
        self.field_buttons = {}
        self.available_fields = []
        self.current_field = None  # Track currently selected field
        
        # Initialize global data ranges for consistent color scaling
        self.global_field_ranges = {}  # Store global min/max for each field across all time steps
        
        # Connection state
        self.connected = False
        
        # Remote server configuration
        self.server_url = None
        self.project_name = None
        self.remote_paraview_info = None
        
        # Initialize UI
        self.setup_ui()
        
        # Connection timer for retry logic
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.retry_connection)
        
        # Note: VTK initialization is deferred until UI setup
        # Auto-connect logic will be handled after UI setup
    
    def set_remote_server(self, server_url: str, project_name: str):
        """Set remote server configuration for ParaView."""
        self.server_url = server_url
        self.project_name = project_name
        
        if REMOTE_PARAVIEW_AVAILABLE:
            self.connection_label.setText(f"Remote server configured: {server_url}")
            self.connection_label.setStyleSheet("color: blue; font-weight: bold;")
            
            # Update connect button to use remote server
            if hasattr(self, 'connect_btn'):
                self.connect_btn.setText("Connect to Remote ParaView Server")
                self.connect_btn.setEnabled(True)
            
            logger.info(f"ParaView widget configured for remote server: {server_url}, project: {project_name}")
        else:
            logger.warning("Remote ParaView management not available")
    
    def connect_to_remote_server(self):
        """Connect to or start remote ParaView server with improved connection logic."""
        logger.info(f"connect_to_remote_server called for project: {self.project_name}")
        
        if not self.server_url or not self.project_name:
            error_msg = "Remote server not configured"
            logger.error(error_msg)
            QMessageBox.warning(self, "Error", error_msg)
            return
        
        # COMPREHENSIVE STATE RESET BEFORE NEW CONNECTION
        logger.info("Performing comprehensive state reset before new connection...")
        try:
            # If we're already connected, do a full cleanup first
            if self.connected:
                logger.info("Already connected - performing cleanup before reconnection")
                self._comprehensive_paraview_cleanup()
                
                # Disconnect cleanly from previous connection
                if PARAVIEW_AVAILABLE:
                    try:
                        pv.Disconnect()
                        logger.info("Disconnected from previous ParaView connection")
                    except Exception as prev_disconnect_error:
                        logger.warning(f"Previous disconnect failed: {prev_disconnect_error}")
                
                self.connected = False
            
            # Always clear internal state for fresh start
            self._clear_internal_state()
            
            # Clear VTK resources to free memory
            self._clear_vtk_resources()
            
            # Force garbage collection before new connection
            import gc
            gc.collect()
            
            logger.info("State reset completed - ready for new connection")
            
        except Exception as reset_error:
            logger.warning(f"State reset failed: {reset_error}")
            # Continue anyway - connection might still work
        
        # Wrap the entire connection process in a try-catch to prevent crashes
        try:
            # Step 1: Check current server status via API
            self.connection_label.setText("Checking remote ParaView server status...")
            self.connection_label.setStyleSheet("color: orange; font-weight: bold;")
            
            server_status = self._check_remote_pvserver_status()
            logger.info(f"Server status check result: {server_status}")
            
            if server_status.get("status") == "error":
                error_msg = f"Failed to check server status: {server_status.get('error', 'Unknown error')}"
                logger.error(error_msg)
                QMessageBox.warning(self, "Error", error_msg)
                return
            
            # Step 2: Start server if not running
            if server_status.get("status") != "running":
                logger.info("PVServer not running, starting it...")
                self.connection_label.setText("Starting remote ParaView server...")
                
                if not self._start_remote_pvserver():
                    error_msg = "Failed to start remote ParaView server"
                    logger.error(error_msg)
                    QMessageBox.warning(self, "Error", error_msg)
                    return
                
                # Wait a moment for server to start
                import time
                time.sleep(2)
                
                # Re-check status to get connection info
                server_status = self._check_remote_pvserver_status()
                logger.info(f"Server status after starting: {server_status}")
            else:
                logger.info("PVServer already running")
            
            # Step 3: Get connection information
            if server_status.get("status") == "running":
                port = server_status.get("port")
                remote_host = self._get_remote_host()
                
                # Debug logging for API response
                logger.info(f"Raw API response port: {port} (type: {type(port)})")
                logger.info(f"Raw remote host: {remote_host}")
                
                # Validate port
                if not port or not isinstance(port, (int, str)) or str(port).strip() == "":
                    error_msg = f"Invalid port received from server: {port}"
                    logger.error(error_msg)
                    QMessageBox.warning(self, "Error", error_msg)
                    return
                
                # Debug: Check if the port already contains duplication
                port_str = str(port)
                if ':' in port_str:
                    logger.error(f"API returned port with colon: {port_str} - this is the source of duplication!")
                
                # Ensure port is a clean integer
                try:
                    port = int(port)
                    if port <= 0 or port > 65535:
                        raise ValueError(f"Port {port} is out of valid range")
                except (ValueError, TypeError) as e:
                    error_msg = f"Invalid port format from server: {port} - {e}"
                    logger.error(error_msg)
                    QMessageBox.warning(self, "Error", error_msg)
                    return
                
                # Validate and clean remote_host
                if not remote_host or remote_host.strip() == "":
                    error_msg = f"Invalid remote host: {remote_host}"
                    logger.error(error_msg)
                    QMessageBox.warning(self, "Error", error_msg)
                    return
                
                # Clean remote_host - ensure it doesn't contain a port
                remote_host = remote_host.strip()
                if ':' in remote_host:
                    # Handle IPv6 addresses vs regular host:port
                    if remote_host.startswith('[') and ']:' in remote_host:
                        # IPv6 address like [::1]:8080 - extract just the IPv6 part
                        remote_host = remote_host.split(']:')[0][1:]
                        logger.info(f"Extracted IPv6 host: {remote_host}")
                    else:
                        # Regular host:port format - extract just the host part
                        original_host = remote_host
                        remote_host = remote_host.split(':')[0]
                        logger.warning(f"Removed port from host: {original_host} -> {remote_host}")
                
                # Validate and clean port
                port_str = str(port).strip()
                if ':' in port_str:
                    # Port contains colon - this is the duplication issue!
                    original_port = port_str
                    port_str = port_str.split(':')[0]  # Take only the first part
                    logger.warning(f"Removed duplicated port: {original_port} -> {port_str}")
                
                # Convert back to integer and validate
                try:
                    port = int(port_str)
                    if port <= 0 or port > 65535:
                        raise ValueError(f"Port {port} is out of valid range")
                except (ValueError, TypeError) as e:
                    error_msg = f"Invalid port after cleanup: {port_str} - {e}"
                    logger.error(error_msg)
                    QMessageBox.warning(self, "Error", error_msg)
                    return
                
                # Final validation - ensure both components are clean
                if ':' in remote_host:
                    error_msg = f"Host still contains colon after cleanup: {remote_host}"
                    logger.error(error_msg)
                    QMessageBox.warning(self, "Error", error_msg)
                    return
                
                connection_string = f"{remote_host}:{port}"
                
                # Final validation of connection string format
                colon_count = connection_string.count(':')
                if colon_count != 1:
                    error_msg = f"Malformed connection string: {connection_string} (has {colon_count} colons, should have 1)"
                    logger.error(error_msg)
                    QMessageBox.warning(self, "Error", error_msg)
                    return
                
                logger.info(f"=== FINAL CONNECTION ATTEMPT ===")
                logger.info(f"Clean remote host: '{remote_host}'")
                logger.info(f"Clean port: {port}")
                logger.info(f"Final connection string: '{connection_string}'")
                logger.info(f"Connection string colon count: {connection_string.count(':')}")
                logger.info(f"=== ATTEMPTING CONNECTION ===")
                
                # Step 4: Try to connect ParaView client if available
                if PARAVIEW_AVAILABLE:
                    connection_successful = self._try_paraview_connection(connection_string)
                    if connection_successful:
                        logger.info("ParaView client connected successfully")
                        
                        # Update connection status with malformed connection check
                        status_message = self._get_connection_status_message()
                        if "bug" in status_message:
                            self.connection_label.setText(f"Connected to {connection_string} - ParaView bug detected")
                            self.connection_label.setStyleSheet("color: orange; font-weight: bold;")
                        else:
                            self.connection_label.setText(f"Connected to remote ParaView server at {connection_string}")
                            self.connection_label.setStyleSheet("color: green; font-weight: bold;")
                        
                        self.connect_btn.setText("Disconnect from Remote Server")
                        self.connect_btn.setEnabled(False)
                        self.disconnect_btn.setEnabled(True)
                        self.enable_controls()
                        
                        # Emit connection status signal
                        self.connection_status_changed.emit(True)
                        
                        # Auto-load the simulation data
                        self._auto_load_remote_data()
                        
                        logger.info("Remote ParaView server connection complete")
                        
                    else:
                        logger.warning("ParaView client connection failed but server is running")
                        self.connection_label.setText(f"Server running at {connection_string} - Client connection failed")
                        self.connection_label.setStyleSheet("color: orange; font-weight: bold;")
                else:
                    logger.info("ParaView client not available, but server is running")
                    self.connection_label.setText(f"Server running at {connection_string} - No ParaView client")
                    self.connection_label.setStyleSheet("color: blue; font-weight: bold;")
            else:
                error_msg = f"Server status is not running: {server_status}"
                logger.error(error_msg)
                self.connection_label.setText("Failed to start/connect to ParaView server")
                self.connection_label.setStyleSheet("color: red; font-weight: bold;")
            
        except Exception as e:
            error_msg = f"Error with remote ParaView server: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error(f"Full connection error traceback: {traceback.format_exc()}")
            
            # Try to provide user-friendly error messages
            if "malformed" in str(e).lower() or "connection string" in str(e).lower():
                user_msg = "Connection failed due to server configuration issue. Please check the server status and try again."
            elif "refused" in str(e).lower():
                user_msg = "Connection refused by server. The server may be busy or not accessible."
            elif "timeout" in str(e).lower():
                user_msg = "Connection timed out. Please check your network connection and server status."
            else:
                user_msg = f"Connection failed: {str(e)}"
            
            QMessageBox.critical(self, "Connection Error", user_msg)
            self.connection_label.setText("Remote ParaView server error")
            self.connection_label.setStyleSheet("color: red; font-weight: bold;")
            
            # Reset connection state
            self.connected = False
    
    def _get_remote_host(self):
        """Extract the remote host from the server URL."""
        if not self.server_url:
            logger.info("No server URL provided, using localhost")
            return "localhost"
        
        logger.info(f"Extracting remote host from server URL: {self.server_url}")
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.server_url)
            
            logger.info(f"Parsed URL - hostname: {parsed.hostname}, netloc: {parsed.netloc}")
            
            # First try to get hostname (this should exclude port)
            if parsed.hostname:
                remote_host = parsed.hostname
                logger.info(f"Using parsed hostname: {remote_host}")
                
                # Extra validation - ensure hostname doesn't contain port
                if ':' in remote_host:
                    logger.warning(f"Hostname contains colon: {remote_host} - this shouldn't happen")
                    remote_host = remote_host.split(':')[0]
                    logger.info(f"Cleaned hostname: {remote_host}")
                
                return remote_host
            
            # Fallback: extract host from netloc, ensuring we only get the host part
            if parsed.netloc:
                # Handle IPv6 addresses in brackets and regular host:port format
                netloc = parsed.netloc
                logger.info(f"Using netloc fallback: {netloc}")
                
                # Remove any user info (user:pass@host:port)
                if '@' in netloc:
                    netloc = netloc.split('@')[1]
                    logger.info(f"Removed user info: {netloc}")
                
                # Handle IPv6 addresses [::1]:port
                if netloc.startswith('[') and ']:' in netloc:
                    remote_host = netloc.split(']:')[0][1:]  # Remove brackets
                    logger.info(f"Extracted IPv6 host: {remote_host}")
                elif ':' in netloc:
                    # Regular host:port format - take only the host part
                    original_netloc = netloc
                    remote_host = netloc.split(':')[0]
                    logger.info(f"Extracted host from netloc: {original_netloc} -> {remote_host}")
                else:
                    # No port specified
                    remote_host = netloc
                    logger.info(f"Using netloc as-is (no port): {remote_host}")
                
                # Final validation
                if ':' in remote_host:
                    logger.error(f"Host still contains colon after extraction: {remote_host}")
                    remote_host = remote_host.split(':')[0]
                    logger.info(f"Emergency cleanup: {remote_host}")
                
                return remote_host
            
            # Final fallback
            logger.warning(f"Could not extract hostname from server URL {self.server_url}, using localhost")
            return "localhost"
            
        except Exception as e:
            logger.warning(f"Could not parse server URL {self.server_url}: {e}")
            return "localhost"
    
    def _try_paraview_connection(self, connection_string):
        """Try to establish ParaView connection with error handling."""
        try:
            # Validate connection string format before attempting connection
            if not connection_string or ':' not in connection_string:
                error_msg = f"Invalid connection string format: {connection_string}"
                logger.error(error_msg)
                return False
            
            # Parse and validate host and port from connection string
            try:
                host, port_str = connection_string.rsplit(':', 1)  # rsplit to handle IPv6
                port = int(port_str)
                if not host or port <= 0 or port > 65535:
                    raise ValueError(f"Invalid host or port: {host}:{port}")
            except (ValueError, TypeError) as parse_error:
                error_msg = f"Cannot parse connection string '{connection_string}': {parse_error}"
                logger.error(error_msg)
                return False
            
            logger.info(f"Attempting ParaView connection to: {connection_string} (host='{host}', port={port})")
            
            # Try to connect to ParaView server using separate host and port to avoid connection string parsing bug
            pv.Connect(host, port)
            self.connected = True
            logger.info("ParaView connection successful")
            
            # Verify the connection was established correctly
            try:
                import paraview.servermanager as sm
                if hasattr(sm, 'ActiveConnection') and sm.ActiveConnection:
                    active_conn_str = str(sm.ActiveConnection)
                    logger.info(f"Active connection verified: {active_conn_str}")
                    
                    # Check if the active connection string looks malformed
                    if active_conn_str.count(':') > 2:  # More than expected colons (cs://host:port should have 2)
                        logger.warning(f"Active connection string appears malformed: {active_conn_str}")
                        logger.warning("This indicates a ParaView connection parsing bug")
                        logger.warning("Keeping the working connection but will add extra protection for operations")
                        
                        # Don't disconnect - the connection is actually working
                        # We'll handle the bug by being extra careful in data operations
                else:
                    logger.warning("No active connection found after Connect() succeeded")
            except Exception as verify_error:
                logger.warning(f"Could not verify connection: {verify_error}")
            
            return True
                
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"ParaView connection failed: {error_msg}")
            
            # Log the full exception for debugging
            import traceback
            logger.debug(f"ParaView connection exception traceback: {traceback.format_exc()}")
            
            # Check for specific error types
            if "version hash mismatch" in error_msg.lower():
                logger.warning("Version mismatch detected - client and server ParaView versions differ")
                logger.warning("Unable to establish ParaView connection due to version incompatibility")
                logger.warning("Server is running but client cannot connect")
                return False
                    
            elif "handshake" in error_msg.lower():
                logger.warning("Handshake failure - connection compatibility issue")
                return False
                
            elif "refused" in error_msg.lower():
                logger.warning("Connection refused - server may not be ready or port blocked")
                return False
                
            elif "invalid" in error_msg.lower() or "malformed" in error_msg.lower():
                logger.error(f"Connection string validation failed: {error_msg}")
                return False
                
            return False
    
    def _auto_load_remote_data(self):
        """Auto-load simulation data from remote server after successful connection."""
        if not self.connected or not self.server_url or not self.project_name:
            return
        
        # Additional safety check for malformed connections that could cause crashes
        try:
            import paraview.servermanager as sm
            if hasattr(sm, 'ActiveConnection') and sm.ActiveConnection:
                active_conn_str = str(sm.ActiveConnection)
                if active_conn_str.count(':') > 2:
                    logger.error(f"Cannot auto-load data: connection string is malformed: {active_conn_str}")
                    logger.error("This will likely cause crashes in ParaView operations")
                    
                    # Update UI to show the issue
                    if hasattr(self, 'visualization_area'):
                        self.visualization_area.setText(
                            "Connection established but ParaView has a known bug\n"
                            "with the connection string format.\n\n"
                            "This may cause crashes during data operations.\n\n"
                            "Try disconnecting and reconnecting, or use a\n"
                            "different ParaView version if the issue persists."
                        )
                    return
        except Exception as check_error:
            logger.warning(f"Could not check connection string: {check_error}")
        
        try:
            # Verify ParaView connection is fully ready
            if not self._verify_paraview_connection():
                logger.warning("ParaView connection not ready for data loading")
                return
            
            # For remote ParaView server connection, we need to use server-local paths
            # The ParaView server runs on the remote machine and accesses local files there
            
            # Get the case path from project info  
            project_info = get_remote_project_info(self.server_url, self.project_name)
            pvserver_info = project_info.get("pvserver_info", {})
            case_path = pvserver_info.get("case_path")
            
            if not case_path:
                logger.warning("Could not determine case path for auto-loading")
                return
            
            # Use the server-local case path (ParaView server will access this locally)
            foam_file_path = f"{case_path}/{self.project_name}.foam"
            
            logger.info(f"Auto-loading OpenFOAM case from server path: {foam_file_path}")
            
            # Use ParaView to load the case with version compatibility
            from paraview.simple import OpenFOAMReader
            
            # ParaView 6.0.0 compatible connection verification
            try:
                import paraview.servermanager as sm
                if hasattr(sm, 'ActiveConnection') and sm.ActiveConnection:
                    logger.info(f"ParaView connection verified (6.0.0 compatible): {sm.ActiveConnection}")
                else:
                    logger.warning("No active ParaView connection found")
                    return
            except Exception as conn_error:
                logger.warning(f"Could not verify ParaView connection: {conn_error}")
                # Continue anyway - connection might work
            
            # ENHANCED MEMORY MANAGEMENT - Clear any existing sources and VTK objects
            try:
                logger.info("Performing enhanced memory management cleanup...")
                
                # Clear current ParaView source
                if hasattr(self, 'current_source') and self.current_source:
                    from paraview.simple import Delete
                    try:
                        Delete(self.current_source)
                        logger.info("Deleted existing ParaView source")
                    except Exception as cleanup_error:
                        logger.warning(f"Could not delete existing source: {cleanup_error}")
                    
                    self.current_source = None
                
                # Clear VTK actors and rendering objects to free memory
                if hasattr(self, 'renderer') and self.renderer:
                    try:
                        # Remove all actors to free VTK memory
                        self.renderer.RemoveAllViewProps()
                        
                        # Clear 2D actors (color bars, text, etc.)
                        actors_2d = self.renderer.GetActors2D()
                        if actors_2d:
                            actors_2d.InitTraversal()
                            actors_to_remove = []
                            for i in range(actors_2d.GetNumberOfItems()):
                                actor = actors_2d.GetNextItem()
                                if actor:
                                    actors_to_remove.append(actor)
                            
                            for actor in actors_to_remove:
                                self.renderer.RemoveActor2D(actor)
                        
                        logger.info("Cleared VTK actors and view props")
                    except Exception as vtk_cleanup_error:
                        logger.warning(f"VTK cleanup failed: {vtk_cleanup_error}")
                
                # Force Python garbage collection to free memory
                import gc
                collected = gc.collect()
                logger.info(f"Garbage collection freed {collected} objects")
                
            except Exception as memory_cleanup_error:
                logger.warning(f"Memory management cleanup failed: {memory_cleanup_error}")
            
            # Create OpenFOAM reader with server-local case path
            # The ParaView server will load this from its local filesystem
            logger.info("Creating OpenFOAM reader...")
            
            # Wrap reader creation in multiple layers of error handling to prevent crashes
            try:
                logger.info("Creating OpenFOAM reader with enhanced error protection...")
                
                # First, try to create the reader with maximum protection
                reader = None
                try:
                    reader = OpenFOAMReader(FileName=foam_file_path)
                    logger.info("OpenFOAM reader created successfully")
                except Exception as create_error:
                    logger.error(f"OpenFOAM reader creation failed: {create_error}")
                    
                    # Check if this might be a connection-related issue
                    try:
                        import paraview.servermanager as sm
                        if hasattr(sm, 'ActiveConnection') and sm.ActiveConnection:
                            active_conn_str = str(sm.ActiveConnection)
                            if active_conn_str.count(':') > 2:
                                logger.error("Reader creation failed - likely due to malformed connection string bug")
                                logger.error("This is a known ParaView 6.0.0 issue that can cause crashes")
                                
                                # Show a user-friendly message instead of crashing
                                if hasattr(self, 'visualization_area'):
                                    self.visualization_area.setText(
                                        "⚠️ Connection established but data loading encountered issues.\n\n"
                                        "This appears to be related to a known ParaView 6.0.0 bug\n"
                                        "with connection string parsing.\n\n"
                                        "The connection is working, but some data operations\n"
                                        "may be unstable.\n\n"
                                        "Suggestions:\n"
                                        "• Try reloading the data manually\n"
                                        "• Restart the application if issues persist\n"
                                        "• Consider using a different ParaView version"
                                    )
                                return
                    except Exception:
                        pass
                    
                    # If not connection-related, show generic error
                    logger.error("OpenFOAM reader creation failed for unknown reason")
                    if hasattr(self, 'visualization_area'):
                        self.visualization_area.setText(
                            f"❌ Failed to load OpenFOAM data.\n\n"
                            f"Error: {str(create_error)}\n\n"
                            "Please check:\n"
                            "• Server connection is stable\n"
                            "• Case files exist on server\n"
                            "• ParaView server is functioning properly"
                        )
                    return
                
                if not reader:
                    logger.error("Failed to create OpenFOAM reader - returned None")
                    if hasattr(self, 'visualization_area'):
                        self.visualization_area.setText(
                            "❌ Failed to create OpenFOAM reader.\n\n"
                            "The reader returned None, which may indicate:\n"
                            "• File not found on server\n"
                            "• Insufficient permissions\n"
                            "• ParaView server issues"
                        )
                    return
                
                logger.info(f"OpenFOAM reader created successfully: {reader}")
                self.current_source = reader
                
            except Exception as reader_error:
                logger.error(f"Critical error in reader creation: {reader_error}")
                import traceback
                logger.error(f"Reader creation traceback: {traceback.format_exc()}")
                
                # Provide user-friendly error message
                if hasattr(self, 'visualization_area'):
                    self.visualization_area.setText(
                        f"❌ Critical error loading OpenFOAM data.\n\n"
                        f"Error: {str(reader_error)}\n\n"
                        "This error prevented the application from loading\n"
                        "the simulation data. Please try:\n"
                        "• Disconnecting and reconnecting\n"
                        "• Restarting the application\n"
                        "• Checking server logs for issues"
                    )
                return
            
            # Configure reader for better data loading (ParaView 6.0.0 compatible)
            try:
                logger.info("Configuring OpenFOAM reader options...")
                
                # CRITICAL: Enable mesh regions first - this is what loads the geometry
                if hasattr(reader, 'MeshRegions'):
                    try:
                        # Get available mesh regions
                        available_regions = reader.MeshRegions.Available
                        logger.info(f"Available mesh regions: {available_regions}")
                        
                        # Enable all available regions (typically includes internalMesh and patches)
                        reader.MeshRegions = available_regions
                        logger.info(f"Enabled mesh regions: {available_regions}")
                    except Exception as mesh_error:
                        logger.warning(f"Could not configure mesh regions: {mesh_error}")
                        # Fallback: try to enable internalMesh manually
                        try:
                            reader.MeshRegions = ['internalMesh']
                            logger.info("Fallback: Enabled internalMesh region")
                        except:
                            logger.warning("Could not enable internalMesh region")
                
                # Enable field arrays - get all available arrays and enable them
                if hasattr(reader, 'CellArrays'):
                    try:
                        available_cell_arrays = reader.CellArrays.Available
                        logger.info(f"Available cell arrays: {available_cell_arrays}")
                        
                        # Enable all available cell arrays
                        reader.CellArrays = available_cell_arrays
                        logger.info(f"Enabled cell arrays: {available_cell_arrays}")
                    except Exception as cell_error:
                        logger.warning(f"Could not configure cell arrays: {cell_error}")
                        # Fallback: try common OpenFOAM fields
                        try:
                            reader.CellArrays = ['p', 'U', 'phi']
                            logger.info("Fallback: Enabled common cell arrays [p, U, phi]")
                        except:
                            logger.warning("Could not enable common cell arrays")
                
                if hasattr(reader, 'PointArrays'):
                    try:
                        available_point_arrays = reader.PointArrays.Available
                        logger.info(f"Available point arrays: {available_point_arrays}")
                        
                        # Enable all available point arrays
                        reader.PointArrays = available_point_arrays
                        logger.info(f"Enabled point arrays: {available_point_arrays}")
                    except Exception as point_error:
                        logger.warning(f"Could not configure point arrays: {point_error}")
                        # Fallback: try common OpenFOAM fields
                        try:
                            reader.PointArrays = ['p', 'U']
                            logger.info("Fallback: Enabled common point arrays [p, U]")
                        except:
                            logger.warning("Could not enable common point arrays")
                
                # Check available properties before setting them
                if hasattr(reader, 'CreateCellToPoint'):
                    reader.CreateCellToPoint = 1
                    logger.info("Enabled CreateCellToPoint")
                elif hasattr(reader, 'CreateCellToPointOn'):
                    reader.CreateCellToPointOn()
                    logger.info("Enabled CreateCellToPointOn")
                    
                if hasattr(reader, 'ReadZones'):
                    reader.ReadZones = 1
                    logger.info("Enabled ReadZones")
                elif hasattr(reader, 'ReadZonesOn'):
                    reader.ReadZonesOn()
                    logger.info("Enabled ReadZonesOn")
                    
                if hasattr(reader, 'CacheMesh'):
                    reader.CacheMesh = 1
                    logger.info("Enabled CacheMesh")
                elif hasattr(reader, 'CacheMeshOn'):
                    reader.CacheMeshOn()
                    logger.info("Enabled CacheMeshOn")
                    
                # Skip DecomposePolyhedra as it's been removed in newer ParaView versions
                if hasattr(reader, 'DecomposePolyhedra'):
                    try:
                        reader.DecomposePolyhedra = 1
                        logger.info("Enabled DecomposePolyhedra")
                    except:
                        logger.info("DecomposePolyhedra property not available (newer ParaView)")
                elif hasattr(reader, 'DecomposePolyhedraOn'):
                    try:
                        reader.DecomposePolyhedraOn()
                        logger.info("Enabled DecomposePolyhedraOn")
                    except:
                        logger.info("DecomposePolyhedraOn method not available (newer ParaView)")
                    
                # Try to enable time information
                if hasattr(reader, 'RefreshTimes'):
                    reader.RefreshTimes()
                    logger.info("Refreshed time step information")
                    
            except Exception as config_error:
                logger.warning(f"Could not configure reader options: {config_error}")
            
            # Update the pipeline to load data
            logger.info("Updating ParaView pipeline...")
            try:
                # CRITICAL: Force reader to apply all configuration changes
                if hasattr(reader, 'UpdateVTKObjects'):
                    try:
                        reader.UpdateVTKObjects()
                        logger.info("UpdateVTKObjects completed")
                    except Exception as vtk_obj_error:
                        logger.error(f"UpdateVTKObjects failed: {vtk_obj_error}")
                        # Check if this is the connection string bug
                        try:
                            import paraview.servermanager as sm
                            if hasattr(sm, 'ActiveConnection') and sm.ActiveConnection:
                                active_conn_str = str(sm.ActiveConnection)
                                if active_conn_str.count(':') > 2:
                                    logger.error("UpdateVTKObjects failed due to malformed connection string")
                                    raise Exception(f"ParaView connection bug detected: {active_conn_str}")
                        except:
                            pass
                        raise vtk_obj_error
                
                # Force the reader to re-read with new configuration
                if hasattr(reader, 'Modified'):
                    reader.Modified()
                    logger.info("Reader marked as modified")
                    
                # Update the pipeline multiple times to ensure data is loaded
                for attempt in range(3):
                    try:
                        if hasattr(reader, 'UpdatePipeline'):
                            reader.UpdatePipeline()
                            logger.info(f"UpdatePipeline completed (attempt {attempt + 1})")
                        elif hasattr(reader, 'Update'):
                            reader.Update()
                            logger.info(f"Update completed (attempt {attempt + 1})")
                        
                        # Check if we now have data
                        if hasattr(reader, 'GetClientSideObject'):
                            client_obj = reader.GetClientSideObject()
                            if client_obj:
                                test_data = client_obj.GetOutput()
                                if test_data and hasattr(test_data, 'GetNumberOfPoints'):
                                    num_points = test_data.GetNumberOfPoints()
                                    if num_points > 0:
                                        logger.info(f"Pipeline update successful - {num_points} points loaded")
                                        break
                                    else:
                                        logger.info(f"Pipeline update {attempt + 1}: No points yet")
                                else:
                                    logger.info(f"Pipeline update {attempt + 1}: No VTK data yet")
                            else:
                                logger.info(f"Pipeline update {attempt + 1}: No client-side object yet")
                        
                    except Exception as update_error:
                        logger.warning(f"Pipeline update attempt {attempt + 1} failed: {update_error}")
                        
                        # Check if this is the connection string bug on the last attempt
                        if attempt == 2:  # Last attempt
                            logger.warning("All pipeline update attempts failed")
                            try:
                                import paraview.servermanager as sm
                                if hasattr(sm, 'ActiveConnection') and sm.ActiveConnection:
                                    active_conn_str = str(sm.ActiveConnection)
                                    if active_conn_str.count(':') > 2:
                                        logger.error("Pipeline updates failed due to malformed connection string")
                                        raise Exception(f"ParaView connection bug prevents data loading: {active_conn_str}")
                            except:
                                pass
                    
            except Exception as pipeline_error:
                logger.error(f"Pipeline update failed: {pipeline_error}")
                
                # Provide user-friendly error message
                if "ParaView connection bug" in str(pipeline_error):
                    if hasattr(self, 'visualization_area'):
                        self.visualization_area.setText(
                            "Pipeline update failed due to ParaView connection bug.\n\n"
                            f"Error: {str(pipeline_error)}\n\n"
                            "This is a known issue with ParaView 6.0.0.\n"
                            "The connection succeeds but internal operations fail.\n\n"
                            "Recommended solutions:\n"
                            "• Disconnect and reconnect\n"
                            "• Restart the application\n"
                            "• Use ParaView 5.x or 6.1+ if available"
                        )
                else:
                    if hasattr(self, 'visualization_area'):
                        self.visualization_area.setText(
                            f"Failed to update data pipeline.\n\n"
                            f"Error: {str(pipeline_error)}\n\n"
                            "Please check server connection and try again."
                        )
                return
            
            logger.info("Successfully auto-loaded remote OpenFOAM case")
            
            # Update connection status
            self.connection_label.setText(f"Connected - Data loaded from {self.project_name}")
            self.connection_label.setStyleSheet("color: green; font-weight: bold;")
            
            # Setup time steps and fields (works regardless of embedded rendering availability)
            self.setup_time_steps()
            self.create_field_buttons()
            
            # Calculate global field ranges across all time steps for consistent color scaling
            self.calculate_global_field_ranges()
            
            # Try to display the data using embedded VTK
            try:
                # Get VTK data from the reader (ParaView 6.0.0 compatible)
                logger.info("Getting VTK data from reader...")
                vtk_data = None
                
                # CRITICAL FIX: Use servermanager.Fetch() to bring server data to client
                logger.info("Attempting to fetch server data to client for embedded rendering...")
                try:
                    import paraview.servermanager as sm
                    
                    # Force data transfer from server to client
                    vtk_data = sm.Fetch(reader)
                    if vtk_data:
                        logger.info(f"✅ Successfully fetched data from server: {vtk_data.GetClassName()} with {vtk_data.GetNumberOfPoints() if hasattr(vtk_data, 'GetNumberOfPoints') else 'N/A'} points")
                        print(f"🎯 BREAKTHROUGH: Data fetched from server to client!")
                        print(f"   Data type: {vtk_data.GetClassName()}")
                        if hasattr(vtk_data, 'GetNumberOfPoints'):
                            print(f"   Points: {vtk_data.GetNumberOfPoints()}")
                        if hasattr(vtk_data, 'GetNumberOfCells'):
                            print(f"   Cells: {vtk_data.GetNumberOfCells()}")
                    else:
                        logger.warning("servermanager.Fetch() returned None")
                        
                except Exception as fetch_error:
                    logger.warning(f"servermanager.Fetch() failed: {fetch_error}")
                    print(f"⚠️ Fetch failed: {fetch_error}")
                
                # FALLBACK: Try the original methods if Fetch() failed
                if not vtk_data:
                    logger.info("Fetch failed, trying original methods...")
                    
                    # Method 1: Try GetClientSideObject (preferred for embedded rendering)
                    if hasattr(reader, 'GetClientSideObject'):
                        try:
                            client_side_obj = reader.GetClientSideObject()
                            if client_side_obj:
                                vtk_data = client_side_obj.GetOutput()
                                logger.info("Got VTK data via GetClientSideObject")
                            else:
                                logger.warning("GetClientSideObject returned None - reader may not have loaded data yet")
                        except Exception as client_error:
                            logger.warning(f"GetClientSideObject failed: {client_error}")
                    
                    # Method 2: Try GetOutputData if GetClientSideObject failed
                    if not vtk_data and hasattr(reader, 'GetOutputData'):
                        try:
                            vtk_data = reader.GetOutputData(0)
                            logger.info("Got VTK data via GetOutputData")
                        except Exception as output_data_error:
                            logger.warning(f"GetOutputData failed: {output_data_error}")
                            
                    # Method 3: Fall back to older API
                    if not vtk_data and hasattr(reader, 'GetOutput'):
                        try:
                            vtk_data = reader.GetOutput()
                            logger.info("Got VTK data via GetOutput")
                        except Exception as output_error:
                            logger.warning(f"GetOutput failed: {output_error}")
                    
                    # Method 4: If all direct methods fail, try using ParaView's standard pipeline
                    if not vtk_data:
                        logger.info("Direct VTK data access failed - trying ParaView visualization pipeline")
                        try:
                            # Use ParaView's standard visualization approach
                            from paraview.simple import Show, GetActiveView, CreateRenderView
                            
                            # Get or create a view
                            view = GetActiveView()
                            if not view:
                                view = CreateRenderView()
                            
                            # Show the data in the view (this forces data loading)
                            display = Show(reader, view)
                            
                            # Try to fetch after showing
                            try:
                                vtk_data = sm.Fetch(reader)
                                if vtk_data:
                                    logger.info("Got VTK data via ParaView pipeline + Fetch")
                                    print("🎯 SUCCESS: Pipeline + Fetch worked!")
                                else:
                                    logger.warning("Pipeline + Fetch still returned None")
                            except Exception as pipeline_fetch_error:
                                logger.warning(f"Pipeline + Fetch failed: {pipeline_fetch_error}")
                            
                            # Final fallback - try GetClientSideObject again after showing
                            if not vtk_data and hasattr(reader, 'GetClientSideObject'):
                                client_side_obj = reader.GetClientSideObject()
                                if client_side_obj:
                                    vtk_data = client_side_obj.GetOutput()
                                    logger.info("Got VTK data via ParaView pipeline + GetClientSideObject")
                            
                            # If we still don't have VTK data, we can at least confirm the reader is working
                            if not vtk_data:
                                logger.info("All methods failed - data stays on server")
                                logger.info("Data should be visible in remote ParaView server")
                                
                                # Update the embedded widget area to show status
                                if hasattr(self, 'visualization_area'):
                                    self.visualization_area.setText(
                                        "Remote ParaView server connected successfully!\n\n"
                                        "Visualization is available in separate ParaView window.\n\n"
                                        "Features available:\n"
                                        "• Time step navigation with Time Controls\n"
                                        "• Field visualization with Field buttons\n"
                                        "• Full ParaView functionality in separate window\n\n"
                                        "Note: Embedded visualization not available due to\n"
                                        "client-server data transfer limitations.\n"
                                        "This is normal for remote ParaView connections."
                                    )
                                
                        except Exception as pipeline_error:
                            logger.warning(f"ParaView visualization pipeline failed: {pipeline_error}")
                
                # Verify and display the data if we got it
                if vtk_data and hasattr(vtk_data, 'GetNumberOfPoints'):
                    num_points = vtk_data.GetNumberOfPoints()
                    num_cells = vtk_data.GetNumberOfCells() if hasattr(vtk_data, 'GetNumberOfCells') else 0
                    
                    logger.info(f"Successfully loaded VTK data: {num_points} points, {num_cells} cells")
                    
                    if num_points > 0 or num_cells > 0:
                        self._display_vtk_data(vtk_data)
                        logger.info("Mesh visualization loaded successfully")
                    else:
                        logger.info("VTK data object exists but contains no geometry")
                else:
                    logger.warning("No VTK data available for embedded rendering")
                    logger.info("Reader configured successfully - data should be visible via remote ParaView connection")
                    
            except Exception as display_error:
                logger.warning(f"Auto-display failed: {display_error}")
                logger.info("Reader created successfully. Use field buttons to visualize data when available.")
                
                # Ensure field buttons are available even if embedded rendering failed
                if not hasattr(self, 'available_fields') or not self.available_fields:
                    print("🔄 Creating field buttons from reader properties after display failure")
                    self.create_field_buttons()
            
            self.visualization_loaded.emit(foam_file_path)
            
        except Exception as e:
            logger.error(f"Auto-load failed with error: {str(e)}")
            import traceback
            logger.error(f"Auto-load traceback: {traceback.format_exc()}")
            logger.info("Case structure created. Use field buttons when simulation data is available.")
    
    def _verify_paraview_connection(self):
        """Verify that ParaView connection is ready for data operations (6.0.0 compatible)."""
        try:
            # Try newer API first
            try:
                from paraview.simple import GetActiveConnection
                active_connection = GetActiveConnection()
                if active_connection:
                    if hasattr(active_connection, 'Session') and active_connection.Session:
                        logger.info("ParaView connection and session verified (new API)")
                        return True
                    else:
                        logger.warning("ParaView connection exists but session is not ready (new API)")
                        return False
                else:
                    logger.warning("No active ParaView connection (new API)")
                    return False
            except ImportError:
                # Fall back to ParaView 6.0.0 compatible API
                logger.info("Using ParaView 6.0.0 compatible connection verification")
                import paraview.servermanager as sm
                
                if hasattr(sm, 'ActiveConnection') and sm.ActiveConnection:
                    logger.info("ParaView connection verified (6.0.0 compatible)")
                    return True
                else:
                    logger.warning("No active ParaView connection (6.0.0 compatible)")
                    return False
                    
        except Exception as e:
            logger.error(f"ParaView connection verification failed: {e}")
            return False
    
    def disconnect_from_remote_server(self):
        """Disconnect from remote ParaView server with comprehensive cleanup."""
        try:
            logger.info("Starting comprehensive disconnection and cleanup...")
            
            # COMPREHENSIVE CLEANUP - Clear all ParaView state first
            self._comprehensive_paraview_cleanup()
            
            # Disconnect from ParaView
            if PARAVIEW_AVAILABLE and self.connected:
                try:
                    pv.Disconnect()
                    logger.info("Disconnected from remote ParaView server")
                except Exception as disconnect_error:
                    logger.warning(f"ParaView disconnect failed: {disconnect_error}")
                
                self.connected = False
            
            # Clear all internal state
            self._clear_internal_state()
            
            # Clear VTK rendering resources
            self._clear_vtk_resources()
            
            # Always stop the remote server without asking user
            if self.server_url and self.project_name:
                logger.info("Stopping remote ParaView server via API...")
                try:
                    self._stop_remote_pvserver()
                except Exception as e:
                    logger.warning(f"Failed to stop remote server via API: {e}")
                    # Fallback to old method if available
                    if REMOTE_PARAVIEW_AVAILABLE:
                        try:
                            result = stop_remote_paraview_server(self.server_url, self.project_name)
                            if "error" in result:
                                logger.warning(f"Fallback stop failed: {result['error']}")
                            else:
                                logger.info("Remote ParaView server stopped via fallback")
                        except Exception as fallback_error:
                            logger.warning(f"Fallback stop also failed: {fallback_error}")
            
            # Update UI
            self.connection_label.setText("Disconnected from remote ParaView server")
            self.connection_label.setStyleSheet("color: orange; font-weight: bold;")
            
            if hasattr(self, 'connect_btn'):
                self.connect_btn.setText("Connect to Remote ParaView Server")
                self.connect_btn.setEnabled(True)
            
            if hasattr(self, 'disconnect_btn'):
                self.disconnect_btn.setEnabled(False)
            
            # Emit connection status signal
            self.connection_status_changed.emit(False)
            
            self.disable_controls()
            self.remote_paraview_info = None
            
            logger.info("Comprehensive disconnection and cleanup completed")
            
        except Exception as e:
            error_msg = f"Error disconnecting from remote server: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error(f"Disconnect error traceback: {traceback.format_exc()}")
            QMessageBox.warning(self, "Warning", error_msg)
    
    def _comprehensive_paraview_cleanup(self):
        """Comprehensive ParaView state cleanup to prevent resource accumulation."""
        try:
            logger.info("Performing comprehensive ParaView cleanup...")
            
            if not PARAVIEW_AVAILABLE:
                return
            
            from paraview.simple import GetSources, Delete, GetViews
            import paraview.servermanager as sm
            
            # Clear all ParaView sources
            try:
                sources = GetSources()
                if sources:
                    logger.info(f"Deleting {len(sources)} ParaView sources...")
                    for source_key, source in sources.items():
                        try:
                            Delete(source)
                            logger.debug(f"Deleted source: {source_key}")
                        except Exception as source_error:
                            logger.warning(f"Failed to delete source {source_key}: {source_error}")
                else:
                    logger.info("No ParaView sources to delete")
            except Exception as sources_error:
                logger.warning(f"Failed to cleanup ParaView sources: {sources_error}")
            
            # Clear all ParaView views (except our current one if using server-side rendering)
            try:
                views = GetViews()
                if views:
                    logger.info(f"Found {len(views)} ParaView views")
                    # Keep only essential views, delete others
                    views_to_delete = []
                    for view in views:
                        # Only delete views that aren't essential for our operation
                        if hasattr(view, 'GetClassName') and 'RenderView' in view.GetClassName():
                            views_to_delete.append(view)
                    
                    for view in views_to_delete:
                        try:
                            Delete(view)
                            logger.debug(f"Deleted ParaView view: {view}")
                        except Exception as view_error:
                            logger.warning(f"Failed to delete view: {view_error}")
                else:
                    logger.info("No ParaView views found")
            except Exception as views_error:
                logger.warning(f"Failed to cleanup ParaView views: {views_error}")
            
            # Force garbage collection in ParaView
            try:
                if hasattr(sm, 'vtkProcessModule'):
                    process_module = sm.vtkProcessModule.GetProcessModule()
                    if process_module:
                        process_module.GetGlobalController().TriggerRMIOnAllChildren()
                        logger.info("Triggered ParaView garbage collection")
            except Exception as gc_error:
                logger.warning(f"Failed to trigger ParaView garbage collection: {gc_error}")
            
            logger.info("ParaView cleanup completed")
            
        except Exception as e:
            logger.warning(f"Comprehensive ParaView cleanup failed: {e}")
    
    def _clear_internal_state(self):
        """Clear all internal widget state."""
        try:
            logger.info("Clearing internal widget state...")
            
            # Clear data source references
            self.current_source = None
            
            # Clear time step data
            self.time_steps = []
            self.time_directories = []
            if hasattr(self, '_current_time_step'):
                delattr(self, '_current_time_step')
            if hasattr(self, '_foam_file_path'):
                delattr(self, '_foam_file_path')
            
            # Clear field data
            self.field_buttons = {}
            self.available_fields = []
            self.current_field = None
            
            # Clear global field ranges
            self.global_field_ranges = {}
            
            # Clear camera state
            if hasattr(self, '_saved_camera_position'):
                delattr(self, '_saved_camera_position')
            if hasattr(self, '_saved_camera_focal_point'):
                delattr(self, '_saved_camera_focal_point')
            if hasattr(self, '_saved_camera_view_up'):
                delattr(self, '_saved_camera_view_up')
            
            # Stop any running animations
            if hasattr(self, 'is_playing') and self.is_playing:
                self.pause_playback()
            
            # Clear connection state flags
            self.connected = False
            
            logger.info("Internal state cleared")
            
        except Exception as e:
            logger.warning(f"Failed to clear internal state: {e}")
    
    def _clear_vtk_resources(self):
        """Clear VTK rendering resources and actors."""
        try:
            logger.info("Clearing VTK rendering resources...")
            
            if not VTK_AVAILABLE or not hasattr(self, 'renderer') or not self.renderer:
                logger.info("No VTK renderer to clear")
                return
            
            # Clear all actors from renderer
            try:
                self.renderer.RemoveAllViewProps()
                logger.info("Removed all VTK view props from renderer")
            except Exception as props_error:
                logger.warning(f"Failed to remove view props: {props_error}")
            
            # Clear all 2D actors (color bars, etc.)
            try:
                actors_2d = self.renderer.GetActors2D()
                if actors_2d:
                    actors_2d.InitTraversal()
                    actors_to_remove = []
                    for i in range(actors_2d.GetNumberOfItems()):
                        actor = actors_2d.GetNextItem()
                        if actor:
                            actors_to_remove.append(actor)
                    
                    for actor in actors_to_remove:
                        self.renderer.RemoveActor2D(actor)
                    
                    logger.info(f"Removed {len(actors_to_remove)} 2D actors")
            except Exception as actors_2d_error:
                logger.warning(f"Failed to clear 2D actors: {actors_2d_error}")
            
            # Reset camera to default position
            try:
                self.renderer.ResetCamera()
                logger.info("Reset VTK camera")
            except Exception as camera_error:
                logger.warning(f"Failed to reset camera: {camera_error}")
            
            # Force render to clear the view
            try:
                if hasattr(self, 'vtk_widget') and self.vtk_widget:
                    self.vtk_widget.GetRenderWindow().Render()
                    logger.info("Cleared VTK render window")
            except Exception as render_error:
                logger.warning(f"Failed to clear render window: {render_error}")
            
            # Force VTK garbage collection
            try:
                import gc
                gc.collect()
                logger.info("Triggered Python garbage collection")
            except Exception as gc_error:
                logger.warning(f"Failed to trigger garbage collection: {gc_error}")
            
            logger.info("VTK resources cleared")
            
        except Exception as e:
            logger.warning(f"Failed to clear VTK resources: {e}")
    
    def handle_connect_request(self, server_url: str, project_name: str):
        """Handle connection request from simulation setup widget."""
        logger.info(f"ParaView connection requested for server: {server_url}, project: {project_name}")
        
        # Set remote server configuration
        self.set_remote_server(server_url, project_name)
        
        # Check if PVServer is already running for this project
        try:
            server_status = self._check_remote_pvserver_status()
            if server_status.get("status") != "running":
                logger.info("PVServer not running, starting it via API...")
                self._start_remote_pvserver()
            else:
                logger.info("PVServer already running, connecting to it...")
        except Exception as e:
            logger.error(f"Failed to check/start PVServer: {e}")
        
        # Connect to the server
        self.connect_to_remote_server()
    
    def handle_disconnect_request(self):
        """Handle disconnection request from simulation setup widget."""
        logger.info("ParaView disconnection requested")
        
        if self.server_url and self.project_name:
            self.disconnect_from_remote_server()
        else:
            self.disconnect_from_server()
    
    def _start_remote_pvserver(self):
        """Start a remote ParaView server via API"""
        if not self.server_url or not self.project_name:
            logger.error("Cannot start PVServer: missing server URL or project name")
            return False
        
        try:
            import requests
            from urllib.parse import urlparse, urljoin
            
            # Extract base URL from server_url
            parsed_url = urlparse(self.server_url)
            api_base = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # Call the API endpoint to start PVServer
            api_url = urljoin(api_base, f"/api/projects/{self.project_name}/pvserver/start")
            response = requests.post(api_url, json={}, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"PVServer started successfully: {result}")
                return True
            else:
                logger.error(f"Failed to start PVServer: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting PVServer via API: {e}")
            return False
    
    def _stop_remote_pvserver(self):
        """Stop a remote ParaView server via API"""
        if not self.server_url or not self.project_name:
            logger.error("Cannot stop PVServer: missing server URL or project name")
            return False
        
        try:
            import requests
            from urllib.parse import urlparse, urljoin
            
            # Extract base URL from server_url
            parsed_url = urlparse(self.server_url)
            api_base = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # Call the API endpoint to stop PVServer
            api_url = urljoin(api_base, f"/api/projects/{self.project_name}/pvserver/stop")
            response = requests.delete(api_url, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"PVServer stopped successfully: {result}")
                return True
            else:
                logger.error(f"Failed to stop PVServer: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error stopping PVServer via API: {e}")
            return False
    
    def handle_load_mesh_request(self, file_path: str):
        """Handle mesh loading request from simulation setup widget."""
        logger.info(f"ParaView mesh loading requested: {file_path}")
        
        if self.connected:
            self.load_foam_file(file_path)
        else:
            logger.warning("ParaView not connected, cannot load mesh")
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(self.get_responsive_spacing(10))
        layout.setContentsMargins(
            self.get_responsive_spacing(10),
            self.get_responsive_spacing(5),
            self.get_responsive_spacing(10),
            self.get_responsive_spacing(5)
        )
        
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
        
        # Header with connection status and controls
        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(5, 5, 5, 5)
        header_layout.setSpacing(10)
        
        # Connection status
        if VTK_QT_AVAILABLE and QVTKRenderWindowInteractor:
            if PARAVIEW_AVAILABLE:
                self.connection_label = QLabel("VTK + ParaView available")
            else:
                self.connection_label = QLabel("Embedded VTK ready")
            self.connection_label.setStyleSheet("color: orange; font-weight: bold; font-size: 11px;")
        elif PARAVIEW_AVAILABLE:
            self.connection_label = QLabel("ParaView server mode")
            self.connection_label.setStyleSheet("color: orange; font-weight: bold; font-size: 11px;")
        else:
            self.connection_label = QLabel("Visualization not available")
            self.connection_label.setStyleSheet("color: red; font-weight: bold; font-size: 11px;")
        
        header_layout.addWidget(self.connection_label)
        header_layout.addStretch()
        
        # Connection controls in header (moved from bottom to save space)
        if hasattr(self, 'server_url') and self.server_url and hasattr(self, 'project_name') and self.project_name:
            button_text = "Connect to Remote"
        elif VTK_QT_AVAILABLE:
            if PARAVIEW_AVAILABLE:
                button_text = "Connect to Server"
            else:
                button_text = "Initialize"
        elif PARAVIEW_AVAILABLE:
            button_text = "Connect to Server"
        else:
            button_text = "Not Available"
            
        self.connect_btn = QPushButton(button_text)
        self.connect_btn.setMaximumHeight(25)
        self.connect_btn.setStyleSheet("font-size: 10px; padding: 4px 8px;")
        
        if not (VTK_QT_AVAILABLE or PARAVIEW_AVAILABLE):
            self.connect_btn.setEnabled(False)
            
        self.connect_btn.clicked.connect(self.connect_to_server)
        header_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setMaximumHeight(25)
        self.disconnect_btn.setStyleSheet("font-size: 10px; padding: 4px 8px;")
        self.disconnect_btn.clicked.connect(self.disconnect_from_server)
        self.disconnect_btn.setEnabled(False)
        header_layout.addWidget(self.disconnect_btn)
        
        layout.addWidget(header_frame)
        
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
                
                # Use responsive minimum size
                min_width, min_height = self.get_responsive_visualization_size()
                self.vtk_widget.setMinimumSize(min_width, min_height)
                
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
                
                # Use responsive minimum size
                min_width, min_height = self.get_responsive_visualization_size()
                self.visualization_area.setMinimumSize(min_width, min_height)
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
                
                # Use responsive minimum size
                min_width, min_height = self.get_responsive_visualization_size()
                self.visualization_area.setMinimumSize(min_width, min_height)
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
        # Visualization controls group (more compact)
        viz_group = QGroupBox("Fields")
        viz_layout = QVBoxLayout(viz_group)
        viz_layout.setSpacing(self.get_responsive_spacing(5))
        viz_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create a label to show current field info (more compact)
        self.field_info_label = QLabel("No fields detected")
        font_size = 9 if self.get_screen_height_class() == "small" else 10
        self.field_info_label.setStyleSheet(f"color: gray; font-style: italic; font-size: {font_size}px;")
        viz_layout.addWidget(self.field_info_label)
        
        # Create a container for dynamic field buttons (always visible as requested)
        self.field_buttons_container = QWidget()
        self.field_buttons_layout = QGridLayout(self.field_buttons_container)
        self.field_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.field_buttons_layout.setSpacing(3)  # Tighter spacing for buttons
        
        # Add the dynamic field buttons container
        viz_layout.addWidget(self.field_buttons_container)
        
        # Store field buttons for later management
        self.field_buttons = {}
        self.available_fields = []
        self.current_field = None  # Track currently selected field
        
        layout.addWidget(viz_group)
        
        # Enhanced time controls group (more compact)
        time_group = QGroupBox("Time Controls")
        time_layout = QVBoxLayout(time_group)
        time_layout.setSpacing(self.get_responsive_spacing(5))
        time_layout.setContentsMargins(5, 5, 5, 5)
        
        # Main time controls in compact layout
        time_controls_layout = QHBoxLayout()
        time_controls_layout.setSpacing(3)  # Tighter spacing
        
        # Get Qt style for standard icons
        style = self.style()
        
        # Responsive button size
        button_size = 30 if self.get_screen_height_class() != "small" else 25
        
        # First frame button
        self.first_frame_btn = QPushButton()
        self.first_frame_btn.setIcon(style.standardIcon(QStyle.SP_MediaSkipBackward))
        self.first_frame_btn.clicked.connect(self.first_time_step)
        self.first_frame_btn.setEnabled(False)
        self.first_frame_btn.setToolTip("Go to first time step")
        self.first_frame_btn.setMaximumSize(button_size, button_size)
        time_controls_layout.addWidget(self.first_frame_btn)
        
        # Previous frame button  
        self.prev_time_btn = QPushButton()
        self.prev_time_btn.setIcon(style.standardIcon(QStyle.SP_MediaSeekBackward))
        self.prev_time_btn.clicked.connect(self.previous_time_step)
        self.prev_time_btn.setEnabled(False)
        self.prev_time_btn.setToolTip("Previous time step")
        self.prev_time_btn.setMaximumSize(button_size, button_size)
        time_controls_layout.addWidget(self.prev_time_btn)
        
        # Play/Pause button
        self.play_pause_btn = QPushButton()
        self.play_pause_btn.setIcon(style.standardIcon(QStyle.SP_MediaPlay))
        self.play_pause_btn.clicked.connect(self.play_pause_toggle)
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.setToolTip("Play/Pause animation")
        self.play_pause_btn.setMaximumSize(button_size, button_size)
        time_controls_layout.addWidget(self.play_pause_btn)
        
        # Next frame button
        self.next_time_btn = QPushButton()
        self.next_time_btn.setIcon(style.standardIcon(QStyle.SP_MediaSeekForward))
        self.next_time_btn.clicked.connect(self.next_time_step)
        self.next_time_btn.setEnabled(False)
        self.next_time_btn.setToolTip("Next time step")
        self.next_time_btn.setMaximumSize(button_size, button_size)
        time_controls_layout.addWidget(self.next_time_btn)
        
        # Last frame button
        self.last_frame_btn = QPushButton()
        self.last_frame_btn.setIcon(style.standardIcon(QStyle.SP_MediaSkipForward))
        self.last_frame_btn.clicked.connect(self.last_time_step)
        self.last_frame_btn.setEnabled(False)
        self.last_frame_btn.setToolTip("Go to last time step")
        self.last_frame_btn.setMaximumSize(button_size, button_size)
        time_controls_layout.addWidget(self.last_frame_btn)
        
        # Time slider
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.valueChanged.connect(self.set_time_step)
        self.time_slider.setEnabled(False)
        self.time_slider.setMaximumHeight(button_size)
        time_controls_layout.addWidget(self.time_slider)
        
        # Time label (more compact)
        self.time_label = QLabel("Time: 0.0")
        label_width = 60 if self.get_screen_height_class() == "small" else 80
        font_size = 9 if self.get_screen_height_class() == "small" else 10
        self.time_label.setMinimumWidth(label_width)
        self.time_label.setStyleSheet(f"font-size: {font_size}px;")
        time_controls_layout.addWidget(self.time_label)
        
        time_layout.addLayout(time_controls_layout)
        
        # Compact playback settings (only show on medium/large screens, or make very compact on small)
        height_class = self.get_screen_height_class()
        if height_class != "small":  # Only show full settings on medium/large screens
            playback_settings_layout = QHBoxLayout()
            playback_settings_layout.setSpacing(5)
            
            # Speed control
            speed_label = QLabel("Speed:")
            speed_label.setStyleSheet(f"font-size: {9 if height_class == 'medium' else 10}px;")
            playback_settings_layout.addWidget(speed_label)
            
            self.speed_control = QDoubleSpinBox()
            self.speed_control.setRange(0.1, 2.0)
            self.speed_control.setValue(1.0)
            self.speed_control.setSingleStep(0.1)
            self.speed_control.setSuffix(" s/frame")
            self.speed_control.setToolTip("Animation speed in seconds per frame")
            self.speed_control.setMaximumWidth(100)
            self.speed_control.setMaximumHeight(button_size)
            self.speed_control.valueChanged.connect(self.update_playback_speed)
            playback_settings_layout.addWidget(self.speed_control)
            
            # Loop checkbox
            self.loop_checkbox = QCheckBox("Loop")
            self.loop_checkbox.setChecked(False)
            self.loop_checkbox.setToolTip("Loop animation when it reaches the end")
            self.loop_checkbox.setStyleSheet(f"font-size: {9 if height_class == 'medium' else 10}px;")
            playback_settings_layout.addWidget(self.loop_checkbox)
            
            # Add stretch to push controls to the left
            playback_settings_layout.addStretch()
            
            time_layout.addLayout(playback_settings_layout)
        else:
            # For small screens, create minimal speed/loop controls inline
            compact_settings_layout = QHBoxLayout()
            compact_settings_layout.setSpacing(3)
            
            self.speed_control = QDoubleSpinBox()
            self.speed_control.setRange(0.1, 2.0)
            self.speed_control.setValue(1.0)
            self.speed_control.setSingleStep(0.1)
            self.speed_control.setSuffix("s")
            self.speed_control.setToolTip("Speed in seconds per frame")
            self.speed_control.setMaximumWidth(70)
            self.speed_control.setMaximumHeight(20)
            self.speed_control.valueChanged.connect(self.update_playback_speed)
            compact_settings_layout.addWidget(self.speed_control)
            
            self.loop_checkbox = QCheckBox("Loop")
            self.loop_checkbox.setChecked(False)
            self.loop_checkbox.setStyleSheet("font-size: 8px;")
            compact_settings_layout.addWidget(self.loop_checkbox)
            
            compact_settings_layout.addStretch()
            
            time_layout.addLayout(compact_settings_layout)
        
        # Initialize playback system
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.advance_frame)
        self.is_playing = False
        
        layout.addWidget(time_group)
    
    def connect_to_server(self):
        """Connect to visualization (remote server, embedded VTK, or ParaView server)"""
        # Priority 1: Check if remote server is configured
        if self.server_url and self.project_name and REMOTE_PARAVIEW_AVAILABLE:
            logger.info(f"Remote server configured - connecting to {self.server_url}")
            self.connect_to_remote_server()
            return
        
        # Priority 2: Check if no visualization system available
        if not PARAVIEW_AVAILABLE and not VTK_QT_AVAILABLE:
            self.show_error("No visualization system available")
            return
        
        # Priority 3: Use embedded VTK or local ParaView
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
                
                logger.info(f"Connecting to local ParaView server at {host}:{port}")
                
                # Connect to pvserver using lower-level API to avoid automatic view creation
                try:
                    import paraview.servermanager as sm
                    
                    # Connect without creating default views
                    if not sm.ActiveConnection:
                        connection = sm.Connect(host, port)
                        logger.info("Connected to local ParaView server using servermanager")
                    else:
                        logger.info("Using existing local ParaView server connection")
                    
                    # Only create render view as fallback if embedded VTK is not available
                    if not self.use_embedded_vtk:
                        # For fallback only - when no embedded VTK is available
                        from paraview.simple import CreateRenderView
                        self.current_view = CreateRenderView()
                        logger.info("Created fallback render view for local ParaView server")
                    else:
                        logger.info("Using embedded VTK widget for local ParaView server data - no render view needed")
                    
                    self.connected = True
                    self.connection_label.setText(f"Connected to local ParaView server ({host}:{port})")
                    self.connection_label.setStyleSheet("color: green; font-weight: bold;")
                    
                    logger.info("Successfully connected to local ParaView server")
                    
                except Exception as e:
                    logger.error(f"Failed to connect with servermanager: {str(e)}")
                    # Fallback to simple Connect
                    try:
                        Connect(host, port)
                        logger.info("Connected using paraview.simple fallback")
                        
                        self.connected = True
                        self.connection_label.setText(f"Connected to local ParaView server ({host}:{port})")
                        self.connection_label.setStyleSheet("color: green; font-weight: bold;")
                        
                    except Exception as e2:
                        logger.error(f"Both local connection methods failed: {str(e2)}")
                        raise e2
                
            else:
                self.show_error("No visualization system available")
                return
            
            # Update button states for successful connection
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            
            # Emit connection status signal
            self.connection_status_changed.emit(True)
            
        except Exception as e:
            logger.error(f"Failed to initialize visualization: {str(e)}")
            self.show_error(f"Failed to initialize visualization: {str(e)}")
            self.connected = False
    
    def disconnect_from_server(self):
        """Disconnect from visualization (remote server, embedded VTK, or local ParaView)"""
        # Priority 1: Check if using remote server
        if self.server_url and self.project_name and REMOTE_PARAVIEW_AVAILABLE:
            logger.info("Disconnecting from remote server")
            self.disconnect_from_remote_server()
            return
        
        # Priority 2: Handle local/embedded disconnection
        try:
            if self.use_embedded_vtk and hasattr(self, 'renderer') and self.renderer:
                # Clear embedded VTK renderer
                self.renderer.RemoveAllViewProps()
                if self.vtk_widget:
                    self.vtk_widget.GetRenderWindow().Render()
                logger.info("Cleared embedded VTK rendering")
                
            elif PARAVIEW_AVAILABLE:
                # Disconnect from local ParaView server
                try:
                    import paraview.servermanager as sm
                    
                    # Clean up render view if it exists
                    if hasattr(self, 'current_view') and self.current_view:
                        # Import here to avoid automatic view creation
                        from paraview.simple import Delete
                        Delete(self.current_view)
                        self.current_view = None
                        logger.info("Cleaned up local ParaView render view")
                    
                    # Disconnect from server
                    if sm.ActiveConnection:
                        sm.Disconnect()
                        logger.info("Disconnected from local ParaView server using servermanager")
                    else:
                        logger.info("No active local ParaView connection to disconnect")
                        
                except Exception as e:
                    logger.error(f"Error disconnecting via servermanager: {str(e)}")
                    # Fallback to simple Disconnect
                    try:
                        Disconnect()
                        logger.info("Disconnected using paraview.simple fallback")
                    except Exception as e2:
                        logger.error(f"Both disconnect methods failed: {str(e2)}")
                
                logger.info("Disconnected from local ParaView server")
            
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
            
            # Update connection status based on available systems
            if VTK_QT_AVAILABLE:
                self.connection_label.setText("Embedded VTK rendering ready")
            elif PARAVIEW_AVAILABLE:
                self.connection_label.setText("ParaView server mode - connect to view")
            else:
                self.connection_label.setText("Visualization not available")
                
            self.connection_label.setStyleSheet("color: orange; font-weight: bold;")
            
            # Update button states
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            
            # Emit connection status signal
            self.connection_status_changed.emit(False)
            
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
        if not self.current_source:
            print("⚠️ No data source available")
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
            
            # Try embedded rendering first
            if hasattr(self, 'renderer') and self.renderer:
                print("🎯 Attempting embedded VTK rendering...")
                
                # Clear current visualization
                self.renderer.RemoveAllViewProps()
                
                # Save current camera position
                try:
                    camera = self.renderer.GetActiveCamera()
                    self._saved_camera_position = camera.GetPosition()
                    self._saved_camera_focal_point = camera.GetFocalPoint()
                    self._saved_camera_view_up = camera.GetViewUp()
                except Exception as cam_error:
                    print(f"⚠️ Could not save camera position: {cam_error}")
                    self._saved_camera_position = None
                
                # Get VTK data - try Fetch() first for server data
                vtk_data = None
                
                # CRITICAL: Use Fetch() to get server data for embedded rendering
                try:
                    import paraview.servermanager as sm
                    self.current_source.UpdatePipeline()
                    vtk_data = sm.Fetch(self.current_source)
                    if vtk_data:
                        print(f"✅ Fetched VTK data for field rendering: {vtk_data.GetClassName()}")
                        if hasattr(vtk_data, 'GetNumberOfPoints'):
                            print(f"   Points: {vtk_data.GetNumberOfPoints()}")
                    else:
                        print("⚠️ Fetch() returned None for field rendering")
                except Exception as fetch_error:
                    print(f"⚠️ Fetch() failed for field rendering: {fetch_error}")
                
                # FALLBACK: Try original methods if Fetch() failed
                if not vtk_data:
                    if hasattr(self.current_source, 'GetClientSideObject'):
                        # ParaView server source
                        try:
                            self.current_source.UpdatePipeline()
                            client_side_obj = self.current_source.GetClientSideObject()
                            if client_side_obj:
                                vtk_data = client_side_obj.GetOutput()
                                print("✅ Got VTK data via GetClientSideObject for embedded rendering")
                        except Exception as e:
                            print(f"⚠️ GetClientSideObject failed: {e}")
                    elif hasattr(self.current_source, 'GetOutput'):
                        # Direct VTK source
                        try:
                            self.current_source.Update()
                            vtk_data = self.current_source.GetOutput()
                            print("✅ Got VTK data via GetOutput for embedded rendering")
                        except Exception as e:
                            print(f"⚠️ GetOutput failed: {e}")
                
                if vtk_data:
                    # Display with specific field in embedded widget
                    self._display_vtk_data_with_field(vtk_data, field_info)
                    print(f"✅ Successfully displayed field in embedded widget: {field_info['display_name']}")
                    return
                else:
                    print("⚠️ No VTK data available for embedded rendering, falling back to ParaView server visualization")
            
            # FALLBACK: Use ParaView server-side visualization
            print("🔄 Using ParaView server-side field visualization...")
            self._show_field_server_side(field_name, field_info)
            
        except Exception as e:
            print(f"❌ Error showing field {field_name}: {e}")
            import traceback
            traceback.print_exc()
    
    def _show_field_server_side(self, field_name: str, field_info):
        """Show field using ParaView server-side visualization (for remote connections)"""
        try:
            from paraview.simple import Show, Hide, ColorBy, GetActiveView, CreateRenderView, GetDisplayProperties, GetScalarBar, Render
            
            # Get or create a ParaView view
            view = GetActiveView()
            if not view:
                print("🔧 Creating ParaView render view for server-side visualization")
                view = CreateRenderView()
            
            # Show the data in the view
            display = Show(self.current_source, view)
            
            # Set up field coloring
            if field_info['type'] == 'cell':
                print(f"🎨 Setting cell field coloring: {field_name}")
                ColorBy(display, ('CELLS', field_name))
            elif field_info['type'] == 'point':
                print(f"🎨 Setting point field coloring: {field_name}")
                ColorBy(display, ('POINTS', field_name))
            
            # Try to get and show color bar
            try:
                scalar_bar = GetScalarBar(field_name, view)
                if scalar_bar:
                    scalar_bar.Title = field_info['display_name']
                    scalar_bar.Visibility = 1
                    print(f"🎨 Color bar configured for {field_info['display_name']}")
            except Exception as bar_error:
                print(f"⚠️ Could not configure color bar: {bar_error}")
            
            # Render the view
            Render(view)
            
            print(f"✅ Server-side visualization updated with field: {field_info['display_name']}")
            
            # Update the embedded widget area to show information
            if hasattr(self, 'visualization_area'):
                self.visualization_area.setText(
                    f"Field visualization: {field_info['display_name']}\n\n"
                    f"Visualization is shown in separate ParaView window.\n\n"
                    f"Field: {field_name} ({field_info['type']} data)\n"
                    f"To enable embedded visualization:\n"
                    f"• Ensure stable network connection\n"
                    f"• Check server OpenGL configuration"
                )
            
        except Exception as e:
            print(f"❌ Server-side field visualization failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _display_vtk_data_with_field(self, vtk_data, field_info):
        """Display VTK data with specific field coloring"""
        try:
            from .paraview_widget import VTK_AVAILABLE, vtk
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
            
            # Get data range - use global range for consistent coloring across time steps
            local_range = field_array.GetRange()
            field_name = field_info['name']
            
            # Use global range if available, otherwise fall back to local range
            if hasattr(self, 'global_field_ranges') and field_name in self.global_field_ranges:
                global_range = self.global_field_ranges[field_name]
                data_range = (global_range['min'], global_range['max'])
                print(f"📊 Field '{field_name}' using global range: {data_range} (local was: {local_range})")
            else:
                data_range = local_range
                print(f"📊 Field '{field_name}' using local range: {data_range} (no global range available)")
            
            # Create custom lookup table based on field type
            lut = self._create_field_lookup_table(field_info, data_range)
            
            # Apply lookup table to mapper
            mapper.SetLookupTable(lut)
            mapper.SetScalarRange(data_range)
            
            # Create actor
            actor = vtk_local.vtkActor()
            actor.SetMapper(mapper)
            actor.GetProperty().SetOpacity(0.8)
            
            # Remove any existing scalar bars to prevent duplicates
            actors_to_remove = []
            actor_collection = self.renderer.GetActors2D()
            actor_collection.InitTraversal()
            for i in range(actor_collection.GetNumberOfItems()):
                actor = actor_collection.GetNextItem()
                if actor and actor.GetClassName() == 'vtkScalarBarActor':
                    actors_to_remove.append(actor)
            
            for old_scalar_bar in actors_to_remove:
                self.renderer.RemoveActor2D(old_scalar_bar)
                print("🗑️ Removed existing scalar bar to prevent duplicates")
            
            # Create new color bar
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
        from .paraview_widget import vtk
        
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
        """Setup time step controls using ParaView reader's time information for remote connections"""
        if not self.current_source:
            return
        
        try:
            # For remote ParaView connections, use the reader's built-in time information
            # instead of trying to scan local filesystem paths
            
            print("🔍 Setting up time steps from ParaView reader...")
            
            # Get time steps directly from the ParaView reader
            time_values = []
            if hasattr(self.current_source, 'TimestepValues'):
                time_values = list(self.current_source.TimestepValues)
                print(f"📊 Reader provides time values: {time_values}")
            else:
                print("⚠️ Reader does not provide time step values")
                return
            
            if time_values:
                # Sort time values
                time_values.sort()
                
                self.time_steps = time_values
                # Store the original file path for reloading if available
                foam_file_path = None
                if hasattr(self.current_source, 'FileName'):
                    foam_file_path = self.current_source.FileName
                elif hasattr(self.current_source, 'GetFileName'):
                    try:
                        foam_file_path = self.current_source.GetFileName()
                    except:
                        pass
                
                if not foam_file_path:
                    foam_file_path = getattr(self, '_foam_file_path', None)
                
                if foam_file_path:
                    self._foam_file_path = foam_file_path
                
                # Enable time controls
                self.time_slider.setRange(0, len(self.time_steps) - 1)
                self.time_slider.setValue(0)
                self.time_slider.setEnabled(True)
                self.first_frame_btn.setEnabled(True)
                self.prev_time_btn.setEnabled(True)
                self.play_pause_btn.setEnabled(True)
                self.next_time_btn.setEnabled(True)
                self.last_frame_btn.setEnabled(True)
                self.update_time_label()
                
                logger.info(f"Found {len(self.time_steps)} time steps from ParaView reader: {self.time_steps}")
                print(f"🕐 Time steps available: {self.time_steps}")
            else:
                logger.info("No time steps found in ParaView reader")
                print("⚠️ No time steps found in ParaView reader")
                
                # Disable time controls if no time steps
                if hasattr(self, 'time_slider'):
                    self.time_slider.setEnabled(False)
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
                        
        except Exception as e:
            logger.error(f"Failed to setup time steps: {str(e)}")
            print(f"⚠️ Time step setup failed: {e}")
            
            # Disable time controls on error
            if hasattr(self, 'time_slider'):
                self.time_slider.setEnabled(False)
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
                from paraview.simple import GetAnimationScene, GetTimeKeeper, UpdatePipeline, Render, GetActiveView
                
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
                
                # Try embedded rendering first
                if hasattr(self, 'renderer') and self.renderer:
                    print("🎯 Attempting embedded rendering for time step")
                    
                    # Try to get the updated data from server using Fetch()
                    vtk_data = None
                    try:
                        import paraview.servermanager as sm
                        vtk_data = sm.Fetch(self.current_source)
                        if vtk_data:
                            print(f"📊 Fetched VTK data for time step: {vtk_data.GetClassName()}")
                            if hasattr(vtk_data, 'GetNumberOfPoints'):
                                print(f"   Points: {vtk_data.GetNumberOfPoints()}")
                        else:
                            print("⚠️ Fetch() returned None for time step")
                    except Exception as fetch_error:
                        print(f"⚠️ Fetch() failed for time step: {fetch_error}")
                        
                        # Fallback to GetClientSideObject
                        try:
                            client_side_obj = self.current_source.GetClientSideObject()
                            if client_side_obj:
                                vtk_data = client_side_obj.GetOutput()
                                print(f"📊 Fallback: Got VTK data via GetClientSideObject")
                                if vtk_data and hasattr(vtk_data, 'GetNumberOfPoints'):
                                    print(f"   Points: {vtk_data.GetNumberOfPoints()}")
                        except Exception as data_error:
                            print(f"⚠️ Fallback GetClientSideObject also failed: {data_error}")
                    
                    if vtk_data and vtk_data.GetNumberOfPoints() > 0:
                        # Clear current visualization
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
                        
                        print(f"✅ Successfully updated embedded visualization for t={time_value}")
                        self.update_time_label()
                        return
                    else:
                        print("⚠️ No VTK data available for embedded rendering")
                
                # FALLBACK: Use server-side rendering (separate window)
                print("🔄 Using server-side rendering for time step update")
                
                # Update server-side visualization by rendering the view
                view = GetActiveView()
                if view:
                    Render(view)
                    print(f"✅ Server-side visualization updated for t={time_value}")
                    
                    # Update the embedded widget area to show current time
                    if hasattr(self, 'visualization_area'):
                        field_name = getattr(self, 'current_field', 'Default')
                        self.visualization_area.setText(
                            f"Time: {time_value:.3f}s\n"
                            f"Field: {field_name}\n\n"
                            f"Visualization is shown in separate ParaView window.\n\n"
                            f"Use Time Controls to navigate through time steps.\n"
                            f"Use Field buttons to change visualization.\n\n"
                            f"To enable embedded visualization:\n"
                            f"• Ensure stable network connection\n"
                            f"• Check server OpenGL configuration"
                        )
                else:
                    print("⚠️ No active ParaView view for server-side rendering")
                
                self.update_time_label()
                return
                
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
                            
                            # Try embedded rendering if possible - use Fetch() first
                            vtk_data = None
                            try:
                                import paraview.servermanager as sm
                                vtk_data = sm.Fetch(self.current_source)
                                if vtk_data:
                                    print(f"📊 Fallback: Fetched VTK data for time step")
                                    if hasattr(vtk_data, 'GetNumberOfPoints'):
                                        print(f"   Points: {vtk_data.GetNumberOfPoints()}")
                                else:
                                    print("⚠️ Fallback: Fetch() returned None")
                            except Exception as fetch_error:
                                print(f"⚠️ Fallback: Fetch() failed: {fetch_error}")
                                
                                # Final fallback to GetClientSideObject
                                try:
                                    client_side_obj = self.current_source.GetClientSideObject()
                                    if client_side_obj:
                                        vtk_data = client_side_obj.GetOutput()
                                        print(f"📊 Final fallback: Got VTK data via GetClientSideObject")
                                        if vtk_data and hasattr(vtk_data, 'GetNumberOfPoints'):
                                            print(f"   Points: {vtk_data.GetNumberOfPoints()}")
                                except Exception as data_error:
                                    print(f"⚠️ Final fallback: GetClientSideObject failed: {data_error}")
                            
                            if vtk_data and vtk_data.GetNumberOfPoints() > 0:
                                # Embedded rendering available
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
                                
                                print(f"✅ Fallback embedded rendering successful for t={time_value}")
                            else:
                                # Fall back to server-side rendering
                                print("🔄 Fallback: Using server-side rendering")
                                from paraview.simple import Render, GetActiveView
                                
                                view = GetActiveView()
                                if view:
                                    Render(view)
                                    print(f"✅ Fallback server-side rendering successful for t={time_value}")
                                    
                                    # Update the embedded widget area
                                    if hasattr(self, 'visualization_area'):
                                        field_name = getattr(self, 'current_field', 'Default')
                                        self.visualization_area.setText(
                                            f"Time: {time_value:.3f}s\n"
                                            f"Field: {field_name}\n\n"
                                            f"Updated via fallback method.\n"
                                            f"Visualization in separate ParaView window.\n\n"
                                            f"To enable embedded visualization:\n"
                                            f"• Check network stability\n"
                                            f"• Verify server configuration"
                                        )
                                else:
                                    print("⚠️ No active view for fallback server-side rendering")
                            
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
            from .paraview_widget import VTK_AVAILABLE, vtk
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
            
            # Get the actual data range for proper color mapping - use global range if available
            data_range = None
            active_field_name = None
            try:
                # Debug: Check what arrays are available
                cell_data = vtk_data.GetCellData()
                print(f"🔍 Available cell data arrays:")
                for i in range(cell_data.GetNumberOfArrays()):
                    array = cell_data.GetArray(i)
                    array_name = array.GetName() if array else "Unknown"
                    print(f"   [{i}] {array_name}")
                
                # Try to get the current field or default to pressure
                target_field = getattr(self, 'current_field', 'p')
                field_array = None
                
                if cell_data.GetArray(target_field):
                    field_array = cell_data.GetArray(target_field)
                    active_field_name = target_field
                    print(f"✅ Found target field '{target_field}'")
                elif cell_data.GetArray('p'):
                    field_array = cell_data.GetArray('p')
                    active_field_name = 'p'
                    print(f"✅ Found pressure array 'p' as fallback")
                elif cell_data.GetNumberOfArrays() > 0:
                    # If target field not found, look for any array that might be pressure
                    for i in range(cell_data.GetNumberOfArrays()):
                        array = cell_data.GetArray(i)
                        array_name = array.GetName() if array else ""
                        if 'p' in array_name.lower() or i == 4:  # 'p' is usually array 4 in OpenFOAM
                            field_array = array
                            active_field_name = array_name
                            print(f"✅ Found pressure-like array: '{array_name}' at index {i}")
                            break
                
                if field_array:
                    local_range = field_array.GetRange()
                    
                    # Use global range if available for consistent coloring
                    if (hasattr(self, 'global_field_ranges') and 
                        active_field_name in self.global_field_ranges):
                        global_range = self.global_field_ranges[active_field_name]
                        data_range = (global_range['min'], global_range['max'])
                        print(f"📊 Using global range for {active_field_name}: {data_range} (local was: {local_range})")
                    else:
                        data_range = local_range
                        print(f"📊 Using local range for {active_field_name}: {data_range}")
                    
                    # Force the mapper to use this specific array
                    mapper.SetScalarModeToUseCellFieldData()
                    mapper.SelectColorArray(field_array.GetName())
                    mapper.SetColorModeToMapScalars()
                    print(f"🎯 Forced mapper to use array: {field_array.GetName()}")
                else:
                    print(f"⚠️ No field found, using fallback")
                    # Force mapper to use cell data and update
                    mapper.SetInputData(vtk_data)
                    mapper.Update()
                    data_range = mapper.GetInput().GetScalarRange()
                    active_field_name = "Unknown"
                    print(f"📊 Fallback data range: {data_range}")
                    
            except Exception as range_error:
                print(f"⚠️ Could not get data range: {range_error}")
                data_range = (0.0, 1.0)  # Safe fallback
                active_field_name = "Unknown"

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
            
            # Remove any existing scalar bars to prevent duplicates
            actors_to_remove = []
            actor_collection = self.renderer.GetActors2D()
            actor_collection.InitTraversal()
            for i in range(actor_collection.GetNumberOfItems()):
                actor = actor_collection.GetNextItem()
                if actor and actor.GetClassName() == 'vtkScalarBarActor':
                    actors_to_remove.append(actor)
            
            for old_scalar_bar in actors_to_remove:
                self.renderer.RemoveActor2D(old_scalar_bar)
                print("🗑️ Removed existing scalar bar to prevent duplicates")
            
            # Create color bar
            scalar_bar = None
            try:
                scalar_bar = vtk_local.vtkScalarBarActor()
                scalar_bar.SetLookupTable(mapper.GetLookupTable())
                
                # Set title based on the active field
                if active_field_name and active_field_name != "Unknown":
                    display_name = self._get_field_display_name(active_field_name)
                    scalar_bar.SetTitle(display_name)
                else:
                    scalar_bar.SetTitle("Pressure")  # Default fallback
                
                scalar_bar.SetWidth(0.12)
                scalar_bar.SetHeight(0.8)
                scalar_bar.SetPosition(0.85, 0.1)
                scalar_bar.SetNumberOfLabels(7)
                
                # Style the color bar
                scalar_bar.GetTitleTextProperty().SetFontSize(12)
                scalar_bar.GetLabelTextProperty().SetFontSize(10)
                scalar_bar.GetTitleTextProperty().SetColor(1.0, 1.0, 1.0)
                scalar_bar.GetLabelTextProperty().SetColor(1.0, 1.0, 1.0)
                
                print(f"🎨 Added color bar legend for {scalar_bar.GetTitle()}")
                
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
        
        # Note: Load Results button is handled separately since it depends on connection state
        
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
        # First check if we have a local connection
        if not self.connected:
            return False
        
        # If we have remote server info, also check if server is actually running
        if self.server_url and self.project_name:
            try:
                server_status = self._check_remote_pvserver_status()
                return server_status.get("status") == "running"
            except Exception as e:
                logger.warning(f"Failed to check remote PVServer status: {e}")
                return False
        
        return True
    
    def _has_malformed_connection(self) -> bool:
        """Check if the current ParaView connection has the malformed connection string bug."""
        try:
            import paraview.servermanager as sm
            if hasattr(sm, 'ActiveConnection') and sm.ActiveConnection:
                active_conn_str = str(sm.ActiveConnection)
                # Normal connection strings should have format: cs://host:port
                # Malformed ones have: cs://host:port:port (extra port)
                if active_conn_str.count(':') > 2:
                    logger.debug(f"Detected malformed connection string: {active_conn_str}")
                    return True
            return False
        except Exception as e:
            logger.warning(f"Could not check connection string format: {e}")
            return False
    
    def _get_connection_status_message(self) -> str:
        """Get a user-friendly message about the current connection status."""
        if not self.connected:
            return "Not connected to ParaView server"
        
        if self._has_malformed_connection():
            return ("Connected but ParaView has a connection string bug.\n"
                   "Data operations may fail or cause crashes.\n"
                   "Try disconnecting and reconnecting.")
        
        return "Connected successfully"
    
    def _check_remote_pvserver_status(self):
        """Check the status of the remote ParaView server via API"""
        if not self.server_url or not self.project_name:
            logger.warning("Cannot check PVServer status: missing server_url or project_name")
            return {"status": "not_configured"}
        
        try:
            # Use the API to check PVServer status for the project
            import requests
            from urllib.parse import urlparse, urljoin
            
            # Extract base URL from server_url
            parsed_url = urlparse(self.server_url)
            api_base = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            logger.info(f"Checking PVServer status via API: {self.server_url}")
            logger.info(f"API base URL: {api_base}")
            logger.info(f"Parsed URL components: scheme={parsed_url.scheme}, netloc={parsed_url.netloc}, hostname={parsed_url.hostname}, port={parsed_url.port}")
            
            # Call the API endpoint to check PVServer info
            api_url = urljoin(api_base, f"/api/projects/{self.project_name}/pvserver/info")
            logger.info(f"Making API call to: {api_url}")
            
            response = requests.get(api_url, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"API response received: {result}")
                
                # Validate the response data
                if "port" in result and result["port"] is not None:
                    port = result["port"]
                    logger.info(f"PVServer port from API: {port} (type: {type(port)})")
                    
                    # Ensure port is a clean integer
                    try:
                        port_int = int(port)
                        if port_int != port:
                            logger.warning(f"Port converted from {port} ({type(port)}) to {port_int}")
                            result["port"] = port_int
                    except (ValueError, TypeError) as port_error:
                        logger.error(f"Invalid port in API response: {port} - {port_error}")
                        result["status"] = "error"
                        result["error"] = f"Invalid port format: {port}"
                
                return result
            else:
                logger.warning(f"API call failed with status {response.status_code}: {response.text}")
                return {"status": "error", "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Failed to check PVServer status via API: {e}")
            import traceback
            logger.debug(f"API check exception traceback: {traceback.format_exc()}")
            return {"status": "error", "error": str(e)}
    
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
            print("🔍 Detecting available fields from ParaView reader properties...")
            
            # FIRST: Try to get fields from ParaView reader properties (works with remote servers)
            if hasattr(self.current_source, 'CellArrays') and hasattr(self.current_source, 'PointArrays'):
                print("🎯 Using ParaView reader array properties for field detection")
                
                # Get cell arrays from reader properties
                try:
                    if hasattr(self.current_source.CellArrays, 'Available'):
                        cell_arrays = list(self.current_source.CellArrays.Available)
                        print(f"📊 Found {len(cell_arrays)} cell arrays from reader: {cell_arrays}")
                        
                        for i, array_name in enumerate(cell_arrays):
                            field_info = {
                                'name': array_name,
                                'display_name': self._get_field_display_name(array_name),
                                'type': 'cell',
                                'size': 'Unknown',  # Can't get size from reader properties
                                'components': 'Unknown',  # Can't get components from reader properties  
                                'range': (0.0, 1.0),  # Will be updated when data is accessed
                                'array_index': i
                            }
                            available_fields.append(field_info)
                            print(f"   📊 Cell field: {array_name}")
                            
                except Exception as cell_error:
                    print(f"⚠️ Failed to get cell arrays from reader: {cell_error}")
                
                # Get point arrays from reader properties
                try:
                    if hasattr(self.current_source.PointArrays, 'Available'):
                        point_arrays = list(self.current_source.PointArrays.Available)
                        print(f"📊 Found {len(point_arrays)} point arrays from reader: {point_arrays}")
                        
                        for i, array_name in enumerate(point_arrays):
                            field_info = {
                                'name': array_name,
                                'display_name': self._get_field_display_name(array_name),
                                'type': 'point',
                                'size': 'Unknown',
                                'components': 'Unknown',
                                'range': (0.0, 1.0),
                                'array_index': i
                            }
                            available_fields.append(field_info)
                            print(f"   📊 Point field: {array_name}")
                            
                except Exception as point_error:
                    print(f"⚠️ Failed to get point arrays from reader: {point_error}")
                
                # If we got fields from reader properties, use them
                if available_fields:
                    print(f"✅ Detected {len(available_fields)} fields from ParaView reader properties")
                    # Sort fields by importance
                    available_fields.sort(key=lambda x: self._get_field_priority(x['name']))
                    return available_fields
            
            # FALLBACK: Try to get VTK data for detailed field information using Fetch()
            print("🔄 Fallback: Trying to get VTK data for detailed field information...")
            vtk_data = None
            
            # Try Fetch() first for server data
            try:
                import paraview.servermanager as sm
                self.current_source.UpdatePipeline()
                vtk_data = sm.Fetch(self.current_source)
                if vtk_data:
                    print(f"✅ Fetched VTK data for field detection: {vtk_data.GetClassName()}")
                else:
                    print("⚠️ Fetch() returned None for field detection")
            except Exception as fetch_error:
                print(f"⚠️ Fetch() failed for field detection: {fetch_error}")
                
                # Original fallback methods
                if hasattr(self.current_source, 'GetClientSideObject'):
                    # ParaView server source
                    try:
                        self.current_source.UpdatePipeline()
                        client_side_obj = self.current_source.GetClientSideObject()
                        if client_side_obj:
                            vtk_data = client_side_obj.GetOutput()
                            print(f"✅ Got VTK data via GetClientSideObject: {vtk_data}")
                        else:
                            print("⚠️ GetClientSideObject returned None")
                    except Exception as e:
                        print(f"⚠️ GetClientSideObject failed: {e}")
                        
                elif hasattr(self.current_source, 'GetOutput'):
                    # Direct VTK source
                    try:
                        self.current_source.Update()
                        vtk_data = self.current_source.GetOutput()
                        print(f"✅ Got VTK data via GetOutput: {vtk_data}")
                    except Exception as e:
                        print(f"⚠️ GetOutput failed: {e}")
            
            # If VTK data is not available but we detected fields from reader properties, that's fine
            if not vtk_data and not available_fields:
                print("⚠️ No VTK data available and no fields from reader properties")
                return []
            elif not vtk_data:
                print("⚠️ No VTK data for detailed info, but using fields from reader properties")
                return available_fields
            
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
    
    def calculate_global_field_ranges(self):
        """Calculate global min/max ranges for all fields across all time steps for consistent color scaling"""
        if not self.current_source or not self.time_steps or not self.available_fields:
            print("⚠️ Cannot calculate global ranges - missing source, time steps, or fields")
            return
        
        print("🔄 Calculating global field ranges across all time steps...")
        
        try:
            import paraview.servermanager as sm
            from paraview.simple import GetAnimationScene, GetTimeKeeper, UpdatePipeline
            
            # Store current time to restore later
            scene = GetAnimationScene()
            original_time = scene.AnimationTime
            
            # Initialize global ranges
            for field in self.available_fields:
                field_name = field['name']
                self.global_field_ranges[field_name] = {'min': float('inf'), 'max': float('-inf')}
            
            # Iterate through all time steps
            for i, time_value in enumerate(self.time_steps):
                if i % 2 == 0 or i == len(self.time_steps) - 1:  # Print progress every other step and the last step
                    print(f"   📊 Processing time step {i+1}/{len(self.time_steps)}: t={time_value}")
                
                # Set time step
                scene.AnimationTime = time_value
                time_keeper = GetTimeKeeper()
                time_keeper.Time = time_value
                
                try:
                    UpdatePipeline(time=time_value, proxy=self.current_source)
                except:
                    self.current_source.UpdatePipeline()
                
                # Fetch data for this time step
                try:
                    vtk_data = sm.Fetch(self.current_source)
                    if not vtk_data:
                        continue
                    
                    # Handle multi-block datasets
                    if vtk_data.GetClassName() == 'vtkMultiBlockDataSet':
                        if vtk_data.GetNumberOfBlocks() > 0:
                            block = vtk_data.GetBlock(0)
                            if block:
                                vtk_data = block
                            else:
                                continue
                        else:
                            continue
                    
                    # Check each field
                    for field in self.available_fields:
                        field_name = field['name']
                        field_type = field['type']
                        
                        # Get the field array
                        field_array = None
                        if field_type == 'cell':
                            cell_data = vtk_data.GetCellData()
                            field_array = cell_data.GetArray(field_name)
                        elif field_type == 'point':
                            point_data = vtk_data.GetPointData()
                            field_array = point_data.GetArray(field_name)
                        
                        if field_array:
                            local_range = field_array.GetRange()
                            # Update global range
                            if local_range[0] < self.global_field_ranges[field_name]['min']:
                                self.global_field_ranges[field_name]['min'] = local_range[0]
                            if local_range[1] > self.global_field_ranges[field_name]['max']:
                                self.global_field_ranges[field_name]['max'] = local_range[1]
                
                except Exception as fetch_error:
                    if i % 5 == 0:  # Only print errors occasionally to reduce log spam
                        print(f"   ⚠️ Failed to fetch data at time {time_value}: {fetch_error}")
                    continue
            
            # Restore original time
            scene.AnimationTime = original_time
            time_keeper.Time = original_time
            try:
                UpdatePipeline(time=original_time, proxy=self.current_source)
            except:
                self.current_source.UpdatePipeline()
            
            # Print final global ranges
            print("✅ Global field ranges calculated:")
            for field_name, ranges in self.global_field_ranges.items():
                if ranges['min'] != float('inf') and ranges['max'] != float('-inf'):
                    print(f"   {field_name}: ({ranges['min']:.3f}, {ranges['max']:.3f})")
                else:
                    print(f"   {field_name}: No valid data found")
                    # Set reasonable defaults
                    self.global_field_ranges[field_name] = {'min': 0.0, 'max': 1.0}
            
        except Exception as e:
            print(f"❌ Failed to calculate global field ranges: {e}")
            # Set reasonable defaults for all fields
            for field in self.available_fields:
                field_name = field['name']
                self.global_field_ranges[field_name] = {'min': 0.0, 'max': 1.0}

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
        # Create a vertical layout for view buttons with responsive sizing
        view_buttons_widget = QWidget()
        
        # Responsive button column width
        height_class = self.get_screen_height_class()
        column_width = 60 if height_class == "small" else 70 if height_class == "medium" else 80
        view_buttons_widget.setMaximumWidth(column_width)
        
        view_buttons_layout = QVBoxLayout(view_buttons_widget)
        margin = self.get_responsive_spacing(5)
        spacing = self.get_responsive_spacing(5) 
        view_buttons_layout.setContentsMargins(margin, margin, margin, margin)
        view_buttons_layout.setSpacing(spacing)
        
        # Get responsive button height
        button_height = self.get_responsive_button_size()
        
        # View orientation buttons with responsive sizing
        self.view_pos_x_btn = QPushButton("+X")
        self.view_pos_x_btn.clicked.connect(self.view_pos_x)
        self.view_pos_x_btn.setToolTip("View along positive X axis")
        self.view_pos_x_btn.setMaximumHeight(button_height)
        view_buttons_layout.addWidget(self.view_pos_x_btn)
        
        self.view_neg_x_btn = QPushButton("-X")
        self.view_neg_x_btn.clicked.connect(self.view_neg_x)
        self.view_neg_x_btn.setToolTip("View along negative X axis")
        self.view_neg_x_btn.setMaximumHeight(button_height)
        view_buttons_layout.addWidget(self.view_neg_x_btn)
        
        self.view_pos_y_btn = QPushButton("+Y")
        self.view_pos_y_btn.clicked.connect(self.view_pos_y)
        self.view_pos_y_btn.setToolTip("View along positive Y axis")
        self.view_pos_y_btn.setMaximumHeight(button_height)
        view_buttons_layout.addWidget(self.view_pos_y_btn)
        
        self.view_neg_y_btn = QPushButton("-Y")
        self.view_neg_y_btn.clicked.connect(self.view_neg_y)
        self.view_neg_y_btn.setToolTip("View along negative Y axis")
        self.view_neg_y_btn.setMaximumHeight(button_height)
        view_buttons_layout.addWidget(self.view_neg_y_btn)
        
        self.view_pos_z_btn = QPushButton("+Z")
        self.view_pos_z_btn.clicked.connect(self.view_pos_z)
        self.view_pos_z_btn.setToolTip("View along positive Z axis")
        self.view_pos_z_btn.setMaximumHeight(button_height)
        view_buttons_layout.addWidget(self.view_pos_z_btn)
        
        self.view_neg_z_btn = QPushButton("-Z")
        self.view_neg_z_btn.clicked.connect(self.view_neg_z)
        self.view_neg_z_btn.setToolTip("View along negative Z axis")
        self.view_neg_z_btn.setMaximumHeight(button_height)
        view_buttons_layout.addWidget(self.view_neg_z_btn)
        
        # Add responsive separator
        separator_spacing = self.get_responsive_spacing(10)
        view_buttons_layout.addSpacing(separator_spacing)
        
        # Rotation buttons with responsive sizing
        self.rotate_cw_btn = QPushButton("↻")
        self.rotate_cw_btn.clicked.connect(self.rotate_clockwise_90)
        self.rotate_cw_btn.setToolTip("Rotate view 90° clockwise")
        self.rotate_cw_btn.setMaximumHeight(button_height)
        view_buttons_layout.addWidget(self.rotate_cw_btn)
        
        self.rotate_ccw_btn = QPushButton("↺")
        self.rotate_ccw_btn.clicked.connect(self.rotate_counterclockwise_90)
        self.rotate_ccw_btn.setToolTip("Rotate view 90° counterclockwise")
        self.rotate_ccw_btn.setMaximumHeight(button_height)
        view_buttons_layout.addWidget(self.rotate_ccw_btn)
        
        # Add stretch to push buttons to top
        view_buttons_layout.addStretch()
        
        # Style the buttons with responsive sizing
        font_size = 10 if height_class == "small" else 11 if height_class == "medium" else 12
        button_style = f"""
            QPushButton {{
                font-size: {font_size}px;
                font-weight: bold;
                min-height: {button_height}px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: #45a049;
            }}
            QPushButton:pressed {{
                background-color: #3d8b40;
            }}
            QPushButton:disabled {{
                background-color: #cccccc;
                color: #666666;
            }}
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
    
    def get_screen_height_class(self):
        """Determine screen height class for responsive design"""
        # Import QApplication here to avoid circular imports
        from PySide6.QtWidgets import QApplication
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
        """Get responsive spacing based on screen height"""
        height_class = self.get_screen_height_class()
        if height_class == "small":
            return int(base_spacing * 0.5)  # 50% reduction
        elif height_class == "medium":
            return int(base_spacing * 0.75)  # 25% reduction
        else:
            return base_spacing  # full spacing
    
    def get_responsive_visualization_size(self):
        """Get responsive visualization area minimum size"""
        height_class = self.get_screen_height_class()
        if height_class == "small":
            return (400, 250)  # Smaller minimum size
        elif height_class == "medium":
            return (500, 300)  # Medium size
        else:
            return (600, 400)  # Original size
    
    def get_responsive_button_size(self):
        """Get responsive button size for view controls"""
        height_class = self.get_screen_height_class()
        if height_class == "small":
            return 25  # Smaller buttons
        elif height_class == "medium":
            return 30  # Medium buttons
        else:
            return 35  # Larger buttons

