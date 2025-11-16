"""
Unit tests for retry module.
"""

import pytest
import time
from unittest.mock import Mock, call

from app.utils.retry import (
    retry_with_backoff,
    retry_on_exception,
    RetryContext,
    RETRIABLE_EXCEPTIONS,
)


class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator."""

    def test_retry_success_first_attempt(self):
        """Test function succeeding on first attempt."""
        mock_func = Mock(return_value="success")

        @retry_with_backoff(max_attempts=3)
        def test_func():
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_success_second_attempt(self):
        """Test function succeeding on second attempt."""
        mock_func = Mock(side_effect=[ConnectionError("fail"), "success"])

        @retry_with_backoff(max_attempts=3, backoff_seconds=0.1)
        def test_func():
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_all_attempts_fail(self):
        """Test all retry attempts failing."""
        mock_func = Mock(side_effect=ConnectionError("always fails"))

        @retry_with_backoff(max_attempts=3, backoff_seconds=0.1)
        def test_func():
            return mock_func()

        with pytest.raises(ConnectionError):
            test_func()

        assert mock_func.call_count == 3

    def test_retry_exponential_backoff(self):
        """Test exponential backoff timing."""
        call_times = []

        def failing_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ConnectionError("fail")
            return "success"

        @retry_with_backoff(max_attempts=3, backoff_seconds=0.1, exponential=True)
        def test_func():
            return failing_func()

        result = test_func()

        assert result == "success"
        assert len(call_times) == 3

        # Check that wait times increase exponentially
        # First wait: 0.1s, Second wait: 0.2s
        if len(call_times) >= 3:
            wait1 = call_times[1] - call_times[0]
            wait2 = call_times[2] - call_times[1]
            assert 0.08 < wait1 < 0.15  # Allow some tolerance
            assert 0.18 < wait2 < 0.25  # Allow some tolerance

    def test_retry_linear_backoff(self):
        """Test linear backoff timing."""
        call_times = []

        def failing_func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ConnectionError("fail")
            return "success"

        @retry_with_backoff(max_attempts=3, backoff_seconds=0.1, exponential=False)
        def test_func():
            return failing_func()

        result = test_func()

        assert result == "success"
        assert len(call_times) == 3

        # Check that wait times are consistent
        if len(call_times) >= 3:
            wait1 = call_times[1] - call_times[0]
            wait2 = call_times[2] - call_times[1]
            assert 0.08 < wait1 < 0.15
            assert 0.08 < wait2 < 0.15

    def test_retry_custom_exceptions(self):
        """Test retrying only on custom exceptions."""
        mock_func = Mock(side_effect=ValueError("custom error"))

        @retry_with_backoff(max_attempts=3, backoff_seconds=0.1, exceptions=(ValueError,))
        def test_func():
            return mock_func()

        with pytest.raises(ValueError):
            test_func()

        assert mock_func.call_count == 3

    def test_retry_non_retriable_exception(self):
        """Test that non-retriable exceptions are not retried."""
        mock_func = Mock(side_effect=ValueError("not retriable"))

        @retry_with_backoff(max_attempts=3, backoff_seconds=0.1)
        def test_func():
            return mock_func()

        with pytest.raises(ValueError):
            test_func()

        # Should fail immediately, not retry
        assert mock_func.call_count == 1

    def test_retry_callback(self):
        """Test retry callback is called."""
        callback_calls = []

        def on_retry_callback(exception, attempt, wait_time):
            callback_calls.append((exception, attempt, wait_time))

        mock_func = Mock(side_effect=[ConnectionError("fail"), "success"])

        @retry_with_backoff(
            max_attempts=3,
            backoff_seconds=0.1,
            on_retry=on_retry_callback
        )
        def test_func():
            return mock_func()

        result = test_func()

        assert result == "success"
        assert len(callback_calls) == 1
        assert callback_calls[0][1] == 1  # First attempt failed
        assert callback_calls[0][2] == 0.1  # Wait time

    def test_retry_max_attempts_validation(self):
        """Test that max_attempts is validated."""
        @retry_with_backoff(max_attempts=0, backoff_seconds=0.1)
        def test_func():
            return "success"

        # Should still work with at least 1 attempt
        result = test_func()
        assert result == "success"

    def test_retry_with_args_kwargs(self):
        """Test retry with function arguments."""
        mock_func = Mock(return_value="success")

        @retry_with_backoff(max_attempts=3)
        def test_func(a, b, c=None):
            return mock_func(a, b, c=c)

        result = test_func(1, 2, c=3)

        assert result == "success"
        mock_func.assert_called_once_with(1, 2, c=3)


class TestRetryOnException:
    """Tests for retry_on_exception decorator."""

    def test_retry_on_specific_exception(self):
        """Test retrying on specific exception type."""
        mock_func = Mock(side_effect=[ValueError("fail"), "success"])

        @retry_on_exception(ValueError, max_attempts=3, backoff_seconds=0.1)
        def test_func():
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_on_exception_not_matching(self):
        """Test that other exceptions are not retried."""
        mock_func = Mock(side_effect=ConnectionError("fail"))

        @retry_on_exception(ValueError, max_attempts=3, backoff_seconds=0.1)
        def test_func():
            return mock_func()

        with pytest.raises(ConnectionError):
            test_func()

        # Should fail immediately
        assert mock_func.call_count == 1


class TestRetryContext:
    """Tests for RetryContext context manager."""

    def test_retry_context_success_first_attempt(self):
        """Test context manager with success on first attempt."""
        attempts = []
        retry_ctx = RetryContext(max_attempts=3, backoff_seconds=0.1)

        for attempt in retry_ctx:
            attempts.append(attempt)
            # Succeed on first attempt
            retry_ctx.success()
            break

        assert len(attempts) == 1

    def test_retry_context_success_second_attempt(self):
        """Test context manager with success on second attempt."""
        attempts = []
        retry_ctx = RetryContext(max_attempts=3, backoff_seconds=0.1)

        for attempt in retry_ctx:
            attempts.append(attempt)
            if attempt == 1:
                # Fail first attempt
                retry_ctx.failure(ConnectionError("fail"))
            else:
                # Succeed on second attempt
                retry_ctx.success()
                break

        assert len(attempts) == 2

    def test_retry_context_all_attempts_fail(self):
        """Test context manager with all attempts failing."""
        attempts = []
        retry_ctx = RetryContext(max_attempts=3, backoff_seconds=0.1)

        with pytest.raises(ConnectionError):
            for attempt in retry_ctx:
                attempts.append(attempt)
                # Fail all attempts
                retry_ctx.failure(ConnectionError("fail"))

        assert len(attempts) == 3

    def test_retry_context_exponential_backoff(self):
        """Test context manager with exponential backoff."""
        call_times = []
        retry_ctx = RetryContext(max_attempts=3, backoff_seconds=0.1, exponential=True)

        for attempt in retry_ctx:
            call_times.append(time.time())
            if attempt < 3:
                retry_ctx.failure(ConnectionError("fail"))
            else:
                retry_ctx.success()
                break

        assert len(call_times) == 3

    def test_retry_context_linear_backoff(self):
        """Test context manager with linear backoff."""
        call_times = []
        retry_ctx = RetryContext(max_attempts=3, backoff_seconds=0.1, exponential=False)

        for attempt in retry_ctx:
            call_times.append(time.time())
            if attempt < 3:
                retry_ctx.failure(ConnectionError("fail"))
            else:
                retry_ctx.success()
                break

        assert len(call_times) == 3


class TestRetriableExceptions:
    """Tests for RETRIABLE_EXCEPTIONS constant."""

    def test_retriable_exceptions_tuple(self):
        """Test that RETRIABLE_EXCEPTIONS is a tuple."""
        assert isinstance(RETRIABLE_EXCEPTIONS, tuple)

    def test_retriable_exceptions_not_empty(self):
        """Test that RETRIABLE_EXCEPTIONS is not empty."""
        assert len(RETRIABLE_EXCEPTIONS) > 0

    def test_retriable_exceptions_includes_connection_error(self):
        """Test that ConnectionError is in RETRIABLE_EXCEPTIONS."""
        assert ConnectionError in RETRIABLE_EXCEPTIONS

    def test_retriable_exceptions_includes_timeout_error(self):
        """Test that TimeoutError is in RETRIABLE_EXCEPTIONS."""
        assert TimeoutError in RETRIABLE_EXCEPTIONS
