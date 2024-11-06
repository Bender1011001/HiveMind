import logging
import os
from datetime import datetime
from pathlib import Path
from functools import wraps
import json
import traceback

# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure logging
log_file = log_dir / f"hivemind_{datetime.now().strftime('%Y%m%d')}.log"

# Create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create file handler
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(formatter)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Create logger
logger = logging.getLogger('hivemind')
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def log_request(func):
    """Decorator to log API requests and responses"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Generate request ID
        request_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        
        # Log request
        logger.info(f"Request {request_id} - Starting {func.__name__}")
        try:
            # Log request parameters
            params = {
                'args': str(args),
                'kwargs': str(kwargs)
            }
            logger.debug(f"Request {request_id} - Parameters: {json.dumps(params, indent=2)}")
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Log success response
            logger.info(f"Request {request_id} - Completed {func.__name__} successfully")
            logger.debug(f"Request {request_id} - Response: {str(result)}")
            
            return result
            
        except Exception as e:
            # Log error with full traceback
            logger.error(f"Request {request_id} - Error in {func.__name__}: {str(e)}")
            logger.debug(f"Request {request_id} - Traceback: {traceback.format_exc()}")
            raise
            
    return wrapper

def get_logger(name):
    """Get a logger instance with the specified name"""
    return logging.getLogger(f'hivemind.{name}')

def set_log_level(level):
    """Set the log level for all handlers"""
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)

def log_message(level, message, **kwargs):
    """Log a message with additional context"""
    extra = json.dumps(kwargs, indent=2) if kwargs else ''
    logger.log(
        level,
        f"{message} {extra}".strip()
    )

# Convenience methods
def debug(message, **kwargs):
    log_message(logging.DEBUG, message, **kwargs)

def info(message, **kwargs):
    log_message(logging.INFO, message, **kwargs)

def warning(message, **kwargs):
    log_message(logging.WARNING, message, **kwargs)

def error(message, **kwargs):
    log_message(logging.ERROR, message, **kwargs)

def critical(message, **kwargs):
    log_message(logging.CRITICAL, message, **kwargs)
