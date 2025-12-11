# search_dnf.py
"""DNF search module with standardized error handling and consistent source naming.
IMPROVEMENTS: Standardized source name to lowercase, used config timeouts, unified exception handling."""

import subprocess
import re
from typing import List, Tuple, Optional
from archpkg.config import TIMEOUTS
from archpkg.exceptions import PackageManagerNotFound, PackageSearchException, TimeoutError, ValidationError, NetworkError
from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)

def search_dnf(query: str, cache_manager: Optional[object] = None) -> List[Tuple[str, str, str]]:
    """Search for packages using DNF package manager.
    
    Args:
        query: Search query string
        cache_manager: Optional cache manager for storing/retrieving results
        
    Returns:
        List[Tuple[str, str, str]]: List of (name, description, source) tuples
        
    Raises:
        ValidationError: When query is empty or invalid
        PackageManagerNotFound: When DNF is not available
        TimeoutError: When search times out
        NetworkError: When network connection fails
        PackageSearchException: For other search-related errors
    """
    logger.info(f"Starting DNF search for query: '{query}'")
    
    if not query or not query.strip():
        logger.debug("Empty search query provided to DNF search")
        raise ValidationError("Empty search query provided")

    # Check cache first if available
    if cache_manager:
        cached_results = cache_manager.get(query, 'dnf')
        if cached_results is not None:
            logger.info(f"Retrieved {len(cached_results)} DNF results from cache")
            return cached_results

    # Check if DNF is available and working
    logger.debug("Checking DNF availability")
    try:
        subprocess.run(
            ["dnf", "--version"],
            capture_output=True,
            check=True,
            timeout=TIMEOUTS['command_check']
        )
        logger.debug("DNF is available and responsive")
    except FileNotFoundError:
        logger.debug("dnf command not found")
        raise PackageManagerNotFound("dnf")
    except subprocess.CalledProcessError as e:
        logger.debug(f"DNF version check failed with return code {e.returncode}")
        raise PackageSearchException("dnf is installed but not working properly.")
    except subprocess.TimeoutExpired:
        logger.debug("DNF version check timed out")
        raise TimeoutError("dnf is not responding.")

    try:
        logger.debug(f"Executing dnf search with timeout {TIMEOUTS['dnf']}s")
        # IMPROVED: Use config timeout value
        result = subprocess.run(
            ["dnf", "search", query.strip()],
            capture_output=True,
            text=True,
            timeout=TIMEOUTS['dnf'],
            check=False
        )

        logger.debug(f"DNF search completed with return code: {result.returncode}")

        # Handle DNF exit codes
        if result.returncode == 1:  # no matches found
            logger.info("DNF search found no matches (normal result)")
            return []
        elif result.returncode != 0:
            error_msg = result.stderr.strip()
            logger.debug(f"DNF search failed with error: {error_msg}")
            
            # Parse common DNF error messages
            if "Error: Cache disabled" in error_msg:
                logger.debug("DNF cache is disabled")
                raise PackageSearchException("DNF cache is disabled. Try: sudo dnf makecache")
            elif "Cannot retrieve metalink" in error_msg:
                logger.debug("DNF cannot connect to repositories")
                raise NetworkError(
                    "Cannot connect to DNF repositories. Check internet connection."
                )
            elif "Permission denied" in error_msg:
                logger.debug("DNF permission denied")
                raise PackageSearchException(
                    "Permission denied accessing DNF. Try: sudo dnf search"
                )
            else:
                logger.debug(f"DNF search failed with unknown error: {error_msg}")
                raise PackageSearchException(
                    f"dnf search failed: {error_msg or 'Unknown error'}"
                )

        output = result.stdout.strip()
        if not output:
            logger.info("DNF search returned empty output")
            return []

        logger.debug("Parsing DNF search results")
        # Parse DNF/DNF5 output. DNF5 may not emit explicit headers and can use tabs or
        # multiple spaces between package name and description. We avoid relying on a
        # header toggle and instead parse any reasonable package line.
        packages = []
        lines_processed = 0

        arch_pattern = r"\.(x86_64|i686|armv7hl|aarch64|ppc64le|s390x|noarch)$"

        for line in output.split("\n"):
            line = line.strip()
            lines_processed += 1

            if not line:
                continue

            # Skip meta/info lines
            lower_line = line.lower()
            if lower_line.startswith((
                "last metadata",
                "updating",
                "repositories",
                "matched fields",
                "error:",
                "warning:"
            )):
                continue

            # DNF classic format: "name : description"
            match = re.match(r"^(\S+)\s*:\s*(.+)$", line)

            # DNF5 format often uses tabs or multiple spaces: "name<TAB>description"
            if not match:
                match = re.match(r"^(\S+)\s{2,}(.+)$", line) or re.match(r"^(\S+)\t+(.+)$", line)

            if match:
                name_version = match.group(1).strip()
                desc = match.group(2).strip()

                # Remove architecture suffix (e.g., .x86_64, .noarch) if present
                name = re.sub(arch_pattern, "", name_version)

                packages.append((name, desc, "dnf"))
                logger.debug(f"Found DNF package: {name}")
                continue

        logger.info(f"DNF search completed: {len(packages)} packages found from {lines_processed} lines")

        logger.info(f"DNF search completed: {len(packages)} packages found from {lines_processed} lines")
        
        # Cache results if cache manager is available
        if cache_manager and packages:
            cache_manager.set(query, 'dnf', packages)
            logger.debug(f"Cached {len(packages)} DNF results")
        
        return packages

    except subprocess.TimeoutExpired:
        logger.debug(f"DNF search timed out after {TIMEOUTS['dnf']}s")
        raise TimeoutError("DNF search timed out. This can happen with large repositories.")
    except (ValidationError, PackageManagerNotFound, TimeoutError, NetworkError, PackageSearchException):
        # Re-raise our specific exceptions
        raise
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error during DNF search", e)
        raise PackageSearchException(f"Unexpected error during DNF search: {repr(e)}")