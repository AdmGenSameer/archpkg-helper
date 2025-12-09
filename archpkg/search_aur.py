# search_aur.py
"""AUR search module with standardized error handling and consistent source naming.
IMPROVEMENTS: Standardized source name to lowercase, used config timeouts, improved exception handling."""

import requests
import json
from typing import List, Tuple, Optional
from archpkg.config import TIMEOUTS
from archpkg.exceptions import NetworkError, TimeoutError, ValidationError, PackageSearchException
from archpkg.logging_config import get_logger, PackageHelperLogger

logger = get_logger(__name__)

def search_aur(query: str, cache_manager: Optional[object] = None) -> List[Tuple[str, str, str]]:
    """Search for packages in the Arch User Repository (AUR).
    
    Args:
        query: Search query string
        cache_manager: Optional cache manager for storing/retrieving results
        
    Returns:
        List[Tuple[str, str, str]]: List of (name, description, source) tuples
        
    Raises:
        ValidationError: When query is empty or invalid
        NetworkError: When network connection fails
        TimeoutError: When request times out
        PackageSearchException: For other search-related errors
    """
    logger.info(f"Starting AUR search for query: '{query}'")
    
    # Validate input
    if not query or not query.strip():
        logger.error("Empty search query provided to AUR search")
        raise ValidationError("Empty search query provided")
    
    # Check cache first if available
    if cache_manager:
        cached_results = cache_manager.get(query, 'aur')
        if cached_results is not None:
            logger.info(f"Retrieved {len(cached_results)} AUR results from cache")
            return cached_results
    
    # Construct AUR RPC search API URL
    url = f"https://aur.archlinux.org/rpc/?v=5&type=search&arg={query.strip()}"
    logger.debug(f"AUR API URL: {url}")
    
    try:
        logger.debug(f"Making AUR API request with timeout {TIMEOUTS['aur']}s")
        # IMPROVED: Use config timeout value
        response = requests.get(url, timeout=TIMEOUTS['aur'])
        response.raise_for_status()  # raise exception for non-2xx responses
        
        logger.debug(f"AUR API responded with status code: {response.status_code}")
        logger.debug(f"Response content length: {len(response.content)} bytes")
        
        # Parse JSON response safely
        try:
            data = response.json()
            logger.debug("Successfully parsed AUR API JSON response")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from AUR: {str(e)}")
            raise PackageSearchException(f"Invalid response from AUR: {str(e)}")
        
        # Ensure response is a dictionary
        if not isinstance(data, dict):
            logger.error(f"Unexpected response format from AUR: {type(data)}")
            raise PackageSearchException("Unexpected response format from AUR")
        
        # Extract results safely
        results = data.get("results", [])
        if not isinstance(results, list):
            logger.error(f"Invalid results format from AUR: {type(results)}")
            raise PackageSearchException("Invalid results format from AUR")
        
        logger.debug(f"AUR API returned {len(results)} raw results")
        
        # Process and validate results
        processed_results = []
        for pkg in results:
            if isinstance(pkg, dict) and 'Name' in pkg:
                name = pkg['Name']
                description = pkg.get('Description', 'No description')
                processed_results.append((name, description, 'aur'))
                logger.debug(f"Found AUR package: {name}")
            else:
                logger.warning(f"Skipping invalid AUR package entry: {pkg}")
        
        logger.info(f"AUR search completed: {len(processed_results)} valid packages found")
        # IMPROVED: Standardized source name to lowercase
        
        # Cache results if cache manager is available
        if cache_manager and processed_results:
            cache_manager.set(query, 'aur', processed_results)
            logger.debug(f"Cached {len(processed_results)} AUR results")
        
        return processed_results
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error during AUR search: {str(e)}")
        raise NetworkError("Cannot connect to AUR servers. Check your internet connection.")
    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout error during AUR search: {str(e)}")
        raise TimeoutError("AUR search request timed out. Try again later.")
    except requests.exceptions.HTTPError as e:
        # Handle HTTP error codes specifically
        status_code = e.response.status_code
        logger.error(f"HTTP error during AUR search: {status_code}")
        
        if status_code == 429:
            logger.warning("AUR rate limit exceeded")
            raise NetworkError("AUR rate limit exceeded. Please wait before searching again.")
        elif status_code >= 500:
            logger.error("AUR server error")
            raise NetworkError("AUR servers are experiencing issues. Try again later.")
        else:
            logger.error(f"AUR request failed with status {status_code}")
            raise NetworkError(f"AUR request failed with status {status_code}")
    except (ValidationError, NetworkError, TimeoutError, PackageSearchException):
        # Re-raise our specific exceptions
        raise
    except Exception as e:
        PackageHelperLogger.log_exception(logger, "Unexpected error during AUR search", e)
        raise PackageSearchException(f"AUR search failed: {str(e)}")