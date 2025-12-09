# search_apt.py
"""APT search module with standardized error handling and consistent source naming.
IMPROVEMENTS: Standardized source name to lowercase, used config timeouts, unified exception handling."""

import subprocess
from typing import List, Tuple, Optional
from archpkg.config import TIMEOUTS
from archpkg.exceptions import PackageManagerNotFound, PackageSearchException, TimeoutError, ValidationError
from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)

def search_apt(query: str, cache_manager: Optional[object] = None) -> List[Tuple[str, str, str]]:
    """Search for packages using the APT package manager.
    
    Args:
        query: Search query string
        cache_manager: Optional cache manager for storing/retrieving results
        
    Returns:
        List[Tuple[str, str, str]]: List of (name, description, source) tuples
        
    Raises:
        ValidationError: When query is empty or invalid
        PackageManagerNotFound: When APT is not available
        TimeoutError: When search times out
        PackageSearchException: For other search-related errors
    """
    logger.info(f"Starting APT search for query: '{query}'")
    
    # Input validation
    if not query or not query.strip():
        logger.error("Empty search query provided to APT search")
        raise ValidationError("Search query cannot be empty. Please provide a package name to search for.")
    
    # Check cache first if available
    if cache_manager:
        cached_results = cache_manager.get(query, 'apt')
        if cached_results is not None:
            logger.info(f"Retrieved {len(cached_results)} APT results from cache")
            return cached_results
    
    # Check if apt-cache is available
    logger.debug("Checking APT availability")
    try:
        subprocess.run(['apt-cache', '--version'], 
                      capture_output=True, check=True, timeout=TIMEOUTS['command_check'])
        logger.debug("APT is available and responsive")
    except FileNotFoundError:
        logger.error("apt-cache command not found")
        raise PackageManagerNotFound(
            "APT package manager is not available on this system. "
            "This feature requires a Debian/Ubuntu-based distribution."
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"APT cache check failed with return code {e.returncode}")
        raise PackageSearchException(
            "APT cache is installed but not functioning properly. Try running: sudo apt update"
        )
    except subprocess.TimeoutExpired:
        logger.warning("APT cache version check timed out")
        raise TimeoutError("APT cache is not responding. Please check your system configuration.")

    try:
        logger.debug(f"Executing apt-cache search with timeout {TIMEOUTS['apt']}s")
        # IMPROVED: Use config timeout value
        result = subprocess.run(
            ["apt-cache", "search", query.strip()], 
            capture_output=True, 
            text=True,
            timeout=TIMEOUTS['apt'],
            check=False
        )
        
        logger.debug(f"APT search completed with return code: {result.returncode}")
        
        if result.returncode != 0:
            error_msg = result.stderr.strip()
            logger.warning(f"APT search failed with error: {error_msg}")
            
            if "Unable to locate package" in error_msg:
                logger.info("No packages found (normal result)")
                return []  # no packages found, which is normal
            elif "E: Could not open lock file" in error_msg:
                logger.error("APT cache is locked")
                raise PackageSearchException(
                    "Cannot access APT cache - another package operation may be running. "
                    "Wait a moment and try again, or run: sudo apt update"
                )
            else:
                logger.error(f"APT search failed with unknown error: {error_msg}")
                raise PackageSearchException(
                    "APT search failed. Try updating your package cache with: sudo apt update"
                )

        output = result.stdout.strip()
        if not output:
            logger.info("APT search returned empty output")
            return []

        logger.debug("Parsing APT search results")
        packages = []
        lines_processed = 0
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            lines_processed += 1
            
            if ' - ' in line:
                name, desc = line.split(' - ', 1)
                # IMPROVED: Standardized source name to lowercase
                packages.append((name.strip(), desc.strip(), "apt"))
                logger.debug(f"Found APT package: {name.strip()}")
            
        logger.info(f"APT search completed: {len(packages)} packages found from {lines_processed} lines")
        
        # Cache results if cache manager is available
        if cache_manager and packages:
            cache_manager.set(query, 'apt', packages)
            logger.debug(f"Cached {len(packages)} APT results")
        
        return packages
        
    except subprocess.TimeoutExpired:
        logger.error(f"APT search timed out after {TIMEOUTS['apt']}s")
        raise TimeoutError(
            "APT search timed out. Your package cache may need updating. Try: sudo apt update"
        )
    except (ValidationError, PackageManagerNotFound, TimeoutError, PackageSearchException):
        # Re-raise our specific exceptions
        raise
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error during APT search", e)
        raise PackageSearchException(
            "An unexpected error occurred while searching APT packages. "
            "Please try again or check your system configuration."
        )