"""
Unit tests for Redis-based rate limiter.
"""

import time
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from redis.exceptions import RedisError

from app.utils.rate_limiter import (
    RedisRateLimiter,
    RateLimitExceededError,
    TimeWindow,
    get_kiwi_rate_limiter,
    get_ryanair_rate_limiter,
    get_skyscanner_rate_limiter,
)


class TestRedisRateLimiter:
    """Tests for RedisRateLimiter class."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch("app.utils.rate_limiter.redis.from_url") as mock_from_url:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_from_url.return_value = mock_client
            yield mock_client

    def test_init_with_default_settings(self, mock_redis):
        """Test initialization with default settings."""
        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        assert limiter.scraper_name == "test"
        assert limiter.max_requests == 100
        assert limiter.time_window == TimeWindow.DAILY
        mock_redis.ping.assert_called_once()

    def test_init_with_redis_connection_error(self):
        """Test initialization when Redis connection fails."""
        with patch("app.utils.rate_limiter.redis.from_url") as mock_from_url:
            mock_from_url.side_effect = RedisError("Connection failed")

            limiter = RedisRateLimiter(
                scraper_name="test",
                max_requests=100,
                time_window=TimeWindow.DAILY,
            )

            assert limiter.redis_client is None

    def test_get_redis_key_hourly(self, mock_redis):
        """Test Redis key generation for hourly window."""
        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=10,
            time_window=TimeWindow.HOURLY,
        )

        key = limiter._get_redis_key()
        now = datetime.now()
        expected_period = now.strftime("%Y-%m-%d-%H")

        assert key == f"rate_limit:test:hourly:{expected_period}"

    def test_get_redis_key_daily(self, mock_redis):
        """Test Redis key generation for daily window."""
        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        key = limiter._get_redis_key()
        now = datetime.now()
        expected_period = now.strftime("%Y-%m-%d")

        assert key == f"rate_limit:test:daily:{expected_period}"

    def test_get_redis_key_monthly(self, mock_redis):
        """Test Redis key generation for monthly window."""
        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=1000,
            time_window=TimeWindow.MONTHLY,
        )

        key = limiter._get_redis_key()
        now = datetime.now()
        expected_period = now.strftime("%Y-%m")

        assert key == f"rate_limit:test:monthly:{expected_period}"

    def test_get_ttl_hourly(self, mock_redis):
        """Test TTL calculation for hourly window."""
        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=10,
            time_window=TimeWindow.HOURLY,
        )

        ttl = limiter._get_ttl()

        # TTL should be less than or equal to 1 hour + 60 seconds buffer
        assert 0 < ttl <= 3660

    def test_get_ttl_daily(self, mock_redis):
        """Test TTL calculation for daily window."""
        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        ttl = limiter._get_ttl()

        # TTL should be less than or equal to 24 hours + 60 seconds buffer
        assert 0 < ttl <= 86400 + 60

    def test_get_ttl_monthly(self, mock_redis):
        """Test TTL calculation for monthly window."""
        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=1000,
            time_window=TimeWindow.MONTHLY,
        )

        ttl = limiter._get_ttl()

        # TTL should be positive and reasonable (max 31 days + buffer)
        assert 0 < ttl <= (31 * 86400 + 60)

    def test_get_current_count_no_requests(self, mock_redis):
        """Test getting current count when no requests made."""
        mock_redis.get.return_value = None

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        count = limiter.get_current_count()

        assert count == 0
        mock_redis.get.assert_called_once()

    def test_get_current_count_with_requests(self, mock_redis):
        """Test getting current count with existing requests."""
        mock_redis.get.return_value = "42"

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        count = limiter.get_current_count()

        assert count == 42

    def test_get_current_count_redis_error(self, mock_redis):
        """Test getting current count when Redis errors."""
        mock_redis.get.side_effect = RedisError("Redis unavailable")

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        count = limiter.get_current_count()

        assert count == 0

    def test_get_remaining_within_limit(self, mock_redis):
        """Test getting remaining requests within limit."""
        mock_redis.get.return_value = "25"

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        remaining = limiter.get_remaining()

        assert remaining == 75

    def test_get_remaining_at_limit(self, mock_redis):
        """Test getting remaining requests at limit."""
        mock_redis.get.return_value = "100"

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        remaining = limiter.get_remaining()

        assert remaining == 0

    def test_get_remaining_over_limit(self, mock_redis):
        """Test getting remaining requests over limit."""
        mock_redis.get.return_value = "150"

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        remaining = limiter.get_remaining()

        assert remaining == 0

    def test_is_allowed_within_limit(self, mock_redis):
        """Test is_allowed returns True when within limit."""
        mock_redis.get.return_value = "50"

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        assert limiter.is_allowed() is True

    def test_is_allowed_at_limit(self, mock_redis):
        """Test is_allowed returns False at limit."""
        mock_redis.get.return_value = "100"

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        assert limiter.is_allowed() is False

    def test_is_allowed_over_limit(self, mock_redis):
        """Test is_allowed returns False over limit."""
        mock_redis.get.return_value = "150"

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        assert limiter.is_allowed() is False

    def test_is_allowed_redis_unavailable(self):
        """Test is_allowed returns True when Redis is unavailable (fail open)."""
        with patch("app.utils.rate_limiter.redis.from_url") as mock_from_url:
            mock_from_url.side_effect = RedisError("Connection failed")

            limiter = RedisRateLimiter(
                scraper_name="test",
                max_requests=100,
                time_window=TimeWindow.DAILY,
            )

            # Should allow request when Redis is down (fail open)
            assert limiter.is_allowed() is True

    def test_record_request_first_request(self, mock_redis):
        """Test recording first request in window."""
        mock_redis.get.return_value = None
        mock_redis.incr.return_value = 1

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        count = limiter.record_request()

        assert count == 1
        mock_redis.incr.assert_called_once()
        mock_redis.expire.assert_called_once()

    def test_record_request_subsequent_request(self, mock_redis):
        """Test recording subsequent request."""
        mock_redis.get.return_value = "25"
        mock_redis.incr.return_value = 26

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        count = limiter.record_request()

        assert count == 26
        mock_redis.incr.assert_called_once()
        # Expire should not be called for subsequent requests
        mock_redis.expire.assert_not_called()

    def test_record_request_when_limit_exceeded(self, mock_redis):
        """Test recording request when limit is exceeded."""
        mock_redis.get.return_value = "100"

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        with pytest.raises(RateLimitExceededError) as exc_info:
            limiter.record_request()

        assert "Rate limit exceeded" in str(exc_info.value)
        mock_redis.incr.assert_not_called()

    def test_record_request_redis_error(self):
        """Test recording request when Redis errors."""
        with patch("app.utils.rate_limiter.redis.from_url") as mock_from_url:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client.get.return_value = "50"
            mock_client.incr.side_effect = RedisError("Redis error")
            mock_from_url.return_value = mock_client

            limiter = RedisRateLimiter(
                scraper_name="test",
                max_requests=100,
                time_window=TimeWindow.DAILY,
            )

            # Should not raise, just log error
            count = limiter.record_request()
            assert count == 0

    def test_check_and_record_success(self, mock_redis):
        """Test check_and_record when allowed."""
        mock_redis.get.return_value = "50"
        mock_redis.incr.return_value = 51

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        result = limiter.check_and_record()

        assert result is True
        mock_redis.incr.assert_called_once()

    def test_check_and_record_limit_exceeded(self, mock_redis):
        """Test check_and_record when limit exceeded."""
        mock_redis.get.return_value = "100"

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        with pytest.raises(RateLimitExceededError):
            limiter.check_and_record()

        mock_redis.incr.assert_not_called()

    def test_reset(self, mock_redis):
        """Test resetting rate limit counter."""
        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        limiter.reset()

        mock_redis.delete.assert_called_once()

    def test_reset_redis_unavailable(self):
        """Test resetting when Redis is unavailable."""
        with patch("app.utils.rate_limiter.redis.from_url") as mock_from_url:
            mock_from_url.side_effect = RedisError("Connection failed")

            limiter = RedisRateLimiter(
                scraper_name="test",
                max_requests=100,
                time_window=TimeWindow.DAILY,
            )

            # Should not raise
            limiter.reset()

    def test_get_status(self, mock_redis):
        """Test getting rate limit status."""
        mock_redis.get.return_value = "42"

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        status = limiter.get_status()

        assert status == {
            "scraper_name": "test",
            "time_window": "daily",
            "max_requests": 100,
            "current_count": 42,
            "remaining": 58,
            "limit_exceeded": False,
        }

    def test_get_status_at_limit(self, mock_redis):
        """Test getting status at limit."""
        mock_redis.get.return_value = "100"

        limiter = RedisRateLimiter(
            scraper_name="test",
            max_requests=100,
            time_window=TimeWindow.DAILY,
        )

        status = limiter.get_status()

        assert status["limit_exceeded"] is True
        assert status["remaining"] == 0


class TestFactoryFunctions:
    """Tests for factory functions."""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        with patch("app.utils.rate_limiter.redis.from_url") as mock_from_url:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_from_url.return_value = mock_client
            yield mock_client

    def test_get_kiwi_rate_limiter(self, mock_redis):
        """Test Kiwi rate limiter factory."""
        limiter = get_kiwi_rate_limiter()

        assert limiter.scraper_name == "kiwi"
        assert limiter.max_requests == 100
        assert limiter.time_window == TimeWindow.MONTHLY

    def test_get_ryanair_rate_limiter(self, mock_redis):
        """Test Ryanair rate limiter factory."""
        limiter = get_ryanair_rate_limiter()

        assert limiter.scraper_name == "ryanair"
        assert limiter.max_requests == 5
        assert limiter.time_window == TimeWindow.DAILY

    def test_get_skyscanner_rate_limiter(self, mock_redis):
        """Test Skyscanner rate limiter factory."""
        limiter = get_skyscanner_rate_limiter()

        assert limiter.scraper_name == "skyscanner"
        assert limiter.max_requests == 10
        assert limiter.time_window == TimeWindow.HOURLY


class TestTimeWindow:
    """Tests for TimeWindow enum."""

    def test_time_window_values(self):
        """Test TimeWindow enum values."""
        assert TimeWindow.HOURLY.value == "hourly"
        assert TimeWindow.DAILY.value == "daily"
        assert TimeWindow.MONTHLY.value == "monthly"

    def test_time_window_is_string(self):
        """Test TimeWindow inherits from str."""
        assert isinstance(TimeWindow.HOURLY, str)
        assert isinstance(TimeWindow.DAILY, str)
        assert isinstance(TimeWindow.MONTHLY, str)


class TestRateLimitExceededError:
    """Tests for RateLimitExceededError exception."""

    def test_exception_can_be_raised(self):
        """Test that exception can be raised."""
        with pytest.raises(RateLimitExceededError):
            raise RateLimitExceededError("Test error")

    def test_exception_message(self):
        """Test exception message is preserved."""
        try:
            raise RateLimitExceededError("Custom message")
        except RateLimitExceededError as e:
            assert str(e) == "Custom message"

    def test_exception_is_exception_subclass(self):
        """Test that RateLimitExceededError is an Exception."""
        assert issubclass(RateLimitExceededError, Exception)
