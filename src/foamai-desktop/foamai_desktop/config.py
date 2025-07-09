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
    
    # API Endpoints
    API_ENDPOINTS = {
        'submit_scenario': '/submit_scenario',
        'approve_mesh': '/approve_mesh',
        'reject_mesh': '/reject_mesh',
        'run_simulation': '/run_simulation',
        'get_results': '/results',
        'get_status': '/status'
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
    
    @classmethod
    def get_server_url(cls):
        """Get the complete server URL"""
        return cls.SERVER_URL
    
    @classmethod
    def get_api_url(cls, endpoint):
        """Get the complete API URL for a specific endpoint"""
        return f"{cls.SERVER_URL}{cls.API_ENDPOINTS[endpoint]}"
    
    @classmethod
    def get_paraview_server_info(cls):
        """Get ParaView server connection info"""
        return {
            'host': cls.PARAVIEW_SERVER_HOST,
            'port': cls.PARAVIEW_SERVER_PORT
        } 