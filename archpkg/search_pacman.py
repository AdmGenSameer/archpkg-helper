# search_pacman.py
"""Pacman search module with standardized error handling and consistent source naming.
IMPROVEMENTS: Kept source name lowercase (already consistent), used config timeouts, unified exception handling."""

import subprocess
from typing import List, Tuple, Optional
from archpkg.config import TIMEOUTS
from archpkg.exceptions import PackageManagerNotFound, PackageSearchException, TimeoutError, ValidationError
from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)

def search_pacman(query: str, cache_manager: Optional[object] = None) -> List[Tuple[str, str, str]]:
    """Search for packages using the pacman package manager.
    
    Args:
        query: Search query string
        cache_manager: Optional cache manager for storing/retrieving results
        
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
        logger.debug("Empty search query provided to pacman search")
        raise ValidationError("Empty search query provided")

    # Check cache first if available
    if cache_manager:
        cached_results = cache_manager.get(query, 'pacman')
        if cached_results is not None:
            logger.info(f"Retrieved {len(cached_results)} pacman results from cache")
            return cached_results

    # Check if paru or pacman is available and working (prefer paru)
    use_paru = False
    logger.debug("Checking paru/pacman availability")
    try:
        subprocess.run(
            ['paru', '--version'],
            capture_output=True,
            check=True,
            timeout=TIMEOUTS['command_check']
        )
        use_paru = True
        logger.debug("paru is available, using it for search")
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        logger.debug("paru not available, checking pacman")
        try:
            subprocess.run(
                ['pacman', '--version'],
                capture_output=True,
                check=True,
                timeout=TIMEOUTS['command_check']
            )
            logger.debug("pacman is available and responsive")
        except FileNotFoundError:
            logger.debug("pacman command not found")
            raise PackageManagerNotFound("pacman command not found. This system may not be Arch-based.")
        except subprocess.CalledProcessError as e:
            logger.debug(f"Pacman version check failed with return code {e.returncode}")
            raise PackageSearchException("pacman is installed but not working properly.")
        except subprocess.TimeoutExpired:
            logger.debug("Pacman version check timed out")
            raise TimeoutError(
                "pacman is not responding. The package manager may be locked or misconfigured."
            )

    # Use selected package manager for search
    search_cmd = 'paru' if use_paru else 'pacman'
    try:
        logger.debug(f"Executing {search_cmd} search with timeout {TIMEOUTS['pacman']}s")
        # IMPROVED: Use config timeout value
        result = subprocess.run(
            [search_cmd, '-Ss', query.strip()],
            capture_output=True,
            text=True,
            timeout=TIMEOUTS['pacman'],
            check=False
        )

        logger.debug(f"{search_cmd} search completed with return code: {result.returncode}")

        # Handle common pacman/paru exit codes
        if result.returncode == 1 and not result.stdout.strip():
            logger.info(f"{search_cmd} search found no matches (normal result)")
            return []
        elif result.returncode != 0:
            error_msg = result.stderr.strip()
            logger.debug(f"{search_cmd} search failed with error: {error_msg}")
            
            if "could not" in error_msg.lower():
                logger.debug("Package manager database issue detected")
                raise PackageSearchException(
                    f"{search_cmd} database not initialized or corrupted. Try: sudo {search_cmd} -Syu"
                )
            else:
                logger.debug(f"{search_cmd} search failed with unknown error: {error_msg}")
                raise PackageSearchException(f"{search_cmd} search failed: {error_msg or 'Unknown error'}")

        output = result.stdout.strip()
        if not output:
            logger.info(f"{search_cmd} search returned empty output")
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
        
        # Cache results if cache manager is available
        if cache_manager and results:
            cache_manager.set(query, 'pacman', results)
            logger.debug(f"Cached {len(results)} pacman results")
        
        return results

    except subprocess.TimeoutExpired:
        logger.debug(f"Pacman search timed out after {TIMEOUTS['pacman']}s")
        raise TimeoutError("pacman search timed out. The package database might be updating.")
    except (ValidationError, PackageManagerNotFound, TimeoutError, PackageSearchException):
        # Re-raise our specific exceptions
        raise
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error during pacman search", e)
        raise PackageSearchException(f"Unexpected error during pacman search: {str(e)}")