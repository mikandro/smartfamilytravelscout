"""
Retry decorator with exponential backoff for SmartFamilyTravelScout.

Provides robust retry logic for handling transient failures in API calls,
network requests, and database operations.
"""

import logging
import time
from functools import wraps
from typing import Callable, Type, Tuple

logger = logging.getLogger(__name__)

# Default exceptions that trigger retries
RETRIABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def retry_with_backoff(
    max_attempts: int = 3,
    backoff_seconds: int = 2,
    exponential: bool = True,
    exceptions: Tuple[Type[Exception], ...] | None = None,
    on_retry: Callable[[Exception, int, int], None] | None = None,
):
    """
    Decorator for retrying functions with exponential backoff.

    Retries the decorated function on specified exceptions with exponential
    or linear backoff between attempts.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        backoff_seconds: Initial backoff time in seconds (default: 2)
        exponential: Use exponential backoff (2s, 4s, 8s) vs linear (2s, 2s, 2s)
        exceptions: Tuple of exception types to catch. If None, uses RETRIABLE_EXCEPTIONS.
        on_retry: Optional callback function(exception, attempt, wait_time) called before retry

    Returns:
        Decorated function with retry logic

    Examples:
        >>> @retry_with_backoff(max_attempts=3, backoff_seconds=1)
        ... def flaky_function():
        ...     # Function that might fail
        ...     return "success"

        >>> @retry_with_backoff(max_attempts=5, exceptions=(ValueError,))
        ... def validate_data(data):
        ...     if not data:
        ...         raise ValueError("Empty data")
        ...     return data

    Raises:
        The last exception if all retry attempts fail
    """
    if exceptions is None:
        exceptions = RETRIABLE_EXCEPTIONS

    if max_attempts < 1:
        max_attempts = 1

    if backoff_seconds < 0:
        backoff_seconds = 0

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt >= max_attempts:
                        # Last attempt failed, raise the exception
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}",
                            exc_info=True,
                        )
                        raise

                    # Calculate wait time
                    if exponential:
                        wait_time = backoff_seconds * (2 ** (attempt - 1))
                    else:
                        wait_time = backoff_seconds

                    logger.warning(
                        f"Function {func.__name__} failed on attempt {attempt}/{max_attempts}: {e}. "
                        f"Retrying in {wait_time}s..."
                    )

                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(e, attempt, wait_time)
                        except Exception as callback_error:
                            logger.warning(
                                f"Retry callback failed: {callback_error}", exc_info=True
                            )

                    # Wait before retrying
                    time.sleep(wait_time)

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def retry_on_exception(
    exception_type: Type[Exception],
    max_attempts: int = 3,
    backoff_seconds: int = 2,
):
    """
    Simplified retry decorator for a single exception type.

    Args:
        exception_type: Exception type to catch and retry
        max_attempts: Maximum number of attempts (default: 3)
        backoff_seconds: Initial backoff time in seconds (default: 2)

    Returns:
        Decorated function with retry logic

    Examples:
        >>> @retry_on_exception(ValueError, max_attempts=3)
        ... def parse_data(data):
        ...     if not data:
        ...         raise ValueError("No data")
        ...     return data
    """
    return retry_with_backoff(
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
        exponential=True,
        exceptions=(exception_type,),
    )


class RetryContext:
    """
    Context manager for retry logic (alternative to decorator).

    Useful when you want to retry a block of code rather than a whole function.

    Examples:
        >>> retry_ctx = RetryContext(max_attempts=3, backoff_seconds=1)
        >>> for attempt in retry_ctx:
        ...     try:
        ...         # Code that might fail
        ...         result = risky_operation()
        ...         retry_ctx.success()
        ...         break
        ...     except ConnectionError as e:
        ...         retry_ctx.failure(e)
    """

    def __init__(
        self,
        max_attempts: int = 3,
        backoff_seconds: int = 2,
        exponential: bool = True,
        exceptions: Tuple[Type[Exception], ...] | None = None,
    ):
        """
        Initialize retry context.

        Args:
            max_attempts: Maximum number of attempts
            backoff_seconds: Initial backoff time in seconds
            exponential: Use exponential backoff
            exceptions: Tuple of exception types to catch
        """
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self.exponential = exponential
        self.exceptions = exceptions or RETRIABLE_EXCEPTIONS
        self.current_attempt = 0
        self.last_exception = None
        self._success = False

    def __iter__(self):
        """Start iteration over retry attempts."""
        self.current_attempt = 0
        self._success = False
        return self

    def __next__(self):
        """Get next retry attempt."""
        if self._success:
            raise StopIteration

        if self.current_attempt >= self.max_attempts:
            if self.last_exception:
                raise self.last_exception
            raise StopIteration

        self.current_attempt += 1

        # Wait before retry (except for first attempt)
        if self.current_attempt > 1 and self.last_exception:
            if self.exponential:
                wait_time = self.backoff_seconds * (2 ** (self.current_attempt - 2))
            else:
                wait_time = self.backoff_seconds

            logger.warning(
                f"Retry attempt {self.current_attempt}/{self.max_attempts}. "
                f"Waiting {wait_time}s..."
            )
            time.sleep(wait_time)

        return self.current_attempt

    def success(self):
        """Mark the operation as successful."""
        self._success = True

    def failure(self, exception: Exception):
        """
        Mark the operation as failed.

        Args:
            exception: The exception that caused the failure
        """
        self.last_exception = exception

        if self.current_attempt >= self.max_attempts:
            logger.error(
                f"All {self.max_attempts} retry attempts failed: {exception}",
                exc_info=True,
            )
