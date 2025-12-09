# search_snap.py
"""Snap search module with standardized error handling and consistent source naming.
IMPROVEMENTS: Kept source name lowercase (already consistent), used config timeouts, unified exception handling."""

import subprocess
from typing import List, Tuple, Optional
from archpkg.config import TIMEOUTS
from archpkg.exceptions import PackageManagerNotFound, PackageSearchException, TimeoutError, ValidationError, NetworkError
from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)

def search_snap(query: str, cache_manager: Optional[object] = None) -> List[Tuple[str, str, str]]:
    """Search for packages using the Snap package manager.
    
    Args:
        query: Search query string
        cache_manager: Optional cache manager for storing/retrieving results
        
    Returns:
        List[Tuple[str, str, str]]: List of (name, description, source) tuples
        
    Raises:
        ValidationError: When query is empty or invalid
        PackageManagerNotFound: When snap is not available
        TimeoutError: When search times out
        NetworkError: When network connection fails
        PackageSearchException: For other search-related errors
    """
    logger.info(f"Starting Snap search for query: '{query}'")
    
    if not query or not query.strip():
        logger.error("Empty search query provided to Snap search")
        raise ValidationError("Empty search query provided")

    # Check cache first if available
    if cache_manager:
        cached_results = cache_manager.get(query, 'snap')
        if cached_results is not None:
            logger.info(f"Retrieved {len(cached_results)} Snap results from cache")
            return cached_results

    # Check if snap is available and working
    logger.debug("Checking Snap availability")
    try:
        subprocess.run(
            ['snap', '--version'],
            capture_output=True,
            check=True,
            timeout=TIMEOUTS['command_check']
        )
        logger.debug("Snap is available and responsive")
    except FileNotFoundError:
        logger.error("snap command not found")
        raise PackageManagerNotFound("snap command not found. Install snapd first.")
    except subprocess.CalledProcessError as e:
        # Check stderr safely
        stderr_str = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr or "")
        logger.error(f"Snap version check failed with return code {e.returncode}, stderr: {stderr_str}")
        
        if "system does not fully support snapd" in stderr_str.lower():
            logger.warning("System does not support snapd")
            raise PackageManagerNotFound("This system does not support snap packages.")
        else:
            logger.error("Snapd not working properly")
            raise PackageSearchException("snapd is installed but not working properly.")
    except subprocess.TimeoutExpired:
        logger.warning("Snap version check timed out")
        raise TimeoutError("snap is not responding. Check if snapd service is running.")

    try:
        logger.debug(f"Executing snap find with timeout {TIMEOUTS['snap']}s")
        # IMPROVED: Use config timeout value
        result = subprocess.run(
            ["snap", "find", query.strip()],
            capture_output=True,
            text=True,
            timeout=TIMEOUTS['snap'],
            check=False
        )

        logger.debug(f"Snap search completed with return code: {result.returncode}")

        # Handle exit codes
        if result.returncode == 1:
            logger.info("Snap search found no matches (normal result)")
            return []
        elif result.returncode != 0:
            error_msg = result.stderr.strip()
            logger.error(f"Snap search failed with error: {error_msg}")
            
            if "cannot communicate with server" in error_msg.lower():
                logger.error("Cannot connect to Snap Store")
                raise NetworkError("Cannot connect to Snap Store. Check internet connection.")
            else:
                logger.error(f"Snap search failed with unknown error: {error_msg}")
                raise PackageSearchException(f"snap search failed: {error_msg or 'Unknown error'}")

        output = result.stdout.strip()
        if not output:
            logger.info("Snap search returned empty output")
            return []

        logger.debug("Parsing Snap search results")
        lines = output.split('\n')
        if len(lines) < 2:
            logger.warning("Snap search returned insufficient output lines")
            return []

        packages = []
        lines_processed = 0
        
        for line in lines[1:]:  # skip header
            if not line.strip():
                continue
                
            lines_processed += 1
            parts = line.split()
            
            if len(parts) >= 2:
                name = parts[0]
                desc_raw = " ".join(parts[1:])
                desc = desc_raw[:100] + ("..." if len(desc_raw) > 100 else "")
                # IMPROVED: Source name already lowercase (kept consistent)
                packages.append((name, desc, "snap"))
                logger.debug(f"Found Snap package: {name}")
            else:
                logger.debug(f"Skipping malformed Snap result line: {line}")

        logger.info(f"Snap search completed: {len(packages)} packages found from {lines_processed} lines")
        
        # Cache results if cache manager is available
        if cache_manager and packages:
            cache_manager.set(query, 'snap', packages)
            logger.debug(f"Cached {len(packages)} Snap results")
        
        return packages

    except subprocess.TimeoutExpired:
        logger.error(f"Snap search timed out after {TIMEOUTS['snap']}s")
        raise TimeoutError("Snap search timed out. Check your internet connection.")
    except (ValidationError, PackageManagerNotFound, TimeoutError, NetworkError, PackageSearchException):
        # Re-raise our specific exceptions
        raise
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error during Snap search", e)
        raise PackageSearchException(f"Unexpected error during snap search: {str(e)}")