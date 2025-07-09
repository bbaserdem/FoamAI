"""
Configuration module for FoamAI backend API.

This module centralizes configuration constants that were previously 
scattered across different modules, improving maintainability and 
making the system more configurable.
"""

# PVServer Management Configuration
MAX_CONCURRENT_PVSERVERS = 6
CLEANUP_THRESHOLD_HOURS = 4

# Port Configuration
PORT_RANGE_START = 11111
PORT_RANGE_END = 11116

# Database Configuration
DATABASE_PATH = 'tasks.db'

# Process Management Configuration
PROCESS_CHECK_TIMEOUT = 5  # seconds
PVSERVER_START_TIMEOUT = 30  # seconds

# Logging Configuration
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Development/Debug Configuration
DEBUG_MODE = False
VERBOSE_LOGGING = False 