# exceptions.py
"""Common exception classes for the Universal Package Helper CLI."""

from typing import Optional


class PackageSearchException(Exception):
    """Base exception class for package search operations.
    
    This is the base class for all package search related exceptions.
    It provides consistent error handling and logging support.
    """
    
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            original_error: The original exception that caused this error, if any
        """
        super().__init__(message)
        self.message = message
        self.original_error = original_error
    
    def __str__(self) -> str:
        """Return string representation of the exception."""
        if self.original_error:
            return f"{self.message} (caused by: {type(self.original_error).__name__}: {str(self.original_error)})"
        return self.message


class PackageManagerNotFound(PackageSearchException):
    """Exception raised when a package manager is not installed or available.
    
    This exception is raised when the system doesn't have the required
    package manager installed or it's not available in the PATH.
    """
    
    def __init__(self, message: str, package_manager: Optional[str] = None, original_error: Optional[Exception] = None):
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            package_manager: Name of the missing package manager
            original_error: The original exception that caused this error, if any
        """
        super().__init__(message, original_error)
        self.package_manager = package_manager


class PackageManagerError(PackageSearchException):
    """Exception raised when a package manager encounters an error.
    
    This exception is raised when a package manager is available but
    encounters an error during operation (e.g., corrupted database,
    configuration issues).
    """
    
    def __init__(self, message: str, package_manager: Optional[str] = None, exit_code: Optional[int] = None, original_error: Optional[Exception] = None):
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            package_manager: Name of the package manager that failed
            exit_code: Exit code returned by the package manager
            original_error: The original exception that caused this error, if any
        """
        super().__init__(message, original_error)
        self.package_manager = package_manager
        self.exit_code = exit_code


class NetworkError(PackageSearchException):
    """Exception raised for network-related errors.
    
    This exception is raised when network operations fail, such as
    when unable to connect to package repositories or when network
    timeouts occur.
    """
    
    def __init__(self, message: str, url: Optional[str] = None, original_error: Optional[Exception] = None):
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            url: The URL that failed to be accessed, if applicable
            original_error: The original exception that caused this error, if any
        """
        super().__init__(message, original_error)
        self.url = url


class TimeoutError(PackageSearchException):
    """Exception raised when operations timeout.
    
    This exception is raised when package manager operations or
    network requests exceed their configured timeout values.
    """
    
    def __init__(self, message: str, timeout_duration: Optional[float] = None, operation: Optional[str] = None, original_error: Optional[Exception] = None):
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            timeout_duration: The timeout duration in seconds, if known
            operation: Description of the operation that timed out
            original_error: The original exception that caused this error, if any
        """
        super().__init__(message, original_error)
        self.timeout_duration = timeout_duration
        self.operation = operation


class ValidationError(PackageSearchException):
    """Exception raised for input validation errors.
    
    This exception is raised when user input or internal data
    fails validation checks (e.g., empty queries, invalid package names).
    """
    
    def __init__(self, message: str, invalid_value: Optional[str] = None, validation_rule: Optional[str] = None, original_error: Optional[Exception] = None):
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            invalid_value: The value that failed validation, if applicable
            validation_rule: Description of the validation rule that was violated
            original_error: The original exception that caused this error, if any
        """
        super().__init__(message, original_error)
        self.invalid_value = invalid_value
        self.validation_rule = validation_rule


class CommandGenerationError(Exception):
    """Exception raised when command generation fails.
    
    This exception is raised when the system cannot generate
    installation commands for packages, typically due to missing
    package managers or unsupported package sources.
    """
    
    def __init__(self, message: str, package_name: Optional[str] = None, source: Optional[str] = None, original_error: Optional[Exception] = None):
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            package_name: Name of the package for which command generation failed
            source: Package source (e.g., 'apt', 'pacman') that failed
            original_error: The original exception that caused this error, if any
        """
        super().__init__(message)
        self.message = message
        self.package_name = package_name
        self.source = source
        self.original_error = original_error
    
    def __str__(self) -> str:
        """Return string representation of the exception."""
        parts = [self.message]
        if self.package_name:
            parts.append(f"package: {self.package_name}")
        if self.source:
            parts.append(f"source: {self.source}")
        if self.original_error:
            parts.append(f"caused by: {type(self.original_error).__name__}: {str(self.original_error)}")
        return " | ".join(parts)


# Custom exception for logging purposes
class LoggedError:
    """Mixin class to add logging capabilities to exceptions.
    
    This class provides helper methods for logging exceptions
    before they are raised or handled.
    """
    
    @staticmethod
    def log_and_raise(logger, exception_class, message: str, **kwargs):
        """Log an error and then raise the specified exception.
        
        Args:
            logger: Logger instance to use
            exception_class: Exception class to instantiate and raise
            message: Error message
            **kwargs: Additional arguments to pass to the exception constructor
        """
        logger.error(f"Raising {exception_class.__name__}: {message}")
        raise exception_class(message, **kwargs)
    
    @staticmethod
    def log_and_reraise(logger, exception: Exception, additional_context: str = ""):
        """Log an exception and then re-raise it.
        
        Args:
            logger: Logger instance to use
            exception: Exception to log and re-raise
            additional_context: Additional context information to log
        """
        context_part = f" | Context: {additional_context}" if additional_context else ""
        logger.error(f"Re-raising {type(exception).__name__}: {str(exception)}{context_part}")
        raise exception