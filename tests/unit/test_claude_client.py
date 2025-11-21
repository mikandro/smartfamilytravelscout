"""
Unit tests for ClaudeClient.

Tests the Claude API integration with mocked API responses to avoid
actual API calls and ensure predictable testing.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from app.ai.claude_client import ClaudeClient, ClaudeAPIError


class TestClaudeClient:
    """Test suite for ClaudeClient class."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.setex = AsyncMock()
        redis.delete = AsyncMock(return_value=0)
        redis.scan_iter = AsyncMock()
        return redis

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def claude_client(self, mock_redis, mock_db_session):
        """Create ClaudeClient instance with mocked dependencies."""
        with patch("app.ai.claude_client.AsyncAnthropic"):
            return ClaudeClient(
                api_key="test-api-key",
                redis_client=mock_redis,
                db_session=mock_db_session,
            )

    @pytest.fixture
    def mock_api_response(self):
        """Create a mock Claude API response."""
        response = Mock()
        response.content = [Mock(text='{"score": 85, "rating": "excellent"}')]
        response.usage = Mock(input_tokens=100, output_tokens=50)
        return response

    def test_initialization(self, claude_client, mock_redis):
        """Test that ClaudeClient initializes correctly."""
        assert claude_client.redis == mock_redis
        assert claude_client.model == "claude-sonnet-4-5-20250929"
        assert claude_client.cache_ttl == 86400

    def test_build_cache_key(self, claude_client):
        """Test cache key generation."""
        prompt = "Test prompt"
        cache_key = claude_client._build_cache_key(prompt, "json", 2048)

        assert cache_key.startswith("claude:response:")
        assert len(cache_key) > 20  # Should be a hash

        # Same input should generate same key
        cache_key2 = claude_client._build_cache_key(prompt, "json", 2048)
        assert cache_key == cache_key2

        # Different input should generate different key
        cache_key3 = claude_client._build_cache_key("Different", "json", 2048)
        assert cache_key != cache_key3

    async def test_get_cached_response_hit(self, claude_client, mock_redis):
        """Test retrieving a cached response (cache hit)."""
        cached_data = {"score": 90, "rating": "excellent"}
        mock_redis.get.return_value = json.dumps(cached_data)

        result = await claude_client._get_cached_response("test_key")

        assert result == cached_data
        mock_redis.get.assert_called_once_with("test_key")

    async def test_get_cached_response_miss(self, claude_client, mock_redis):
        """Test retrieving from cache when not present (cache miss)."""
        mock_redis.get.return_value = None

        result = await claude_client._get_cached_response("test_key")

        assert result is None
        mock_redis.get.assert_called_once_with("test_key")

    async def test_cache_response(self, claude_client, mock_redis):
        """Test storing a response in cache."""
        response = {"score": 85, "rating": "good"}
        cache_key = "test_cache_key"

        await claude_client._cache_response(cache_key, response)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == cache_key
        assert call_args[0][1] == claude_client.cache_ttl
        # Verify JSON serialization
        assert json.loads(call_args[0][2]) == response

    def test_parse_json_response_plain(self, claude_client):
        """Test parsing plain JSON response."""
        response_text = '{"score": 85, "rating": "excellent"}'
        result = claude_client.parse_json_response(response_text)

        assert result == {"score": 85, "rating": "excellent"}

    def test_parse_json_response_markdown_json(self, claude_client):
        """Test parsing JSON wrapped in ```json markdown block."""
        response_text = """
        Here's the analysis:
        ```json
        {
          "score": 85,
          "rating": "excellent"
        }
        ```
        """
        result = claude_client.parse_json_response(response_text)

        assert result == {"score": 85, "rating": "excellent"}

    def test_parse_json_response_markdown_plain(self, claude_client):
        """Test parsing JSON wrapped in ``` markdown block."""
        response_text = """
        ```
        {"score": 90, "rating": "outstanding"}
        ```
        """
        result = claude_client.parse_json_response(response_text)

        assert result == {"score": 90, "rating": "outstanding"}

    def test_parse_json_response_invalid(self, claude_client):
        """Test parsing invalid JSON raises ClaudeAPIError."""
        response_text = "This is not valid JSON"

        with pytest.raises(ClaudeAPIError) as exc_info:
            claude_client.parse_json_response(response_text)

        assert "Failed to parse JSON response" in str(exc_info.value)

    async def test_track_cost(self, claude_client, mock_db_session):
        """Test cost calculation and database logging."""
        input_tokens = 1000
        output_tokens = 500

        cost = await claude_client.track_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            operation="test_operation",
            prompt_hash="abc123",
        )

        # Verify cost calculation
        expected_cost = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        assert cost == pytest.approx(expected_cost)

        # Verify database logging
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

        # Verify the ApiCost object
        api_cost = mock_db_session.add.call_args[0][0]
        assert api_cost.service == "claude"
        assert api_cost.model == claude_client.model
        assert api_cost.input_tokens == input_tokens
        assert api_cost.output_tokens == output_tokens
        assert api_cost.cost_usd == pytest.approx(expected_cost)
        assert api_cost.operation == "test_operation"
        assert api_cost.prompt_hash == "abc123"
        assert api_cost.cache_hit is False

    async def test_track_cache_hit(self, claude_client, mock_db_session):
        """Test tracking a cache hit."""
        await claude_client._track_cache_hit(
            prompt_hash="test_hash", operation="test_op"
        )

        # Verify database logging
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

        # Verify the ApiCost object for cache hit
        api_cost = mock_db_session.add.call_args[0][0]
        assert api_cost.cache_hit is True
        assert api_cost.input_tokens == 0
        assert api_cost.output_tokens == 0
        assert api_cost.cost_usd == 0.0

    async def test_track_error(self, claude_client, mock_db_session):
        """Test tracking an API error."""
        error_message = "API connection failed"

        await claude_client._track_error(error_message, operation="test_op")

        # Verify database logging
        mock_db_session.add.assert_called_once()

        # Verify the ApiCost object for error
        api_cost = mock_db_session.add.call_args[0][0]
        assert api_cost.error == error_message
        assert api_cost.cost_usd == 0.0

    async def test_analyze_success(self, claude_client, mock_api_response, mock_redis):
        """Test successful analyze call."""
        # Mock the API call
        claude_client._call_api_with_retry = AsyncMock(return_value=mock_api_response)

        result = await claude_client.analyze(
            prompt="Score this deal: {deal}",
            data={"deal": "Flight to Lisbon €400"},
            response_format="json",
            operation="deal_scoring",
        )

        # Verify result structure
        assert "score" in result
        assert "rating" in result
        assert "_cost" in result
        assert "_model" in result
        assert "_tokens" in result

        # Verify API was called
        claude_client._call_api_with_retry.assert_called_once()

        # Verify response was cached
        mock_redis.setex.assert_called_once()

    async def test_analyze_with_cache_hit(
        self, claude_client, mock_redis, mock_api_response
    ):
        """Test analyze with cache hit (no API call)."""
        cached_response = {
            "score": 85,
            "rating": "excellent",
            "_cost": 0.01,
            "_model": "claude-sonnet-4-5-20250929",
            "_tokens": {"input": 100, "output": 50, "total": 150},
        }
        mock_redis.get.return_value = json.dumps(cached_response)

        # Mock the API call (should not be called)
        claude_client._call_api_with_retry = AsyncMock(return_value=mock_api_response)

        result = await claude_client.analyze(
            prompt="Test prompt",
            data={},
            use_cache=True,
        )

        # Verify cached result was returned
        assert result["score"] == 85

        # Verify API was NOT called
        claude_client._call_api_with_retry.assert_not_called()

    async def test_analyze_text_format(self, claude_client, mock_redis):
        """Test analyze with text response format."""
        # Mock API response with plain text
        mock_response = Mock()
        mock_response.content = [Mock(text="This is a text response.")]
        mock_response.usage = Mock(input_tokens=50, output_tokens=25)

        claude_client._call_api_with_retry = AsyncMock(return_value=mock_response)

        result = await claude_client.analyze(
            prompt="Describe this destination",
            data={},
            response_format="text",
        )

        # Verify text format result
        assert "text" in result
        assert result["text"] == "This is a text response."
        assert "_cost" in result

    async def test_analyze_no_cache(self, claude_client, mock_redis, mock_api_response):
        """Test analyze with caching disabled."""
        claude_client._call_api_with_retry = AsyncMock(return_value=mock_api_response)

        await claude_client.analyze(
            prompt="Test",
            data={},
            use_cache=False,
        )

        # Verify cache was not checked
        mock_redis.get.assert_not_called()

        # Verify response was not cached
        mock_redis.setex.assert_not_called()

    async def test_analyze_api_error(self, claude_client):
        """Test analyze handling API errors."""
        from anthropic import APIError
        from httpx import Request

        # Create a mock request for APIError
        mock_request = Request("POST", "https://api.anthropic.com/v1/messages")

        # Mock API to raise error
        claude_client._call_api_with_retry = AsyncMock(
            side_effect=APIError("API Error", request=mock_request, body=None)
        )

        with pytest.raises(ClaudeAPIError) as exc_info:
            await claude_client.analyze(prompt="Test", data={})

        assert "Claude API call failed" in str(exc_info.value)

    async def test_clear_cache(self, claude_client, mock_redis):
        """Test clearing cached responses."""
        # Mock scan_iter to return some keys
        mock_keys = [
            b"claude:response:key1",
            b"claude:response:key2",
            b"claude:response:key3",
        ]

        async def async_gen():
            for key in mock_keys:
                yield key

        mock_redis.scan_iter = MagicMock(return_value=async_gen())
        mock_redis.delete.return_value = len(mock_keys)

        deleted = await claude_client.clear_cache()

        assert deleted == 3
        mock_redis.delete.assert_called_once_with(*mock_keys)

    async def test_get_cache_stats(self, claude_client, mock_redis):
        """Test getting cache statistics."""
        # Mock scan_iter to return some keys
        async def async_gen():
            for _ in range(5):
                yield b"claude:response:key"

        mock_redis.scan_iter = MagicMock(return_value=async_gen())

        stats = await claude_client.get_cache_stats()

        assert stats["cached_responses"] == 5
        assert stats["cache_ttl"] == claude_client.cache_ttl

    def test_pricing_constants(self):
        """Test that pricing constants are set correctly."""
        assert ClaudeClient.INPUT_COST_PER_MILLION == 3.0
        assert ClaudeClient.OUTPUT_COST_PER_MILLION == 15.0

    async def test_analyze_with_formatting(self, claude_client, mock_api_response):
        """Test analyze with prompt formatting."""
        claude_client._call_api_with_retry = AsyncMock(return_value=mock_api_response)

        await claude_client.analyze(
            prompt="Analyze {destination} for {travelers} travelers",
            data={"destination": "Paris", "travelers": 4},
        )

        # Verify prompt was formatted correctly
        call_args = claude_client._call_api_with_retry.call_args[0]
        formatted_prompt = call_args[0]
        assert "Paris" in formatted_prompt
        assert "4" in formatted_prompt
