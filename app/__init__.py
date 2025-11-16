"""
SmartFamilyTravelScout - AI-powered family travel deal finder.

This module initializes the application with proper logging configuration.
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Any, Dict

from app.config import settings

__version__ = "0.1.0"
__app_name__ = "SmartFamilyTravelScout"


def get_logging_config() -> Dict[str, Any]:
    """
    Get logging configuration dictionary.

    Returns JSON-formatted logs for production, simple format for development.
    """
    log_level = settings.log_level.upper()

    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "class": "logging.Formatter",
                "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d}',
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "simple": {
                "class": "logging.Formatter",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "class": "logging.Formatter",
                "format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "json" if settings.environment == "production" else "simple",
                "stream": sys.stdout,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": "json",
                "filename": "logs/app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": "logs/error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "app": {
                "level": log_level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING" if not settings.debug else "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "celery": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file"],
        },
    }

    return config


def setup_logging() -> None:
    """Configure logging for the application."""
    config = get_logging_config()
    logging.config.dictConfig(config)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized for {__app_name__} v{__version__}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Log level: {settings.log_level}")
    logger.info(f"Debug mode: {settings.debug}")


# Initialize logging when the module is imported
setup_logging()

# Get logger for this module
logger = logging.getLogger(__name__)
logger.info(f"{__app_name__} initialized")
