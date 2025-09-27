# logging_config.py
"""Centralized logging configuration for the Universal Package Helper CLI."""

import logging
import logging.handlers
import sys
import os
from pathlib import Path
from typing import Optional


class PackageHelperLogger:
    """Centralized logger configuration for consistent logging across modules."""
    
    _instance: Optional['PackageHelperLogger'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'PackageHelperLogger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            PackageHelperLogger._initialized = True
    
    def _get_log_directory(self) -> Path:
        """Get the appropriate log directory for the current platform."""
        if sys.platform == 'win32':
            # Windows: Use AppData/Local
            base_dir = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
            return base_dir / 'archpkg-helper'
        else:
            # Linux/macOS: Use XDG standard
            xdg_data_home = os.environ.get('XDG_DATA_HOME')
            if xdg_data_home:
                return Path(xdg_data_home) / 'archpkg-helper'
            else:
                return Path.home() / '.local' / 'share' / 'archpkg-helper'
    
    def _setup_console_only_logging(self) -> None:
        """Fallback to console-only logging if file logging fails."""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Clear any existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler only
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.WARNING)
        
        console_formatter = logging.Formatter(
            '%(levelname)s - %(name)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        print("Warning: File logging unavailable, using console logging only")
    
    def _setup_logging(self) -> None:
        """Setup centralized logging configuration with robust error handling."""
        try:
            # Get cross-platform log directory
            log_dir = self._get_log_directory()
            
            # Attempt to create log directory
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError) as e:
                print(f"Warning: Cannot create log directory {log_dir}: {e}")
                self._setup_console_only_logging()
                return
            
            log_file = log_dir / 'archpkg-helper.log'
            
            # Test file creation/write access
            try:
                # Test write access
                test_file = log_dir / '.test_write'
                with open(test_file, 'w') as f:
                    f.write('test')
                test_file.unlink()  # Remove test file
            except (OSError, PermissionError) as e:
                print(f"Warning: Cannot write to log directory {log_dir}: {e}")
                self._setup_console_only_logging()
                return
            
            # Configure root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.DEBUG)
            
            # Clear any existing handlers
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            
            # File handler with rotation
            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file,
                    maxBytes=5 * 1024 * 1024,  # 5MB
                    backupCount=3,
                    encoding='utf-8'
                )
                file_handler.setLevel(logging.DEBUG)
                
                # formatter for file
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler.setFormatter(file_formatter)
                root_logger.addHandler(file_handler)
                
            except (OSError, PermissionError) as e:
                print(f"Warning: Cannot create log file {log_file}: {e}")
                self._setup_console_only_logging()
                return
            
            # Console handler (only for warnings and errors by default)
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.WARNING)
            
            # formatter for console
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
            
            # Log the successful initialization
            logger = logging.getLogger(__name__)
            logger.info("Logging system initialized successfully")
            logger.info(f"Log file location: {log_file}")
            logger.debug(f"Log directory: {log_dir}")
            logger.debug(f"Platform: {sys.platform}")
            
        except Exception as e:
            # Final fallback - something went very wrong
            print(f"Error: Logging setup completely failed: {e}")
            import traceback
            traceback.print_exc()
            self._setup_console_only_logging()
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """Get a logger with the specified name.
        
        Args:
            name: Logger name (typically __name__)
            
        Returns:
            logging.Logger: Configured logger instance
        """
        # Ensure logging is initialized
        PackageHelperLogger()
        return logging.getLogger(name)
    
    @staticmethod
    def set_debug_mode(enabled: bool = True) -> None:
        """Enable or disable debug mode logging.
        
        Args:
            enabled: Whether to enable debug mode
        """
        console_handler = None
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stderr:
                console_handler = handler
                break
        
        if console_handler:
            if enabled:
                console_handler.setLevel(logging.DEBUG)
                logger = logging.getLogger(__name__)
                logger.info("Debug mode enabled - console will show all log levels")
                print("Debug mode enabled - verbose logging to console")
            else:
                console_handler.setLevel(logging.WARNING)
                logger = logging.getLogger(__name__)
                logger.info("Debug mode disabled - console shows warnings/errors only")
        else:
            print("Warning: Could not find console handler to modify debug level")
    
    @staticmethod
    def log_exception(logger: logging.Logger, message: str, exception: Exception) -> None:
        """Log an exception with full traceback.
        
        Args:
            logger: Logger instance to use
            message: Descriptive message about the error
            exception: Exception instance to log
        """
        try:
            logger.error(f"{message}: {type(exception).__name__}: {str(exception)}", exc_info=True)
        except Exception:
            # If logging the exception fails, at least print it
            print(f"Logging failed - {message}: {type(exception).__name__}: {str(exception)}")
    
    @staticmethod
    def get_log_file_path() -> Optional[Path]:
        """Get the current log file path if file logging is enabled.
        
        Returns:
            Optional[Path]: Path to log file, or None if only console logging
        """
        try:
            for handler in logging.getLogger().handlers:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    return Path(handler.baseFilename)
            return None
        except Exception:
            return None


def get_logger(name: str) -> logging.Logger:
    """Convenience function to get a configured logger.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return PackageHelperLogger.get_logger(name)


def get_log_info() -> dict:
    """Get information about current logging configuration.
    
    Returns:
        dict: Logging configuration information
    """
    log_file = PackageHelperLogger.get_log_file_path()
    return {
        'log_file': str(log_file) if log_file else None,
        'file_logging_enabled': log_file is not None,
        'log_level': logging.getLogger().level,
        'handler_count': len(logging.getLogger().handlers)
    }