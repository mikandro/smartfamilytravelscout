"""
Unit tests for Airbnb scraper.

Tests both Apify integration and Playwright fallback with mocked responses.
"""

import os
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Set minimal required environment variables for testing
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_anthropic_key")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing")

from app.scrapers.airbnb_scraper import AirbnbClient


class TestAirbnbClient:
    """Test cases for AirbnbClient class."""

    @pytest.fixture
    def client(self):
        """Create AirbnbClient instance without Apify client."""
        # Don't provide API key so apify_client stays None
        return AirbnbClient(apify_api_key=None)

    @pytest.fixture
    def sample_apify_results(self):
        """Sample Apify actor results."""
        return [
            {
                "name": "Cozy Family Apartment in Lisbon",
                "url": "https://www.airbnb.com/rooms/12345",
                "price": {"rate": "€120"},
                "bedrooms": 2,
                "beds": 3,
                "bathrooms": 1,
                "amenities": ["Kitchen", "Wifi", "TV", "Family/kid friendly"],
                "rating": 4.8,
                "reviewsCount": 125,
                "location": {"city": "Lisbon"},
                "images": [
                    "https://example.com/image1.jpg",
                    "https://example.com/image2.jpg",
                ],
                "description": "Perfect for families with children",
            },
            {
                "name": "Spacious Home with Pool",
                "url": "https://www.airbnb.com/rooms/67890",
                "price": {"rate": 89.50},
                "bedrooms": 3,
                "beds": 4,
                "bathrooms": 2,
                "amenities": ["Kitchen", "Pool", "Garden", "Parking"],
                "rating": 4.9,
                "reviewsCount": 87,
                "location": {"city": "Lisbon"},
                "images": ["https://example.com/image3.jpg"],
            },
            {
                "name": "Small Studio - No Kitchen",
                "url": "https://www.airbnb.com/rooms/11111",
                "price": {"rate": "€45"},
                "bedrooms": 0,
                "beds": 1,
                "bathrooms": 1,
                "amenities": ["Wifi", "TV"],
                "rating": 4.5,
                "reviewsCount": 42,
                "location": {"city": "Lisbon"},
                "images": [],
            },
        ]

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        client = AirbnbClient(apify_api_key="test_key")
        assert client.apify_api_key == "test_key"
        assert client.credits_used == 0.0

    def test_init_without_api_key(self):
        """Test initialization without API key uses settings."""
        with patch("app.scrapers.airbnb_scraper.settings") as mock_settings:
            mock_settings.apify_api_key = "settings_key"
            client = AirbnbClient()
            assert client.apify_api_key == "settings_key"

    def test_build_apify_input(self, client):
        """Test building Apify actor input configuration."""
        check_in = date(2025, 12, 20)
        check_out = date(2025, 12, 27)

        input_config = client.build_apify_input(
            city="Lisbon, Portugal",
            check_in=check_in,
            check_out=check_out,
            adults=2,
            children=2,
            max_listings=20,
        )

        assert input_config["locationQuery"] == "Lisbon, Portugal"
        assert input_config["checkIn"] == "2025-12-20"
        assert input_config["checkOut"] == "2025-12-27"
        assert input_config["currency"] == "EUR"
        assert input_config["adults"] == 2
        assert input_config["children"] == 2
        assert input_config["propertyType"] == ["Entire place"]
        assert input_config["minBedrooms"] == 2
        assert input_config["amenities"] == ["Kitchen"]
        assert input_config["maxListings"] == 20
        assert input_config["includeReviews"] is False

    def test_parse_apify_results(self, client, sample_apify_results):
        """Test parsing Apify results to accommodation format."""
        accommodations = client.parse_apify_results(sample_apify_results)

        assert len(accommodations) == 3

        # Check first accommodation
        acc1 = accommodations[0]
        assert acc1["name"] == "Cozy Family Apartment in Lisbon"
        assert acc1["type"] == "apartment"
        assert acc1["destination_city"] == "Lisbon"
        assert acc1["bedrooms"] == 2
        assert acc1["price_per_night"] == 120.0
        assert acc1["family_friendly"] is True  # Has "family" in amenities
        assert acc1["has_kitchen"] is True
        assert acc1["has_kids_club"] is False
        assert acc1["rating"] == 4.8
        assert acc1["review_count"] == 125
        assert acc1["source"] == "airbnb"
        assert acc1["url"] == "https://www.airbnb.com/rooms/12345"
        assert acc1["image_url"] == "https://example.com/image1.jpg"

        # Check second accommodation
        acc2 = accommodations[1]
        assert acc2["bedrooms"] == 3
        assert acc2["price_per_night"] == 89.50
        assert acc2["has_kitchen"] is True

        # Check third accommodation (no kitchen in amenities list)
        acc3 = accommodations[2]
        assert acc3["has_kitchen"] is False
        assert acc3["bedrooms"] == 0

    def test_parse_apify_results_with_invalid_data(self, client):
        """Test parsing handles invalid data gracefully."""
        invalid_results = [
            {"name": "Valid Listing", "price": {"rate": "€100"}, "bedrooms": 2},
            {"invalid": "data"},  # Missing required fields
            {},  # Empty dict
        ]

        accommodations = client.parse_apify_results(invalid_results)

        # Should parse the valid one and skip invalid ones
        assert len(accommodations) >= 1

    def test_filter_family_suitable(self, client):
        """Test filtering for family-suitable accommodations."""
        listings = [
            {
                "name": "Perfect Family Home",
                "bedrooms": 3,
                "has_kitchen": True,
                "price_per_night": 120.0,
            },
            {
                "name": "Small Apartment",
                "bedrooms": 1,  # Too few bedrooms
                "has_kitchen": True,
                "price_per_night": 80.0,
            },
            {
                "name": "No Kitchen",
                "bedrooms": 2,
                "has_kitchen": False,  # No kitchen
                "price_per_night": 100.0,
            },
            {
                "name": "Too Expensive",
                "bedrooms": 3,
                "has_kitchen": True,
                "price_per_night": 200.0,  # Too expensive
            },
            {
                "name": "Another Good One",
                "bedrooms": 2,
                "has_kitchen": True,
                "price_per_night": 140.0,
            },
        ]

        filtered = client.filter_family_suitable(listings)

        # Should keep only 2 suitable listings
        assert len(filtered) == 2
        assert filtered[0]["name"] == "Perfect Family Home"
        assert filtered[1]["name"] == "Another Good One"

    @pytest.mark.asyncio
    async def test_search_with_apify(self, client, sample_apify_results):
        """Test searching with Apify integration."""
        # Mock Apify client methods
        mock_actor = MagicMock()
        mock_run = {
            "defaultDatasetId": "test_dataset_id",
            "stats": {"computeUnits": 0.05},
        }
        mock_actor.call.return_value = mock_run

        mock_dataset = MagicMock()
        mock_dataset.iterate_items.return_value = iter(sample_apify_results)

        client.apify_client = MagicMock()
        client.apify_client.actor.return_value = mock_actor
        client.apify_client.dataset.return_value = mock_dataset

        # Perform search
        results = await client.search(
            city="Lisbon, Portugal",
            check_in=date(2025, 12, 20),
            check_out=date(2025, 12, 27),
            adults=2,
            children=2,
            max_listings=20,
        )

        # Verify results
        assert len(results) == 3
        assert results[0]["name"] == "Cozy Family Apartment in Lisbon"

        # Verify credits were tracked
        assert client.credits_used == 0.05

        # Verify actor was called
        mock_actor.call.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_fallback_to_playwright(self, client):
        """Test fallback to Playwright when Apify fails."""
        # Disable Apify client
        client.apify_client = None

        # Mock Playwright scraping
        with patch.object(
            client, "_scrape_airbnb_direct", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = [
                {
                    "name": "Playwright Result",
                    "bedrooms": 2,
                    "price_per_night": 100.0,
                }
            ]

            results = await client.search(
                city="Barcelona",
                check_in=date(2025, 12, 20),
                check_out=date(2025, 12, 27),
            )

            # Verify Playwright was called
            mock_scrape.assert_called_once()
            assert len(results) == 1
            assert results[0]["name"] == "Playwright Result"

    def test_build_airbnb_url(self, client):
        """Test building Airbnb search URL."""
        url = client._build_airbnb_url(
            city="Lisbon, Portugal",
            check_in=date(2025, 12, 20),
            check_out=date(2025, 12, 27),
            adults=2,
            children=2,
        )

        assert "Lisbon" in url or "Lisbon,-Portugal" in url
        assert "checkin=2025-12-20" in url
        assert "checkout=2025-12-27" in url
        assert "adults=2" in url
        assert "children=2" in url
        assert "min_bedrooms=2" in url
        assert "amenities" in url

    def test_extract_price_from_text(self, client):
        """Test extracting price from various text formats."""
        assert client._extract_price_from_text("€123 per night") == 123.0
        assert client._extract_price_from_text("$99.50") == 99.50
        assert client._extract_price_from_text("150") == 150.0
        assert client._extract_price_from_text("No price") == 0.0
        assert client._extract_price_from_text("") == 0.0

    def test_extract_rating_from_text(self, client):
        """Test extracting rating from text."""
        assert client._extract_rating_from_text("4.8 (123 reviews)") == 4.8
        assert client._extract_rating_from_text("4.5") == 4.5
        assert client._extract_rating_from_text("New") is None
        assert client._extract_rating_from_text("") is None
        # Out of range rating
        result = client._extract_rating_from_text("10.5")
        # Should be None or handled appropriately

    @pytest.mark.asyncio
    async def test_save_to_database(self, client):
        """Test saving accommodations to database."""
        listings = [
            {
                "name": "Test Apartment",
                "type": "apartment",
                "destination_city": "Lisbon",
                "bedrooms": 2,
                "price_per_night": 120.0,
                "family_friendly": True,
                "has_kitchen": True,
                "has_kids_club": False,
                "rating": 4.8,
                "review_count": 100,
                "source": "airbnb",
                "url": "https://www.airbnb.com/rooms/test",
                "image_url": "https://example.com/image.jpg",
                "scraped_at": datetime.utcnow(),
            }
        ]

        # Mock database session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        saved_count = await client.save_to_database(listings, session=mock_session)

        # Verify session was used
        assert mock_session.add.called
        assert mock_session.commit.called
        assert saved_count == 1

    @pytest.mark.asyncio
    async def test_save_to_database_updates_existing(self, client):
        """Test that existing accommodations are updated instead of duplicated."""
        listings = [
            {
                "name": "Updated Name",
                "type": "apartment",
                "destination_city": "Lisbon",
                "bedrooms": 3,
                "price_per_night": 130.0,
                "family_friendly": True,
                "has_kitchen": True,
                "has_kids_club": False,
                "rating": 4.9,
                "review_count": 150,
                "source": "airbnb",
                "url": "https://www.airbnb.com/rooms/existing",
                "image_url": "https://example.com/new_image.jpg",
                "scraped_at": datetime.utcnow(),
            }
        ]

        # Mock existing accommodation
        mock_existing = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        saved_count = await client.save_to_database(listings, session=mock_session)

        # Should update, not add new
        assert not mock_session.add.called
        assert mock_session.commit.called
        assert saved_count == 0  # 0 new, 1 updated

    def test_get_credits_used(self, client):
        """Test getting Apify credits usage."""
        assert client.get_credits_used() == 0.0

        client.credits_used = 1.5
        assert client.get_credits_used() == 1.5

    @pytest.mark.asyncio
    async def test_search_with_apify_error_fallback(self, client):
        """Test that Apify errors trigger Playwright fallback."""
        # Mock Apify to raise an error
        client.apify_client = MagicMock()
        client.apify_client.actor.side_effect = Exception("Apify error")

        # Mock Playwright
        with patch.object(
            client, "_scrape_airbnb_direct", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = [{"name": "Fallback result"}]

            results = await client.search(
                city="Porto",
                check_in=date(2025, 12, 20),
                check_out=date(2025, 12, 27),
            )

            # Should fall back to Playwright
            mock_scrape.assert_called_once()
            assert len(results) == 1
            assert results[0]["name"] == "Fallback result"


class TestAirbnbClientConstants:
    """Test AirbnbClient class constants."""

    def test_constants(self):
        """Test that class constants are set correctly."""
        assert AirbnbClient.AIRBNB_ACTOR_ID == "dtrungtin/airbnb-scraper"
        assert AirbnbClient.MIN_BEDROOMS == 2
        assert AirbnbClient.MAX_PRICE_PER_NIGHT == 150.0
        assert AirbnbClient.REQUIRED_AMENITIES == ["Kitchen"]
        assert AirbnbClient.PROPERTY_TYPE == "Entire place"
