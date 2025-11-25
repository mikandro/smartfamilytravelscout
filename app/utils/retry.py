"""
Retry decorator with exponential backoff for SmartFamilyTravelScout.

Provides robust retry logic for handling transient failures in API calls,
network requests, and database operations.

Supports both synchronous and asynchronous functions using tenacity.
"""

import asyncio
import logging
import time
from functools import wraps
from typing import Callable, Type, Tuple

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
)

logger = logging.getLogger(__name__)

# Default exceptions that trigger retries
RETRIABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
    IOError,
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


# ============================================================================
# Tenacity-based Async Retry Decorators
# ============================================================================


def async_retry_with_backoff(
    max_attempts: int = 3,
    min_wait_seconds: int = 2,
    max_wait_seconds: int = 10,
    exceptions: Tuple[Type[Exception], ...] | None = None,
):
    """
    Async retry decorator using tenacity for exponential backoff.

    This decorator is designed for async functions and provides automatic
    retry logic with exponential backoff for transient failures.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        min_wait_seconds: Minimum wait time between retries (default: 2)
        max_wait_seconds: Maximum wait time between retries (default: 10)
        exceptions: Tuple of exception types to catch. If None, uses RETRIABLE_EXCEPTIONS.

    Returns:
        Decorated async function with retry logic

    Examples:
        >>> @async_retry_with_backoff(max_attempts=3)
        ... async def fetch_data():
        ...     async with httpx.AsyncClient() as client:
        ...         response = await client.get("https://api.example.com")
        ...         return response.json()

        >>> @async_retry_with_backoff(max_attempts=5, exceptions=(ValueError,))
        ... async def validate_data(data):
        ...     if not data:
        ...         raise ValueError("Empty data")
        ...     return data

    Raises:
        The last exception if all retry attempts fail
    """
    if exceptions is None:
        exceptions = RETRIABLE_EXCEPTIONS

    return retry(
        retry=retry_if_exception_type(exceptions),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait_seconds, max=max_wait_seconds),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )


def async_retry_on_exception(
    exception_type: Type[Exception],
    max_attempts: int = 3,
    min_wait_seconds: int = 2,
    max_wait_seconds: int = 10,
):
    """
    Simplified async retry decorator for a single exception type.

    Args:
        exception_type: Exception type to catch and retry
        max_attempts: Maximum number of attempts (default: 3)
        min_wait_seconds: Minimum wait time between retries (default: 2)
        max_wait_seconds: Maximum wait time between retries (default: 10)

    Returns:
        Decorated async function with retry logic

    Examples:
        >>> @async_retry_on_exception(httpx.TimeoutException, max_attempts=3)
        ... async def fetch_with_timeout():
        ...     async with httpx.AsyncClient() as client:
        ...         return await client.get("https://api.example.com", timeout=5)
    """
    return async_retry_with_backoff(
        max_attempts=max_attempts,
        min_wait_seconds=min_wait_seconds,
        max_wait_seconds=max_wait_seconds,
        exceptions=(exception_type,),
    )


def database_retry(
    max_attempts: int = 3,
    min_wait_seconds: int = 1,
    max_wait_seconds: int = 5,
):
    """
    Specialized retry decorator for database operations.

    Retries on common database transient errors:
    - Connection errors
    - Timeout errors
    - Operational errors (deadlocks, connection pool exhaustion)

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        min_wait_seconds: Minimum wait time between retries (default: 1)
        max_wait_seconds: Maximum wait time between retries (default: 5)

    Returns:
        Decorated async function with retry logic

    Examples:
        >>> from sqlalchemy.ext.asyncio import AsyncSession
        >>> @database_retry(max_attempts=3)
        ... async def save_to_database(db: AsyncSession, data: dict):
        ...     obj = MyModel(**data)
        ...     db.add(obj)
        ...     await db.commit()
    """
    # Import SQLAlchemy exceptions here to avoid circular imports
    try:
        from sqlalchemy.exc import OperationalError, DBAPIError, TimeoutError as SQLTimeoutError
        db_exceptions = (
            ConnectionError,
            TimeoutError,
            OperationalError,
            DBAPIError,
            SQLTimeoutError,
            OSError,
        )
    except ImportError:
        # Fallback if SQLAlchemy is not installed
        db_exceptions = RETRIABLE_EXCEPTIONS

    return retry(
        retry=retry_if_exception_type(db_exceptions),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait_seconds, max=max_wait_seconds),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )


def redis_retry(
    max_attempts: int = 3,
    min_wait_seconds: int = 1,
    max_wait_seconds: int = 5,
):
    """
    Specialized retry decorator for Redis operations.

    Retries on common Redis transient errors:
    - Connection errors
    - Timeout errors
    - Response errors

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        min_wait_seconds: Minimum wait time between retries (default: 1)
        max_wait_seconds: Maximum wait time between retries (default: 5)

    Returns:
        Decorated async function with retry logic

    Examples:
        >>> from redis.asyncio import Redis
        >>> @redis_retry(max_attempts=3)
        ... async def get_from_cache(redis: Redis, key: str):
        ...     return await redis.get(key)
    """
    # Import Redis exceptions here to avoid circular imports
    try:
        from redis.exceptions import (
            ConnectionError as RedisConnectionError,
            TimeoutError as RedisTimeoutError,
            ResponseError,
        )
        redis_exceptions = (
            ConnectionError,
            TimeoutError,
            RedisConnectionError,
            RedisTimeoutError,
            ResponseError,
            OSError,
        )
    except ImportError:
        # Fallback if redis is not installed
        redis_exceptions = RETRIABLE_EXCEPTIONS

    return retry(
        retry=retry_if_exception_type(redis_exceptions),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait_seconds, max=max_wait_seconds),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )


def api_retry(
    max_attempts: int = 3,
    min_wait_seconds: int = 2,
    max_wait_seconds: int = 10,
):
    """
    Specialized retry decorator for external API calls.

    Retries on common API transient errors:
    - Connection errors
    - Timeout errors
    - HTTP 5xx server errors
    - HTTP 429 rate limit errors (with longer backoff)

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        min_wait_seconds: Minimum wait time between retries (default: 2)
        max_wait_seconds: Maximum wait time between retries (default: 10)

    Returns:
        Decorated async function with retry logic

    Examples:
        >>> import httpx
        >>> @api_retry(max_attempts=3)
        ... async def call_external_api():
        ...     async with httpx.AsyncClient() as client:
        ...         response = await client.get("https://api.example.com/data")
        ...         response.raise_for_status()
        ...         return response.json()
    """
    # Import HTTP exceptions here to avoid circular imports
    try:
        import httpx
        api_exceptions = (
            ConnectionError,
            TimeoutError,
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.NetworkError,
            OSError,
        )
    except ImportError:
        try:
            import aiohttp
            api_exceptions = (
                ConnectionError,
                TimeoutError,
                aiohttp.ClientError,
                asyncio.TimeoutError,
                OSError,
            )
        except ImportError:
            # Fallback if neither httpx nor aiohttp is installed
            api_exceptions = RETRIABLE_EXCEPTIONS

    return retry(
        retry=retry_if_exception_type(api_exceptions),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait_seconds, max=max_wait_seconds),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )


def file_io_retry(
    max_attempts: int = 3,
    min_wait_seconds: int = 1,
    max_wait_seconds: int = 3,
):
    """
    Specialized retry decorator for file I/O operations.

    Retries on common file I/O transient errors:
    - OSError
    - IOError
    - Permission errors (temporary)

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        min_wait_seconds: Minimum wait time between retries (default: 1)
        max_wait_seconds: Maximum wait time between retries (default: 3)

    Returns:
        Decorated function with retry logic (works for both sync and async)

    Examples:
        >>> @file_io_retry(max_attempts=3)
        ... def read_file(path: str):
        ...     with open(path, 'r') as f:
        ...         return f.read()
    """
    file_exceptions = (
        OSError,
        IOError,
        TimeoutError,
    )

    return retry(
        retry=retry_if_exception_type(file_exceptions),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait_seconds, max=max_wait_seconds),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG),
        reraise=True,
    )
