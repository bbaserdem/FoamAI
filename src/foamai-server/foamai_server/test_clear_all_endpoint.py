#!/usr/bin/env python3
"""
Test script to call the new clear-all pvservers endpoint.
"""

import requests
import json
import sys
from config import EC2_HOST, API_PORT

def test_clear_all_endpoint():
    """Test the clear-all pvservers endpoint"""
    
    # Get host and port from config
    host = EC2_HOST
    port = API_PORT
    
    url = f"http://{host}:{port}/api/pvservers/clear-all"
    
    print(f"🧹 Testing clear-all endpoint: {url}")
    print("=" * 50)
    
    try:
        # Make the POST request
        response = requests.post(url, json={}, timeout=30)
        
        print(f"📡 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Success! Response:")
            print(json.dumps(result, indent=2))
            
            # Show summary
            print("\n📊 Summary:")
            print(f"   Task PVServers Stopped: {result.get('task_pvservers_stopped', 0)}")
            print(f"   Project PVServers Stopped: {result.get('project_pvservers_stopped', 0)}")
            print(f"   System Processes Stopped: {result.get('system_processes_stopped', 0)}")
            print(f"   Stale Entries Cleaned: {result.get('stale_entries_cleaned', 0)}")
            print(f"   Total Stopped: {result.get('total_stopped', 0)}")
            print(f"   Total Failed: {result.get('total_failed', 0)}")
            
            if result.get('total_stopped', 0) > 0:
                print(f"\n🎉 Successfully cleared {result.get('total_stopped', 0)} PVServers!")
            else:
                print("\n💡 No PVServers were running")
                
        else:
            print(f"❌ Error: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Error text: {response.text}")
                
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Could not connect to the server")
        print(f"   Make sure the server is running at {host}:{port}")
        return False
    except requests.exceptions.Timeout:
        print("❌ Timeout Error: Request took too long")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🧪 FoamAI Clear-All PVServers Test")
    print("=" * 40)
    
    success = test_clear_all_endpoint()
    
    if success:
        print("\n✅ Test completed!")
    else:
        print("\n❌ Test failed!")
        sys.exit(1) 