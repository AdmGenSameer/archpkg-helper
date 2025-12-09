# search_zypper.py
"""Zypper search module with standardized error handling and consistent source naming.
Supports openSUSE's zypper package manager."""

import subprocess
import re
from typing import List, Tuple, Optional
from archpkg.config import TIMEOUTS
from archpkg.exceptions import PackageManagerNotFound, PackageSearchException, TimeoutError, ValidationError, NetworkError
from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)

def search_zypper(query: str, cache_manager: Optional[object] = None) -> List[Tuple[str, str, str]]:
    """Search for packages using Zypper package manager.
    
    Args:
        query: Search query string
        cache_manager: Optional cache manager for storing/retrieving results
        
    Returns:
        List[Tuple[str, str, str]]: List of (name, description, source) tuples
        
    Raises:
        ValidationError: When query is empty or invalid
        PackageManagerNotFound: When Zypper is not available
        TimeoutError: When search times out
        NetworkError: When network connection fails
        PackageSearchException: For other search-related errors
    """
    logger.info(f"Starting Zypper search for query: '{query}'")
    
    if not query or not query.strip():
        logger.debug("Empty search query provided to Zypper search")
        raise ValidationError("Empty search query provided")

    # Check cache first if available
    if cache_manager:
        cached_results = cache_manager.get(query, 'zypper')
        if cached_results is not None:
            logger.info(f"Retrieved {len(cached_results)} Zypper results from cache")
            return cached_results

    # Check if Zypper is available and working
    logger.debug("Checking Zypper availability")
    try:
        subprocess.run(
            ["zypper", "--version"],
            capture_output=True,
            check=True,
            timeout=TIMEOUTS['command_check']
        )
        logger.debug("Zypper is available and responsive")
    except FileNotFoundError:
        logger.debug("zypper command not found")
        raise PackageManagerNotFound(
            "zypper command not found. This system may not be openSUSE-based."
        )
    except subprocess.CalledProcessError as e:
        logger.debug(f"Zypper version check failed with return code {e.returncode}")
        raise PackageSearchException("zypper is installed but not working properly.")
    except subprocess.TimeoutExpired:
        logger.debug("Zypper version check timed out")
        raise TimeoutError("zypper is not responding.")

    try:
        logger.debug(f"Executing zypper search with timeout {TIMEOUTS['zypper']}s")
        # Use zypper search with non-interactive mode and detailed output
        result = subprocess.run(
            ["zypper", "--non-interactive", "search", "--details", query.strip()],
            capture_output=True,
            text=True,
            timeout=TIMEOUTS['zypper'],
            check=False
        )

        logger.debug(f"Zypper search completed with return code: {result.returncode}")

        # Handle Zypper exit codes
        if result.returncode == 104:  # no matches found
            logger.info("Zypper search found no matches (normal result)")
            return []
        elif result.returncode != 0:
            error_msg = result.stderr.strip()
            logger.debug(f"Zypper search failed with error: {error_msg}")
            
            # Parse common Zypper error messages
            if "ZYPPER_EXIT_INF_REBOOT_NEEDED" in error_msg or "System management is locked" in error_msg:
                logger.debug("Zypper is locked by another process")
                raise PackageSearchException("Zypper is locked. Another package operation may be running.")
            elif "Failed to cache rpm database" in error_msg:
                logger.debug("Zypper cache error")
                raise PackageSearchException("Zypper cache error. Try: sudo zypper refresh")
            elif "Cannot access" in error_msg or "Download failed" in error_msg:
                logger.debug("Zypper cannot connect to repositories")
                raise NetworkError(
                    "Cannot connect to Zypper repositories. Check internet connection."
                )
            elif "Permission denied" in error_msg:
                logger.debug("Zypper permission denied")
                raise PackageSearchException(
                    "Permission denied accessing Zypper. Try running with sudo if needed."
                )
            else:
                logger.debug(f"Zypper search failed with unknown error: {error_msg}")
                raise PackageSearchException(
                    f"zypper search failed: {error_msg or 'Unknown error'}"
                )

        output = result.stdout.strip()
        if not output:
            logger.info("Zypper search returned empty output")
            return []

        logger.debug("Parsing Zypper search results")
        # Parse Zypper output
        packages = []
        in_results = False
        lines_processed = 0

        for line in output.split("\n"):
            line = line.strip()
            lines_processed += 1
            
            if not line:
                continue

            # Detect start of results section (zypper --details produces table format)
            if line.startswith("---") or line.startswith("===") or ("|" in line and "Name" in line):
                logger.debug("Found Zypper results section header")
                in_results = True
                continue

            # Process package lines - zypper --details uses table format with | separators
            # Format: | Status | Name | Type | Version | Arch | Repository
            if in_results and "|" in line:
                # Split by | and clean up
                parts = [p.strip() for p in line.split("|")]
                
                # Filter out empty parts and header repetitions
                parts = [p for p in parts if p and not p.startswith("-")]
                
                if len(parts) >= 3:  # At least Status, Name, Type
                    # Skip if it's a header line
                    if parts[0] in ["S", "Status"] or "Name" in parts:
                        continue
                    
                    # Extract package name (usually second column after status)
                    # Status is usually in first column (i, v, etc.)
                    name_idx = 1 if len(parts) > 1 else 0
                    if name_idx < len(parts):
                        name = parts[name_idx].strip()
                        
                        # For zypper, descriptions are often in summary field
                        # Since --details doesn't show description inline, we'll use a default
                        desc = "Package from openSUSE repository"
                        
                        # Skip invalid entries
                        if name and not name.startswith("-") and name not in ["Name", "S", "Status"]:
                            packages.append((name, desc, "zypper"))
                            logger.debug(f"Found Zypper package: {name}")
            elif in_results and line and not line.startswith("Loading") and not line.startswith("Retrieving"):
                # Alternative format: simple list without table
                # Try to parse as "name : description" format
                if " | " in line:
                    parts = line.split(" | ", 1)
                    if len(parts) >= 1:
                        name = parts[0].strip()
                        desc = parts[1].strip() if len(parts) > 1 else "Package from openSUSE repository"
                        
                        if name and not name.startswith("-"):
                            packages.append((name, desc, "zypper"))
                            logger.debug(f"Found Zypper package: {name}")

        logger.info(f"Zypper search completed: {len(packages)} packages found from {lines_processed} lines")
        
        # Cache results if cache manager is available
        if cache_manager and packages:
            cache_manager.set(query, 'zypper', packages)
            logger.debug(f"Cached {len(packages)} Zypper results")
        
        return packages

    except subprocess.TimeoutExpired:
        logger.debug(f"Zypper search timed out after {TIMEOUTS['zypper']}s")
        raise TimeoutError("Zypper search timed out. This can happen with large repositories.")
    except (ValidationError, PackageManagerNotFound, TimeoutError, NetworkError, PackageSearchException):
        # Re-raise our specific exceptions
        raise
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error during Zypper search", e)
        raise PackageSearchException(f"Unexpected error during Zypper search: {repr(e)}")
