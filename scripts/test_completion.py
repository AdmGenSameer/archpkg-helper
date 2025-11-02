#!/usr/bin/env python3
"""
Test script for archpkg autocomplete functionality.
Run this to verify that the completion system is working correctly.
"""

import sys
import os

# Add the archpkg module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from archpkg.completion import get_completion_backend, complete_packages

def test_basic_completion():
    """Test basic completion functionality."""
    print("Testing basic completion...")
    
    result = complete_packages("firefox", "install", 5)
    print(f"firefox -> {result}")
    assert "firefox" in result
    
    result = complete_packages("vs", "install", 5)
    print(f"vs -> {result}")
    assert any("visual-studio-code" in line for line in result.split('\n'))
    
    result = complete_packages("vsc", "install", 5)
    print(f"vsc -> {result}")
    assert any("visual-studio-code" in line for line in result.split('\n'))
    
    print("✓ Basic completion tests passed")

def test_alias_mapping():
    """Test alias mapping functionality."""
    print("\nTesting alias mapping...")
    
    backend = get_completion_backend()
    
    result = complete_packages("vscode", "install", 5)
    print(f"vscode -> {result}")
    assert "visual-studio-code" in result
    
    result = complete_packages("chrome", "install", 5)
    print(f"chrome -> {result}")
    assert "google-chrome" in result
    
    result = complete_packages("ff", "install", 5)
    print(f"ff -> {result}")
    assert "firefox" in result
    
    print("✓ Alias mapping tests passed")

def test_context_awareness():
    """Test context-aware completion."""
    print("\nTesting context awareness...")
    
    install_result = complete_packages("vim", "install", 5)
    remove_result = complete_packages("vim", "remove", 5)
    
    print(f"install context: {install_result}")
    print(f"remove context: {remove_result}")
    
    # Both should return vim, but scoring might differ
    assert "vim" in install_result
    assert "vim" in remove_result
    
    print("✓ Context awareness tests passed")

def test_frequency_tracking():
    """Test frequency tracking functionality."""
    print("\nTesting frequency tracking...")
    
    backend = get_completion_backend()
    
    # Record some usage
    backend.record_usage("firefox")
    backend.record_usage("firefox")
    backend.record_usage("chrome")
    
    # Test that frequency affects scoring
    result = complete_packages("f", "install", 5)
    print(f"f -> {result}")
    
    # Firefox should appear before chrome due to higher frequency
    lines = result.split('\n')
    firefox_index = next((i for i, line in enumerate(lines) if 'firefox' in line), -1)
    chrome_index = next((i for i, line in enumerate(lines) if 'chrome' in line), -1)
    
    if firefox_index != -1 and chrome_index != -1:
        assert firefox_index < chrome_index, "Firefox should rank higher than Chrome due to frequency"
    
    print("✓ Frequency tracking tests passed")

def test_edge_cases():
    """Test edge cases and error handling."""
    print("\nTesting edge cases...")
    
    # Test empty query
    result = complete_packages("", "install", 5)
    assert result == ""
    
    # Test non-existent package
    result = complete_packages("nonexistentpackage12345", "install", 5)
    assert result == ""
    
    # Test very long query
    result = complete_packages("a" * 100, "install", 5)
    assert result == ""
    
    print("✓ Edge cases tests passed")

def main():
    """Run all tests."""
    print("Archpkg Autocomplete Test Suite")
    print("=" * 40)
    
    try:
        test_basic_completion()
        test_alias_mapping()
        test_context_awareness()
        test_frequency_tracking()
        test_edge_cases()
        
        print("\n" + "=" * 40)
        print("🎉 All tests passed! Autocomplete is working correctly.")
        
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
