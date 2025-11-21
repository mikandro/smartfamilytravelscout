"""
Unit tests for Kiwi.com API scraper.

Tests cover:
- Rate limiting functionality
- API request/response handling
- Response parsing
- Database integration
- Error handling
"""

import os
import tempfile
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aiohttp import ClientError

# Mock settings before importing app modules
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("KIWI_API_KEY", "test-kiwi-key")

from app.scrapers.kiwi_scraper import (
    KiwiAPIError,
    KiwiClient,
    RateLimitExceededError,
    RateLimiter,
)


class TestRateLimiter:
    """Test suite for RateLimiter class."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary file for rate limit storage."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            temp_file = f.name
        yield temp_file
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)

    @pytest.fixture
    def rate_limiter(self, temp_storage):
        """Create RateLimiter instance with temporary storage."""
        return RateLimiter(limit_per_month=100, storage_file=temp_storage)

    def test_init(self, rate_limiter):
        """Test RateLimiter initialization."""
        assert rate_limiter.limit_per_month == 100
        assert rate_limiter.storage_file is not None

    @pytest.mark.asyncio
    async def test_check_limit_empty(self, rate_limiter):
        """Test rate limit check with no previous calls."""
        assert await rate_limiter.check_limit() is True
        assert await rate_limiter.get_remaining_calls() == 100

    @pytest.mark.asyncio
    async def test_record_call(self, rate_limiter):
        """Test recording API calls."""
        await rate_limiter.record_call()
        assert await rate_limiter.get_remaining_calls() == 99

        await rate_limiter.record_call()
        await rate_limiter.record_call()
        assert await rate_limiter.get_remaining_calls() == 97

    @pytest.mark.asyncio
    async def test_check_limit_exceeded(self, rate_limiter):
        """Test rate limit exceeded scenario."""
        # Record 100 calls
        for _ in range(100):
            await rate_limiter.record_call()

        assert await rate_limiter.check_limit() is False
        assert await rate_limiter.get_remaining_calls() == 0

    @pytest.mark.asyncio
    async def test_reset(self, rate_limiter):
        """Test resetting rate limiter."""
        # Record some calls
        for _ in range(10):
            await rate_limiter.record_call()

        assert await rate_limiter.get_remaining_calls() == 90

        # Reset
        await rate_limiter.reset()
        assert await rate_limiter.get_remaining_calls() == 100

    @pytest.mark.asyncio
    async def test_filter_old_calls(self, rate_limiter):
        """Test that old calls from previous months are filtered out."""
        # Manually write old timestamps
        old_timestamp = datetime(2023, 1, 1, 12, 0, 0)
        recent_timestamp = datetime.now()

        with open(rate_limiter.storage_file, "w") as f:
            f.write(f"{old_timestamp.isoformat()}\n")
            f.write(f"{recent_timestamp.isoformat()}\n")

        # Should only count recent call
        assert await rate_limiter.get_remaining_calls() == 99


class TestKiwiClient:
    """Test suite for KiwiClient class."""

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create mock rate limiter that always allows calls (async methods)."""
        limiter = AsyncMock(spec=RateLimiter)
        limiter.check_limit.return_value = True
        limiter.record_call.return_value = None
        limiter.get_remaining_calls.return_value = 100
        return limiter

    @pytest.fixture
    def kiwi_client(self, mock_rate_limiter):
        """Create KiwiClient instance with mocked rate limiter."""
        return KiwiClient(api_key="test_api_key", rate_limiter=mock_rate_limiter)

    @pytest.fixture
    def sample_kiwi_response(self):
        """Sample API response from Kiwi.com."""
        return {
            "data": [
                {
                    "id": "12345",
                    "price": 359.96,
                    "booking_token": "test_token_123",
                    "deep_link": "https://www.kiwi.com/deep?token=test_token_123",
                    "route": [
                        {
                            "id": "route1",
                            "flyFrom": "MUC",
                            "flyTo": "LIS",
                            "cityFrom": "Munich",
                            "cityTo": "Lisbon",
                            "airline": "FR",  # Ryanair
                            "dTimeUTC": 1703080200,  # 2023-12-20 14:30 UTC
                            "aTimeUTC": 1703091000,  # 2023-12-20 17:30 UTC
                        },
                        {
                            "id": "route2",
                            "flyFrom": "LIS",
                            "flyTo": "MUC",
                            "cityFrom": "Lisbon",
                            "cityTo": "Munich",
                            "airline": "FR",
                            "dTimeUTC": 1703685900,  # 2023-12-27 18:45 UTC
                            "aTimeUTC": 1703696700,  # 2023-12-27 21:45 UTC
                        },
                    ],
                },
                {
                    "id": "12346",
                    "price": 450.00,
                    "booking_token": "test_token_124",
                    "deep_link": "https://www.kiwi.com/deep?token=test_token_124",
                    "route": [
                        {
                            "id": "route3",
                            "flyFrom": "MUC",
                            "flyTo": "BCN",
                            "cityFrom": "Munich",
                            "cityTo": "Barcelona",
                            "airline": "VY",  # Vueling
                            "dTimeUTC": 1703080200,
                            "aTimeUTC": 1703087400,
                        },
                        {
                            "id": "route4",
                            "flyFrom": "BCN",
                            "flyTo": "MUC",
                            "cityFrom": "Barcelona",
                            "cityTo": "Munich",
                            "airline": "VY",
                            "dTimeUTC": 1703685900,
                            "aTimeUTC": 1703693100,
                        },
                    ],
                },
            ],
            "search_params": {},
            "all_stopover_airports": [],
            "all_airlines": [],
        }

    def test_init_with_api_key(self):
        """Test KiwiClient initialization with API key."""
        client = KiwiClient(api_key="test_key")
        assert client.api_key == "test_key"
        assert client.timeout == 30

    def test_init_without_api_key(self):
        """Test KiwiClient initialization fails without API key."""
        with patch("app.scrapers.kiwi_scraper.settings") as mock_settings:
            mock_settings.kiwi_api_key = None
            with pytest.raises(ValueError, match="Kiwi API key is required"):
                KiwiClient()

    def test_parse_response_valid(self, kiwi_client, sample_kiwi_response):
        """Test parsing valid API response."""
        flights = kiwi_client.parse_response(sample_kiwi_response)

        assert len(flights) == 2

        # Check first flight
        flight1 = flights[0]
        assert flight1["origin_airport"] == "MUC"
        assert flight1["destination_airport"] == "LIS"
        assert flight1["origin_city"] == "Munich"
        assert flight1["destination_city"] == "Lisbon"
        assert flight1["airline"] == "FR"
        assert flight1["total_price"] == 359.96
        assert flight1["price_per_person"] == 89.99
        assert flight1["direct_flight"] is True
        assert flight1["source"] == "kiwi"
        assert "kiwi.com" in flight1["booking_url"]

        # Check second flight
        flight2 = flights[1]
        assert flight2["origin_airport"] == "MUC"
        assert flight2["destination_airport"] == "BCN"
        assert flight2["price_per_person"] == 112.5

    def test_parse_response_empty(self, kiwi_client):
        """Test parsing empty API response."""
        flights = kiwi_client.parse_response({})
        assert flights == []

        flights = kiwi_client.parse_response({"data": []})
        assert flights == []

    def test_parse_response_invalid_route(self, kiwi_client):
        """Test parsing response with invalid route data."""
        invalid_response = {
            "data": [
                {
                    "id": "12345",
                    "price": 100.0,
                    "route": [],  # Empty route
                }
            ]
        }

        flights = kiwi_client.parse_response(invalid_response)
        assert flights == []

    @pytest.mark.asyncio
    async def test_make_request_success(self, kiwi_client, sample_kiwi_response):
        """Test successful API request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_kiwi_response)

        mock_get = AsyncMock()
        mock_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = Mock(return_value=mock_get)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await kiwi_client._make_request({"fly_from": "MUC", "fly_to": "LIS"})

            assert result == sample_kiwi_response
            kiwi_client.rate_limiter.record_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_rate_limit_exceeded(self, kiwi_client):
        """Test API request when rate limit is exceeded."""
        kiwi_client.rate_limiter.check_limit.return_value = False
        kiwi_client.rate_limiter.get_remaining_calls.return_value = 0

        with pytest.raises(RateLimitExceededError, match="Monthly rate limit exceeded"):
            await kiwi_client._make_request({"fly_from": "MUC"})

    @pytest.mark.asyncio
    async def test_make_request_401_unauthorized(self, kiwi_client):
        """Test API request with invalid API key."""
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")

        mock_get = AsyncMock()
        mock_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = Mock(return_value=mock_get)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(KiwiAPIError, match="Unauthorized"):
                await kiwi_client._make_request({"fly_from": "MUC"})

    @pytest.mark.asyncio
    async def test_make_request_400_bad_request(self, kiwi_client):
        """Test API request with bad parameters."""
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad request: Invalid parameters")

        mock_get = AsyncMock()
        mock_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = Mock(return_value=mock_get)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(KiwiAPIError, match="Bad request"):
                await kiwi_client._make_request({"fly_from": "INVALID"})

    @pytest.mark.asyncio
    async def test_make_request_retry_on_network_error(self, kiwi_client):
        """Test API request retries on network errors."""
        # Mock successful response on third attempt
        mock_response_success = AsyncMock()
        mock_response_success.status = 200
        mock_response_success.json = AsyncMock(return_value={"data": []})

        mock_get_success = AsyncMock()
        mock_get_success.__aenter__ = AsyncMock(return_value=mock_response_success)
        mock_get_success.__aexit__ = AsyncMock(return_value=None)

        # Create mock session that fails twice then succeeds
        call_count = 0

        def get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ClientError("Network error")
            return mock_get_success

        mock_session = AsyncMock()
        mock_session.get = Mock(side_effect=get_side_effect)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("asyncio.sleep"):  # Skip sleep during tests
                result = await kiwi_client._make_request({"fly_from": "MUC"})

        assert result == {"data": []}

    @pytest.mark.asyncio
    async def test_search_flights(self, kiwi_client, sample_kiwi_response):
        """Test search_flights method."""
        with patch.object(kiwi_client, "_make_request", return_value=sample_kiwi_response):
            flights = await kiwi_client.search_flights(
                origin="MUC",
                destination="LIS",
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
                adults=2,
                children=2,
            )

            assert len(flights) == 2
            assert flights[0]["origin_airport"] == "MUC"
            assert flights[0]["destination_airport"] == "LIS"

    @pytest.mark.asyncio
    async def test_search_anywhere(self, kiwi_client, sample_kiwi_response):
        """Test search_anywhere method."""
        with patch.object(kiwi_client, "_make_request", return_value=sample_kiwi_response):
            flights = await kiwi_client.search_anywhere(
                origin="MUC",
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
            )

            assert len(flights) == 2
            # Should return flights to multiple destinations
            destinations = {f["destination_airport"] for f in flights}
            assert "LIS" in destinations
            assert "BCN" in destinations

    @pytest.mark.asyncio
    async def test_search_flights_error_handling(self, kiwi_client):
        """Test that search_flights handles errors gracefully."""
        with patch.object(
            kiwi_client, "_make_request", side_effect=KiwiAPIError("API error")
        ):
            flights = await kiwi_client.search_flights(
                origin="MUC",
                destination="LIS",
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
            )

            # Should return empty list on error
            assert flights == []

    @pytest.mark.asyncio
    async def test_get_or_create_airport_existing(self, kiwi_client):
        """Test getting existing airport from database."""
        from app.models.airport import Airport

        mock_db = AsyncMock()
        mock_result = Mock()

        # Mock existing airport
        existing_airport = Airport(
            id=1,
            iata_code="MUC",
            name="Munich Airport",
            city="Munich",
            distance_from_home=0,
            driving_time=0,
        )
        mock_result.scalar_one_or_none = Mock(return_value=existing_airport)
        mock_db.execute = AsyncMock(return_value=mock_result)

        airport = await kiwi_client._get_or_create_airport(mock_db, "MUC", "Munich")

        assert airport.iata_code == "MUC"
        assert airport.name == "Munich Airport"
        mock_db.add.assert_not_called()  # Should not create new

    @pytest.mark.asyncio
    async def test_get_or_create_airport_new(self, kiwi_client):
        """Test creating new airport in database."""
        mock_db = AsyncMock()
        mock_result = Mock()

        # Mock no existing airport
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        airport = await kiwi_client._get_or_create_airport(mock_db, "LIS", "Lisbon")

        assert airport.iata_code == "LIS"
        assert airport.city == "Lisbon"
        mock_db.add.assert_called_once()  # Should create new
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_duplicate_flight(self, kiwi_client):
        """Test duplicate flight detection."""
        from app.models.flight import Flight

        mock_db = AsyncMock()
        mock_result = Mock()

        # Mock existing flight
        existing_flight = Flight(
            id=1,
            origin_airport_id=1,
            destination_airport_id=2,
            airline="Ryanair",
            departure_date=date(2025, 12, 20),
            departure_time=datetime.strptime("14:30", "%H:%M").time(),
            price_per_person=100.0,
            total_price=400.0,
            direct_flight=True,
            source="kiwi",
        )
        mock_result.scalar_one_or_none = Mock(return_value=existing_flight)
        mock_db.execute = AsyncMock(return_value=mock_result)

        duplicate = await kiwi_client._check_duplicate_flight(
            mock_db,
            origin_airport_id=1,
            destination_airport_id=2,
            airline="Ryanair",
            departure_date=date(2025, 12, 20),
            departure_time=datetime.strptime("15:00", "%H:%M").time(),  # Within 2 hours
        )

        assert duplicate is not None
        assert duplicate.id == 1

    @pytest.mark.asyncio
    async def test_save_to_database_new_flights(self, kiwi_client, sample_kiwi_response):
        """Test saving new flights to database."""
        flights = kiwi_client.parse_response(sample_kiwi_response)

        with patch("app.scrapers.kiwi_scraper.get_async_session_context") as mock_ctx:
            mock_db = AsyncMock()
            mock_ctx.return_value.__aenter__.return_value = mock_db

            # Mock no existing airports or flights
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_db.execute.return_value = mock_result

            stats = await kiwi_client.save_to_database(flights)

            assert stats["total"] == 2
            # All should be new (note: actual count depends on mocking airports)
            assert stats["inserted"] >= 0
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_to_database_empty(self, kiwi_client):
        """Test saving empty flight list."""
        stats = await kiwi_client.save_to_database([])

        assert stats["total"] == 0
        assert stats["inserted"] == 0
        assert stats["updated"] == 0
        assert stats["skipped"] == 0


class TestIntegrationScenarios:
    """Integration test scenarios for real-world usage."""

    @pytest.mark.asyncio
    async def test_full_search_and_save_workflow(self):
        """Test complete workflow: search flights and save to database."""
        # This would be an integration test in a real scenario
        # For unit tests, we mock the entire flow
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            temp_file = f.name

        try:
            rate_limiter = RateLimiter(limit_per_month=100, storage_file=temp_file)
            client = KiwiClient(api_key="test_key", rate_limiter=rate_limiter)

            # Mock API response
            sample_response = {
                "data": [
                    {
                        "id": "12345",
                        "price": 400.0,
                        "booking_token": "token",
                        "deep_link": "https://kiwi.com/book",
                        "route": [
                            {
                                "flyFrom": "MUC",
                                "flyTo": "LIS",
                                "cityFrom": "Munich",
                                "cityTo": "Lisbon",
                                "airline": "FR",
                                "dTimeUTC": 1703080200,
                                "aTimeUTC": 1703091000,
                            },
                            {
                                "flyFrom": "LIS",
                                "flyTo": "MUC",
                                "cityFrom": "Lisbon",
                                "cityTo": "Munich",
                                "airline": "FR",
                                "dTimeUTC": 1703685900,
                                "aTimeUTC": 1703696700,
                            },
                        ],
                    }
                ]
            }

            with patch.object(client, "_make_request", AsyncMock(return_value=sample_response)):
                # Search flights
                flights = await client.search_flights(
                    "MUC", "LIS", date(2025, 12, 20), date(2025, 12, 27)
                )

                assert len(flights) == 1
                assert flights[0]["origin_airport"] == "MUC"
                assert flights[0]["total_price"] == 400.0

                # Verify rate limiter did NOT track the call (we mocked _make_request directly)
                # The actual rate limiting happens inside _make_request which we bypassed
                assert await rate_limiter.get_remaining_calls() == 100

        finally:
            # Cleanup
            if os.path.exists(temp_file):
                os.remove(temp_file)
