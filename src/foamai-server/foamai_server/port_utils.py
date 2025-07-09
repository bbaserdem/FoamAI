import socket
from typing import Optional, Tuple

# Port Configuration
PVSERVER_PORT_RANGE = (11111, 11116)  # 6 ports: 11111-11116

class PortError(Exception):
    """Custom exception for port-related errors"""
    pass

class PortInUseError(PortError):
    """Exception raised when a port is already in use"""
    pass

def port_is_available(port: int) -> bool:
    """
    Check if a port is available for use
    
    Args:
        port: Port number to check
        
    Returns:
        bool: True if port is available, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', port))
            return True
    except socket.error:
        return False

def find_available_port(port_range: Optional[Tuple[int, int]] = None) -> Optional[int]:
    """
    Find the next available port in the configured range
    
    Args:
        port_range: Optional tuple of (start_port, end_port). If None, uses PVSERVER_PORT_RANGE
        
    Returns:
        Optional[int]: Available port number, or None if no ports available
    """
    if port_range is None:
        port_range = PVSERVER_PORT_RANGE
    
    start_port, end_port = port_range
    
    for port in range(start_port, end_port + 1):
        if port_is_available(port):
            return port
    
    return None

def get_port_range() -> Tuple[int, int]:
    """
    Get the configured port range for pvservers
    
    Returns:
        Tuple[int, int]: (start_port, end_port)
    """
    return PVSERVER_PORT_RANGE

def get_available_port_count(port_range: Optional[Tuple[int, int]] = None) -> int:
    """
    Count how many ports are available in the range
    
    Args:
        port_range: Optional tuple of (start_port, end_port). If None, uses PVSERVER_PORT_RANGE
        
    Returns:
        int: Number of available ports
    """
    if port_range is None:
        port_range = PVSERVER_PORT_RANGE
    
    start_port, end_port = port_range
    available_count = 0
    
    for port in range(start_port, end_port + 1):
        if port_is_available(port):
            available_count += 1
    
    return available_count

def get_port_status(port_range: Optional[Tuple[int, int]] = None) -> dict:
    """
    Get detailed status of all ports in the range
    
    Args:
        port_range: Optional tuple of (start_port, end_port). If None, uses PVSERVER_PORT_RANGE
        
    Returns:
        dict: Dictionary with port numbers as keys and availability status as values
    """
    if port_range is None:
        port_range = PVSERVER_PORT_RANGE
    
    start_port, end_port = port_range
    port_status = {}
    
    for port in range(start_port, end_port + 1):
        port_status[port] = port_is_available(port)
    
    return port_status

def validate_port_range(start_port: int, end_port: int) -> bool:
    """
    Validate that a port range is valid
    
    Args:
        start_port: Starting port number
        end_port: Ending port number
        
    Returns:
        bool: True if range is valid, False otherwise
    """
    return (
        isinstance(start_port, int) and
        isinstance(end_port, int) and
        1 <= start_port <= 65535 and
        1 <= end_port <= 65535 and
        start_port <= end_port
    )

def is_port_in_range(port: int, port_range: Optional[Tuple[int, int]] = None) -> bool:
    """
    Check if a port is within the configured range
    
    Args:
        port: Port number to check
        port_range: Optional tuple of (start_port, end_port). If None, uses PVSERVER_PORT_RANGE
        
    Returns:
        bool: True if port is in range, False otherwise
    """
    if port_range is None:
        port_range = PVSERVER_PORT_RANGE
    
    start_port, end_port = port_range
    return start_port <= port <= end_port 