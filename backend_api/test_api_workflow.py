#!/usr/bin/env python3
"""
FoamAI API Workflow Test Script
Demonstrates complete workflow: Submit scenario -> Approve mesh -> Get results
"""

import requests
import json
import time
import sys
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://3.139.77.134:8000"  # Replace with your actual EC2 instance
HEADERS = {"Content-Type": "application/json"}

def print_json_response(title: str, response: requests.Response) -> Dict[Any, Any]:
    """Print formatted JSON response"""
    print(f"\n{'='*60}")
    print(f"📡 {title}")
    print(f"{'='*60}")
    print(f"🌐 URL: {response.url}")
    print(f"📊 Status Code: {response.status_code}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            print(f"✅ Response JSON:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return data
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON response")
            print(f"Raw response: {response.text}")
            return {}
    else:
        print(f"❌ Error Response:")
        print(f"Raw response: {response.text}")
        return {}

def wait_for_task_completion(task_id: str, max_wait_seconds: int = 300) -> Dict[Any, Any]:
    """Wait for task to complete and return final status"""
    print(f"\n⏳ Waiting for task {task_id} to complete...")
    start_time = time.time()
    
    while time.time() - start_time < max_wait_seconds:
        try:
            response = requests.get(f"{API_BASE_URL}/api/task_status/{task_id}")
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', 'unknown')
                
                print(f"⏱️  [{int(time.time() - start_time)}s] Status: {status}")
                
                if status in ['SUCCESS', 'FAILURE']:
                    return data
                elif status == 'PENDING':
                    print(f"   📝 Task is queued...")
                elif status == 'PROGRESS':
                    progress_msg = data.get('progress', {}).get('message', 'Processing...')
                    print(f"   🔄 {progress_msg}")
                
                time.sleep(3)  # Wait 3 seconds between checks
            else:
                print(f"❌ Error checking status: {response.status_code}")
                time.sleep(5)
        except Exception as e:
            print(f"❌ Exception checking status: {e}")
            time.sleep(5)
    
    print(f"⏰ Timeout waiting for task completion")
    return {}

def test_health_check():
    """Test API health check"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        print_json_response("Health Check", response)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def step1_generate_mesh() -> str:
    """Step 1: Generate mesh (submit scenario)"""
    print(f"\n🚀 STEP 1: Generate Mesh (Submit Scenario)")
    
    # Cavity flow scenario parameters
    mesh_payload = {
        "scenario_type": "cavity_flow",
        "parameters": {
            "geometry": {
                "width": 1.0,
                "height": 1.0,
                "depth": 0.1
            },
            "mesh": {
                "resolution": 20,
                "boundary_layers": 3
            },
            "boundary_conditions": {
                "moving_wall_velocity": 1.0,
                "kinematic_viscosity": 0.01
            }
        }
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/generate_mesh",
            json=mesh_payload,
            headers=HEADERS,
            timeout=30
        )
        
        data = print_json_response("Generate Mesh Request", response)
        
        if response.status_code == 200:
            task_id = data.get('task_id')
            if task_id:
                print(f"✅ Mesh generation started - Task ID: {task_id}")
                return task_id
            else:
                print(f"❌ No task_id in response")
                return ""
        else:
            print(f"❌ Mesh generation failed")
            return ""
            
    except Exception as e:
        print(f"❌ Exception in mesh generation: {e}")
        return ""

def step2_run_solver(task_id: str) -> str:
    """Step 2: Run solver (approve mesh)"""
    print(f"\n🚀 STEP 2: Run Solver (Approve Mesh)")
    
    solver_payload = {
        "task_id": task_id,
        "solver_type": "icoFoam",
        "parameters": {
            "end_time": 10.0,
            "time_step": 0.005,
            "write_interval": 1.0
        }
    }
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/run_solver",
            json=solver_payload,
            headers=HEADERS,
            timeout=30
        )
        
        data = print_json_response("Run Solver Request", response)
        
        if response.status_code == 200:
            solver_task_id = data.get('task_id')
            if solver_task_id:
                print(f"✅ Solver started - Task ID: {solver_task_id}")
                return solver_task_id
            else:
                print(f"❌ No task_id in response")
                return ""
        else:
            print(f"❌ Solver execution failed")
            return ""
            
    except Exception as e:
        print(f"❌ Exception in solver execution: {e}")
        return ""

def step3_get_results(task_id: str):
    """Step 3: Get results and pvserver info"""
    print(f"\n🚀 STEP 3: Get Results and PVServer Info")
    
    # Get final task status
    try:
        response = requests.get(f"{API_BASE_URL}/api/task_status/{task_id}")
        final_status = print_json_response("Final Task Status", response)
        
        # Get pvserver connection info
        response = requests.get(f"{API_BASE_URL}/api/pvserver_info/{task_id}")
        pvserver_info = print_json_response("PVServer Connection Info", response)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 WORKFLOW SUMMARY")
        print(f"{'='*60}")
        
        if final_status:
            print(f"🎯 Task Status: {final_status.get('status', 'unknown')}")
            if final_status.get('status') == 'SUCCESS':
                print(f"✅ Simulation completed successfully!")
                
                # Extract pvserver info
                if pvserver_info and pvserver_info.get('pvserver_info'):
                    pv_info = pvserver_info['pvserver_info']
                    print(f"🖥️  ParaView Connection Info:")
                    print(f"   📡 Host: {pv_info.get('host', 'N/A')}")
                    print(f"   🔌 Port: {pv_info.get('port', 'N/A')}")
                    print(f"   📁 Case Path: {pv_info.get('case_path', 'N/A')}")
                    print(f"   🎮 Status: {pv_info.get('status', 'N/A')}")
                    
                    if pv_info.get('status') == 'running':
                        print(f"\n🚀 Ready to connect ParaView to:")
                        print(f"   pvserver://{pv_info.get('host', 'localhost')}:{pv_info.get('port', 11111)}")
                else:
                    print(f"⚠️  No PVServer info available")
            else:
                print(f"❌ Simulation failed or still running")
                if final_status.get('error'):
                    print(f"   Error: {final_status['error']}")
        else:
            print(f"❌ Could not get final status")
            
    except Exception as e:
        print(f"❌ Exception getting results: {e}")

def main():
    """Main workflow function"""
    print(f"🎯 FoamAI API Workflow Test")
    print(f"{'='*60}")
    print(f"🌐 API Base URL: {API_BASE_URL}")
    print(f"📅 Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if user provided API URL
    if len(sys.argv) > 1:
        global API_BASE_URL
        API_BASE_URL = sys.argv[1].rstrip('/')
        print(f"🔄 Using provided API URL: {API_BASE_URL}")
    
    # Health check
    if not test_health_check():
        print(f"❌ Health check failed. Please check:")
        print(f"   1. API server is running")
        print(f"   2. URL is correct: {API_BASE_URL}")
        print(f"   3. Firewall allows connection")
        return
    
    print(f"✅ API is healthy!")
    
    # Step 1: Generate mesh
    mesh_task_id = step1_generate_mesh()
    if not mesh_task_id:
        print(f"❌ Failed to start mesh generation")
        return
    
    # Wait for mesh generation to complete
    mesh_result = wait_for_task_completion(mesh_task_id)
    if not mesh_result or mesh_result.get('status') != 'SUCCESS':
        print(f"❌ Mesh generation failed or timeout")
        return
    
    print(f"✅ Mesh generation completed!")
    
    # Step 2: Run solver
    solver_task_id = step2_run_solver(mesh_task_id)
    if not solver_task_id:
        print(f"❌ Failed to start solver")
        return
    
    # Wait for solver to complete
    solver_result = wait_for_task_completion(solver_task_id, max_wait_seconds=600)  # 10 minutes
    if not solver_result:
        print(f"❌ Solver execution timeout")
        return
    
    # Step 3: Get results
    step3_get_results(solver_task_id)
    
    print(f"\n🎉 Workflow completed!")
    print(f"📅 Finished at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 
