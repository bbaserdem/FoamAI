# FoamAI Desktop Application Setup Guide

The FoamAI Desktop Application provides a user-friendly graphical interface for computational fluid dynamics (CFD) simulations with AI assistance, 3D visualization, and OpenFOAM integration.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [ParaView 6.0.0-RC2 Installation](#paraview-600-rc2-installation)
- [FoamAI Desktop Installation](#foamai-desktop-installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Features & Usage](#features--usage)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## Overview

The FoamAI Desktop Application is a PySide6-based GUI that provides:

- **Conversational AI Interface**: Natural language interaction for simulation setup
- **Automated Mesh Generation**: AI-driven mesh generation with validation workflow
- **3D Visualization**: Embedded ParaView integration for mesh and results visualization
- **Time-step Navigation**: Navigate through simulation results with intuitive controls
- **Cross-platform Support**: Works on Windows, macOS, and Linux
- **Project Management**: Organize simulations into projects with full lifecycle management

## Prerequisites

### System Requirements

- **Python 3.12 or higher** (required for PySide6 compatibility)
- **Operating System**: Windows 10/11, macOS 10.15+, or Linux (Ubuntu 20.04+)
- **Memory**: Minimum 4GB RAM, recommended 8GB+ for complex simulations
- **Graphics**: OpenGL-capable graphics card with driver support
- **Disk Space**: 2GB for application + additional space for simulation data

### Essential Dependencies

Before installing FoamAI Desktop, ensure you have:

1. **Python 3.12+** with pip/uv package manager
2. **ParaView 6.0.0-RC2** (critical version requirement - see below)
3. **OpenFOAM server** (local or remote) with REST API
4. **UV package manager** for Python dependencies

## ParaView 6.0.0-RC2 Installation

> **⚠️ CRITICAL VERSION REQUIREMENT**  
> FoamAI Desktop requires **exactly ParaView 6.0.0-RC2** for proper Python integration and visualization compatibility. Other versions may cause import errors or visualization failures.

### Download ParaView 6.0.0-RC2

1. **Visit ParaView Downloads**: Go to [ParaView Download Archive](https://www.paraview.org/download/)
2. **Navigate to Version 6.0.0-RC2**: Look for version 6.0.0-RC2 in the archives
3. **Select Your Platform**:
   - **Linux**: `ParaView-6.0.0-RC2-osmesa-MPI-Linux-Python3.7-64bit.tar.gz`
   - **Windows**: `ParaView-6.0.0-RC2-Windows-Python3.7-msvc2015-64bit.exe`
   - **macOS**: `ParaView-6.0.0-RC2-Darwin-Python3.7-64bit.dmg`

### Platform-Specific Installation

#### Linux Installation

```bash
# Download and extract ParaView 6.0.0-RC2
cd /opt
sudo wget https://www.paraview.org/files/v6.0/ParaView-6.0.0-RC2-osmesa-MPI-Linux-Python3.7-64bit.tar.gz
sudo tar -xzf ParaView-6.0.0-RC2-osmesa-MPI-Linux-Python3.7-64bit.tar.gz
sudo mv ParaView-6.0.0-RC2-osmesa-MPI-Linux-Python3.7-64bit paraview-6.0.0

# Create symbolic links for system access
sudo ln -sf /opt/paraview-6.0.0/bin/paraview /usr/local/bin/paraview
sudo ln -sf /opt/paraview-6.0.0/bin/pvserver /usr/local/bin/pvserver
sudo ln -sf /opt/paraview-6.0.0/bin/pvpython /usr/local/bin/pvpython

# Set up environment variables (add to ~/.bashrc or ~/.zshrc)
echo 'export PARAVIEW_HOME="/opt/paraview-6.0.0"' >> ~/.bashrc
echo 'export PATH="$PARAVIEW_HOME/bin:$PATH"' >> ~/.bashrc
echo 'export PYTHONPATH="$PARAVIEW_HOME/lib/python3.7/site-packages:$PYTHONPATH"' >> ~/.bashrc
source ~/.bashrc

# Verify installation
paraview --version
# Should output: paraview version 6.0.0-RC2
```

#### Windows Installation

```powershell
# Download and run the installer
# ParaView-6.0.0-RC2-Windows-Python3.7-msvc2015-64bit.exe

# After installation, add to system PATH
# Default installation path: C:\Program Files\ParaView 6.0.0-RC2

# Set environment variables in PowerShell (as Administrator)
[Environment]::SetEnvironmentVariable("PARAVIEW_HOME", "C:\Program Files\ParaView 6.0.0-RC2", "Machine")
[Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\Program Files\ParaView 6.0.0-RC2\bin", "Machine")

# Add Python path for ParaView modules
[Environment]::SetEnvironmentVariable("PYTHONPATH", "C:\Program Files\ParaView 6.0.0-RC2\lib\site-packages;" + $env:PYTHONPATH, "Machine")

# Restart PowerShell and verify
paraview.exe --version
```

#### macOS Installation

```bash
# Download and install the DMG file
# ParaView-6.0.0-RC2-Darwin-Python3.7-64bit.dmg

# After installation, set up environment
echo 'export PARAVIEW_HOME="/Applications/ParaView-6.0.0-RC2.app/Contents"' >> ~/.zshrc
echo 'export PATH="$PARAVIEW_HOME/bin:$PATH"' >> ~/.zshrc
echo 'export PYTHONPATH="$PARAVIEW_HOME/lib/python3.7/site-packages:$PYTHONPATH"' >> ~/.zshrc
source ~/.zshrc

# Create symbolic links for command line access
sudo ln -sf "/Applications/ParaView-6.0.0-RC2.app/Contents/bin/paraview" /usr/local/bin/paraview
sudo ln -sf "/Applications/ParaView-6.0.0-RC2.app/Contents/bin/pvserver" /usr/local/bin/pvserver

# Verify installation
paraview --version
```

### Verify ParaView Python Integration

Test that Python can import ParaView modules:

```bash
# Test ParaView Python integration
python3 -c "
import sys
print('Python version:', sys.version)
try:
    import paraview
    print('✅ ParaView module imported successfully')
    print('ParaView version:', paraview.version)
    
    from paraview.simple import *
    print('✅ ParaView.simple imported successfully')
    
    import vtk
    print('✅ VTK imported successfully')
    print('VTK version:', vtk.vtkVersion.GetVTKVersion())
    
except ImportError as e:
    print('❌ ParaView import failed:', e)
    print('Check PYTHONPATH and ParaView installation')
"
```

**Expected Output**:
```
Python version: 3.12.x
✅ ParaView module imported successfully
ParaView version: 6.0.0-RC2
✅ ParaView.simple imported successfully
✅ VTK imported successfully
VTK version: 9.2.x
```

## FoamAI Desktop Installation

### Step 1: Clone Repository and Setup UV

```bash
# Clone the FoamAI repository
git clone https://github.com/your-repo/FoamAI.git
cd FoamAI

# Install UV package manager (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
pip install uv

# Verify UV installation
uv --version
```

### Step 2: Install FoamAI Desktop with UV

```bash
# Navigate to project root
cd FoamAI

# Sync all workspace dependencies including desktop app
uv sync

# Specifically install desktop dependencies
uv sync --package foamai-desktop

# Install with development dependencies (if developing)
uv sync --package foamai-desktop --group dev
```

### Step 3: Verify Installation

```bash
# Test that all packages are available
uv run python -c "
import sys
print('Python version:', sys.version)

# Test FoamAI core imports
try:
    from foamai_core.orchestrator import create_cfd_workflow
    print('✅ FoamAI core imported successfully')
except ImportError as e:
    print('❌ FoamAI core import failed:', e)

# Test PySide6
try:
    from PySide6.QtWidgets import QApplication
    print('✅ PySide6 imported successfully')
except ImportError as e:
    print('❌ PySide6 import failed:', e)

# Test ParaView with specific version check
try:
    import paraview
    from paraview.simple import *
    import vtk
    print('✅ ParaView integration verified')
    print('ParaView version:', paraview.version)
    if '6.0.0' in str(paraview.version):
        print('✅ Correct ParaView version detected')
    else:
        print('⚠️  Warning: ParaView version may not be 6.0.0-RC2')
except ImportError as e:
    print('❌ ParaView integration failed:', e)
    print('Please check ParaView 6.0.0-RC2 installation')
"
```

## Configuration

### Step 1: Environment Configuration

Create a `.env` file in the project root:

```bash
# Create configuration file
cat > .env << 'EOF'
# FoamAI Server Configuration
SERVER_HOST=localhost
SERVER_PORT=8000

# ParaView Server Configuration
PARAVIEW_SERVER_HOST=localhost
PARAVIEW_SERVER_PORT=11111

# Application Window Settings
WINDOW_WIDTH=1400
WINDOW_HEIGHT=900

# Chat Interface Settings
CHAT_HISTORY_LIMIT=200

# ParaView Integration Settings
PARAVIEW_TIMEOUT=45

# API Request Settings
REQUEST_TIMEOUT=120

# File Upload Settings (MB)
MAX_UPLOAD_SIZE=300

# Logging Level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
EOF
```

### Step 2: Server Configuration

Ensure you have a running FoamAI server. For local development:

```bash
# Option 1: Start local server with UV
cd src/foamai-server
uv run python -m foamai_server.main

# Option 2: Use Docker (if available)
docker-compose up foamai-server

# Option 3: Configure for remote server
# Update SERVER_HOST and SERVER_PORT in .env file
```

### Step 3: Verify Server Connection

```bash
# Test server connectivity
curl http://localhost:8000/api/health

# Expected response:
# {"status": "healthy", "timestamp": "2024-01-15T10:30:00.123456"}
```

## Running the Application

### Start FoamAI Desktop

```bash
# Method 1: Run with UV (recommended)
cd FoamAI
uv run python -m foamai_desktop.main

# Method 2: Run from desktop package directory
cd src/foamai-desktop
uv run python -m foamai_desktop.main

# Method 3: Direct Python execution (after uv sync)
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
python -m foamai_desktop.main
```

### Command Line Options

```bash
# Run with specific configuration
uv run python -m foamai_desktop.main --config custom.env

# Run with debug logging
uv run python -m foamai_desktop.main --debug

# Run with specific server
uv run python -m foamai_desktop.main --server http://remote-server:8000

# Run in development mode
uv run python -m foamai_desktop.main --dev
```

### Startup Sequence

1. **Dependency Check**: Verifies PySide6, ParaView, and server connectivity
2. **Configuration Load**: Loads settings from .env and command line
3. **UI Initialization**: Creates main window and interface components
4. **Server Connection**: Establishes connection to FoamAI backend
5. **ParaView Setup**: Initializes visualization components
6. **Ready State**: Application ready for user interaction

## Features & Usage

### Main Interface Components

#### 1. Chat Interface
- **Purpose**: Natural language input for CFD scenarios
- **Usage**: Type descriptions like "turbulent flow around a cylinder at Re=10000"
- **Features**: Chat history, validation feedback, AI responses

#### 2. 3D Visualization Area
- **Purpose**: Real-time mesh and results visualization with advanced analysis
- **Integration**: Embedded ParaView 6.0.0-RC2 widgets with custom visualization pipeline
- **Controls**: Rotate, zoom, pan, field selection, time navigation, animation support
- **Formats**: Supports OpenFOAM .foam files, VTK, STL, ParaView state files

#### 3. Configuration Panel
- **Purpose**: Review and approve AI-generated configurations
- **Components**: Mesh settings, solver parameters, boundary conditions
- **Workflow**: Approve → Run Simulation → View Results

#### 4. Project Management
- **Purpose**: Organize simulations into projects
- **Features**: Create, load, save, delete projects
- **Integration**: Server-side project storage and management

### Basic Workflow

1. **Create New Project**:
   ```
   File → New Project → Enter project name
   ```

2. **Describe Scenario**:
   ```
   Chat: "I want to analyze turbulent flow around a cylinder at Reynolds number 1000"
   ```

3. **Review Configuration**:
   ```
   - Check generated mesh parameters
   - Verify boundary conditions
   - Confirm solver settings
   ```

4. **Approve & Run**:
   ```
   Click "✓ Approve Configuration"
   Monitor simulation progress
   ```

5. **Visualize Results**:
   ```
   - View pressure/velocity fields
   - Navigate through time steps
   - Export images/animations
   ```

### Advanced Features

#### STL File Support
```bash
# Upload custom geometry
File → Upload STL → Select geometry.stl
Chat: "Flow around this custom geometry at 10 m/s"
```

#### Remote Execution
```python
# Configure remote server in UI
Settings → Server Configuration
Server URL: http://remote-server:8000
Project: my_remote_simulation
```

#### Mesh Convergence Studies
```
Chat: "Run mesh convergence study with 4 levels for pressure drop"
```

#### GPU Acceleration
```
Chat: "Use GPU acceleration for this simulation"
```

### Advanced Visualization & Analysis

The desktop application provides comprehensive visualization capabilities powered by ParaView integration:

#### Comprehensive Visualization Types

**Flow Field Visualization**:
- **Pressure Field**: Contour plots with customizable color maps and iso-surfaces
- **Velocity Field**: Vector plots, magnitude contours, and streamline analysis
- **Streamlines**: Enhanced seeding with wake-focused placement for flow analysis
- **Surface Analysis**: Surface pressure and shear stress distribution mapping

**Advanced Vortex Analysis**:
- **Vorticity Magnitude**: 3D vorticity field visualization with iso-surfaces
- **Q-Criterion**: Vortex core identification with automatic threshold selection
- **Time-Averaged Flow**: Mean flow analysis for unsteady cases with statistical processing
- **Turbulence Fields**: k, omega, epsilon, and nut visualization with wall function integration

**Specialized Visualizations**:
- **Temperature Distribution**: Thermal field visualization for heat transfer analysis
- **Multiphase Visualization**: Volume fraction and interface tracking for two-phase flows
- **Particle Tracking**: Lagrangian particle visualization for mixing and separation analysis

#### Intelligent Visualization Selection

The application automatically selects appropriate visualization types based on:
- **Geometry Type**: Cylinder flows → vortex shedding analysis with Q-criterion
- **Flow Conditions**: High Reynolds number → turbulence field visualization
- **Solver Type**: interFoam → multiphase volume fraction fields
- **Time Dependency**: Unsteady simulations → animation and time-series analysis

#### ParaView Integration Features

**Automatic Generation**:
- **Foam File Creation**: Automatic .foam file generation for ParaView compatibility
- **State Files**: ParaView state files for reproducible visualizations
- **Batch Processing**: pvpython integration for automated visualization workflows
- **Animation Support**: Time-dependent flow animations with customizable frame rates

**Export Capabilities**:
- **Image Export**: High-resolution PNG images for publications
- **VTK Data**: Raw VTK data export for custom analysis
- **ParaView States**: Reusable visualization configurations
- **Animation Videos**: MP4 video export for time-dependent results

#### Custom Visualization Pipeline

**Automated Pipeline Creation**:
- **Field Detection**: Automatic detection of available fields in simulation results
- **Filter Application**: Smart application of ParaView filters based on field types
- **Color Map Optimization**: Physics-appropriate color maps for different field variables
- **Lighting Setup**: Optimized lighting for 3D visualization clarity

**Interactive Controls**:
- **Real-time Manipulation**: Live rotation, zoom, and pan with smooth interaction
- **Field Switching**: Quick switching between pressure, velocity, and turbulence fields
- **Time Navigation**: Scrub through simulation time steps with frame-by-frame control
- **View Management**: Save and restore custom camera views and visualization settings

## Troubleshooting

### Common Issues

#### 1. ParaView Import Errors

**Problem**: `ImportError: No module named 'paraview'`

**Solution**:
```bash
# Check ParaView installation
which paraview
paraview --version

# Verify Python path
echo $PYTHONPATH
python -c "import sys; print('\n'.join(sys.path))"

# Fix PYTHONPATH (Linux/macOS)
export PYTHONPATH="/opt/paraview-6.0.0/lib/python3.7/site-packages:$PYTHONPATH"

# Fix PYTHONPATH (Windows)
set PYTHONPATH=C:\Program Files\ParaView 6.0.0-RC2\lib\site-packages;%PYTHONPATH%
```

#### 2. PySide6 Qt Platform Issues

**Problem**: `qt.qpa.plugin: Could not load the Qt platform plugin`

**Solution**:
```bash
# Linux - install Qt platform plugins
sudo apt-get install qt6-qpa-plugins

# macOS - install via Homebrew
brew install qt6

# Windows - ensure Visual C++ Redistributable is installed
# Download from Microsoft website

# Alternative: Set Qt plugin path
export QT_QPA_PLATFORM_PLUGIN_PATH="/opt/Qt/6.5.0/gcc_64/plugins/platforms"
```

#### 3. Server Connection Issues

**Problem**: Cannot connect to FoamAI server

**Solution**:
```bash
# Check server status
curl http://localhost:8000/api/health

# Start local server
cd src/foamai-server
uv run python -m foamai_server.main

# Check firewall/networking
telnet localhost 8000

# Update .env configuration
SERVER_HOST=your-server-ip
SERVER_PORT=8000
```

#### 4. Visualization Widget Issues

**Problem**: Black screen or empty visualization area

**Solution**:
```bash
# Check OpenGL support
glxinfo | grep OpenGL  # Linux
# Ensure graphics drivers are up to date

# Try software rendering
export MESA_GL_VERSION_OVERRIDE=3.3
export MESA_GLSL_VERSION_OVERRIDE=330

# Check ParaView server
pvserver --help
pvserver --port=11111 &
```

#### 5. Memory Issues with Large Meshes

**Problem**: Application crashes with large simulations

**Solution**:
```bash
# Increase memory limits
export PARAVIEW_MEMORY_LIMIT=4096  # MB

# Use server-side rendering
Settings → Visualization → Enable Remote Rendering

# Reduce mesh resolution
Chat: "Use coarse mesh for faster processing"
```

### Debug Mode

Run the application with enhanced debugging:

```bash
# Enable debug logging
uv run python -m foamai_desktop.main --debug

# Check log files
tail -f logs/openfoam_app.log

# Enable Qt debugging
export QT_LOGGING_RULES="*.debug=true"
uv run python -m foamai_desktop.main
```

### Performance Optimization

```bash
# Enable hardware acceleration
export VTK_USE_OPENGL2=1

# Optimize for large datasets
export PARAVIEW_USE_MPI=1

# Memory-efficient rendering
Settings → Performance → Enable Level-of-Detail
```

## Development

### Development Setup

```bash
# Install with development dependencies
uv sync --group dev

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest src/foamai-desktop/tests/

# Run with hot reload (if available)
uv run python -m foamai_desktop.main --dev --reload
```

### Building Standalone Application

```bash
# Install build dependencies
uv add --dev pyinstaller

# Build standalone executable
uv run pyinstaller \
    --onefile \
    --windowed \
    --add-data "src/foamai-desktop/foamai_desktop:foamai_desktop" \
    --add-data "/opt/paraview-6.0.0/lib/python3.7/site-packages:paraview" \
    src/foamai-desktop/foamai_desktop/main.py

# Output will be in dist/main.exe (Windows) or dist/main (Linux/macOS)
```

### Custom Themes and Styling

```python
# Custom Qt stylesheet
# src/foamai-desktop/foamai_desktop/themes/dark.qss
QMainWindow {
    background-color: #2b2b2b;
    color: #ffffff;
}

# Apply theme in main.py
app.setStyleSheet(open("themes/dark.qss").read())
```

### Plugin Development

```python
# Create custom visualization plugin
# src/foamai-desktop/plugins/custom_viz.py
class CustomVisualizationPlugin:
    def process_results(self, simulation_data):
        # Custom visualization logic
        pass
```

## Docker Container Deployment

For containerized deployment of the FoamAI Desktop Application:

### Quick Start with Docker

```bash
# Allow X11 forwarding (Linux/macOS)
xhost +local:docker

# Run with Docker Compose
docker-compose -f docker-compose.desktop.yml up

# Or run directly
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v $HOME/.Xauthority:/tmp/.Xauthority \
  --network host \
  foamai-desktop
```

### Windows Docker Setup

```powershell
# Install VcXsrv and start with "Disable access control" checked
docker run -it --rm \
  -e DISPLAY=host.docker.internal:0 \
  foamai-desktop
```

### Building the Container

```bash
# Build the desktop container
docker build -f docker/desktop/Dockerfile -t foamai-desktop .

# Build with specific versions
docker build \
  --build-arg PYTHON_VERSION=3.12 \
  --build-arg PARAVIEW_VERSION=6.0.0 \
  -f docker/desktop/Dockerfile \
  -t foamai-desktop .
```

### Container Configuration

Environment variables for container deployment:

```env
# Server Configuration
SERVER_HOST=host.docker.internal
SERVER_PORT=8000
PARAVIEW_SERVER_HOST=host.docker.internal
PARAVIEW_SERVER_PORT=11111

# Application Settings  
WINDOW_WIDTH=1400
WINDOW_HEIGHT=900
CHAT_HISTORY_LIMIT=200
PARAVIEW_TIMEOUT=45
REQUEST_TIMEOUT=120

# Display Settings
DISPLAY=:0
QT_X11_NO_MITSHM=1
```

## Testing & Validation

### Development Testing

```bash
# Test desktop application functionality
cd src/foamai-desktop
uv run pytest tests/

# Test ParaView integration
uv run python test_paraview_integration.py

# Test server connectivity
uv run python test_server_connection.py --host localhost --port 8000
```

### Manual Test Workflow

1. **Component Tests**:
   ```bash
   # Test ParaView widget
   uv run python -c "
   from foamai_desktop.paraview_widget import ParaViewWidget
   print('✅ ParaView widget imports successfully')
   "
   
   # Test API client
   uv run python -c "
   from foamai_desktop.api_client import APIClient
   client = APIClient('http://localhost:8000')
   print('✅ API client initialized')
   "
   ```

2. **Full Workflow Test**:
   ```bash
   # Start test servers
   python start_all_servers.py
   
   # Run workflow test
   python test_workflow.py
   ```

### Performance Testing

```bash
# Large mesh performance test
uv run python test_large_mesh_performance.py

# Memory usage monitoring
uv run python test_memory_usage.py --duration 300

# Rendering performance test
uv run python test_rendering_performance.py --resolution 1920x1080
```

## Additional Resources

- [FoamAI Contributing Guide](Contributing.md) - Development setup and workflows
- [Backend API Reference](BackendAPI.md) - Server API documentation
- [LangGraph Agents System](Agents.md) - AI agent architecture
- [DevOps Guide](DevOps.md) - Infrastructure deployment and testing
- [ParaView Documentation](https://www.paraview.org/documentation/) - ParaView user guide
- [PySide6 Documentation](https://doc.qt.io/qtforpython/) - Qt Python bindings

---

*For additional support, check the [troubleshooting section](#troubleshooting) or create an issue in the project repository. Remember that ParaView 6.0.0-RC2 is a critical requirement for proper functionality.*