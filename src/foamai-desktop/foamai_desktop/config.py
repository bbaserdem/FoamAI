"""
Configuration settings for OpenFOAM Desktop Application
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration class"""
    
    # Server Configuration
    SERVER_HOST = os.getenv('SERVER_HOST', 'localhost')
    SERVER_PORT = os.getenv('SERVER_PORT', '8000')
    SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
    
    # ParaView Server Configuration
    PARAVIEW_SERVER_HOST = os.getenv('PARAVIEW_SERVER_HOST', 'localhost')
    PARAVIEW_SERVER_PORT = int(os.getenv('PARAVIEW_SERVER_PORT', '11111'))
    
    # New Project-Based API Endpoints
    API_ENDPOINTS = {
        # Health check
        'health': '/health',
        
        # Project management
        'projects': '/api/projects',
        'project_detail': '/api/projects/{project_name}',
        'project_delete': '/api/projects/{project_name}',
        
        # File management
        'upload_file': '/api/projects/{project_name}/upload',
        
        # Command execution
        'run_command': '/api/projects/{project_name}/run_command',
        
        # ParaView server management
        'start_pvserver': '/api/projects/{project_name}/pvserver/start',
        'stop_pvserver': '/api/projects/{project_name}/pvserver/stop',
        'pvserver_info': '/api/projects/{project_name}/pvserver/info',
        
        # System information
        'list_pvservers': '/api/pvservers',
        'system_stats': '/api/system/stats',
    }
    
    # Application Settings
    WINDOW_WIDTH = int(os.getenv('WINDOW_WIDTH', '1200'))
    WINDOW_HEIGHT = int(os.getenv('WINDOW_HEIGHT', '800'))
    
    # Chat Interface Settings
    CHAT_HISTORY_LIMIT = int(os.getenv('CHAT_HISTORY_LIMIT', '100'))
    
    # ParaView Settings
    PARAVIEW_TIMEOUT = int(os.getenv('PARAVIEW_TIMEOUT', '30'))
    
    # Request Timeout
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '60'))
    
    # File Upload Settings
    MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', '300'))  # MB
    
    @classmethod
    def get_server_url(cls):
        """Get the complete server URL"""
        return cls.SERVER_URL
    
    @classmethod
    def get_api_url(cls, endpoint, **kwargs):
        """Get the complete API URL for a specific endpoint with parameter substitution"""
        endpoint_template = cls.API_ENDPOINTS[endpoint]
        endpoint_path = endpoint_template.format(**kwargs)
        return f"{cls.SERVER_URL}{endpoint_path}"
    
    @classmethod
    def get_paraview_server_info(cls):
        """Get ParaView server connection info"""
        return {
            'host': cls.PARAVIEW_SERVER_HOST,
            'port': cls.PARAVIEW_SERVER_PORT
        } 