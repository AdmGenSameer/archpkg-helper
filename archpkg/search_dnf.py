# search_dnf.py
"""DNF search module with standardized error handling and consistent source naming.
IMPROVEMENTS: Standardized source name to lowercase, used config timeouts, unified exception handling."""

import subprocess
import re
from typing import List, Tuple
from archpkg.config import TIMEOUTS
from archpkg.exceptions import PackageManagerNotFound, PackageSearchException, TimeoutError, ValidationError, NetworkError
from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)

def search_dnf(query: str) -> List[Tuple[str, str, str]]:
    """Search for packages using DNF package manager.
    
    Args:
        query: Search query string
        
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
        logger.error("Empty search query provided to DNF search")
        raise ValidationError("Empty search query provided")

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
        logger.error("dnf command not found")
        raise PackageManagerNotFound(
            "dnf command not found. This system may not be Fedora/RHEL-based."
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"DNF version check failed with return code {e.returncode}")
        raise PackageSearchException("dnf is installed but not working properly.")
    except subprocess.TimeoutExpired:
        logger.warning("DNF version check timed out")
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
            logger.error(f"DNF search failed with error: {error_msg}")
            
            # Parse common DNF error messages
            if "Error: Cache disabled" in error_msg:
                logger.warning("DNF cache is disabled")
                raise PackageSearchException("DNF cache is disabled. Try: sudo dnf makecache")
            elif "Cannot retrieve metalink" in error_msg:
                logger.error("DNF cannot connect to repositories")
                raise NetworkError(
                    "Cannot connect to DNF repositories. Check internet connection."
                )
            elif "Permission denied" in error_msg:
                logger.warning("DNF permission denied")
                raise PackageSearchException(
                    "Permission denied accessing DNF. Try: sudo dnf search"
                )
            else:
                logger.error(f"DNF search failed with unknown error: {error_msg}")
                raise PackageSearchException(
                    f"dnf search failed: {error_msg or 'Unknown error'}"
                )

        output = result.stdout.strip()
        if not output:
            logger.info("DNF search returned empty output")
            return []

        logger.debug("Parsing DNF search results")
        # Parse DNF output
        packages = []
        in_results = False
        lines_processed = 0

        for line in output.split("\n"):
            line = line.strip()
            lines_processed += 1
            
            if not line:
                continue

            # Detect start of results section
            if "====" in line or ("Name" in line and "Matched" in line):
                logger.debug("Found DNF results section header")
                in_results = True
                continue

            # Process package lines
            if in_results and line and not line.startswith("Last metadata"):
                if " : " in line:  # standard DNF format: "package : description"
                    parts = line.split(" : ", 1)
                    if len(parts) == 2:
                        name_version = parts[0].strip()
                        desc = parts[1].strip()

                        # Remove architecture suffix (e.g., .x86_64, .noarch) if present
                        arch_pattern = r"\.(x86_64|i686|armv7hl|aarch64|ppc64le|s390x|noarch)$"
                        name = re.sub(arch_pattern, "", name_version)

                        # IMPROVED: Standardized source name to lowercase
                        packages.append((name, desc, "dnf"))
                        logger.debug(f"Found DNF package: {name}")

        logger.info(f"DNF search completed: {len(packages)} packages found from {lines_processed} lines")
        return packages

    except subprocess.TimeoutExpired:
        logger.error(f"DNF search timed out after {TIMEOUTS['dnf']}s")
        raise TimeoutError("DNF search timed out. This can happen with large repositories.")
    except (ValidationError, PackageManagerNotFound, TimeoutError, NetworkError, PackageSearchException):
        # Re-raise our specific exceptions
        raise
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error during DNF search", e)
        raise PackageSearchException(f"Unexpected error during DNF search: {repr(e)}")