"""
Logging configuration for the AI-powered Storyteller.

Provides centralized logging setup with file and console output.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Global logger cache
_loggers = {}


def setup_logger(
    name: str = "raspi_storyteller",
    log_file: Optional[str] = None,
    level: str = "DEBUG",
) -> logging.Logger:
    """
    Set up a logger with console and optional file output.

    Args:
        name: Logger name.
        log_file: Path to log file (optional).
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if logger.handlers:
        return logger

    # Set level
    log_level = getattr(logging, level.upper(), logging.DEBUG)
    logger.setLevel(log_level)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        try:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.FileHandler(log_path)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (IOError, OSError) as e:
            logger.warning(f"Could not create log file {log_file}: {e}")

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the given name.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Logger instance.
    """
    if name not in _loggers:
        # Get log settings from environment
        log_level = os.getenv("LOG_LEVEL", "DEBUG")
        log_file = os.getenv("LOG_FILE", None)

        # Create child logger under main logger
        parent_name = "raspi_storyteller"
        if not name.startswith(parent_name):
            full_name = f"{parent_name}.{name}"
        else:
            full_name = name

        # Ensure parent logger is set up
        if parent_name not in _loggers:
            _loggers[parent_name] = setup_logger(parent_name, log_file, log_level)

        _loggers[name] = logging.getLogger(full_name)

    return _loggers[name]
