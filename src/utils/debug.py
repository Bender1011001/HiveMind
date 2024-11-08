"""Debug utilities and enhanced logging functionality."""

import logging
import os
from datetime import datetime
from pathlib import Path
from functools import wraps
import json
import traceback
from typing import Any, Callable, Dict, Optional
from .logging_setup import setup_logging

# Set up centralized logging
logger = setup_logging(__name__)

class DebugLogger:
    """Enhanced logging functionality with debug utilities."""

    def __init__(self):
        """Initialize debug logger with file and console handlers."""
        try:
            # Create logs directory if it doesn't exist
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)
            logger.info(f"Debug logs directory created/verified: {log_dir}")

            # Configure daily log file
            log_file = log_dir / f"hivemind_debug_{datetime.now().strftime('%Y%m%d')}.log"
            logger.info(f"Debug log file initialized: {log_file}")

            # Create formatter with more detailed format for debugging
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
            )

            # Create file handler with rotation
            self.file_handler = logging.FileHandler(log_file)
            self.file_handler.setFormatter(formatter)
            self.file_handler.setLevel(logging.DEBUG)

            # Create console handler
            self.console_handler = logging.StreamHandler()
            self.console_handler.setFormatter(formatter)
            self.console_handler.setLevel(logging.INFO)

            logger.info("Debug logging system initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing debug logger: {str(e)}", exc_info=True)
            raise

    def log_request(self, include_params: bool = True, include_response: bool = True) -> Callable:
        """
        Decorator to log API requests and responses with detailed debugging information.

        Args:
            include_params: Whether to include request parameters in debug logs
            include_response: Whether to include response data in debug logs
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate unique request ID
                request_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')

                try:
                    # Log request start
                    logger.info(f"Request {request_id} - Starting {func.__name__}")

                    # Log request parameters if enabled
                    if include_params:
                        try:
                            params = {
                                'args': self._safe_str(args),
                                'kwargs': self._safe_str(kwargs)
                            }
                            logger.debug(f"Request {request_id} - Parameters: {json.dumps(params, indent=2)}")
                        except Exception as e:
                            logger.warning(f"Failed to log request parameters: {str(e)}", exc_info=True)

                    # Execute function
                    start_time = datetime.now()
                    result = func(*args, **kwargs)
                    execution_time = (datetime.now() - start_time).total_seconds()

                    # Log success response
                    logger.info(f"Request {request_id} - Completed {func.__name__} in {execution_time:.3f}s")

                    # Log response data if enabled
                    if include_response:
                        try:
                            logger.debug(f"Request {request_id} - Response: {self._safe_str(result)}")
                        except Exception as e:
                            logger.warning(f"Failed to log response data: {str(e)}", exc_info=True)

                    return result

                except Exception as e:
                    # Log error with full context
                    logger.error(
                        f"Request {request_id} - Error in {func.__name__}: {str(e)}",
                        exc_info=True,
                        extra={
                            'request_id': request_id,
                            'function': func.__name__,
                            'args': self._safe_str(args),
                            'kwargs': self._safe_str(kwargs),
                            'traceback': traceback.format_exc()
                        }
                    )
                    raise

            return wrapper
        return decorator

    def _safe_str(self, obj: Any) -> str:
        """Safely convert object to string, handling sensitive data."""
        try:
            if isinstance(obj, dict):
                # Mask sensitive fields
                safe_dict = {}
                sensitive_fields = {'password', 'token', 'api_key', 'secret'}
                for k, v in obj.items():
                    if any(field in k.lower() for field in sensitive_fields):
                        safe_dict[k] = '***'
                    else:
                        safe_dict[k] = v
                return str(safe_dict)
            return str(obj)
        except Exception:
            return '<unprintable object>'

    def set_log_level(self, level: int) -> None:
        """Set the log level for all handlers."""
        try:
            logger.setLevel(level)
            self.file_handler.setLevel(level)
            self.console_handler.setLevel(level)
            logger.info(f"Log level set to: {logging.getLevelName(level)}")
        except Exception as e:
            logger.error(f"Error setting log level: {str(e)}", exc_info=True)
            raise

    def log_message(self, level: int, message: str, **kwargs: Any) -> None:
        """
        Log a message with additional context and proper formatting.

        Args:
            level: Logging level to use
            message: Main message to log
            **kwargs: Additional context to include in the log
        """
        try:
            # Format additional context
            extra = json.dumps(kwargs, indent=2) if kwargs else ''

            # Add source code context if available
            frame = traceback.extract_stack()[-2]  # Get caller's frame
            source_context = f"[{frame.filename}:{frame.lineno}]"

            # Construct final message
            full_message = f"{source_context} {message} {extra}".strip()

            logger.log(level, full_message)

        except Exception as e:
            logger.error(f"Error logging message: {str(e)}", exc_info=True)
            raise

# Create singleton instance
debug_logger = DebugLogger()

# Convenience methods using the singleton instance
def log_request(include_params: bool = True, include_response: bool = True) -> Callable:
    return debug_logger.log_request(include_params, include_response)

def set_log_level(level: int) -> None:
    debug_logger.set_log_level(level)

def log_message(level: int, message: str, **kwargs: Any) -> None:
    debug_logger.log_message(level, message, **kwargs)

# Standard logging convenience functions
def debug(message: str, **kwargs: Any) -> None:
    log_message(logging.DEBUG, message, **kwargs)

def info(message: str, **kwargs: Any) -> None:
    log_message(logging.INFO, message, **kwargs)

def warning(message: str, **kwargs: Any) -> None:
    log_message(logging.WARNING, message, **kwargs)

def error(message: str, **kwargs: Any) -> None:
    log_message(logging.ERROR, message, **kwargs)

def critical(message: str, **kwargs: Any) -> None:
    log_message(logging.CRITICAL, message, **kwargs)
