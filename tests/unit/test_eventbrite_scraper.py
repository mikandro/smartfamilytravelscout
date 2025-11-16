"""
Unit tests for EventBrite API scraper.

Tests event searching, categorization, price extraction, and database operations
with mocked API responses.
"""

import pytest
import httpx
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.scrapers.eventbrite_scraper import (
    EventBriteClient,
    EventBriteAPIError,
    EventBriteRateLimitError,
    EVENTBRITE_EVENTS_ENDPOINT,
)


# Mock EventBrite API Responses
MOCK_EVENT_FAMILY = {
    "id": "123456",
    "name": {"text": "Kids Christmas Workshop"},
    "description": {
        "text": "<p>Fun workshop for children ages 5-12. Learn to make holiday crafts!</p>"
    },
    "start": {"utc": "2025-12-20T10:00:00Z"},
    "end": {"utc": "2025-12-20T12:00:00Z"},
    "is_free": False,
    "url": "https://www.eventbrite.com/e/kids-christmas-workshop-123456",
    "ticket_availability": {
        "minimum_ticket_price": {
            "currency": "EUR",
            "major_value": 15,
        }
    },
}

MOCK_EVENT_PARENT_ESCAPE = {
    "id": "234567",
    "name": {"text": "Wine Tasting Evening"},
    "description": {
        "text": "<p>Adults only wine tasting event. Sample premium wines from Portugal.</p>"
    },
    "start": {"utc": "2025-12-22T19:00:00Z"},
    "end": {"utc": "2025-12-22T22:00:00Z"},
    "is_free": False,
    "url": "https://www.eventbrite.com/e/wine-tasting-234567",
    "ticket_availability": {
        "minimum_ticket_price": {
            "currency": "EUR",
            "major_value": 35,
        }
    },
}

MOCK_EVENT_CULTURAL = {
    "id": "345678",
    "name": {"text": "Museum Night: Modern Art Exhibition"},
    "description": {
        "text": "<p>Explore contemporary art from local and international artists.</p>"
    },
    "start": {"utc": "2025-12-18T18:00:00Z"},
    "end": {"utc": "2025-12-18T23:00:00Z"},
    "is_free": True,
    "url": "https://www.eventbrite.com/e/museum-night-345678",
    "ticket_availability": None,
}

MOCK_EVENT_SPORTS = {
    "id": "456789",
    "name": {"text": "City Marathon 2025"},
    "description": {
        "text": "<p>Annual marathon race through the historic city center.</p>"
    },
    "start": {"utc": "2025-12-25T08:00:00Z"},
    "end": {"utc": "2025-12-25T14:00:00Z"},
    "is_free": False,
    "url": "https://www.eventbrite.com/e/marathon-456789",
    "ticket_availability": {
        "minimum_ticket_price": {
            "currency": "EUR",
            "major_value": 55,
        }
    },
}

MOCK_EVENT_MULTIDAY = {
    "id": "567890",
    "name": {"text": "Christmas Market Festival"},
    "description": {"text": "<p>Traditional Christmas market with family activities.</p>"},
    "start": {"utc": "2025-12-20T10:00:00Z"},
    "end": {"utc": "2025-12-24T20:00:00Z"},
    "is_free": True,
    "url": "https://www.eventbrite.com/e/christmas-market-567890",
    "ticket_availability": None,
}

MOCK_API_RESPONSE = {
    "events": [
        MOCK_EVENT_FAMILY,
        MOCK_EVENT_PARENT_ESCAPE,
        MOCK_EVENT_CULTURAL,
        MOCK_EVENT_SPORTS,
        MOCK_EVENT_MULTIDAY,
    ],
    "pagination": {
        "object_count": 5,
        "page_number": 1,
        "page_size": 50,
        "page_count": 1,
        "has_more_items": False,
    },
}

MOCK_API_RESPONSE_PAGINATED_PAGE1 = {
    "events": [MOCK_EVENT_FAMILY, MOCK_EVENT_PARENT_ESCAPE],
    "pagination": {
        "object_count": 4,
        "page_number": 1,
        "page_size": 2,
        "page_count": 2,
        "has_more_items": True,
    },
}

MOCK_API_RESPONSE_PAGINATED_PAGE2 = {
    "events": [MOCK_EVENT_CULTURAL, MOCK_EVENT_SPORTS],
    "pagination": {
        "object_count": 4,
        "page_number": 2,
        "page_size": 2,
        "page_count": 2,
        "has_more_items": False,
    },
}


@pytest.fixture
def api_key():
    """Fixture providing test API key."""
    return "test_api_key_12345"


@pytest.fixture
def mock_settings(api_key):
    """Fixture to mock settings with EventBrite API key."""
    with patch("app.scrapers.eventbrite_scraper.settings") as mock:
        mock.eventbrite_api_key = api_key
        mock.scraper_timeout = 30
        yield mock


class TestEventBriteClientInitialization:
    """Test EventBrite client initialization."""

    def test_init_with_api_key(self, api_key):
        """Test initialization with explicit API key."""
        client = EventBriteClient(api_key=api_key)
        assert client.api_key == api_key
        assert client._call_count == 0

    def test_init_with_settings(self, mock_settings, api_key):
        """Test initialization using settings."""
        client = EventBriteClient()
        assert client.api_key == api_key

    def test_init_without_api_key(self):
        """Test initialization fails without API key."""
        with patch("app.scrapers.eventbrite_scraper.settings") as mock:
            mock.eventbrite_api_key = None
            with pytest.raises(ValueError, match="EventBrite API key is required"):
                EventBriteClient()


class TestEventCategorization:
    """Test event categorization logic."""

    def test_categorize_family_event(self, api_key):
        """Test family event categorization."""
        client = EventBriteClient(api_key=api_key)
        category = client.categorize_event(MOCK_EVENT_FAMILY)
        assert category == "family"

    def test_categorize_parent_escape_event(self, api_key):
        """Test parent escape event categorization."""
        client = EventBriteClient(api_key=api_key)
        category = client.categorize_event(MOCK_EVENT_PARENT_ESCAPE)
        assert category == "parent_escape"

    def test_categorize_cultural_event(self, api_key):
        """Test cultural event categorization."""
        client = EventBriteClient(api_key=api_key)
        category = client.categorize_event(MOCK_EVENT_CULTURAL)
        assert category == "cultural"

    def test_categorize_sports_event(self, api_key):
        """Test sports event categorization."""
        client = EventBriteClient(api_key=api_key)
        category = client.categorize_event(MOCK_EVENT_SPORTS)
        assert category == "sports"

    def test_categorize_event_with_keywords_in_title(self, api_key):
        """Test categorization based on title keywords."""
        client = EventBriteClient(api_key=api_key)

        event = {
            "name": {"text": "Family Fun Day"},
            "description": {"text": "Regular event"},
        }
        assert client.categorize_event(event) == "family"

    def test_categorize_event_default_cultural(self, api_key):
        """Test default categorization to cultural."""
        client = EventBriteClient(api_key=api_key)

        event = {
            "name": {"text": "Generic Event"},
            "description": {"text": "Some event description"},
        }
        assert client.categorize_event(event) == "cultural"


class TestPriceExtraction:
    """Test price range extraction."""

    def test_extract_free_event(self, api_key):
        """Test free event price extraction."""
        client = EventBriteClient(api_key=api_key)
        price_range = client._extract_price_range(MOCK_EVENT_CULTURAL)
        assert price_range == "free"

    def test_extract_under_20_price(self, api_key):
        """Test price under €20."""
        client = EventBriteClient(api_key=api_key)
        price_range = client._extract_price_range(MOCK_EVENT_FAMILY)
        assert price_range == "<€20"

    def test_extract_20_to_50_price(self, api_key):
        """Test price €20-50."""
        client = EventBriteClient(api_key=api_key)
        price_range = client._extract_price_range(MOCK_EVENT_PARENT_ESCAPE)
        assert price_range == "€20-50"

    def test_extract_over_50_price(self, api_key):
        """Test price over €50."""
        client = EventBriteClient(api_key=api_key)
        price_range = client._extract_price_range(MOCK_EVENT_SPORTS)
        assert price_range == "€50+"

    def test_extract_price_no_ticket_info(self, api_key):
        """Test price extraction when no ticket info available."""
        client = EventBriteClient(api_key=api_key)

        event = {
            "is_free": False,
            "ticket_availability": None,
        }
        price_range = client._extract_price_range(event)
        assert price_range == "free"


class TestEventParsing:
    """Test event parsing to standardized format."""

    def test_parse_family_event(self, api_key):
        """Test parsing family event."""
        client = EventBriteClient(api_key=api_key)
        parsed = client.parse_event(MOCK_EVENT_FAMILY, "Prague")

        assert parsed is not None
        assert parsed["destination_city"] == "Prague"
        assert parsed["title"] == "Kids Christmas Workshop"
        assert parsed["event_date"] == "2025-12-20"
        assert parsed["end_date"] is None  # Same day event
        assert parsed["category"] == "family"
        assert parsed["price_range"] == "<€20"
        assert parsed["source"] == "eventbrite"
        assert "eventbrite.com" in parsed["url"]
        assert parsed["ai_relevance_score"] is None

    def test_parse_multiday_event(self, api_key):
        """Test parsing multi-day event."""
        client = EventBriteClient(api_key=api_key)
        parsed = client.parse_event(MOCK_EVENT_MULTIDAY, "Lisbon")

        assert parsed is not None
        assert parsed["event_date"] == "2025-12-20"
        assert parsed["end_date"] == "2025-12-24"

    def test_parse_event_strips_html(self, api_key):
        """Test that HTML is stripped from description."""
        client = EventBriteClient(api_key=api_key)
        parsed = client.parse_event(MOCK_EVENT_FAMILY, "Prague")

        assert parsed is not None
        assert "<p>" not in parsed["description"]
        assert "</p>" not in parsed["description"]
        assert "Fun workshop for children" in parsed["description"]

    def test_parse_event_without_start_date(self, api_key):
        """Test parsing event without start date returns None."""
        client = EventBriteClient(api_key=api_key)

        event = {
            "id": "999999",
            "name": {"text": "Invalid Event"},
            "start": {},  # No utc field
        }
        parsed = client.parse_event(event, "Prague")
        assert parsed is None

    def test_parse_event_truncates_long_description(self, api_key):
        """Test that long descriptions are truncated."""
        client = EventBriteClient(api_key=api_key)

        event = MOCK_EVENT_FAMILY.copy()
        event["description"] = {"text": "A" * 2000}

        parsed = client.parse_event(event, "Prague")
        assert parsed is not None
        assert len(parsed["description"]) <= 1000
        assert parsed["description"].endswith("...")


@pytest.mark.asyncio
class TestEventSearch:
    """Test event searching functionality."""

    async def test_search_events_success(self, api_key, mock_settings):
        """Test successful event search."""
        async with EventBriteClient(api_key=api_key) as client:
            # Mock the API request
            with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_request:
                mock_request.return_value = MOCK_API_RESPONSE

                events = await client.search_events(
                    city="Prague",
                    start_date=date(2025, 12, 15),
                    end_date=date(2025, 12, 25),
                )

                assert len(events) == 5
                assert all(isinstance(e, dict) for e in events)
                assert all(e["destination_city"] == "Prague" for e in events)

                # Verify API was called
                mock_request.assert_called_once()
                # Verify the endpoint URL was called correctly
                call_args = mock_request.call_args
                assert EVENTBRITE_EVENTS_ENDPOINT in str(call_args)

    async def test_search_events_with_categories(self, api_key, mock_settings):
        """Test event search with category filter."""
        async with EventBriteClient(api_key=api_key) as client:
            with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_request:
                mock_request.return_value = MOCK_API_RESPONSE

                events = await client.search_events(
                    city="Lisbon",
                    start_date=date(2025, 12, 15),
                    end_date=date(2025, 12, 25),
                    categories=["family", "cultural"],
                )

                # Verify API was called
                mock_request.assert_called_once()
                # Events should be returned
                assert len(events) == 5

    async def test_search_events_pagination(self, api_key, mock_settings):
        """Test event search handles pagination."""
        async with EventBriteClient(api_key=api_key) as client:
            with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_request:
                # Mock two pages of results
                mock_request.side_effect = [
                    MOCK_API_RESPONSE_PAGINATED_PAGE1,
                    MOCK_API_RESPONSE_PAGINATED_PAGE2,
                ]

                events = await client.search_events(
                    city="Prague",
                    start_date=date(2025, 12, 15),
                    end_date=date(2025, 12, 25),
                    max_results=100,
                )

                # Should have fetched both pages
                assert len(events) == 4
                assert mock_request.call_count == 2

    async def test_search_events_respects_max_results(self, api_key, mock_settings):
        """Test that max_results parameter is respected."""
        async with EventBriteClient(api_key=api_key) as client:
            with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_request:
                mock_request.return_value = MOCK_API_RESPONSE

                events = await client.search_events(
                    city="Prague",
                    start_date=date(2025, 12, 15),
                    end_date=date(2025, 12, 25),
                    max_results=3,
                )

                assert len(events) == 3

    async def test_search_events_api_error(self, api_key, mock_settings):
        """Test event search handles API errors."""
        async with EventBriteClient(api_key=api_key) as client:
            with patch.object(client, "_make_request", new_callable=AsyncMock) as mock_request:
                mock_request.side_effect = EventBriteAPIError("API Error")

                events = await client.search_events(
                    city="Prague",
                    start_date=date(2025, 12, 15),
                    end_date=date(2025, 12, 25),
                )

                # Should return empty list on error
                assert events == []


@pytest.mark.asyncio
class TestRateLimiting:
    """Test rate limiting functionality."""

    async def test_track_api_calls(self, api_key, mock_settings):
        """Test API call tracking."""
        client = EventBriteClient(api_key=api_key)
        initial_count = client.get_call_count()

        # Test _track_api_call directly
        client._track_api_call()

        assert client.get_call_count() > initial_count

    async def test_rate_limit_exceeded(self, api_key, mock_settings):
        """Test rate limit exception when limit exceeded."""
        import app.scrapers.eventbrite_scraper as scraper_module

        # Mock the global counter to be at limit
        original_count = scraper_module._api_call_count
        scraper_module._api_call_count = 1000

        try:
            client = EventBriteClient(api_key=api_key)
            with pytest.raises(EventBriteRateLimitError):
                client._track_api_call()
        finally:
            # Reset counter
            scraper_module._api_call_count = original_count


@pytest.mark.asyncio
class TestDatabaseOperations:
    """Test database saving functionality."""

    async def test_save_events_to_database(self, api_key, mock_settings):
        """Test saving events to database."""
        client = EventBriteClient(api_key=api_key)

        events = [
            {
                "destination_city": "Prague",
                "title": "Test Event 1",
                "event_date": "2025-12-20",
                "end_date": None,
                "category": "family",
                "description": "Test description",
                "price_range": "free",
                "source": "eventbrite",
                "url": "https://eventbrite.com/test",
                "ai_relevance_score": None,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

        # Mock database session
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_session.commit = AsyncMock()

        saved_count = await client.save_to_database(events, db=mock_session)

        # Should have tried to add the event
        assert saved_count == 1
        assert mock_session.add.called
        assert mock_session.commit.called

    async def test_save_empty_events_list(self, api_key):
        """Test saving empty events list."""
        client = EventBriteClient(api_key=api_key)

        saved_count = await client.save_to_database([])
        assert saved_count == 0

    async def test_save_events_skips_duplicates(self, api_key):
        """Test that duplicate events are skipped."""
        client = EventBriteClient(api_key=api_key)

        events = [
            {
                "destination_city": "Prague",
                "title": "Test Event",
                "event_date": "2025-12-20",
                "end_date": None,
                "category": "family",
                "description": "Test",
                "price_range": "free",
                "source": "eventbrite",
                "url": "https://eventbrite.com/test",
                "ai_relevance_score": None,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

        # Mock finding existing event
        existing_event = MagicMock()
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_event))
        )
        mock_session.commit = AsyncMock()

        saved_count = await client.save_to_database(events, db=mock_session)

        # Should not have added duplicate
        assert saved_count == 0
        assert not mock_session.add.called


@pytest.mark.asyncio
class TestContextManager:
    """Test async context manager functionality."""

    async def test_context_manager_creates_session(self, api_key, mock_settings):
        """Test context manager creates HTTP session."""
        async with EventBriteClient(api_key=api_key) as client:
            assert client.session is not None
            assert isinstance(client.session, httpx.AsyncClient)

    async def test_context_manager_closes_session(self, api_key, mock_settings):
        """Test context manager closes HTTP session."""
        client = EventBriteClient(api_key=api_key)

        async with client as c:
            session = c.session
            assert not session.is_closed

        # Session should be closed after exiting context
        assert session.is_closed
