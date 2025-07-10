#!/usr/bin/env python3
"""
FoamAI Service Test Suite

Tests the deployed FoamAI CFD service functionality across all components:
- Current API endpoints (minimal FastAPI)
- Infrastructure components (OpenFOAM, ParaView)  
- Future CFD functionality preparation

Prerequisites:
    uv sync --group test  # Install testing dependencies

Usage:
    python test-foamai-service.py [--host <deployment-host>] [--verbose]
"""

import asyncio
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse
import os

try:
    import aiohttp
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError as e:
    print(f"Missing required dependencies. Install with:")
    print(f"uv sync --group test")
    sys.exit(1)

class FoamAIServiceTester:
    """Comprehensive FoamAI service functionality tester"""
    
    def __init__(self, host: str = "localhost", api_port: int = 8000, paraview_port: int = 11111, verbose: bool = False):
        self.host = host
        self.api_port = api_port
        self.paraview_port = paraview_port
        self.verbose = verbose
        self.test_results = {}
        
    def log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        if level == "ERROR" or self.verbose:
            print(f"[{timestamp}] {level}: {message}")
    
    async def test_current_api_functionality(self) -> Dict[str, bool]:
        """Test the currently deployed minimal FastAPI functionality"""
        self.log("Testing current FastAPI functionality...")
        
        results = {}
        base_url = f"http://{self.host}:{self.api_port}"
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            # Test root endpoint
            try:
                async with session.get(f"{base_url}/") as response:
                    results["root_endpoint"] = response.status == 200
                    if response.status == 200:
                        content = await response.json()
                        expected_message = "FoamAI API is running!"
                        results["root_message_correct"] = content.get("message") == expected_message
                        self.log(f"✓ Root endpoint: {content}")
                    else:
                        results["root_message_correct"] = False
                        self.log(f"✗ Root endpoint failed: {response.status}", "ERROR")
            except Exception as e:
                results["root_endpoint"] = False
                results["root_message_correct"] = False
                self.log(f"✗ Root endpoint error: {e}", "ERROR")
            
            # Test health check
            try:
                async with session.get(f"{base_url}/ping") as response:
                    results["health_check"] = response.status == 200
                    if response.status == 200:
                        content = await response.text()
                        content_clean = content.strip('"')  # Remove quotes if present
                        results["health_response_correct"] = content_clean == "pong"
                        self.log(f"✓ Health check: {content_clean}")
                    else:
                        results["health_response_correct"] = False
                        self.log(f"✗ Health check failed: {response.status}", "ERROR")
            except Exception as e:
                results["health_check"] = False
                results["health_response_correct"] = False
                self.log(f"✗ Health check error: {e}", "ERROR")
            
            # Test API documentation
            try:
                async with session.get(f"{base_url}/docs") as response:
                    results["api_docs"] = response.status == 200
                    if response.status == 200:
                        self.log("✓ API documentation accessible")
                    else:
                        self.log(f"✗ API docs failed: {response.status}", "ERROR")
            except Exception as e:
                results["api_docs"] = False
                self.log(f"✗ API docs error: {e}", "ERROR")
            
            # Test OpenAPI schema
            try:
                async with session.get(f"{base_url}/openapi.json") as response:
                    results["openapi_schema"] = response.status == 200
                    if response.status == 200:
                        schema = await response.json()
                        results["openapi_has_endpoints"] = len(schema.get("paths", {})) >= 2
                        self.log(f"✓ OpenAPI schema: {len(schema.get('paths', {}))} endpoints")
                    else:
                        results["openapi_has_endpoints"] = False
                        self.log(f"✗ OpenAPI schema failed: {response.status}", "ERROR")
            except Exception as e:
                results["openapi_schema"] = False
                results["openapi_has_endpoints"] = False
                self.log(f"✗ OpenAPI schema error: {e}", "ERROR")
        
        self.test_results["current_api"] = results
        return results
    
    async def test_infrastructure_components(self) -> Dict[str, bool]:
        """Test the infrastructure components (containers, services)"""
        self.log("Testing infrastructure components...")
        
        results = {}
        
        # Test ParaView server port accessibility
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.host, self.paraview_port))
            sock.close()
            
            results["paraview_port_accessible"] = result == 0
            if result == 0:
                self.log(f"✓ ParaView server port {self.paraview_port} accessible")
            else:
                self.log(f"✗ ParaView server port {self.paraview_port} not accessible", "ERROR")
        except Exception as e:
            results["paraview_port_accessible"] = False
            self.log(f"✗ ParaView port test error: {e}", "ERROR")
        
        # Test if we can reach the host's Docker API (if local)
        if self.host in ["localhost", "127.0.0.1"]:
            try:
                result = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=10)
                results["docker_accessible"] = result.returncode == 0
                if result.returncode == 0:
                    self.log("✓ Docker daemon accessible")
                    # Check for FoamAI containers
                    containers = result.stdout
                    results["foamai_containers_running"] = "foamai" in containers.lower()
                    if "foamai" in containers.lower():
                        self.log("✓ FoamAI containers detected")
                    else:
                        self.log("! No FoamAI containers detected in docker ps")
                else:
                    results["foamai_containers_running"] = False
                    self.log(f"✗ Docker command failed: {result.stderr}", "ERROR")
            except Exception as e:
                results["docker_accessible"] = False
                results["foamai_containers_running"] = False
                self.log(f"✗ Docker test error: {e}", "ERROR")
        else:
            results["docker_accessible"] = None  # Cannot test remotely
            results["foamai_containers_running"] = None
            self.log("! Docker tests skipped (remote host)")
        
        self.test_results["infrastructure"] = results
        return results
    
    async def test_future_cfd_endpoints(self) -> Dict[str, bool]:
        """Test endpoints that should exist in the full CFD implementation"""
        self.log("Testing for future CFD functionality endpoints...")
        
        results = {}
        base_url = f"http://{self.host}:{self.api_port}"
        
        # Expected CFD endpoints based on the architecture docs
        expected_endpoints = [
            ("/simulation/create", "POST", "Create new CFD simulation"),
            ("/simulation/{id}/status", "GET", "Get simulation status"),
            ("/simulation/{id}/results", "GET", "Get simulation results"),
            ("/openfoam/solvers", "GET", "List available OpenFOAM solvers"),
            ("/paraview/session", "POST", "Create ParaView session"),
            ("/health", "GET", "Enhanced health check"),
            ("/agents/interpret", "POST", "Natural language interpretation"),
        ]
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            for endpoint, method, description in expected_endpoints:
                endpoint_key = f"future_{endpoint.replace('/', '_').replace('{', '').replace('}', '')}"
                
                try:
                    # Test with actual endpoint (replace placeholders)
                    test_endpoint = endpoint.replace("{id}", "test-id")
                    url = f"{base_url}{test_endpoint}"
                    
                    async with session.request(method, url) as response:
                        # We expect 404 for now since these don't exist yet
                        # But if we get 200, 405 (method not allowed), or other responses, note them
                        results[endpoint_key] = response.status != 404
                        
                        if response.status == 404:
                            self.log(f"- {description}: Not implemented yet (404) ✓ Expected")
                        elif response.status == 405:
                            self.log(f"- {description}: Method not allowed (405) - endpoint exists!")
                        elif response.status < 400:
                            self.log(f"✓ {description}: Working! ({response.status})")
                        else:
                            self.log(f"! {description}: Unexpected response ({response.status})")
                            
                except Exception as e:
                    results[endpoint_key] = False
                    if self.verbose:
                        self.log(f"- {description}: {e}")
        
        self.test_results["future_cfd"] = results
        return results
    
    async def test_service_performance(self) -> Dict[str, bool]:
        """Test basic service performance and reliability"""
        self.log("Testing service performance...")
        
        results = {}
        base_url = f"http://{self.host}:{self.api_port}"
        
        # Response time test
        response_times = []
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            for i in range(5):
                try:
                    start_time = time.time()
                    async with session.get(f"{base_url}/ping") as response:
                        end_time = time.time()
                        if response.status == 200:
                            response_times.append(end_time - start_time)
                except Exception as e:
                    self.log(f"Performance test {i+1} failed: {e}", "ERROR")
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            results["avg_response_time_acceptable"] = avg_response_time < 1.0  # Less than 1 second
            results["all_requests_successful"] = len(response_times) == 5
            self.log(f"✓ Average response time: {avg_response_time:.3f}s")
        else:
            results["avg_response_time_acceptable"] = False
            results["all_requests_successful"] = False
            self.log("✗ No successful performance tests", "ERROR")
        
        self.test_results["performance"] = results
        return results
    
    def print_detailed_report(self):
        """Print a comprehensive test report"""
        print("\n" + "="*80)
        print("FOAMAI SERVICE TEST REPORT")
        print("="*80)
        
        # Current API functionality
        if "current_api" in self.test_results:
            print("\n🚀 CURRENT API FUNCTIONALITY:")
            print("-" * 40)
            api_results = self.test_results["current_api"]
            for test, passed in api_results.items():
                status = "✓ PASS" if passed else "✗ FAIL"
                print(f"  {test}: {status}")
        
        # Infrastructure
        if "infrastructure" in self.test_results:
            print("\n🏗️ INFRASTRUCTURE COMPONENTS:")
            print("-" * 40)
            infra_results = self.test_results["infrastructure"]
            for test, passed in infra_results.items():
                if passed is None:
                    status = "- SKIP"
                else:
                    status = "✓ PASS" if passed else "✗ FAIL"
                print(f"  {test}: {status}")
        
        # Future CFD endpoints
        if "future_cfd" in self.test_results:
            print("\n🔮 FUTURE CFD ENDPOINTS:")
            print("-" * 40)
            cfd_results = self.test_results["future_cfd"]
            implemented_count = sum(1 for passed in cfd_results.values() if passed)
            total_count = len(cfd_results)
            print(f"  Implemented: {implemented_count}/{total_count}")
            if implemented_count > 0:
                for test, passed in cfd_results.items():
                    if passed:
                        print(f"  ✓ {test}: IMPLEMENTED")
        
        # Performance
        if "performance" in self.test_results:
            print("\n⚡ PERFORMANCE TESTS:")
            print("-" * 40)
            perf_results = self.test_results["performance"]
            for test, passed in perf_results.items():
                status = "✓ PASS" if passed else "✗ FAIL"
                print(f"  {test}: {status}")
        
        # Summary
        print("\n" + "="*80)
        total_tests = sum(len(results) for results in self.test_results.values() if isinstance(results, dict))
        passed_tests = sum(
            sum(1 for passed in results.values() if passed is True)
            for results in self.test_results.values() 
            if isinstance(results, dict)
        )
        print(f"OVERALL SUMMARY: {passed_tests}/{total_tests} tests passed")
        
        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        print("-" * 40)
        if "current_api" in self.test_results:
            api_results = self.test_results["current_api"]
            if all(api_results.values()):
                print("  ✓ Basic API is working perfectly")
            else:
                print("  ! Basic API has issues - check connectivity")
        
        cfd_implemented = 0
        if "future_cfd" in self.test_results:
            cfd_implemented = sum(1 for passed in self.test_results["future_cfd"].values() if passed)
        
        if cfd_implemented == 0:
            print("  📋 Next step: Implement CFD functionality (OpenFOAM integration)")
            print("  📋 Next step: Add natural language processing endpoints")
            print("  📋 Next step: Implement simulation management endpoints")
        else:
            print(f"  🎉 CFD implementation is underway! ({cfd_implemented} endpoints found)")
        
        print("="*80)

async def main():
    parser = argparse.ArgumentParser(description="Test FoamAI service functionality")
    parser.add_argument("--host", default="localhost", help="Target host (default: localhost)")
    parser.add_argument("--api-port", type=int, default=8000, help="API port (default: 8000)")
    parser.add_argument("--paraview-port", type=int, default=11111, help="ParaView port (default: 11111)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    tester = FoamAIServiceTester(
        host=args.host,
        api_port=args.api_port,
        paraview_port=args.paraview_port,
        verbose=args.verbose
    )
    
    print(f"🧪 Testing FoamAI service at {args.host}:{args.api_port}")
    print(f"📊 ParaView server at {args.host}:{args.paraview_port}")
    print("="*80)
    
    # Run all tests
    await tester.test_current_api_functionality()
    await tester.test_infrastructure_components()
    await tester.test_future_cfd_endpoints()
    await tester.test_service_performance()
    
    # Print comprehensive report
    tester.print_detailed_report()

if __name__ == "__main__":
    asyncio.run(main()) 