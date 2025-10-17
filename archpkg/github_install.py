#!/usr/bin/env python3
"""
GitHub repository installation module for archpkg-helper
"""

import os
import sys
import shutil
import tempfile
import subprocess
import re
from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path
from abc import ABC, abstractmethod

from archpkg.logging_config import get_logger

logger = get_logger(__name__)

class ProjectTypeHandler(ABC):
    """Abstract base class for project type handlers"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the project type"""
        pass

    @property
    @abstractmethod
    def indicators(self) -> List[str]:
        """Files that indicate this project type"""
        pass

    @abstractmethod
    def can_handle(self, repo_path: Path) -> bool:
        """Check if this handler can handle the project"""
        pass

    @abstractmethod
    def build_and_install(self, repo_path: Path, temp_dir: Path) -> bool:
        """Build and install the project"""
        pass

    def log_command(self, command: List[str], description: str) -> None:
        """Log a command execution"""
        logger.info(f"{description}: {' '.join(command)}")
        print(f"  → {description}: {' '.join(command)}")

class PythonHandler(ProjectTypeHandler):
    """Handler for Python projects"""

    @property
    def name(self) -> str:
        return "Python"

    @property
    def indicators(self) -> List[str]:
        return ["setup.py", "pyproject.toml", "requirements.txt", "Pipfile"]

    def can_handle(self, repo_path: Path) -> bool:
        return any((repo_path / indicator).exists() for indicator in self.indicators)

    def build_and_install(self, repo_path: Path, temp_dir: Path) -> bool:
        try:
            # Change to repo directory
            os.chdir(repo_path)

            # Check for setup.py or pyproject.toml
            if (repo_path / "setup.py").exists():
                self.log_command(["pip", "install", "."], "Installing Python package")
                result = subprocess.run(["pip", "install", "."], capture_output=True, text=True)
            elif (repo_path / "pyproject.toml").exists():
                self.log_command(["pip", "install", "."], "Installing Python package (PEP 517)")
                result = subprocess.run(["pip", "install", "."], capture_output=True, text=True)
            else:
                print("  ⚠ No setup.py or pyproject.toml found, installing requirements if present")
                if (repo_path / "requirements.txt").exists():
                    self.log_command(["pip", "install", "-r", "requirements.txt"], "Installing requirements")
                    result = subprocess.run(["pip", "install", "-r", "requirements.txt"], capture_output=True, text=True)
                else:
                    print("  ✗ No installation method found for Python project")
                    return False

            if result.returncode == 0:
                print("  ✓ Python package installed successfully")
                return True
            else:
                print(f"  ✗ Python installation failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"  ✗ Python installation error: {e}")
            return False

class NodeJSHandler(ProjectTypeHandler):
    """Handler for Node.js projects"""

    @property
    def name(self) -> str:
        return "Node.js"

    @property
    def indicators(self) -> List[str]:
        return ["package.json", "yarn.lock", "package-lock.json"]

    def can_handle(self, repo_path: Path) -> bool:
        return (repo_path / "package.json").exists()

    def build_and_install(self, repo_path: Path, temp_dir: Path) -> bool:
        try:
            os.chdir(repo_path)

            # Check if yarn or npm should be used
            use_yarn = (repo_path / "yarn.lock").exists()

            if use_yarn:
                # Install dependencies with yarn
                self.log_command(["yarn", "install"], "Installing dependencies with yarn")
                result = subprocess.run(["yarn", "install"], capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"  ✗ Yarn install failed: {result.stderr}")
                    return False

                # Build if build script exists
                if self._has_build_script():
                    self.log_command(["yarn", "build"], "Building project with yarn")
                    result = subprocess.run(["yarn", "build"], capture_output=True, text=True)
                    if result.returncode != 0:
                        print(f"  ✗ Yarn build failed: {result.stderr}")
                        return False

                # Install globally if it's a CLI tool
                if self._is_cli_tool():
                    self.log_command(["yarn", "global", "add", "."], "Installing CLI tool globally")
                    result = subprocess.run(["yarn", "global", "add", "."], capture_output=True, text=True)
                else:
                    print("  ⚠ Not a CLI tool, skipping global installation")
                    return True

            else:
                # Use npm
                self.log_command(["npm", "install"], "Installing dependencies with npm")
                result = subprocess.run(["npm", "install"], capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"  ✗ NPM install failed: {result.stderr}")
                    return False

                # Build if build script exists
                if self._has_build_script():
                    self.log_command(["npm", "run", "build"], "Building project with npm")
                    result = subprocess.run(["npm", "run", "build"], capture_output=True, text=True)
                    if result.returncode != 0:
                        print(f"  ✗ NPM build failed: {result.stderr}")
                        return False

                # Install globally if it's a CLI tool
                if self._is_cli_tool():
                    self.log_command(["npm", "install", "-g", "."], "Installing CLI tool globally")
                    result = subprocess.run(["npm", "install", "-g", "."], capture_output=True, text=True)
                else:
                    print("  ⚠ Not a CLI tool, skipping global installation")
                    return True

            if result.returncode == 0:
                print("  ✓ Node.js package installed successfully")
                return True
            else:
                print(f"  ✗ Node.js installation failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"  ✗ Node.js installation error: {e}")
            return False

    def _has_build_script(self) -> bool:
        """Check if package.json has a build script"""
        try:
            import json
            with open("package.json", "r") as f:
                data = json.load(f)
                return "scripts" in data and "build" in data["scripts"]
        except:
            return False

    def _is_cli_tool(self) -> bool:
        """Check if this is a CLI tool by looking for bin field"""
        try:
            import json
            with open("package.json", "r") as f:
                data = json.load(f)
                return "bin" in data or ("name" in data and data["name"].startswith("@"))
        except:
            return False

class CMakeHandler(ProjectTypeHandler):
    """Handler for CMake projects"""

    @property
    def name(self) -> str:
        return "CMake"

    @property
    def indicators(self) -> List[str]:
        return ["CMakeLists.txt", "cmake"]

    def can_handle(self, repo_path: Path) -> bool:
        return (repo_path / "CMakeLists.txt").exists()

    def build_and_install(self, repo_path: Path, temp_dir: Path) -> bool:
        try:
            os.chdir(repo_path)

            # Create build directory
            build_dir = repo_path / "build"
            build_dir.mkdir(exist_ok=True)
            os.chdir(build_dir)

            # Configure with CMake
            self.log_command(["cmake", ".."], "Configuring with CMake")
            result = subprocess.run(["cmake", ".."], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  ✗ CMake configure failed: {result.stderr}")
                return False

            # Build
            self.log_command(["make", "-j$(nproc)"], "Building with make")
            result = subprocess.run(["make", f"-j{os.cpu_count() or 1}"], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  ✗ Make build failed: {result.stderr}")
                return False

            # Install
            self.log_command(["sudo", "make", "install"], "Installing with make")
            result = subprocess.run(["sudo", "make", "install"], capture_output=True, text=True)
            if result.returncode == 0:
                print("  ✓ CMake project installed successfully")
                return True
            else:
                print(f"  ✗ Make install failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"  ✗ CMake installation error: {e}")
            return False

class MakefileHandler(ProjectTypeHandler):
    """Handler for Makefile projects"""

    @property
    def name(self) -> str:
        return "Makefile"

    @property
    def indicators(self) -> List[str]:
        return ["Makefile", "makefile"]

    def can_handle(self, repo_path: Path) -> bool:
        return (repo_path / "Makefile").exists() or (repo_path / "makefile").exists()

    def build_and_install(self, repo_path: Path, temp_dir: Path) -> bool:
        try:
            os.chdir(repo_path)

            # Try make install first
            self.log_command(["make", "install"], "Installing with make")
            result = subprocess.run(["make", "install"], capture_output=True, text=True)

            if result.returncode == 0:
                print("  ✓ Makefile project installed successfully")
                return True
            else:
                # Try with sudo
                self.log_command(["sudo", "make", "install"], "Installing with sudo make")
                result = subprocess.run(["sudo", "make", "install"], capture_output=True, text=True)
                if result.returncode == 0:
                    print("  ✓ Makefile project installed successfully")
                    return True
                else:
                    print(f"  ✗ Make install failed: {result.stderr}")
                    return False

        except Exception as e:
            print(f"  ✗ Makefile installation error: {e}")
            return False

class GoHandler(ProjectTypeHandler):
    """Handler for Go projects"""

    @property
    def name(self) -> str:
        return "Go"

    @property
    def indicators(self) -> List[str]:
        return ["go.mod", "main.go", ".go"]

    def can_handle(self, repo_path: Path) -> bool:
        return (repo_path / "go.mod").exists() or any(f.suffix == ".go" for f in repo_path.glob("*.go"))

    def build_and_install(self, repo_path: Path, temp_dir: Path) -> bool:
        try:
            os.chdir(repo_path)

            # Install with go install
            self.log_command(["go", "install", "."], "Installing Go package")
            result = subprocess.run(["go", "install", "."], capture_output=True, text=True)

            if result.returncode == 0:
                print("  ✓ Go package installed successfully")
                return True
            else:
                print(f"  ✗ Go install failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"  ✗ Go installation error: {e}")
            return False

class RustHandler(ProjectTypeHandler):
    """Handler for Rust projects"""

    @property
    def name(self) -> str:
        return "Rust"

    @property
    def indicators(self) -> List[str]:
        return ["Cargo.toml", "Cargo.lock"]

    def can_handle(self, repo_path: Path) -> bool:
        return (repo_path / "Cargo.toml").exists()

    def build_and_install(self, repo_path: Path, temp_dir: Path) -> bool:
        try:
            os.chdir(repo_path)

            # Install with cargo
            self.log_command(["cargo", "install", "--path", "."], "Installing Rust package")
            result = subprocess.run(["cargo", "install", "--path", "."], capture_output=True, text=True)

            if result.returncode == 0:
                print("  ✓ Rust package installed successfully")
                return True
            else:
                print(f"  ✗ Cargo install failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"  ✗ Rust installation error: {e}")
            return False

class ProjectTypeRegistry:
    """Registry for project type handlers"""

    def __init__(self):
        self.handlers: List[ProjectTypeHandler] = [
            PythonHandler(),
            NodeJSHandler(),
            CMakeHandler(),
            MakefileHandler(),
            GoHandler(),
            RustHandler(),
        ]

    def detect_project_type(self, repo_path: Path) -> Optional[ProjectTypeHandler]:
        """Detect the project type and return appropriate handler"""
        for handler in self.handlers:
            if handler.can_handle(repo_path):
                return handler
        return None

    def get_supported_types(self) -> List[str]:
        """Get list of supported project types"""
        return [handler.name for handler in self.handlers]

def clone_repository(repo_url: str, temp_dir: Path) -> Optional[Path]:
    """Clone a GitHub repository to a temporary directory"""
    try:
        print(f"📥 Cloning repository: {repo_url}")

        # Use GitPython if available, otherwise use subprocess
        try:
            from git import Repo
            logger.info(f"Cloning {repo_url} to {temp_dir}")
            Repo.clone_from(repo_url, temp_dir)
            print("  ✓ Repository cloned successfully")
            return temp_dir
        except ImportError:
            # Fallback to subprocess
            logger.info(f"Cloning {repo_url} to {temp_dir} using subprocess")
            result = subprocess.run(["git", "clone", repo_url, str(temp_dir)], capture_output=True, text=True)
            if result.returncode == 0:
                print("  ✓ Repository cloned successfully")
                return temp_dir
            else:
                print(f"  ✗ Git clone failed: {result.stderr}")
                return None

    except Exception as e:
        print(f"  ✗ Repository cloning error: {e}")
        return None

def validate_github_url(url_or_repo: str) -> Optional[str]:
    """Validate and convert GitHub URL or user/repo format to full URL"""
    # Handle github:user/repo format
    if url_or_repo.startswith("github:"):
        repo = url_or_repo[7:]  # Remove "github:" prefix
        if "/" not in repo:
            print("  ✗ Invalid GitHub repo format. Use: github:user/repo")
            return None
        return f"https://github.com/{repo}.git"

    # Handle full GitHub URLs
    if url_or_repo.startswith("https://github.com/"):
        if not url_or_repo.endswith(".git"):
            url_or_repo += ".git"
        return url_or_repo

    # Handle git@github.com:user/repo.git format
    if url_or_repo.startswith("git@github.com:"):
        return url_or_repo

    print("  ✗ Invalid GitHub URL format. Use: github:user/repo or https://github.com/user/repo")
    return None

def install_from_github(repo_spec: str) -> bool:
    """Main function to install from GitHub repository"""
    print(f"\n🔧 Installing from GitHub: {repo_spec}")

    # Validate the repo specification
    repo_url = validate_github_url(repo_spec)
    if not repo_url:
        return False

    # Create temporary directory
    temp_dir = None
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix="archpkg-github-"))
        print(f"📁 Working in temporary directory: {temp_dir}")

        # Clone the repository
        repo_path = clone_repository(repo_url, temp_dir)
        if not repo_path:
            return False

        # Detect project type
        registry = ProjectTypeRegistry()
        handler = registry.detect_project_type(repo_path)

        if not handler:
            # List found files to help user
            files = list(repo_path.glob("*"))
            file_names = [f.name for f in files[:10]]  # Show first 10 files
            print(f"  ✗ Unsupported project type")
            print(f"  📄 Found files: {', '.join(file_names)}")
            if len(files) > 10:
                print(f"  ... and {len(files) - 10} more files")
            print(f"  💡 Supported types: {', '.join(registry.get_supported_types())}")
            print(f"  💡 Try manual installation or request support for this project type")
            return False

        print(f"  🔍 Detected project type: {handler.name}")

        # Build and install
        success = handler.build_and_install(repo_path, temp_dir)

        if success:
            print(f"🎉 Successfully installed {repo_spec}!")
            return True
        else:
            print(f"❌ Failed to install {repo_spec}")
            return False

    except Exception as e:
        print(f"  ✗ Unexpected error during installation: {e}")
        return False

    finally:
        # Clean up temporary directory
        if temp_dir and temp_dir.exists():
            print(f"🧹 Cleaning up temporary directory: {temp_dir}")
            try:
                shutil.rmtree(temp_dir)
                print("  ✓ Cleanup completed")
            except Exception as e:
                print(f"  ⚠ Cleanup warning: {e}")

def check_dependencies() -> Dict[str, bool]:
    """Check if required dependencies are available"""
    deps = {
        "git": False,
        "python": False,
        "node": False,
        "npm": False,
        "yarn": False,
        "cmake": False,
        "make": False,
        "go": False,
        "cargo": False,
    }

    # Check each dependency
    for dep in deps.keys():
        try:
            result = subprocess.run([dep, "--version"], capture_output=True, timeout=5)
            deps[dep] = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            deps[dep] = False

    return deps