"""
Configuration module for FoamAI backend API.

This module centralizes configuration constants that were previously 
scattered across different modules, improving maintainability and 
making the system more configurable.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists
load_dotenv()

# PVServer Management Configuration
MAX_CONCURRENT_PVSERVERS = 6
CLEANUP_THRESHOLD_HOURS = 4

# Port Configuration
PORT_RANGE_START = 11111
PORT_RANGE_END = 11116
API_PORT = int(os.environ.get("API_PORT", "8000"))

# Database Configuration
DATABASE_PATH = 'tasks.db'

# Project Configuration
PROJECTS_BASE_PATH = Path(os.environ.get("PROJECTS_BASE_PATH", "~/foam_projects")).expanduser()

# File Upload Configuration
MAX_UPLOAD_SIZE = 300 * 1024 * 1024  # 300MB in bytes

# --- General Application Settings ---
# Load EC2_HOST from environment or default to localhost if not set
EC2_HOST = os.environ.get("EC2_HOST", "127.0.0.1")

# --- PVServer Management Configuration ---
PROCESS_CHECK_TIMEOUT = 5  # seconds
PVSERVER_START_TIMEOUT = 30  # seconds

# Logging Configuration
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Development/Debug Configuration
DEBUG_MODE = False
VERBOSE_LOGGING = False 
