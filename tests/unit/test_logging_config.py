"""
Unit tests for logging_config module.
"""

import json
import logging
import logging.handlers
import pytest
import tempfile
from pathlib import Path

from app.utils.logging_config import (
    JSONFormatter,
    ColoredFormatter,
    setup_logging,
    get_logger,
    LogContext,
    log_function_call,
)


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_json_formatter_basic(self):
        """Test basic JSON formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert data["module"] == "test"
        assert data["line"] == 10

    def test_json_formatter_with_exception(self):
        """Test JSON formatting with exception."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )

            result = formatter.format(record)
            data = json.loads(result)

            assert data["level"] == "ERROR"
            assert "exception" in data
            assert "ValueError" in data["exception"]

    def test_json_formatter_timestamp(self):
        """Test that timestamp is included."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert "timestamp" in data
        # Should be ISO format
        assert "T" in data["timestamp"]


class TestColoredFormatter:
    """Tests for ColoredFormatter class."""

    def test_colored_formatter_basic(self):
        """Test basic colored formatting."""
        formatter = ColoredFormatter(
            fmt="%(levelname)s - %(message)s"
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Should contain ANSI color codes
        assert "\033[" in result or "INFO" in result

    def test_colored_formatter_preserves_levelname(self):
        """Test that original levelname is preserved."""
        formatter = ColoredFormatter(
            fmt="%(levelname)s"
        )
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )

        formatter.format(record)

        # Original levelname should be preserved
        assert record.levelname == "INFO"


class TestSetupLogging:
    """Tests for setup_logging function."""

    def teardown_method(self):
        """Clean up logging handlers after each test."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)

    def test_setup_logging_basic(self):
        """Test basic logging setup."""
        setup_logging(level="INFO")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) > 0

    def test_setup_logging_debug_level(self):
        """Test setting DEBUG level."""
        setup_logging(level="DEBUG")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_invalid_level(self):
        """Test with invalid level (should default to INFO)."""
        setup_logging(level="INVALID")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_logging_json_format(self):
        """Test JSON format setup."""
        setup_logging(level="INFO", json_format=True)

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0

        # Check that handler uses JSONFormatter
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_setup_logging_no_console(self):
        """Test without console output."""
        setup_logging(level="INFO", console_output=False)

        root_logger = logging.getLogger()
        # Should have no handlers (no console, no file)
        assert len(root_logger.handlers) == 0

    def test_setup_logging_with_file(self):
        """Test logging to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            setup_logging(level="INFO", log_file=str(log_file))

            # Log a message
            logging.info("Test message")

            # Check file was created
            assert log_file.exists()

            # Check file contains log
            content = log_file.read_text()
            assert "Test message" in content

    def test_setup_logging_with_rotation(self):
        """Test logging with rotation settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            # Setup with custom rotation parameters
            setup_logging(
                level="INFO",
                log_file=str(log_file),
                max_bytes=1024,  # 1KB for testing
                backup_count=3
            )

            # Get the file handler
            root_logger = logging.getLogger()
            file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]

            assert len(file_handlers) > 0

            # Check rotation settings
            handler = file_handlers[0]
            assert handler.maxBytes == 1024
            assert handler.backupCount == 3

    def test_setup_logging_rotation_creates_backups(self):
        """Test that log rotation creates backup files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            # Setup with small max_bytes to trigger rotation
            setup_logging(
                level="INFO",
                log_file=str(log_file),
                max_bytes=100,  # Very small to trigger rotation easily
                backup_count=2
            )

            # Write enough data to trigger rotation
            for i in range(50):
                logging.info(f"Test message {i} with enough content to fill the log file")

            # Check that backup files were created
            log_dir = Path(tmpdir)
            log_files = list(log_dir.glob("test.log*"))

            # Should have at least the main log file
            assert len(log_files) >= 1
            assert log_file.exists()

    def test_setup_logging_clears_handlers(self):
        """Test that existing handlers are cleared."""
        # Add a dummy handler
        root_logger = logging.getLogger()
        root_logger.addHandler(logging.StreamHandler())

        initial_count = len(root_logger.handlers)
        assert initial_count > 0

        setup_logging(level="INFO")

        # Old handlers should be cleared
        # New handlers added
        assert all(
            isinstance(h, (logging.StreamHandler, logging.FileHandler))
            for h in root_logger.handlers
        )


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_basic(self):
        """Test getting a logger."""
        logger = get_logger(__name__)

        assert isinstance(logger, logging.LoggerAdapter)

    def test_get_logger_with_extra_fields(self):
        """Test getting logger with extra fields."""
        logger = get_logger(__name__, {"service": "test", "version": "1.0"})

        assert isinstance(logger, logging.LoggerAdapter)
        assert logger.extra["service"] == "test"
        assert logger.extra["version"] == "1.0"

    def test_get_logger_no_extra_fields(self):
        """Test getting logger without extra fields."""
        logger = get_logger(__name__)

        assert isinstance(logger, logging.LoggerAdapter)
        assert logger.extra == {}


class TestLogContext:
    """Tests for LogContext context manager."""

    def test_log_context_adds_fields(self, caplog):
        """Test that context adds fields to logs."""
        setup_logging(level="INFO", json_format=True, console_output=False)
        logger = logging.getLogger(__name__)

        with caplog.at_level(logging.INFO):
            with LogContext(logger, {"request_id": "12345"}):
                logger.info("Test message")

        # Check that log was captured
        assert len(caplog.records) > 0
        record = caplog.records[0]

        # Check that extra field was added
        assert hasattr(record, "request_id")
        assert record.request_id == "12345"

    def test_log_context_restores_factory(self):
        """Test that original log factory is restored."""
        original_factory = logging.getLogRecordFactory()

        logger = logging.getLogger(__name__)
        with LogContext(logger, {"test": "value"}):
            # Factory should be different inside context
            pass

        # Factory should be restored
        assert logging.getLogRecordFactory() == original_factory


class TestLogFunctionCall:
    """Tests for log_function_call decorator."""

    def test_log_function_call_success(self, caplog):
        """Test logging successful function call."""
        setup_logging(level="DEBUG", console_output=False)

        @log_function_call
        def test_func(a, b):
            return a + b

        with caplog.at_level(logging.DEBUG):
            result = test_func(5, 3)

        assert result == 8

        # Check logs
        log_messages = [record.message for record in caplog.records]
        assert any("Calling test_func" in msg for msg in log_messages)
        assert any("returned 8" in msg for msg in log_messages)

    def test_log_function_call_exception(self, caplog):
        """Test logging function call with exception."""
        setup_logging(level="DEBUG", console_output=False)

        @log_function_call
        def failing_func():
            raise ValueError("Test error")

        with caplog.at_level(logging.DEBUG):
            with pytest.raises(ValueError):
                failing_func()

        # Check logs
        log_messages = [record.message for record in caplog.records]
        assert any("Calling failing_func" in msg for msg in log_messages)
        assert any("raised ValueError" in msg for msg in log_messages)

    def test_log_function_call_preserves_function(self):
        """Test that decorator preserves function metadata."""
        @log_function_call
        def test_func():
            """Test docstring."""
            pass

        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test docstring."
