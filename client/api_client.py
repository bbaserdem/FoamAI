"""
API Client for OpenFOAM Desktop Application
Handles all REST API communication with the server
"""
import requests
import json
import logging
from typing import Dict, Any, Optional
from config import Config

logger = logging.getLogger(__name__)

class APIClient:
    """Client for communicating with the OpenFOAM server API"""
    
    def __init__(self):
        self.base_url = Config.get_server_url()
        self.timeout = Config.REQUEST_TIMEOUT
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'OpenFOAM-Desktop-App/1.0'
        })
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make a generic HTTP request to the server
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint key from config
            data: Optional data to send with request
            
        Returns:
            Response data as dictionary
            
        Raises:
            requests.RequestException: If request fails
        """
        try:
            url = Config.get_api_url(endpoint)
            
            logger.info(f"Making {method} request to {url}")
            
            if method.upper() == 'GET':
                response = self.session.get(url, timeout=self.timeout)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, timeout=self.timeout)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, timeout=self.timeout)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                return response.json()
            except json.JSONDecodeError:
                return {'message': response.text}
                
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise
    
    def submit_scenario(self, scenario_description: str) -> Dict[str, Any]:
        """
        Submit a simulation scenario to the server
        
        Args:
            scenario_description: Natural language description of the scenario
            
        Returns:
            Server response with task ID and status
        """
        data = {
            'scenario': scenario_description,
            'timestamp': self._get_timestamp()
        }
        
        return self._make_request('POST', 'submit_scenario', data)
    
    def approve_mesh(self, task_id: str) -> Dict[str, Any]:
        """
        Approve a generated mesh
        
        Args:
            task_id: Task ID from the scenario submission
            
        Returns:
            Server response confirming approval
        """
        data = {
            'task_id': task_id,
            'approved': True
        }
        
        return self._make_request('POST', 'approve_mesh', data)
    
    def reject_mesh(self, task_id: str, feedback: str) -> Dict[str, Any]:
        """
        Reject a generated mesh with feedback
        
        Args:
            task_id: Task ID from the scenario submission
            feedback: User feedback about why mesh was rejected
            
        Returns:
            Server response confirming rejection
        """
        data = {
            'task_id': task_id,
            'approved': False,
            'feedback': feedback
        }
        
        return self._make_request('POST', 'reject_mesh', data)
    
    def run_simulation(self, task_id: str) -> Dict[str, Any]:
        """
        Start simulation execution
        
        Args:
            task_id: Task ID from the scenario submission
            
        Returns:
            Server response with simulation status
        """
        data = {
            'task_id': task_id
        }
        
        return self._make_request('POST', 'run_simulation', data)
    
    def get_results(self, task_id: str) -> Dict[str, Any]:
        """
        Get simulation results
        
        Args:
            task_id: Task ID from the scenario submission
            
        Returns:
            Server response with results file paths
        """
        url = f"{Config.get_api_url('get_results')}/{task_id}"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get results: {str(e)}")
            raise
    
    def get_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status
        
        Args:
            task_id: Task ID to check status for
            
        Returns:
            Server response with current task status
        """
        url = f"{Config.get_api_url('get_status')}/{task_id}"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get status: {str(e)}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test if the server is reachable
        
        Returns:
            True if server is reachable, False otherwise
        """
        try:
            response = self.session.get(self.base_url, timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def _get_timestamp(self) -> str:
        """Get current timestamp as string"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def close(self):
        """Close the session"""
        self.session.close() 