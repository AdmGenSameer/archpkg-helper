# search_flatpak.py
"""Flatpak search module with standardized error handling and consistent source naming.
IMPROVEMENTS: Standardized source name to lowercase, used config timeouts, unified exception handling."""

import subprocess
from typing import List, Tuple
from archpkg.config import TIMEOUTS
from archpkg.exceptions import PackageManagerNotFound, PackageSearchException, TimeoutError, ValidationError
from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)

def search_flatpak(query: str) -> List[Tuple[str, str, str]]:
    """Search for packages using the Flatpak package manager.
    
    Args:
        query: Search query string
        
    Returns:
        List[Tuple[str, str, str]]: List of (name, description, source) tuples
        
    Raises:
        ValidationError: When query is empty or invalid
        PackageManagerNotFound: When Flatpak is not available
        TimeoutError: When search times out
        PackageSearchException: For other search-related errors
    """
    logger.info(f"Starting Flatpak search for query: '{query}'")
    
    if not query or not query.strip():
        logger.error("Empty search query provided to Flatpak search")
        raise ValidationError("Empty search query provided")

    # Check if flatpak is available and working
    logger.debug("Checking Flatpak availability")
    try:
        subprocess.run(
            ['flatpak', '--version'],
            capture_output=True,
            check=True,
            timeout=TIMEOUTS['command_check']
        )
        logger.debug("Flatpak is available and responsive")
    except FileNotFoundError:
        logger.error("flatpak command not found")
        raise PackageManagerNotFound("flatpak command not found. Install flatpak first.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Flatpak version check failed with return code {e.returncode}")
        raise PackageSearchException("flatpak is installed but not working properly.")
    except subprocess.TimeoutExpired:
        logger.warning("Flatpak version check timed out")
        raise TimeoutError("flatpak is not responding. Check if the service is running.")

    try:
        logger.debug(f"Executing flatpak search with timeout {TIMEOUTS['flatpak']}s")
        # IMPROVED: Use config timeout value
        result = subprocess.run(
            ['flatpak', 'search', query.strip()],
            capture_output=True,
            text=True,
            timeout=TIMEOUTS['flatpak'],
            check=False
        )

        logger.debug(f"Flatpak search completed with return code: {result.returncode}")

        # Handle exit codes
        if result.returncode == 1:
            logger.info("Flatpak search found no matches (normal result)")
            return []
        elif result.returncode != 0:
            error_msg = result.stderr.strip()
            logger.error(f"Flatpak search failed with error: {error_msg}")
            
            if "No remotes found" in error_msg:
                logger.warning("No Flatpak remotes configured")
                raise PackageSearchException(
                    "No Flatpak remotes configured. Run: "
                    "flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo"
                )
            else:
                logger.error(f"Flatpak search failed with unknown error: {error_msg}")
                raise PackageSearchException(f"flatpak search failed: {error_msg or 'Unknown error'}")

        output = result.stdout.strip()
        if not output:
            logger.info("Flatpak search returned empty output")
            return []

        logger.debug("Parsing Flatpak search results")
        # Parse search results (tab-separated format)
        lines = output.split('\n')
        if len(lines) < 2:
            logger.warning("Flatpak search returned insufficient output lines")
            return []

        packages = []
        lines_processed = 0
        
        for line in lines[1:]:  # skip header row
            if not line.strip():
                continue
                
            lines_processed += 1
            cols = line.split('\t')
            
            if len(cols) >= 3:
                name = cols[0].strip()
                description = cols[1].strip()
                app_id = cols[2].strip()
                # IMPROVED: Standardized source name to lowercase
                packages.append((app_id, f"{name} - {description}", "flatpak"))
                logger.debug(f"Found Flatpak package: {app_id}")
            else:
                logger.debug(f"Skipping malformed Flatpak result line: {line}")

        logger.info(f"Flatpak search completed: {len(packages)} packages found from {lines_processed} lines")
        return packages

    except subprocess.TimeoutExpired:
        logger.error(f"Flatpak search timed out after {TIMEOUTS['flatpak']}s")
        raise TimeoutError("Flatpak search timed out. Check your internet connection.")
    except (ValidationError, PackageManagerNotFound, TimeoutError, PackageSearchException):
        # Re-raise our specific exceptions
        raise
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error during Flatpak search", e)
        raise PackageSearchException(f"Unexpected error during flatpak search: {str(e)}")