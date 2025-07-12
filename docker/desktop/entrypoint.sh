#!/bin/bash
set -e

# FoamAI Desktop Application Entrypoint Script
# Handles display setup and environment configuration

echo "============================================"
echo "FoamAI Desktop Application Container"
echo "============================================"

# Display configuration
echo "Configuring display settings..."

# Set display if not already set
if [ -z "$DISPLAY" ]; then
    echo "WARNING: DISPLAY environment variable not set."
    echo "For GUI applications, you may need to set DISPLAY and mount X11 socket."
    echo "Example: -e DISPLAY=\$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix"
    export DISPLAY=:0
fi

echo "Using DISPLAY: $DISPLAY"

# Configure Qt platform plugin
export QT_QPA_PLATFORM="xcb"
export QT_X11_NO_MITSHM=1
export QT_XCB_GL_INTEGRATION="xcb_egl"

# Additional Qt/X11 environment variables
export QT_AUTO_SCREEN_SCALE_FACTOR=0
export QT_SCALE_FACTOR=1
export QT_FONT_DPI=96

echo "Qt platform: $QT_QPA_PLATFORM"

# Create Xauthority file if needed
if [ ! -f "$HOME/.Xauthority" ] && [ -n "$XAUTHORITY" ]; then
    echo "Creating Xauthority file..."
    touch "$HOME/.Xauthority"
    chmod 600 "$HOME/.Xauthority"
fi

# Test X11 connection (non-blocking)
echo "Testing X11 connection..."
if command -v xset >/dev/null 2>&1; then
    if xset q >/dev/null 2>&1; then
        echo "✓ X11 connection successful"
    else
        echo "⚠ X11 connection test failed, but continuing..."
        echo "  Make sure you have X11 forwarding enabled"
    fi
else
    echo "⚠ xset not available, skipping X11 test"
fi

# Environment validation
echo "Validating environment..."

# Check Python
if python3.12 --version >/dev/null 2>&1; then
    echo "✓ Python 3.12: $(python3.12 --version)"
else
    echo "✗ Python 3.12 not found"
    exit 1
fi

# Check ParaView
if [ -d "$PARAVIEW_HOME" ]; then
    echo "✓ ParaView found at: $PARAVIEW_HOME"
    echo "  PYTHONPATH includes: $PYTHONPATH"
    
    # Try to find ParaView Python bindings
    PARAVIEW_PYTHON_FOUND=false
    for path in "/opt/paraview/lib/python3.12/site-packages" "/opt/paraview/bin/Lib/site-packages"; do
        if [ -d "$path" ] && [ -f "$path/paraview.py" ]; then
            echo "  ✓ ParaView Python bindings found at: $path"
            export PYTHONPATH="$path:$PYTHONPATH"
            PARAVIEW_PYTHON_FOUND=true
            break
        fi
    done
    
    if [ "$PARAVIEW_PYTHON_FOUND" = false ]; then
        echo "  ⚠ ParaView Python bindings not found, but continuing..."
    fi
else
    echo "✗ ParaView not found at: $PARAVIEW_HOME"
    exit 1
fi

# Check foamai packages
echo "Checking foamai packages..."
if python3.12 -c "import foamai_core; print('✓ foamai-core imported successfully')" 2>/dev/null; then
    echo "✓ foamai-core package available"
else
    echo "✗ foamai-core package not found"
    exit 1
fi

if python3.12 -c "import foamai_desktop; print('✓ foamai-desktop imported successfully')" 2>/dev/null; then
    echo "✓ foamai-desktop package available"
else
    echo "✗ foamai-desktop package not found"
    exit 1
fi

# Check essential dependencies
echo "Checking essential dependencies..."
python3.12 -c "
import sys
packages = ['PySide6', 'requests', 'numpy', 'dotenv']
failed = []
for pkg in packages:
    try:
        __import__(pkg)
        print(f'✓ {pkg}')
    except ImportError:
        print(f'✗ {pkg}')
        failed.append(pkg)
if failed:
    print(f'ERROR: Missing packages: {failed}')
    sys.exit(1)
"

# Set up working directory
cd /app/src/foamai-desktop

# Create logs directory if it doesn't exist
mkdir -p logs

# Log startup information
echo "============================================"
echo "Starting FoamAI Desktop Application..."
echo "Working directory: $(pwd)"
echo "User: $(whoami)"
echo "Home: $HOME"
echo "Display: $DISPLAY"
echo "Time: $(date)"
echo "============================================"

# Execute the main command
echo "Executing: $@"
exec "$@" 