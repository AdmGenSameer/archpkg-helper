# search_pacman.py
"""Pacman search module with standardized error handling and consistent source naming.
IMPROVEMENTS: Kept source name lowercase (already consistent), used config timeouts, unified exception handling."""

import subprocess
from typing import List, Tuple
from archpkg.config import TIMEOUTS
from archpkg.exceptions import PackageManagerNotFound, PackageSearchException, TimeoutError, ValidationError
from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)

def search_pacman(query: str) -> List[Tuple[str, str, str]]:
    """Search for packages using the pacman package manager.
    
    Args:
        query: Search query string
        
    Returns:
        List[Tuple[str, str, str]]: List of (name, description, source) tuples
        
    Raises:
        ValidationError: When query is empty or invalid
        PackageManagerNotFound: When pacman is not available
        TimeoutError: When search times out
        PackageSearchException: For other search-related errors
    """
    logger.info(f"Starting pacman search for query: '{query}'")
    
    if not query or not query.strip():
        logger.error("Empty search query provided to pacman search")
        raise ValidationError("Empty search query provided")

    # Check if pacman is available and working
    logger.debug("Checking pacman availability")
    try:
        subprocess.run(
            ['pacman', '--version'],
            capture_output=True,
            check=True,
            timeout=TIMEOUTS['command_check']
        )
        logger.debug("Pacman is available and responsive")
    except FileNotFoundError:
        logger.error("pacman command not found")
        raise PackageManagerNotFound("pacman command not found. This system may not be Arch-based.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Pacman version check failed with return code {e.returncode}")
        raise PackageSearchException("pacman is installed but not working properly.")
    except subprocess.TimeoutExpired:
        logger.warning("Pacman version check timed out")
        raise TimeoutError(
            "pacman is not responding. The package manager may be locked or misconfigured."
        )

    try:
        logger.debug(f"Executing pacman search with timeout {TIMEOUTS['pacman']}s")
        # IMPROVED: Use config timeout value
        result = subprocess.run(
            ['pacman', '-Ss', query.strip()],
            capture_output=True,
            text=True,
            timeout=TIMEOUTS['pacman'],
            check=False
        )

        logger.debug(f"Pacman search completed with return code: {result.returncode}")

        # Handle common pacman exit codes
        if result.returncode == 1 and not result.stdout.strip():
            logger.info("Pacman search found no matches (normal result)")
            return []
        elif result.returncode != 0:
            error_msg = result.stderr.strip()
            logger.error(f"Pacman search failed with error: {error_msg}")
            
            if "could not" in error_msg.lower():
                logger.warning("Pacman database issue detected")
                raise PackageSearchException(
                    "pacman database not initialized or corrupted. Try: sudo pacman -Syu"
                )
            else:
                logger.error(f"Pacman search failed with unknown error: {error_msg}")
                raise PackageSearchException(f"pacman search failed: {error_msg or 'Unknown error'}")

        output = result.stdout.strip()
        if not output:
            logger.info("Pacman search returned empty output")
            return []

        logger.debug("Parsing pacman search results")
        # Parse pacman search output
        lines = output.split('\n')
        results = []
        lines_processed = 0

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            lines_processed += 1
            
            if not line:
                i += 1
                continue

            if "/" in line:  # line containing package repo/name and version
                parts = line.split()
                if len(parts) >= 2:
                    pkg_full = parts[0]  # e.g., extra/vim
                    pkg_name = pkg_full.split("/")[-1]
                    desc = lines[i + 1].strip() if i + 1 < len(lines) else "No description"
                    # IMPROVED: Source name already lowercase (kept consistent)
                    results.append((pkg_name, desc, "pacman"))
                    logger.debug(f"Found pacman package: {pkg_name}")
                i += 2
            else:
                i += 1

        logger.info(f"Pacman search completed: {len(results)} packages found from {lines_processed} lines")
        return results

    except subprocess.TimeoutExpired:
        logger.error(f"Pacman search timed out after {TIMEOUTS['pacman']}s")
        raise TimeoutError("pacman search timed out. The package database might be updating.")
    except (ValidationError, PackageManagerNotFound, TimeoutError, PackageSearchException):
        # Re-raise our specific exceptions
        raise
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error during pacman search", e)
        raise PackageSearchException(f"Unexpected error during pacman search: {str(e)}")