#!/usr/bin/env python3
"""
Validation script for purpose_mapping.yaml
This script helps validate the YAML structure and content.
"""

import yaml
import sys
import os
from pathlib import Path

def validate_mapping_file(file_path: str) -> bool:
    """Validate the purpose mapping YAML file.
    
    Args:
        file_path: Path to the YAML file
        
    Returns:
        True if valid, False otherwise
    """
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found")
        return False
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"YAML parsing error: {e}")
        return False
    except Exception as e:
        print(f"File reading error: {e}")
        return False
    
    if not isinstance(data, dict):
        print(" Error: Root element must be a dictionary")
        return False
    
    if not data:
        print("Error: File is empty or contains no data")
        return False
    
    print(f"YAML file is valid")
    print(f"Found {len(data)} purpose categories")
    
    # Validate each purpose category
    issues = []
    for purpose, apps in data.items():
        if not isinstance(apps, list):
            issues.append(f"Purpose '{purpose}' should be a list, got {type(apps)}")
            continue
            
        if not apps:
            issues.append(f"Purpose '{purpose}' has no applications")
            continue
            
        for i, app in enumerate(apps):
            if not isinstance(app, str):
                issues.append(f"Purpose '{purpose}' item {i+1} should be a string, got {type(app)}")
            elif not app.strip():
                issues.append(f"Purpose '{purpose}' has empty application name at position {i+1}")
            elif ' ' in app and not app.startswith('"') and not app.endswith('"'):
                # Warn about spaces in package names (might need quotes)
                print(f"Warning: Purpose '{purpose}' has app '{app}' with spaces - ensure it's properly quoted")
    
    if issues:
        print("\nValidation issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    
    print("All purpose categories are valid")
    
    # Show summary
    total_apps = sum(len(apps) for apps in data.values())
    print(f"Total applications: {total_apps}")
    
    # Show some examples
    print("\nSample purposes:")
    for purpose, apps in list(data.items())[:3]:
        sample_apps = apps[:3]
        if len(apps) > 3:
            sample_apps.append("...")
        print(f"  - {purpose}: {', '.join(sample_apps)}")
    
    return True

def main():
    """Main validation function."""
    script_dir = Path(__file__).parent
    mapping_file = script_dir / "data" / "purpose_mapping.yaml"
    
    print(f"Validating {mapping_file}")
    print("=" * 50)
    
    if validate_mapping_file(str(mapping_file)):
        print("\nValidation passed! The mapping file is ready for use.")
        sys.exit(0)
    else:
        print("\nValidation failed! Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
