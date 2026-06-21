#!/usr/bin/env python3
"""
Test script for archpkg GUI - minimal version without external dependencies
Demonstrates the GUI structure and functionality
"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("ArchPkg GUI Test Suite")
print("=" * 70)

# Test 1: Check module structure
print("\n[TEST 1] Checking module structure...")
expected_modules = [
    'archpkg',
    'archpkg.interfaces',
    'archpkg.interfaces.cli',
    'archpkg.interfaces.gui',
    'archpkg.search',
    'archpkg.config',
    'archpkg.package_management',
    'archpkg.intelligence',
    'archpkg.integrations',
    'archpkg.system',
    'archpkg.core',
]

import os
import importlib.util

for module in expected_modules:
    module_path = module.replace('.', '/')
    if '.' in module:
        # Submodule
        parts = module.split('.')
        check_path = project_root / 'archpkg' / '/'.join(parts[1:])
        if check_path.is_dir():
            init_file = check_path / '__init__.py'
            if init_file.exists():
                print(f"  ✓ {module}")
            else:
                print(f"  ✗ {module} - missing __init__.py")
        else:
            print(f"  ⚠ {module} - directory not found")
    else:
        if (project_root / module).is_dir():
            print(f"  ✓ {module}")
        else:
            print(f"  ✗ {module}")

# Test 2: Check core configuration
print("\n[TEST 2] Checking core configuration modules...")
try:
    from archpkg.config.base import DISTRO_MAP
    print(f"  ✓ config.base - DISTRO_MAP loaded ({len(DISTRO_MAP)} distros)")
except ImportError as e:
    print(f"  ⚠ config.base: {e}")

try:
    from archpkg.core.exceptions import NetworkError
    print(f"  ✓ core.exceptions - exception classes loaded")
except ImportError as e:
    print(f"  ⚠ core.exceptions: {e}")

try:
    from archpkg.config.logging import get_logger
    print(f"  ✓ config.logging - logger functions loaded")
except ImportError as e:
    print(f"  ⚠ config.logging: {e}")

try:
    from archpkg.config.manager import get_user_config
    print(f"  ✓ config.manager - configuration manager loaded")
except ImportError as e:
    print(f"  ⚠ config.manager: {e}")

# Test 3: GUI Files
print("\n[TEST 3] Checking GUI files...")
gui_file = project_root / 'archpkg' / 'interfaces' / 'gui.py'
cli_file = project_root / 'archpkg' / 'interfaces' / 'cli.py'

if gui_file.exists():
    size = gui_file.stat().st_size
    print(f"  ✓ interfaces/gui.py ({size:,} bytes)")
else:
    print(f"  ✗ interfaces/gui.py not found")

if cli_file.exists():
    size = cli_file.stat().st_size
    print(f"  ✓ interfaces/cli.py ({size:,} bytes)")
else:
    print(f"  ✗ interfaces/cli.py not found")

# Test 4: Check compatibility wrappers
print("\n[TEST 4] Checking compatibility wrappers...")
compat_gui = project_root / 'archpkg' / 'gui.py'
compat_cli = project_root / 'archpkg' / 'cli.py'

if compat_gui.exists():
    with open(compat_gui) as f:
        content = f.read()
        if 'archpkg.interfaces.gui' in content:
            print(f"  ✓ archpkg/gui.py (wrapper → interfaces.gui)")
        else:
            print(f"  ⚠ archpkg/gui.py (exists but may not be wrapper)")
else:
    print(f"  ✗ archpkg/gui.py not found")

if compat_cli.exists():
    with open(compat_cli) as f:
        content = f.read()
        if 'archpkg.interfaces.cli' in content:
            print(f"  ✓ archpkg/cli.py (wrapper → interfaces.cli)")
        else:
            print(f"  ⚠ archpkg/cli.py (exists but may not be wrapper)")
else:
    print(f"  ✗ archpkg/cli.py not found")

# Test 5: Entry points configuration
print("\n[TEST 5] Checking entry points...")
pyproject_file = project_root / 'pyproject.toml'
if pyproject_file.exists():
    try:
        with open(pyproject_file) as f:
            content = f.read()
        
        if 'archpkg.interfaces.cli:main' in content:
            print(f"  ✓ Entry point: archpkg = 'archpkg.interfaces.cli:main'")
            print(f"    ✓ Correctly pointing to interfaces.cli")
        elif 'archpkg.cli:main' in content:
            print(f"  ⚠ Entry point is using old path (archpkg.cli)")
        else:
            print(f"  ✗ Could not find archpkg entry point")
    except Exception as e:
        print(f"  ⚠ Error reading pyproject.toml: {e}")
else:
    print(f"  ✗ pyproject.toml not found")

# Test 6: Search modules
print("\n[TEST 6] Checking search modules...")
search_modules = [
    'pacman', 'aur', 'apt', 'dnf', 'zypper', 
    'flatpak', 'snap', 'rpm', 'ranking'
]

for module_name in search_modules:
    module_file = project_root / 'archpkg' / 'search' / f'{module_name}.py'
    if module_file.exists():
        print(f"  ✓ search/{module_name}.py")
    else:
        print(f"  ✗ search/{module_name}.py not found")

print("\n" + "=" * 70)
print("GUI Structure Tests Complete!")
print("=" * 70)

print("\n📝 NEXT STEPS:")
print("1. Install dependencies: pip install -e .")
print("2. Run the GUI: archpkg gui")
print("3. Or run CLI: archpkg search firefox")
print("\nDependencies needed (install with pip):")
print("  - PyQt5 (for GUI)")
print("  - requests (for API calls)")
print("  - rich (for terminal output)")
print("  - typer (for CLI)")
print("  - distro (for distribution detection)")
