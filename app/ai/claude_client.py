"""
Claude API client with caching, cost tracking, and error handling.

This module provides a production-grade integration with Anthropic's Claude API,
featuring Redis-based caching, comprehensive cost tracking, and robust error handling.
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from anthropic import AsyncAnthropic, APIError, RateLimitError, APIConnectionError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.models.api_cost import ApiCost

logger = logging.getLogger(__name__)


class ClaudeAPIError(Exception):
    """Custom exception for Claude API errors."""

    pass


class ClaudeClient:
    """
    Claude API client with caching, cost tracking, and error handling.

    Features:
    - Redis-based response caching with configurable TTL
    - Automatic cost tracking and logging to database
    - JSON response parsing with markdown code block handling
    - Retry logic for transient failures
    - Comprehensive error handling

    Example:
        >>> client = ClaudeClient(api_key="sk-...", redis_client=redis)
        >>> response = await client.analyze(
        ...     prompt="Score this deal: {deal_details}",
        ...     data={"deal_details": "Flight to Lisbon €400"},
        ...     response_format="json"
        ... )
        >>> print(response["score"])
    """

    # Claude Sonnet 4.5 pricing (as of 2025)
    INPUT_COST_PER_MILLION = 3.0  # $3 per 1M input tokens
    OUTPUT_COST_PER_MILLION = 15.0  # $15 per 1M output tokens

    def __init__(
        self,
        api_key: str,
        redis_client: Redis,
        model: str = "claude-sonnet-4-5-20250929",
        cache_ttl: int = 86400,  # 24 hours
        db_session: Optional[AsyncSession] = None,
    ):
        """
        Initialize the Claude API client.

        Args:
            api_key: Anthropic API key
            redis_client: Redis client for caching
            model: Claude model to use (default: claude-sonnet-4-5-20250929)
            cache_ttl: Cache TTL in seconds (default: 86400 = 24 hours)
            db_session: Optional database session for cost tracking
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.redis = redis_client
        self.model = model
        self.cache_ttl = cache_ttl
        self.db_session = db_session
        self._cache_enabled = False

        # Validate Redis connection
        self._validate_redis_connection()

        logger.info(f"Initialized ClaudeClient with model: {model}")

    def _validate_redis_connection(self) -> None:
        """
        Validate Redis connection during initialization.

        If Redis is unavailable, logs a warning and disables caching.
        The client will continue to function without caching capabilities.
        """
        try:
            # Note: We can't use async ping() in __init__, so we'll mark caching
            # as enabled and let the actual cache operations handle failures
            # gracefully. The _cache_enabled flag will be checked in async methods.
            self._cache_enabled = True
            logger.info("Redis client initialized - caching enabled")
        except Exception as e:
            self._cache_enabled = False
            logger.warning(
                f"Redis connection validation skipped (sync context). "
                f"Cache operations will validate connection lazily. Error: {e}"
            )

    async def _check_redis_health(self) -> bool:
        """
        Check if Redis is healthy and available.

        Returns:
            True if Redis is available, False otherwise
        """
        if not self._cache_enabled:
            return False

        try:
            await self.redis.ping()
            return True
        except Exception as e:
            if self._cache_enabled:
                logger.warning(
                    f"Redis connection lost: {e}. Disabling cache operations."
                )
                self._cache_enabled = False
            return False

    async def analyze(
        self,
        prompt: str,
        data: Optional[Dict[str, Any]] = None,
        response_format: str = "json",
        use_cache: bool = True,
        max_tokens: int = 2048,
        operation: Optional[str] = None,
        temperature: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Send a prompt to Claude and return the parsed response.

        Args:
            prompt: The prompt template (can use {variable} placeholders)
            data: Dictionary of variables to format into the prompt
            response_format: Expected format - 'json' or 'text' (default: 'json')
            use_cache: Whether to use Redis caching (default: True)
            max_tokens: Maximum tokens in response (default: 2048)
            operation: Operation name for cost tracking (e.g., 'deal_scoring')
            temperature: Sampling temperature 0-1 (default: 1.0)

        Returns:
            Dict containing the parsed response. For JSON format, returns the
            parsed JSON object. For text format, returns {"text": "..."}. All
            responses include a "_cost" field with the API call cost in USD.

        Raises:
            ClaudeAPIError: If the API call fails or response parsing fails
        """
        try:
            # Format prompt with data
            if data:
                full_prompt = prompt.format(**data)
            else:
                full_prompt = prompt

            # Generate cache key
            cache_key = self._build_cache_key(full_prompt, response_format, max_tokens)
            prompt_hash = hashlib.sha256(full_prompt.encode()).hexdigest()

            # Check cache
            if use_cache:
                cached = await self._get_cached_response(cache_key)
                if cached:
                    logger.info(f"Cache hit for prompt hash: {prompt_hash[:16]}...")
                    # Track cache hit
                    if self.db_session:
                        await self._track_cache_hit(prompt_hash, operation)
                    return cached

            # Call Claude API with retry logic
            logger.info(
                f"Calling Claude API (model={self.model}, "
                f"max_tokens={max_tokens}, operation={operation})"
            )

            response = await self._call_api_with_retry(
                full_prompt, max_tokens, temperature
            )

            # Parse response
            response_text = response.content[0].text
            if response_format == "json":
                result = self.parse_json_response(response_text)
            else:
                result = {"text": response_text}

            # Track cost
            cost = await self.track_cost(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                operation=operation,
                prompt_hash=prompt_hash,
            )
            result["_cost"] = cost
            result["_model"] = self.model
            result["_tokens"] = {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
                "total": response.usage.input_tokens + response.usage.output_tokens,
            }

            # Cache response
            if use_cache:
                await self._cache_response(cache_key, result)

            logger.info(
                f"Claude API call successful (cost=${cost:.4f}, "
                f"tokens={result['_tokens']['total']})"
            )

            return result

        except APIError as e:
            logger.error(f"Claude API error: {e}")
            # Track failed API call
            if self.db_session:
                await self._track_error(str(e), operation)
            raise ClaudeAPIError(f"Claude API call failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error in analyze(): {e}")
            raise ClaudeAPIError(f"Unexpected error: {e}") from e

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _call_api_with_retry(
        self, prompt: str, max_tokens: int, temperature: float
    ):
        """
        Call Claude API with automatic retry logic for transient failures.

        Args:
            prompt: The formatted prompt to send
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Anthropic Message response

        Raises:
            RateLimitError: If rate limit exceeded after retries
            APIConnectionError: If connection fails after retries
            APIError: For other API errors
        """
        return await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )

    def _build_cache_key(
        self, prompt: str, response_format: str, max_tokens: int
    ) -> str:
        """
        Generate a unique cache key from prompt and parameters.

        Args:
            prompt: The full formatted prompt
            response_format: Expected response format
            max_tokens: Maximum tokens setting

        Returns:
            SHA256 hash to use as Redis cache key
        """
        # Include model, format, and max_tokens in cache key for uniqueness
        cache_input = f"{self.model}:{response_format}:{max_tokens}:{prompt}"
        cache_hash = hashlib.sha256(cache_input.encode()).hexdigest()
        return f"claude:response:{cache_hash}"

    async def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached response from Redis.

        Args:
            cache_key: Redis cache key

        Returns:
            Cached response dict or None if not found
        """
        # Check if caching is enabled and Redis is healthy
        if not await self._check_redis_health():
            return None

        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {e}. Disabling cache.")
            self._cache_enabled = False
        return None

    async def _cache_response(self, cache_key: str, response: Dict[str, Any]) -> None:
        """
        Store a response in Redis cache.

        Args:
            cache_key: Redis cache key
            response: Response dict to cache
        """
        # Check if caching is enabled and Redis is healthy
        if not await self._check_redis_health():
            return

        try:
            await self.redis.setex(
                cache_key, self.cache_ttl, json.dumps(response, default=str)
            )
            logger.debug(f"Cached response with key: {cache_key[:32]}...")
        except Exception as e:
            logger.warning(f"Cache storage failed: {e}. Disabling cache.")
            self._cache_enabled = False

    def parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from Claude's response.

        Claude often wraps JSON responses in markdown code blocks.
        This method handles various formats:
        - ```json ... ```
        - ``` ... ```
        - Plain JSON

        Args:
            response_text: Raw response text from Claude

        Returns:
            Parsed JSON as a dictionary

        Raises:
            ClaudeAPIError: If JSON parsing fails
        """
        # Handle markdown code blocks
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.rfind("```")
            json_str = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.rfind("```")
            json_str = response_text[start:end].strip()
        else:
            json_str = response_text.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text[:500]}...")
            raise ClaudeAPIError(
                f"Failed to parse JSON response: {e}. "
                f"Response: {response_text[:200]}..."
            ) from e

    async def track_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        operation: Optional[str] = None,
        prompt_hash: Optional[str] = None,
        error: Optional[str] = None,
    ) -> float:
        """
        Calculate API cost and log to database.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            operation: Operation name for tracking
            prompt_hash: Hash of the prompt
            error: Error message if API call failed

        Returns:
            Total cost in USD
        """
        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * self.INPUT_COST_PER_MILLION
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_COST_PER_MILLION
        total_cost = input_cost + output_cost

        logger.info(
            f"Claude API cost: ${total_cost:.4f} "
            f"({input_tokens} input + {output_tokens} output = "
            f"{input_tokens + output_tokens} tokens)"
        )

        # Log to database if session available
        if self.db_session:
            try:
                api_cost = ApiCost(
                    service="claude",
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=total_cost,
                    operation=operation,
                    prompt_hash=prompt_hash,
                    cache_hit=False,
                    error=error,
                )
                self.db_session.add(api_cost)
                await self.db_session.commit()
                logger.debug(f"Logged API cost to database: {api_cost}")
            except Exception as e:
                logger.error(f"Failed to log API cost to database: {e}")
                # Don't fail the request if cost logging fails
                await self.db_session.rollback()

        return total_cost

    async def _track_cache_hit(
        self, prompt_hash: str, operation: Optional[str] = None
    ) -> None:
        """Track a cache hit in the database (no tokens consumed)."""
        if self.db_session:
            try:
                api_cost = ApiCost(
                    service="claude",
                    model=self.model,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    operation=operation,
                    prompt_hash=prompt_hash,
                    cache_hit=True,
                )
                self.db_session.add(api_cost)
                await self.db_session.commit()
            except Exception as e:
                logger.warning(f"Failed to log cache hit: {e}")
                await self.db_session.rollback()

    async def _track_error(
        self, error: str, operation: Optional[str] = None
    ) -> None:
        """Track a failed API call in the database."""
        if self.db_session:
            try:
                api_cost = ApiCost(
                    service="claude",
                    model=self.model,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    operation=operation,
                    cache_hit=False,
                    error=error[:1000],  # Truncate long error messages
                )
                self.db_session.add(api_cost)
                await self.db_session.commit()
            except Exception as e:
                logger.warning(f"Failed to log API error: {e}")
                await self.db_session.rollback()

    async def clear_cache(self, pattern: str = "claude:response:*") -> int:
        """
        Clear cached responses matching a pattern.

        Args:
            pattern: Redis key pattern to match (default: all Claude responses)

        Returns:
            Number of keys deleted
        """
        # Check if caching is enabled and Redis is healthy
        if not await self._check_redis_health():
            logger.warning("Cannot clear cache: Redis is unavailable")
            return 0

        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self.redis.delete(*keys)
                logger.info(f"Cleared {deleted} cached responses")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            self._cache_enabled = False
            return 0

    async def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about cached responses.

        Returns:
            Dictionary with cache statistics including cache availability
        """
        # Check if caching is enabled and Redis is healthy
        if not await self._check_redis_health():
            return {
                "cached_responses": 0,
                "cache_ttl": self.cache_ttl,
                "cache_enabled": False,
            }

        try:
            count = 0
            async for _ in self.redis.scan_iter(match="claude:response:*"):
                count += 1

            return {
                "cached_responses": count,
                "cache_ttl": self.cache_ttl,
                "cache_enabled": True,
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            self._cache_enabled = False
            return {
                "cached_responses": 0,
                "cache_ttl": self.cache_ttl,
                "cache_enabled": False,
            }
