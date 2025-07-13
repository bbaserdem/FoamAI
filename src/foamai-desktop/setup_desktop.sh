#!/bin/bash

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to get OS type
get_os() {
    case "$OSTYPE" in
        msys*|cygwin*|win32*)
            echo "windows"
            ;;
        darwin*)
            echo "macos"
            ;;
        linux*)
            echo "linux"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Function to check Python 3.12
check_python() {
    print_info "Checking for Python 3.12..."
    
    if command_exists python3.12; then
        PYTHON_CMD="python3.12"
    elif command_exists python3; then
        # Check if python3 is version 3.12
        python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        if [[ "$python_version" == "3.12" ]]; then
            PYTHON_CMD="python3"
        else
            print_error "Python 3.12 is required, but found Python $python_version"
            print_info "Please install Python 3.12 from https://www.python.org/downloads/"
            exit 1
        fi
    elif command_exists python; then
        # Check if python is version 3.12
        python_version=$(python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        if [[ "$python_version" == "3.12" ]]; then
            PYTHON_CMD="python"
        else
            print_error "Python 3.12 is required, but found Python $python_version"
            print_info "Please install Python 3.12 from https://www.python.org/downloads/"
            exit 1
        fi
    else
        print_error "Python 3.12 not found. Please install it from https://www.python.org/downloads/"
        exit 1
    fi
    
    print_success "Found Python 3.12: $($PYTHON_CMD --version)"
}

# Function to find ParaView installation
find_paraview() {
    print_info "Searching for ParaView 6.0.0 installation..."
    
    OS=$(get_os)
    PARAVIEW_PATH=""
    
    case "$OS" in
        "windows")
            # Windows common locations
            locations=(
                "/c/Program Files/ParaView 6.0.0"
                "/c/Program Files (x86)/ParaView 6.0.0"
                "/c/ParaView-6.0.0"
                "$HOME/ParaView-6.0.0"
            )
            ;;
        "macos")
            # macOS common locations
            locations=(
                "/Applications/ParaView-6.0.0.app"
                "/Applications/ParaView.app"
                "$HOME/Applications/ParaView-6.0.0.app"
                "$HOME/Applications/ParaView.app"
                "/opt/ParaView-6.0.0"
            )
            ;;
        "linux")
            # Linux common locations
            locations=(
                "/opt/ParaView-6.0.0"
                "/opt/paraview"
                "/usr/local/ParaView-6.0.0"
                "/usr/local/paraview"
                "$HOME/ParaView-6.0.0"
                "$HOME/paraview"
            )
            ;;
        *)
            print_error "Unsupported operating system: $OSTYPE"
            exit 1
            ;;
    esac
    
    # Check each location
    for location in "${locations[@]}"; do
        if [[ -d "$location" ]]; then
            PARAVIEW_PATH="$location"
            print_success "Found ParaView at: $PARAVIEW_PATH"
            break
        fi
    done
    
    # If not found, check command line argument
    if [[ -z "$PARAVIEW_PATH" ]] && [[ -n "$1" ]]; then
        if [[ -d "$1" ]]; then
            PARAVIEW_PATH="$1"
            print_success "Using provided ParaView path: $PARAVIEW_PATH"
        else
            print_error "Provided ParaView path does not exist: $1"
            exit 1
        fi
    fi
    
    if [[ -z "$PARAVIEW_PATH" ]]; then
        print_error "ParaView 6.0.0 not found in common locations."
        print_info "Please either:"
        print_info "  1. Install ParaView 6.0.0 from https://www.paraview.org/download/"
        print_info "  2. Run this script with the ParaView path: $0 /path/to/paraview"
        exit 1
    fi
}

# Function to find ParaView Python packages
find_paraview_python() {
    print_info "Locating ParaView Python packages..."
    
    OS=$(get_os)
    
    case "$OS" in
        "windows")
            PARAVIEW_PYTHON_PATH="$PARAVIEW_PATH/bin/Lib/site-packages"
            ;;
        "macos")
            if [[ "$PARAVIEW_PATH" == *.app ]]; then
                PARAVIEW_PYTHON_PATH="$PARAVIEW_PATH/Contents/bin/site-packages"
            else
                PARAVIEW_PYTHON_PATH="$PARAVIEW_PATH/lib/python3.12/site-packages"
            fi
            ;;
        "linux")
            PARAVIEW_PYTHON_PATH="$PARAVIEW_PATH/lib/python3.12/site-packages"
            ;;
    esac
    
    if [[ ! -d "$PARAVIEW_PYTHON_PATH" ]]; then
        print_error "ParaView Python packages not found at: $PARAVIEW_PYTHON_PATH"
        print_info "Please verify your ParaView installation or provide the correct path."
        exit 1
    fi
    
    print_success "Found ParaView Python packages at: $PARAVIEW_PYTHON_PATH"
}

# Function to set PYTHONPATH
set_python_path() {
    print_info "Setting up PYTHONPATH..."
    
    # Get current directory for .typing folder
    TYPING_PATH="$(pwd)/.typing"
    
    # Create .typing directory if it doesn't exist
    if [[ ! -d "$TYPING_PATH" ]]; then
        mkdir -p "$TYPING_PATH"
        print_info "Created .typing directory"
    fi
    
    OS=$(get_os)
    
    case "$OS" in
        "windows")
            # Windows uses semicolon separator
            export PYTHONPATH="$TYPING_PATH;$PARAVIEW_PYTHON_PATH"
            ;;
        "macos"|"linux")
            # Unix systems use colon separator
            export PYTHONPATH="$TYPING_PATH:$PARAVIEW_PYTHON_PATH"
            ;;
    esac
    
    print_success "PYTHONPATH set to: $PYTHONPATH"
}

# Function to setup virtual environment
setup_venv() {
    print_info "Setting up virtual environment..."
    
    VENV_DIR="venv"
    
    if [[ ! -d "$VENV_DIR" ]]; then
        print_info "Creating new virtual environment..."
        $PYTHON_CMD -m venv "$VENV_DIR"
        print_success "Virtual environment created"
    else
        print_info "Using existing virtual environment"
    fi
    
    # Activate virtual environment
    print_info "Activating virtual environment..."
    OS=$(get_os)
    
    case "$OS" in
        "windows")
            source "$VENV_DIR/Scripts/activate"
            ;;
        "macos"|"linux")
            source "$VENV_DIR/bin/activate"
            ;;
    esac
    
    print_success "Virtual environment activated"
    
    # Upgrade pip
    print_info "Upgrading pip..."
    python -m pip install --upgrade pip
}

# Function to install packages
install_packages() {
    print_info "Installing required packages..."
    
    # Install both foamai-core and foamai-desktop in development mode
    print_info "Installing foamai-core (development mode)..."
    pip install -e ../foamai-core/
    
    print_info "Installing foamai-desktop (development mode)..."
    pip install -e .
    
    print_success "All packages installed successfully"
}

# Function to run the application
run_application() {
    print_info "Starting FoamAI Desktop Application..."
    print_info "PYTHONPATH is set to: $PYTHONPATH"
    print_info "Running: python -m foamai_desktop.main"
    
    python -m foamai_desktop.main
}

# Main script execution
main() {
    print_info "FoamAI Desktop Setup Script"
    print_info "=============================="
    
    # Parse command line arguments
    PARAVIEW_CUSTOM_PATH=""
    SKIP_RUN=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --paraview-path)
                PARAVIEW_CUSTOM_PATH="$2"
                shift 2
                ;;
            --skip-run)
                SKIP_RUN=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --paraview-path PATH    Specify custom ParaView installation path"
                echo "  --skip-run             Set up environment but don't run the application"
                echo "  --help, -h             Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Execute setup steps
    check_python
    find_paraview "$PARAVIEW_CUSTOM_PATH"
    find_paraview_python
    set_python_path
    setup_venv
    install_packages
    
    if [[ "$SKIP_RUN" == false ]]; then
        echo
        print_success "Setup completed successfully!"
        print_info "You can now run the application anytime with:"
        print_info "  cd src/foamai-desktop"
        print_info "  source venv/bin/activate  # (or venv\\Scripts\\activate on Windows)"
        print_info "  export PYTHONPATH=\"$(pwd)/.typing:$PARAVIEW_PYTHON_PATH\"  # (adjust path separator for your OS)"
        print_info "  python -m foamai_desktop.main"
        echo
        run_application
    else
        print_success "Setup completed successfully!"
        print_info "To run the application:"
        print_info "  source venv/bin/activate  # (or venv\\Scripts\\activate on Windows)"
        print_info "  python -m foamai_desktop.main"
    fi
}

# Run main function with all arguments
main "$@" 