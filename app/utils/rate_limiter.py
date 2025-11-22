"""
Unified Redis-based rate limiter for API scrapers.

This module provides a centralized rate limiting mechanism that works across
processes and containers, solving the inconsistency issues with file-based
and in-memory rate limiting approaches.

Features:
- Redis-based storage (persists across restarts, works in containers)
- Configurable request limits and time windows per scraper
- Thread-safe and process-safe
- Graceful fallback when Redis is unavailable
- Support for multiple time window types (hourly, daily, monthly)
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)


class TimeWindow(str, Enum):
    """Time window types for rate limiting."""

    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""

    pass


class RedisRateLimiter:
    """
    Redis-based rate limiter with configurable limits and time windows.

    This class provides a unified rate limiting solution that works across
    multiple processes and containers by storing rate limit data in Redis.

    Examples:
        >>> # Create rate limiter for Kiwi API (100 calls/month)
        >>> limiter = RedisRateLimiter(
        ...     scraper_name="kiwi",
        ...     max_requests=100,
        ...     time_window=TimeWindow.MONTHLY
        ... )
        >>>
        >>> # Check if request is allowed
        >>> if limiter.is_allowed():
        ...     # Make API call
        ...     limiter.record_request()
        ... else:
        ...     print(f"Rate limit exceeded. {limiter.get_remaining()} requests remaining")
    """

    def __init__(
        self,
        scraper_name: str,
        max_requests: int,
        time_window: TimeWindow = TimeWindow.DAILY,
        redis_url: Optional[str] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            scraper_name: Unique identifier for the scraper (e.g., "kiwi", "ryanair")
            max_requests: Maximum number of requests allowed in the time window
            time_window: Time window type (hourly, daily, monthly)
            redis_url: Redis connection URL (defaults to settings.redis_url)
        """
        self.scraper_name = scraper_name
        self.max_requests = max_requests
        self.time_window = time_window
        self.redis_url = redis_url or str(settings.redis_url)

        # Initialize Redis client
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            self.redis_client.ping()
            logger.info(
                f"RedisRateLimiter initialized for '{scraper_name}': "
                f"{max_requests} requests per {time_window.value}"
            )
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    def _get_redis_key(self) -> str:
        """
        Get Redis key for current time window.

        The key format is: rate_limit:{scraper_name}:{window}:{period}
        For example: rate_limit:kiwi:monthly:2025-11
        """
        now = datetime.now()

        if self.time_window == TimeWindow.HOURLY:
            period = now.strftime("%Y-%m-%d-%H")
        elif self.time_window == TimeWindow.DAILY:
            period = now.strftime("%Y-%m-%d")
        elif self.time_window == TimeWindow.MONTHLY:
            period = now.strftime("%Y-%m")
        else:
            raise ValueError(f"Invalid time window: {self.time_window}")

        return f"rate_limit:{self.scraper_name}:{self.time_window.value}:{period}"

    def _get_ttl(self) -> int:
        """
        Get TTL (time to live) in seconds for the current window.

        Returns:
            TTL in seconds until the end of the current time window
        """
        now = datetime.now()

        if self.time_window == TimeWindow.HOURLY:
            # Expire at end of current hour
            next_window = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        elif self.time_window == TimeWindow.DAILY:
            # Expire at end of current day
            next_window = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
                days=1
            )
        elif self.time_window == TimeWindow.MONTHLY:
            # Expire at end of current month
            if now.month == 12:
                next_window = now.replace(
                    year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0
                )
            else:
                next_window = now.replace(
                    month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0
                )
        else:
            raise ValueError(f"Invalid time window: {self.time_window}")

        ttl = int((next_window - now).total_seconds())
        # Add a small buffer to ensure the key expires
        return ttl + 60

    def get_current_count(self) -> int:
        """
        Get the current request count for this time window.

        Returns:
            Number of requests made in the current time window
        """
        if not self.redis_client:
            logger.warning("Redis unavailable, returning 0")
            return 0

        try:
            key = self._get_redis_key()
            count = self.redis_client.get(key)
            return int(count) if count else 0
        except RedisError as e:
            logger.error(f"Error getting count from Redis: {e}")
            return 0

    def get_remaining(self) -> int:
        """
        Get the number of remaining requests in this time window.

        Returns:
            Number of requests remaining (0 if limit exceeded)
        """
        current = self.get_current_count()
        remaining = max(0, self.max_requests - current)
        return remaining

    def is_allowed(self) -> bool:
        """
        Check if a request is allowed under the rate limit.

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        if not self.redis_client:
            logger.warning("Redis unavailable, allowing request (no rate limiting)")
            return True

        try:
            current_count = self.get_current_count()
            is_allowed = current_count < self.max_requests

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for '{self.scraper_name}': "
                    f"{current_count}/{self.max_requests} requests this {self.time_window.value}"
                )

            return is_allowed
        except RedisError as e:
            logger.error(f"Error checking rate limit: {e}")
            # Fail open: allow request if Redis is down
            return True

    def record_request(self) -> int:
        """
        Record a new request and increment the counter.

        Returns:
            New request count after increment

        Raises:
            RateLimitExceededError: If rate limit is exceeded
        """
        if not self.redis_client:
            logger.warning("Redis unavailable, cannot record request")
            return 0

        try:
            # Check limit first
            if not self.is_allowed():
                raise RateLimitExceededError(
                    f"Rate limit exceeded for '{self.scraper_name}': "
                    f"{self.get_current_count()}/{self.max_requests} requests this {self.time_window.value}"
                )

            # Increment counter
            key = self._get_redis_key()
            new_count = self.redis_client.incr(key)

            # Set expiration if this is the first request in the window
            if new_count == 1:
                ttl = self._get_ttl()
                self.redis_client.expire(key, ttl)

            logger.info(
                f"Request recorded for '{self.scraper_name}': "
                f"{new_count}/{self.max_requests} requests this {self.time_window.value}"
            )

            return new_count
        except RateLimitExceededError:
            raise
        except RedisError as e:
            logger.error(f"Error recording request in Redis: {e}")
            return 0

    def check_and_record(self) -> bool:
        """
        Check rate limit and record request in a single operation.

        This is a convenience method that combines is_allowed() and record_request().

        Returns:
            True if request was allowed and recorded, False otherwise

        Raises:
            RateLimitExceededError: If rate limit is exceeded
        """
        if not self.is_allowed():
            raise RateLimitExceededError(
                f"Rate limit exceeded for '{self.scraper_name}': "
                f"{self.get_current_count()}/{self.max_requests} requests this {self.time_window.value}"
            )

        self.record_request()
        return True

    def reset(self) -> None:
        """
        Reset the rate limit counter for the current window.

        This is useful for testing or manual resets.
        """
        if not self.redis_client:
            logger.warning("Redis unavailable, cannot reset")
            return

        try:
            key = self._get_redis_key()
            self.redis_client.delete(key)
            logger.info(f"Rate limit reset for '{self.scraper_name}'")
        except RedisError as e:
            logger.error(f"Error resetting rate limit: {e}")

    def get_status(self) -> dict:
        """
        Get current rate limit status.

        Returns:
            Dictionary with rate limit status information
        """
        current = self.get_current_count()
        remaining = self.get_remaining()

        return {
            "scraper_name": self.scraper_name,
            "time_window": self.time_window.value,
            "max_requests": self.max_requests,
            "current_count": current,
            "remaining": remaining,
            "limit_exceeded": current >= self.max_requests,
        }


# Convenience factory functions for common scrapers
def get_kiwi_rate_limiter() -> RedisRateLimiter:
    """
    Get rate limiter for Kiwi API (100 requests/month).

    Returns:
        Configured RedisRateLimiter instance
    """
    return RedisRateLimiter(
        scraper_name="kiwi", max_requests=100, time_window=TimeWindow.MONTHLY
    )


def get_ryanair_rate_limiter() -> RedisRateLimiter:
    """
    Get rate limiter for Ryanair scraper (5 requests/day).

    Returns:
        Configured RedisRateLimiter instance
    """
    return RedisRateLimiter(
        scraper_name="ryanair", max_requests=5, time_window=TimeWindow.DAILY
    )


def get_skyscanner_rate_limiter() -> RedisRateLimiter:
    """
    Get rate limiter for Skyscanner scraper (10 requests/hour).

    Returns:
        Configured RedisRateLimiter instance
    """
    return RedisRateLimiter(
        scraper_name="skyscanner", max_requests=10, time_window=TimeWindow.HOURLY
    )
