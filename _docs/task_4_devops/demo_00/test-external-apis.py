#!/usr/bin/env python3
"""
FoamAI External API Access Test Suite

This script tests all external API access points for the FoamAI CFD deployment:
- AWS ECR (Elastic Container Registry) access for Docker images
- FastAPI backend service endpoints  
- ParaView server TCP connectivity
- General network connectivity and DNS resolution

Prerequisites:
    uv sync --group test  # Install testing dependencies

Usage:
    python test-external-apis.py [--host <deployment-host>] [--verbose]
    ./test-connectivity.sh [host]  # For quick shell-based tests
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
    print(f"or manually: uv add --group test aiohttp boto3")
    sys.exit(1)


class APITestSuite:
    """Comprehensive external API testing for FoamAI deployment"""
    
    def __init__(self, host: str = "localhost", verbose: bool = False):
        self.host = host
        self.verbose = verbose
        self.test_results: Dict[str, Dict] = {}
        
        # Service endpoints from docker-compose.yml
        self.api_port = 8000
        self.paraview_port = 11111
        
        # AWS ECR configuration
        self.aws_region = "us-west-2"  # From docker-compose.yml
        self.ecr_account_id = "843135096105"  # From docker-compose.yml
        self.ecr_repositories = [
            "foamai/api",
            "foamai/openfoam", 
            "foamai/pvserver"
        ]

    def log(self, message: str, level: str = "INFO") -> None:
        """Log messages with optional verbose output"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        if self.verbose or level == "ERROR":
            print(f"[{timestamp}] {level}: {message}")

    async def test_network_connectivity(self) -> Dict[str, bool]:
        """Test basic network connectivity and DNS resolution"""
        self.log("Testing network connectivity...")
        
        results = {}
        test_hosts = [
            ("google.com", 443),
            ("github.com", 443),
            ("docker.io", 443),
            (f"{self.ecr_account_id}.dkr.ecr.{self.aws_region}.amazonaws.com", 443),
            (self.host, self.api_port) if self.host != "localhost" else None
        ]
        
        for host_info in test_hosts:
            if host_info is None:
                continue
                
            host, port = host_info
            try:
                # DNS Resolution test
                socket.gethostbyname(host)
                results[f"dns_{host}"] = True
                self.log(f"✓ DNS resolution for {host}")
                
                # Port connectivity test  
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                sock.close()
                
                results[f"port_{host}_{port}"] = result == 0
                if result == 0:
                    self.log(f"✓ Port {port} accessible on {host}")
                else:
                    self.log(f"✗ Port {port} not accessible on {host}", "ERROR")
                    
            except Exception as e:
                results[f"dns_{host}"] = False
                results[f"port_{host}_{port}"] = False
                self.log(f"✗ Network test failed for {host}: {e}", "ERROR")
        
        self.test_results["network"] = results
        return results

    async def test_aws_ecr_access(self) -> Dict[str, bool]:
        """Test AWS ECR access for Docker image repositories"""
        self.log("Testing AWS ECR access...")
        
        results = {}
        
        try:
            # Test AWS credentials
            session = boto3.Session()
            credentials = session.get_credentials()
            
            if not credentials:
                self.log("No AWS credentials found. Skipping ECR tests.", "ERROR")
                results["credentials"] = False
                self.test_results["ecr"] = results
                return results
            
            results["credentials"] = True
            self.log("✓ AWS credentials found")
            
            # Test ECR client creation
            ecr_client = session.client('ecr', region_name=self.aws_region)
            results["client"] = True
            self.log("✓ ECR client created")
            
            # Test repository access
            for repo in self.ecr_repositories:
                try:
                    response = ecr_client.describe_repositories(
                        repositoryNames=[repo]
                    )
                    results[f"repo_{repo}"] = True
                    self.log(f"✓ ECR repository accessible: {repo}")
                    
                    # Test image listing
                    images = ecr_client.describe_images(
                        repositoryName=repo,
                        maxResults=5
                    )
                    image_count = len(images.get('imageDetails', []))
                    results[f"images_{repo}"] = image_count > 0
                    self.log(f"✓ Found {image_count} images in {repo}")
                    
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    results[f"repo_{repo}"] = False
                    results[f"images_{repo}"] = False
                    self.log(f"✗ ECR repository error {repo}: {error_code}", "ERROR")
            
            # Test ECR token generation
            try:
                token_response = ecr_client.get_authorization_token()
                results["auth_token"] = True
                self.log("✓ ECR authorization token generated")
            except ClientError as e:
                results["auth_token"] = False
                self.log(f"✗ ECR auth token failed: {e}", "ERROR")
                
        except NoCredentialsError:
            results["credentials"] = False
            self.log("✗ AWS credentials not configured", "ERROR")
        except Exception as e:
            results["error"] = str(e)
            self.log(f"✗ ECR access test failed: {e}", "ERROR")
        
        self.test_results["ecr"] = results
        return results

    async def test_fastapi_endpoints(self) -> Dict[str, bool]:
        """Test FastAPI backend service endpoints"""
        self.log("Testing FastAPI endpoints...")
        
        results = {}
        base_url = f"http://{self.host}:{self.api_port}"
        
        # Define test endpoints
        endpoints = [
            ("/", "GET", "root endpoint"),
            ("/ping", "GET", "health check"),
            ("/docs", "GET", "API documentation"),
            ("/openapi.json", "GET", "OpenAPI schema")
        ]
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            for path, method, description in endpoints:
                url = f"{base_url}{path}"
                try:
                    async with session.request(method, url) as response:
                        success = response.status < 400
                        results[f"endpoint_{path}"] = success
                        
                        if success:
                            self.log(f"✓ {description} ({path}): {response.status}")
                        else:
                            self.log(f"✗ {description} ({path}): {response.status}", "ERROR")
                            
                        # Log response content for critical endpoints
                        if path in ["/", "/ping"] and self.verbose:
                            try:
                                content = await response.text()
                                self.log(f"  Response: {content[:200]}")
                            except:
                                pass
                                
                except Exception as e:
                    results[f"endpoint_{path}"] = False
                    self.log(f"✗ {description} ({path}): {e}", "ERROR")
        
        self.test_results["fastapi"] = results
        return results

    async def test_paraview_server(self) -> Dict[str, bool]:
        """Test ParaView server TCP connectivity"""
        self.log("Testing ParaView server connectivity...")
        
        results = {}
        
        try:
            # Test TCP connection to ParaView port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((self.host, self.paraview_port))
            sock.close()
            
            results["tcp_connection"] = result == 0
            
            if result == 0:
                self.log(f"✓ ParaView server port {self.paraview_port} accessible")
                
                # Additional ParaView-specific tests could go here
                # (e.g., sending ParaView protocol messages)
                
            else:
                self.log(f"✗ ParaView server port {self.paraview_port} not accessible", "ERROR")
                
        except Exception as e:
            results["tcp_connection"] = False
            results["error"] = str(e)
            self.log(f"✗ ParaView server test failed: {e}", "ERROR")
        
        self.test_results["paraview"] = results
        return results

    async def test_docker_functionality(self) -> Dict[str, bool]:
        """Test Docker-related functionality on the deployment host"""
        self.log("Testing Docker functionality...")
        
        results = {}
        
        # Only test if we're on the actual deployment host
        if self.host == "localhost":
            try:
                # Test Docker daemon
                result = subprocess.run(
                    ["docker", "version"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                results["docker_daemon"] = result.returncode == 0
                
                if result.returncode == 0:
                    self.log("✓ Docker daemon accessible")
                else:
                    self.log(f"✗ Docker daemon not accessible: {result.stderr}", "ERROR")
                
                # Test Docker Compose
                result = subprocess.run(
                    ["docker-compose", "version"], 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                results["docker_compose"] = result.returncode == 0
                
                if result.returncode == 0:
                    self.log("✓ Docker Compose available")
                else:
                    self.log(f"✗ Docker Compose not available: {result.stderr}", "ERROR")
                
                # Test container status if compose file exists
                if Path("docker-compose.yml").exists():
                    result = subprocess.run(
                        ["docker-compose", "ps"], 
                        capture_output=True, 
                        text=True, 
                        timeout=10
                    )
                    results["compose_status"] = result.returncode == 0
                    
                    if result.returncode == 0:
                        self.log("✓ Docker Compose status retrieved")
                        if self.verbose:
                            self.log(f"  Status:\n{result.stdout}")
                    else:
                        self.log(f"✗ Docker Compose status failed: {result.stderr}", "ERROR")
                        
            except FileNotFoundError:
                results["docker_daemon"] = False
                results["docker_compose"] = False
                self.log("✗ Docker not installed or not in PATH", "ERROR")
            except Exception as e:
                results["error"] = str(e)
                self.log(f"✗ Docker functionality test failed: {e}", "ERROR")
        else:
            self.log("Skipping Docker tests (remote host)")
            results["skipped"] = True
        
        self.test_results["docker"] = results
        return results

    async def run_all_tests(self) -> Dict[str, Dict]:
        """Run all external API tests"""
        self.log("Starting FoamAI External API Test Suite...")
        self.log(f"Target host: {self.host}")
        
        # Run tests in parallel where possible
        network_task = self.test_network_connectivity()
        ecr_task = self.test_aws_ecr_access()
        docker_task = self.test_docker_functionality()
        
        # Wait for basic connectivity before testing services
        await network_task
        await ecr_task
        await docker_task
        
        # Test services if basic connectivity passes
        if self.test_results.get("network", {}).get(f"port_{self.host}_{self.api_port}", True):
            await self.test_fastapi_endpoints()
            await self.test_paraview_server()
        else:
            self.log("Skipping service tests due to connectivity issues", "ERROR")
        
        return self.test_results

    def generate_report(self) -> str:
        """Generate a comprehensive test report"""
        total_tests = 0
        passed_tests = 0
        
        report = ["", "=" * 60, "FoamAI External API Test Report", "=" * 60, ""]
        
        for category, tests in self.test_results.items():
            report.append(f"\n{category.upper()} Tests:")
            report.append("-" * 30)
            
            for test_name, result in tests.items():
                if isinstance(result, bool):
                    total_tests += 1
                    if result:
                        passed_tests += 1
                        status = "✓ PASS"
                    else:
                        status = "✗ FAIL"
                    report.append(f"  {test_name}: {status}")
                elif isinstance(result, (str, int)):
                    report.append(f"  {test_name}: {result}")
        
        report.extend([
            "",
            "=" * 60,
            f"Test Summary: {passed_tests}/{total_tests} tests passed",
            "=" * 60,
            ""
        ])
        
        return "\n".join(report)


async def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Test FoamAI external API access")
    parser.add_argument(
        "--host", 
        default="localhost", 
        help="Deployment host to test (default: localhost)"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true", 
        help="Enable verbose output"
    )
    parser.add_argument(
        "--output", 
        help="Save test results to JSON file"
    )
    
    args = parser.parse_args()
    
    # Create test suite
    test_suite = APITestSuite(host=args.host, verbose=args.verbose)
    
    try:
        # Run all tests
        results = await test_suite.run_all_tests()
        
        # Generate and display report
        report = test_suite.generate_report()
        print(report)
        
        # Save results if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Test results saved to: {args.output}")
        
        # Exit with error code if any tests failed
        total_tests = sum(
            1 for category in results.values() 
            for test, result in category.items() 
            if isinstance(result, bool)
        )
        passed_tests = sum(
            1 for category in results.values() 
            for test, result in category.items() 
            if isinstance(result, bool) and result
        )
        
        if passed_tests < total_tests:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nTest suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Test suite failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 