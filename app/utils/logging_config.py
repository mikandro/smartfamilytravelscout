"""
Logging configuration for SmartFamilyTravelScout.

Provides structured logging with JSON format for production and
human-readable format for development.
"""

import json
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Outputs log records as JSON objects with consistent fields:
    - timestamp: ISO format timestamp
    - level: Log level (INFO, WARNING, ERROR, etc.)
    - message: Log message
    - module: Module name
    - function: Function name
    - line: Line number
    - extra: Any additional fields
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON string representation of the log record
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record.__dict__
        reserved_fields = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "stack_info",
        }

        for key, value in record.__dict__.items():
            if key not in reserved_fields and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """
    Colored formatter for console output in development.

    Adds colors to different log levels for better readability.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record with colors.

        Args:
            record: Log record to format

        Returns:
            Formatted string with ANSI color codes
        """
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"

        # Format the message
        formatted = super().format(record)

        # Reset levelname to original (without colors)
        record.levelname = levelname

        return formatted


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: str | None = None,
    console_output: bool = True,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON format for logs (recommended for production)
        log_file: Optional path to log file. If None, no file logging.
        console_output: Enable console output (default: True)
        max_bytes: Maximum size of log file in bytes before rotation (default: 10MB)
        backup_count: Number of backup log files to keep (default: 5)

    Examples:
        >>> # Development setup with colored console output
        >>> setup_logging(level="DEBUG", json_format=False)

        >>> # Production setup with JSON logs to file
        >>> setup_logging(level="INFO", json_format=True, log_file="logs/app.log")

        >>> # Disable console output (file only)
        >>> setup_logging(level="INFO", log_file="logs/app.log", console_output=False)

        >>> # Custom rotation settings (50MB files, 10 backups)
        >>> setup_logging(level="INFO", log_file="logs/app.log", max_bytes=52428800, backup_count=10)
    """
    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if level.upper() not in valid_levels:
        level = "INFO"

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        # Human-readable format with colors
        formatter = ColoredFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use RotatingFileHandler to prevent log files from growing indefinitely
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(logging, level.upper()))

        # Always use JSON format for file logging
        if not json_format:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(formatter)

        root_logger.addHandler(file_handler)

    # Log initial message
    logging.info(
        f"Logging configured: level={level}, json_format={json_format}, "
        f"log_file={log_file}, console_output={console_output}, "
        f"max_bytes={max_bytes}, backup_count={backup_count}"
    )


def get_logger(name: str, extra_fields: Dict[str, Any] | None = None) -> logging.LoggerAdapter:
    """
    Get a logger with optional extra fields for context.

    Args:
        name: Logger name (usually __name__)
        extra_fields: Optional dict of extra fields to include in all logs

    Returns:
        LoggerAdapter with extra fields

    Examples:
        >>> logger = get_logger(__name__, {"service": "scraper", "version": "1.0"})
        >>> logger.info("Started scraping")
        # Output includes service and version fields
    """
    logger = logging.getLogger(name)

    if extra_fields:
        return logging.LoggerAdapter(logger, extra_fields)

    return logging.LoggerAdapter(logger, {})


class LogContext:
    """
    Context manager for temporary logging context.

    Useful for adding context fields to a block of code.

    Examples:
        >>> logger = logging.getLogger(__name__)
        >>> with LogContext(logger, {"request_id": "12345", "user_id": "67890"}):
        ...     logger.info("Processing request")
        ...     # Logs will include request_id and user_id
    """

    def __init__(self, logger: logging.Logger, context: Dict[str, Any]):
        """
        Initialize log context.

        Args:
            logger: Logger to add context to
            context: Dictionary of context fields
        """
        self.logger = logger
        self.context = context
        self.original_factory = None

    def __enter__(self):
        """Enter context, adding context fields to logger."""
        self.original_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = self.original_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context, restoring original log record factory."""
        if self.original_factory:
            logging.setLogRecordFactory(self.original_factory)


def log_function_call(func):
    """
    Decorator to log function calls with arguments and return values.

    Useful for debugging and tracing function execution.

    Examples:
        >>> @log_function_call
        ... def calculate(x, y):
        ...     return x + y
        >>> calculate(5, 3)
        # Logs: "Calling calculate with args=(5, 3), kwargs={}"
        # Logs: "calculate returned 8"
        8
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)

        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")

        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} returned {result}")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} raised {type(e).__name__}: {e}", exc_info=True)
            raise

    return wrapper
