# command_gen.py
"""Command generation module with improved error handling and validation.
IMPROVEMENTS: Added type hints, standardized exception handling, consistent timeout values."""

import subprocess
from typing import Optional, List
from archpkg.config import TIMEOUTS, AUR_HELPERS
from archpkg.exceptions import CommandGenerationError, PackageManagerNotFound, ValidationError
from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)

def check_command_availability(command: str) -> bool:
    """Check if a command is available in the system PATH.
    
    Args:
        command: The command to check
        
    Returns:
        bool: True if command is available, False otherwise
    """
    logger.debug(f"Checking availability of command: {command}")
    
    try:
        result = subprocess.run([command, '--version'], 
                              capture_output=True, 
                              check=True, 
                              timeout=TIMEOUTS['command_check'])
        logger.debug(f"Command '{command}' is available (exit code: {result.returncode})")
        return True
    except FileNotFoundError:
        logger.debug(f"Command '{command}' not found in PATH")
        return False
    except subprocess.CalledProcessError as e:
        logger.debug(f"Command '{command}' found but returned error code {e.returncode}")
        return False
    except subprocess.TimeoutExpired:
        logger.warning(f"Command '{command}' check timed out after {TIMEOUTS['command_check']}s")
        return False
    except Exception as e:
        PackageHelperLogger.log_exception(logger, f"Unexpected error checking command '{command}'", e)
        return False

def validate_package_name(pkg_name: str) -> tuple[bool, str]:
    """Validate package name format.
    
    Args:
        pkg_name: Package name to validate
        
    Returns:
        tuple[bool, str]: (is_valid, message)
    """
    logger.debug(f"Validating package name: '{pkg_name}'")
    
    if not pkg_name:
        logger.warning("Empty package name provided for validation")
        return False, "Package name cannot be empty"
        
    # Basic validation - package names shouldn't contain certain characters
    invalid_chars = ['/', '\\', '<', '>', '|', '&', ';', '`', '$']
    for char in invalid_chars:
        if char in pkg_name:
            logger.warning(f"Package name '{pkg_name}' contains invalid character: '{char}'")
            return False, f"Package name contains invalid character: '{char}'"
            
    # Check length
    if len(pkg_name) > 100:
        logger.warning(f"Package name '{pkg_name}' is too long ({len(pkg_name)} characters)")
        return False, "Package name is too long"
        
    logger.debug(f"Package name '{pkg_name}' is valid")
    return True, "Valid package name"

def generate_command(pkg_name: str, source: str) -> Optional[str]:
    """Generate install command with detailed validation and error handling.
    
    Args:
        pkg_name: Name of the package to install
        source: Package source (pacman, aur, flatpak, etc.)
        
    Returns:
        Optional[str]: Install command or None if generation fails
        
    Raises:
        CommandGenerationError: When command generation fails
        ValidationError: When input validation fails
    """
    logger.info(f"Generating install command for package '{pkg_name}' from source '{source}'")
    
    # IMPROVED: Input validation with detailed error messages
    if not pkg_name or not pkg_name.strip():
        logger.error("Empty package name provided to generate_command")
        raise ValidationError("Package name cannot be empty")
        
    if not source or not source.strip():
        logger.error("Empty package source provided to generate_command")
        raise ValidationError("Package source cannot be empty")
    
    # Validate package name format
    is_valid, validation_msg = validate_package_name(pkg_name.strip())
    if not is_valid:
        logger.error(f"Package name validation failed: {validation_msg}")
        raise ValidationError(validation_msg)
        
    pkg_name = pkg_name.strip()
    source = source.strip().lower()  # IMPROVED: Ensure lowercase for consistency
    logger.debug(f"Processing package '{pkg_name}' from source '{source}'")
    
    # Generate commands based on source
    try:
        if source == 'pacman':
            logger.debug("Generating pacman install command")
            if not check_command_availability('pacman'):
                logger.error("pacman command not available")
                raise PackageManagerNotFound(
                    "pacman is not installed or not available in PATH. "
                    "Install pacman or run on an Arch-based system."
                )
            command = f"sudo pacman -S {pkg_name}"
            logger.info(f"Generated pacman command: {command}")
            return command
            
        elif source == 'aur':
            logger.debug("Generating AUR install command")
            # Check for common AUR helpers in order of preference
            available_helper = None
            
            for helper in AUR_HELPERS:  # IMPROVED: Use config constant
                logger.debug(f"Checking for AUR helper: {helper}")
                if check_command_availability(helper):
                    available_helper = helper
                    logger.info(f"Found AUR helper: {helper}")
                    break
                    
            if not available_helper:
                logger.error("No AUR helper found on system")
                raise PackageManagerNotFound(
                    "No AUR helper found. Install one of the following:\n"
                    "- yay: sudo pacman -S yay\n"
                    "- paru: sudo pacman -S paru\n"
                    "- Or build manually from AUR"
                )
            command = f"{available_helper} -S {pkg_name}"
            logger.info(f"Generated AUR command: {command}")
            return command
            
        elif source == 'flatpak':
            logger.debug("Generating Flatpak install command")
            if not check_command_availability('flatpak'):
                logger.error("flatpak command not available")
                raise PackageManagerNotFound(
                    "Flatpak is not installed. Install it with your system package manager."
                )
            command = f"flatpak install flathub {pkg_name}"
            logger.info(f"Generated Flatpak command: {command}")
            return command
            
        elif source == 'apt':
            logger.debug("Generating APT install command")
            if not check_command_availability('apt'):
                logger.error("apt command not available")
                raise PackageManagerNotFound(
                    "APT is not available. This command requires a Debian/Ubuntu-based system."
                )
            command = f"sudo apt install {pkg_name}"
            logger.info(f"Generated APT command: {command}")
            return command
            
        elif source == 'dnf':
            logger.debug("Generating DNF install command")
            if not check_command_availability('dnf'):
                logger.error("dnf command not available")
                raise PackageManagerNotFound(
                    "DNF is not available. This command requires a Fedora/RHEL-based system."
                )
            command = f"sudo dnf install {pkg_name}"
            logger.info(f"Generated DNF command: {command}")
            return command
            
        elif source == 'snap':
            logger.debug("Generating Snap install command")
            if not check_command_availability('snap'):
                logger.error("snap command not available")
                raise PackageManagerNotFound(
                    "Snap is not installed. Install snapd with your system package manager."
                )
            command = f"sudo snap install {pkg_name}"
            logger.info(f"Generated Snap command: {command}")
            return command
            
        else:
            logger.error(f"Unsupported package source: '{source}'")
            raise ValidationError(
                f"Unsupported package source: '{source}'. "
                "Supported sources: pacman, aur, flatpak, apt, dnf, snap"
            )
            
    except (PackageManagerNotFound, ValidationError):
        # Re-raise our specific exceptions
        raise
    except Exception as e:
        # Wrap unexpected errors
        PackageHelperLogger.log_exception(logger, "Unexpected error generating command", e)
        raise CommandGenerationError(f"Unexpected error generating command: {str(e)}")

def get_install_suggestions(source: str) -> List[str]:
    """Provide installation suggestions for missing package managers.
    
    Args:
        source: Package manager source name
        
    Returns:
        List[str]: List of installation suggestions
    """
    logger.debug(f"Getting install suggestions for source: {source}")
    
    suggestions = {
        'pacman': [
            "This package requires an Arch-based Linux distribution",
            "Consider using the Flatpak or Snap version if available"
        ],
        'aur': [
            "Install an AUR helper like yay: sudo pacman -S yay",
            "Or manually build from AUR following the Arch Wiki"
        ],
        'flatpak': [
            "Install Flatpak:",
            "- Arch: sudo pacman -S flatpak",
            "- Ubuntu: sudo apt install flatpak",
            "- Fedora: sudo dnf install flatpak"
        ],
        'apt': [
            "This package requires a Debian/Ubuntu-based system",
            "Consider using the Flatpak or Snap version if available"
        ],
        'dnf': [
            "This package requires a Fedora/RHEL-based system", 
            "Consider using the Flatpak or Snap version if available"
        ],
        'snap': [
            "Install Snap:",
            "- Arch: sudo pacman -S snapd && sudo systemctl enable --now snapd",
            "- Ubuntu: sudo apt install snapd",
            "- Fedora: sudo dnf install snapd"
        ]
    }
    
    result = suggestions.get(source.lower(), ["Check your system's package manager documentation"])
    logger.debug(f"Returning {len(result)} suggestions for source '{source}'")
    return result