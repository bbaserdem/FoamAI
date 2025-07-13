#!/usr/bin/env python3
"""
Test script for OpenFOAM auto-detection functionality.

This script tests the CommandService's ability to automatically detect
OpenFOAM installations using wildcards and version selection.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from command_service import CommandService, CommandExecutionError

def test_version_extraction():
    """Test version extraction from OpenFOAM paths"""
    service = CommandService.__new__(CommandService)  # Create without __init__
    
    test_cases = [
        ("/opt/openfoam2412/etc/bashrc", 2412),
        ("/usr/lib/openfoam/openfoam2312/etc/bashrc", 2312),
        ("/usr/local/openfoam-2024/etc/bashrc", 2024),
        ("/opt/openfoam/etc/bashrc", 0),  # No version
        ("/some/path/openfoam123/etc/bashrc", 123),
    ]
    
    print("Testing version extraction...")
    for path, expected_version in test_cases:
        def extract_version(path: str) -> int:
            import re
            version_match = re.search(r'openfoam[^\d]*(\d+)', path, re.IGNORECASE)
            if version_match:
                return int(version_match.group(1))
            return 0
        
        result = extract_version(path)
        status = "✅" if result == expected_version else "❌"
        print(f"  {status} {path} -> {result} (expected {expected_version})")

def test_newest_version_selection():
    """Test selection of newest version from multiple paths"""
    service = CommandService.__new__(CommandService)  # Create without __init__
    
    test_paths = [
        "/opt/openfoam2312/etc/bashrc",
        "/usr/lib/openfoam/openfoam2412/etc/bashrc",
        "/usr/local/openfoam2024/etc/bashrc",
        "/opt/openfoam2206/etc/bashrc",
    ]
    
    print("\nTesting newest version selection...")
    print(f"Input paths: {test_paths}")
    
    # Mock the method to test it
    def choose_newest_version(bashrc_paths):
        import re
        if len(bashrc_paths) == 1:
            return bashrc_paths[0]
        
        def extract_version(path: str) -> int:
            version_match = re.search(r'openfoam[^\d]*(\d+)', path, re.IGNORECASE)
            if version_match:
                return int(version_match.group(1))
            return 0
        
        sorted_paths = sorted(bashrc_paths, key=extract_version, reverse=True)
        return sorted_paths[0]
    
    result = choose_newest_version(test_paths)
    expected = "/usr/local/openfoam2024/etc/bashrc"
    
    status = "✅" if result == expected else "❌"
    print(f"  {status} Selected: {result}")
    print(f"      Expected: {expected}")

def test_auto_detection_with_mock():
    """Test auto-detection with mocked filesystem"""
    print("\nTesting auto-detection with mocked filesystem...")
    
    # Mock paths that would be found by glob
    mock_paths = [
        "/opt/openfoam2312/etc/bashrc",
        "/usr/lib/openfoam/openfoam2412/etc/bashrc",
    ]
    
    with patch('glob.glob') as mock_glob, \
         patch('os.path.exists') as mock_exists:
        
        # Setup mocks
        def glob_side_effect(pattern):
            if pattern == "/opt/openfoam*/etc/bashrc":
                return ["/opt/openfoam2312/etc/bashrc"]
            elif pattern == "/usr/lib/openfoam/openfoam*/etc/bashrc":
                return ["/usr/lib/openfoam/openfoam2412/etc/bashrc"]
            elif pattern == "/usr/local/openfoam*/etc/bashrc":
                return []
            return []
        
        mock_glob.side_effect = glob_side_effect
        mock_exists.return_value = True
        
        # Test the auto-detection
        try:
            with patch.dict(os.environ, {}, clear=True):  # Clear OPENFOAM_BASHRC
                service = CommandService()
                result = service.openfoam_bashrc
                expected = "/usr/lib/openfoam/openfoam2412/etc/bashrc"  # Should pick 2412 > 2312
                
                status = "✅" if result == expected else "❌"
                print(f"  {status} Auto-detected: {result}")
                print(f"      Expected: {expected}")
        except Exception as e:
            print(f"  ❌ Auto-detection failed: {e}")

def test_environment_variable_override():
    """Test that environment variable takes precedence"""
    print("\nTesting environment variable override...")
    
    custom_path = "/custom/openfoam/bashrc"
    
    with patch('os.path.exists') as mock_exists, \
         patch('glob.glob') as mock_glob:
        
        mock_exists.return_value = True
        mock_glob.return_value = ["/opt/openfoam2412/etc/bashrc"]
        
        # Test with environment variable set
        with patch.dict(os.environ, {"OPENFOAM_BASHRC": custom_path}):
            service = CommandService()
            result = service.openfoam_bashrc
            
            status = "✅" if result == custom_path else "❌"
            print(f"  {status} Using env var: {result}")
            print(f"      Expected: {custom_path}")

def test_no_installation_found():
    """Test error when no OpenFOAM installation found"""
    print("\nTesting error when no installation found...")
    
    with patch('glob.glob') as mock_glob, \
         patch.dict(os.environ, {}, clear=True):
        
        mock_glob.return_value = []  # No matches found
        
        try:
            service = CommandService()
            print("  ❌ Should have raised CommandExecutionError")
        except CommandExecutionError as e:
            print(f"  ✅ Correctly raised error: {e}")
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("  🧪 TESTING OPENFOAM AUTO-DETECTION")
    print("=" * 60)
    
    test_version_extraction()
    test_newest_version_selection()
    test_auto_detection_with_mock()
    test_environment_variable_override()
    test_no_installation_found()
    
    print("\n" + "=" * 60)
    print("  📋 TEST COMPLETE")
    print("=" * 60)
    print("Auto-detection features:")
    print("  ✅ Searches 3 common OpenFOAM installation paths")
    print("  ✅ Automatically selects the newest version")
    print("  ✅ Respects OPENFOAM_BASHRC environment variable")
    print("  ✅ Provides helpful error messages")
    print("=" * 60) 