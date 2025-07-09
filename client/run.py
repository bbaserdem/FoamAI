#!/usr/bin/env python3
"""
Quick start script for OpenFOAM Desktop Assistant
Provides better error handling and setup checks
"""
import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is sufficient"""
    if sys.version_info < (3, 7):
        print("Error: Python 3.7 or higher is required.")
        print(f"Current version: {sys.version}")
        return False
    return True

def check_dependencies():
    """Check if required packages are installed"""
    # Map package names to their actual import names
    required_packages = {
        'PySide6': 'PySide6',
        'requests': 'requests',
        'python-dotenv': 'dotenv',
        'numpy': 'numpy'
    }
    
    optional_packages = {
        'paraview': 'paraview'
    }
    
    missing_required = []
    missing_optional = []
    
    for package_name, import_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_required.append(package_name)
    
    for package_name, import_name in optional_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_optional.append(package_name)
    
    if missing_required:
        print("Error: Missing required packages:")
        for package in missing_required:
            print(f"  - {package}")
        print("\nInstall missing packages with:")
        print("  pip install -r requirements.txt")
        return False
    
    if missing_optional:
        print("Warning: Missing optional packages:")
        for package in missing_optional:
            print(f"  - {package}")
        print("Some features may not work properly.")
        print()
    
    return True

def create_env_file():
    """Create .env file if it doesn't exist"""
    env_file = Path('.env')
    if not env_file.exists():
        print("Creating .env file with default settings...")
        env_content = """# OpenFOAM Desktop Application Configuration

# Server Configuration
SERVER_HOST=localhost
SERVER_PORT=8000

# ParaView Server Configuration
PARAVIEW_SERVER_HOST=localhost
PARAVIEW_SERVER_PORT=11111

# Application Settings
WINDOW_WIDTH=1200
WINDOW_HEIGHT=800

# Chat Interface Settings
CHAT_HISTORY_LIMIT=100

# ParaView Settings
PARAVIEW_TIMEOUT=30

# Request Timeout (seconds)
REQUEST_TIMEOUT=60
"""
        with open(env_file, 'w') as f:
            f.write(env_content)
        print(f"Created {env_file}")
        print("Please edit this file to match your server configuration.")
        print()

def create_logs_directory():
    """Create logs directory if it doesn't exist"""
    logs_dir = Path('logs')
    if not logs_dir.exists():
        logs_dir.mkdir()
        print(f"Created {logs_dir} directory")

def main():
    """Main function to run the application"""
    print("OpenFOAM Desktop Assistant - Quick Start")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Create necessary files/directories
    create_env_file()
    create_logs_directory()
    
    print("Starting OpenFOAM Desktop Assistant...")
    print("=" * 40)
    print()
    
    # Import and run the main application
    try:
        from main import main as app_main
        sys.exit(app_main())
    except ImportError as e:
        print(f"Error importing main application: {e}")
        print("Please ensure all files are in the correct location.")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 