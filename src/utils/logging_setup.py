"""Centralized logging configuration for the HiveMind system."""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional
from datetime import datetime
from pathlib import Path

class LogConfig:
    """Logging configuration constants."""
    DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    DEBUG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - [%(threadName)s] - %(message)s'
    MAX_BYTES = 10_485_760  # 10MB
    BACKUP_COUNT = 5
    DEFAULT_LEVEL = logging.INFO

def setup_logging(
    name: str,
    log_dir: str = "logs",
    level: Optional[int] = None,
    enable_console: bool = True,
    enable_debug: bool = False,
    rotate_when: str = 'midnight'
) -> logging.Logger:
    """
    Sets up logging configuration for the given module name.

    Args:
        name: Name of the module/logger
        log_dir: Directory to store log files, defaults to "logs"
        level: Logging level to use, defaults to INFO
        enable_console: Whether to enable console logging
        enable_debug: Whether to enable debug logging with extra detail
        rotate_when: When to rotate log files ('midnight' or 'size')

    Returns:
        logging.Logger: Configured logger instance
    """
    try:
        # Create logs directory if it doesn't exist
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(exist_ok=True)

        # Get or create logger
        logger = logging.getLogger(name)

        # Set level (respect existing level if already set)
        if level is not None:
            logger.setLevel(level)
        elif not logger.hasHandlers():
            logger.setLevel(LogConfig.DEFAULT_LEVEL)

        # Only add handlers if they don't already exist
        if not logger.handlers:
            # Create formatters
            standard_formatter = logging.Formatter(LogConfig.DEFAULT_FORMAT)
            debug_formatter = logging.Formatter(LogConfig.DEBUG_FORMAT)

            # Create and configure handlers based on rotation type
            if rotate_when == 'midnight':
                # Daily rotation at midnight
                log_file = log_dir_path / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
                file_handler = TimedRotatingFileHandler(
                    filename=str(log_file),
                    when='midnight',
                    interval=1,
                    backupCount=LogConfig.BACKUP_COUNT,
                    encoding='utf-8'
                )
            else:
                # Size-based rotation
                log_file = log_dir_path / f"{name}.log"
                file_handler = RotatingFileHandler(
                    filename=str(log_file),
                    maxBytes=LogConfig.MAX_BYTES,
                    backupCount=LogConfig.BACKUP_COUNT,
                    encoding='utf-8'
                )

            # Configure file handler
            file_handler.setFormatter(debug_formatter if enable_debug else standard_formatter)
            logger.addHandler(file_handler)

            # Add console handler if enabled
            if enable_console:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(standard_formatter)
                # Console shows INFO and above by default
                console_handler.setLevel(logging.INFO)
                logger.addHandler(console_handler)

            logger.debug(f"Logging initialized for {name} in {log_dir}")
            logger.debug(f"Log file: {log_file}")
            logger.debug(f"Debug mode: {enable_debug}")
            logger.debug(f"Console output: {enable_console}")
            logger.debug(f"Rotation: {rotate_when}")

    except Exception as e:
        # Fallback to basic logging if setup fails
        logging.basicConfig(
            level=logging.INFO,
            format=LogConfig.DEFAULT_FORMAT,
            stream=sys.stdout
        )
        logger = logging.getLogger(name)
        logger.error(f"Failed to setup logging: {str(e)}", exc_info=True)

    return logger

def get_logger(
    name: str,
    parent: Optional[str] = None,
    **kwargs
) -> logging.Logger:
    """
    Get a logger with optional parent logger inheritance.

    Args:
        name: Name for the new logger
        parent: Optional parent logger name to inherit settings from
        **kwargs: Additional arguments to pass to setup_logging

    Returns:
        logging.Logger: Configured logger instance
    """
    if parent:
        # Inherit parent's handlers and level
        parent_logger = logging.getLogger(parent)
        logger = logging.getLogger(f"{parent}.{name}")
        logger.handlers = parent_logger.handlers
        logger.setLevel(parent_logger.level)
        return logger

    return setup_logging(name, **kwargs)

def update_log_level(logger_name: str, level: int) -> None:
    """
    Update the log level for an existing logger.

    Args:
        logger_name: Name of the logger to update
        level: New logging level to set
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Update handler levels if they exist
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.setLevel(level)
        # Keep console handler at INFO or above
        elif isinstance(handler, logging.StreamHandler):
            handler.setLevel(max(level, logging.INFO))

def create_audit_logger(name: str, log_dir: str = "logs/audit") -> logging.Logger:
    """
    Create a specialized logger for audit trails.

    Args:
        name: Name for the audit logger
        log_dir: Directory to store audit logs

    Returns:
        logging.Logger: Configured audit logger
    """
    audit_format = '%(asctime)s - %(name)s - [AUDIT] - %(message)s'
    formatter = logging.Formatter(audit_format)

    # Create audit log directory
    audit_dir = Path(log_dir)
    audit_dir.mkdir(exist_ok=True, parents=True)

    # Create logger
    logger = logging.getLogger(f"audit.{name}")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        # Use daily rotation for audit logs
        handler = TimedRotatingFileHandler(
            filename=str(audit_dir / f"{name}_audit.log"),
            when='midnight',
            interval=1,
            backupCount=30,  # Keep 30 days of audit logs
            encoding='utf-8'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
