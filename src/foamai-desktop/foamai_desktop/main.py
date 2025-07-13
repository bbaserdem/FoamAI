"""
Main entry point for OpenFOAM Desktop Application
"""
import sys
import logging
import os
from pathlib import Path
print(os.environ["PYTHONPATH"])
# Import PySide6 components
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QIcon

# Import application components
from .main_window import MainWindow
from .config import Config

def setup_logging():
    """Setup application logging"""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'openfoam_app.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific loggers
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)

def check_dependencies():
    """Check if all required dependencies are available"""
    missing_deps = []
    
    # Check PySide6
    try:
        import PySide6
    except ImportError:
        missing_deps.append("PySide6")
    
    # Check requests
    try:
        import requests
    except ImportError:
        missing_deps.append("requests")
    
    # Check python-dotenv
    try:
        import dotenv
    except ImportError:
        missing_deps.append("python-dotenv")
    
    # Check numpy
    try:
        import numpy
    except ImportError:
        missing_deps.append("numpy")
    
    # Note: ParaView is optional and handled separately in the application
    
    return missing_deps

def ensure_env_file():
    """Create .env file if it doesn't exist"""
    env_file = Path('.env')
    if not env_file.exists():
        print("Creating .env file with default settings...")
        env_content = """# OpenFOAM Desktop Application Configuration

# OpenAI API Key
OPENAI_API_KEY=sk-proj-

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
        print("You can modify these settings using File > Settings in the application.")
        print()

def create_splash_screen():
    """Create and return a splash screen"""
    # Create a simple splash screen
    splash = QSplashScreen()
    splash.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.SplashScreen)
    
    # Set splash screen text
    splash.showMessage(
        "OpenFOAM Desktop Assistant\nLoading...",
        Qt.AlignCenter | Qt.AlignBottom,
        Qt.white
    )
    
    return splash

def main():
    """Main application entry point"""
    # Ensure .env file exists before setup
    ensure_env_file()
    
    # Setup logging
    logger = setup_logging()
    logger.info("Starting OpenFOAM Desktop Application")
    
    # Check dependencies
    missing_deps = check_dependencies()
    if missing_deps:
        logger.error(f"Missing dependencies: {', '.join(missing_deps)}")
        print(f"Error: Missing required dependencies: {', '.join(missing_deps)}")
        print("Please install missing dependencies using: pip install -r requirements.txt")
        return 1
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("OpenFOAM Desktop Assistant")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("OpenFOAM")
    app.setOrganizationDomain("openfoam.org")
    
    # Set application icon (if available)
    try:
        app.setWindowIcon(QIcon("assets/icon.png"))
    except:
        pass  # Icon file not found, continue without it
    
    # Create and show splash screen
    splash = create_splash_screen()
    splash.show()
    
    # Process events to show splash screen
    app.processEvents()
    
    try:
        # Create main window
        splash.showMessage("Initializing interface...", Qt.AlignCenter | Qt.AlignBottom, Qt.white)
        app.processEvents()
        
        main_window = MainWindow()
        
        # Show main window after a short delay
        def show_main_window():
            splash.finish(main_window)
            main_window.show()
            logger.info("Application started successfully")
        
        # Delay to show splash screen
        QTimer.singleShot(2000, show_main_window)
        
        # Start the application event loop
        exit_code = app.exec()
        
        logger.info(f"Application exiting with code: {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.error(f"Critical error: {str(e)}", exc_info=True)
        
        # Close splash screen if still showing
        if splash:
            splash.close()
        
        # Show error dialog
        error_dialog = QMessageBox()
        error_dialog.setIcon(QMessageBox.Critical)
        error_dialog.setWindowTitle("Critical Error")
        error_dialog.setText("A critical error occurred:")
        error_dialog.setDetailedText(str(e))
        error_dialog.setStandardButtons(QMessageBox.Ok)
        error_dialog.exec()
        
        return 1

if __name__ == "__main__":
    sys.exit(main()) 