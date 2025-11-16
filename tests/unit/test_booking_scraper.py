"""
Unit tests for Booking.com scraper.

Tests the BookingClient class with mocked Playwright pages to verify
property extraction, filtering, and database operations.
"""

from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.booking_scraper import BookingClient


@pytest.fixture
def mock_element():
    """Create a mock Playwright element."""

    def _create_element(text="", attributes=None, inner_html=""):
        elem = AsyncMock()
        elem.inner_text = AsyncMock(return_value=text)
        elem.inner_html = AsyncMock(return_value=inner_html)
        elem.get_attribute = AsyncMock(
            side_effect=lambda attr: (attributes or {}).get(attr)
        )
        elem.query_selector = AsyncMock(return_value=None)
        elem.query_selector_all = AsyncMock(return_value=[])
        return elem

    return _create_element


@pytest.fixture
def mock_property_card(mock_element):
    """Create a mock property card element with typical Booking.com data."""

    async def _create_card(
        name="Family Apartment Central Lisbon",
        price=80.0,
        rating=8.5,
        review_count=234,
        bedrooms=2,
        has_kitchen=True,
        property_type="apartment",
    ):
        card = mock_element()

        # Card text includes all information
        card_text = f"""
        {name}
        {property_type.title()}
        {bedrooms} bedroom apartment
        {'Kitchen' if has_kitchen else ''}
        {'Kids club' if property_type == 'hotel' else ''}
        Scored {rating}
        {review_count} reviews
        €{price}
        """
        card.inner_text = AsyncMock(return_value=card_text)

        # Name element
        name_elem = mock_element(text=name)
        card.query_selector = AsyncMock(
            side_effect=lambda selector: {
                "[data-testid='title'], .sr-hotel__name, h3, h2": name_elem,
                "a[data-testid='title-link'], a.hotel_name_link": mock_element(
                    attributes={"href": "/hotel/test-property.html"}
                ),
                "[data-testid='price-and-discounted-price']": mock_element(
                    text=f"€{price}"
                ),
                "[data-testid='review-score'] [aria-label]": mock_element(
                    attributes={"aria-label": f"Scored {rating}"}
                ),
                "[data-testid='review-score'] + div": mock_element(
                    text=f"{review_count} reviews"
                ),
                "img[data-testid='image'], img": mock_element(
                    attributes={"src": "https://example.com/image.jpg"}
                ),
            }.get(selector)
        )

        return card

    return _create_card


@pytest.fixture
def mock_page(mock_element):
    """Create a mock Playwright page."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.click = AsyncMock()
    page.screenshot = AsyncMock()
    page.close = AsyncMock()
    page.evaluate = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)
    page.query_selector_all = AsyncMock(return_value=[])
    return page


class TestBookingClient:
    """Test suite for BookingClient class."""

    def test_init(self):
        """Test BookingClient initialization."""
        client = BookingClient(headless=False, rate_limit_seconds=3.0)

        assert client.headless is False
        assert client.rate_limit_seconds == 3.0
        assert client.screenshots_dir.exists()
        assert client.browser is None

    def test_build_search_url(self):
        """Test search URL construction."""
        client = BookingClient()

        url = client._build_search_url(
            city="Lisbon",
            check_in=date(2025, 12, 20),
            check_out=date(2025, 12, 27),
            adults=2,
            children_ages=[3, 6],
            no_rooms=1,
        )

        assert "booking.com/searchresults.html" in url
        assert "ss=Lisbon" in url
        assert "checkin=2025-12-20" in url
        assert "checkout=2025-12-27" in url
        assert "group_adults=2" in url
        assert "group_children=2" in url
        assert "age=3" in url
        assert "age=6" in url
        assert "no_rooms=1" in url

    def test_build_search_url_default_children(self):
        """Test search URL with default children ages."""
        client = BookingClient()

        url = client._build_search_url(
            city="Barcelona",
            check_in=date(2025, 6, 1),
            check_out=date(2025, 6, 8),
        )

        assert "age=3" in url
        assert "age=6" in url

    @pytest.mark.asyncio
    async def test_handle_cookie_consent(self, mock_page):
        """Test cookie consent handling."""
        client = BookingClient()

        # Simulate accept button exists
        accept_btn = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(return_value=accept_btn)

        await client._handle_cookie_consent(mock_page)

        mock_page.click.assert_called()

    @pytest.mark.asyncio
    async def test_handle_cookie_consent_no_banner(self, mock_page):
        """Test cookie consent when no banner appears."""
        client = BookingClient()

        # Simulate no banner (timeout)
        mock_page.wait_for_selector = AsyncMock(
            side_effect=Exception("Timeout")
        )

        # Should not raise exception
        await client._handle_cookie_consent(mock_page)

    @pytest.mark.asyncio
    async def test_wait_for_results_success(self, mock_page):
        """Test waiting for search results successfully."""
        client = BookingClient()

        result = await client._wait_for_results(mock_page)

        assert result is True
        mock_page.wait_for_selector.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_price(self, mock_element):
        """Test price extraction from property card."""
        client = BookingClient()

        # Test various price formats
        test_cases = [
            ("€80", 80.0),
            ("€150.50", 150.5),
            ("€1,200", 1200.0),
            ("US$100", 100.0),
        ]

        for price_text, expected in test_cases:
            card = mock_element()
            price_elem = mock_element(text=price_text)
            card.query_selector = AsyncMock(return_value=price_elem)

            price = await client._extract_price(card)
            assert price == expected

    @pytest.mark.asyncio
    async def test_extract_rating(self, mock_element):
        """Test rating extraction from property card."""
        client = BookingClient()

        card = mock_element()
        rating_elem = mock_element(
            attributes={"aria-label": "Scored 8.5"},
            text="8.5"
        )
        card.query_selector = AsyncMock(return_value=rating_elem)

        rating = await client._extract_rating(card)
        assert rating == 8.5

    @pytest.mark.asyncio
    async def test_extract_review_count(self, mock_element):
        """Test review count extraction from property card."""
        client = BookingClient()

        card = mock_element()
        review_elem = mock_element(text="234 reviews")
        card.query_selector = AsyncMock(return_value=review_elem)

        review_count = await client._extract_review_count(card)
        assert review_count == 234

    @pytest.mark.asyncio
    async def test_extract_property_type_apartment(self, mock_element):
        """Test property type detection for apartments."""
        client = BookingClient()

        card = mock_element(text="Lovely 2-bedroom apartment in city center")
        property_type = await client._extract_property_type(
            card, "Family Apartment"
        )

        assert property_type == "apartment"

    @pytest.mark.asyncio
    async def test_extract_property_type_hotel(self, mock_element):
        """Test property type detection for hotels."""
        client = BookingClient()

        card = mock_element(text="Luxury hotel with family rooms")
        property_type = await client._extract_property_type(
            card, "Grand Hotel"
        )

        assert property_type == "hotel"

    @pytest.mark.asyncio
    async def test_extract_bedrooms(self, mock_element):
        """Test bedroom count extraction."""
        client = BookingClient()

        test_cases = [
            ("2 bedroom apartment", 2),
            ("3-bedroom flat", 3),
            ("1 bed apartment", 1),
            ("Family room", 2),
            ("Standard room", None),
        ]

        for text, expected in test_cases:
            card = mock_element(text=text)
            bedrooms = await client._extract_bedrooms(card)
            assert bedrooms == expected

    @pytest.mark.asyncio
    async def test_extract_amenities_kitchen(self, mock_element):
        """Test amenity extraction for kitchen."""
        client = BookingClient()

        card = mock_element(text="Apartment with full kitchen and cooking facilities")
        amenities = await client.extract_amenities(card)

        assert amenities["has_kitchen"] is True

    @pytest.mark.asyncio
    async def test_extract_amenities_kids_club(self, mock_element):
        """Test amenity extraction for kids club."""
        client = BookingClient()

        card = mock_element(text="Hotel with kids club and playground")
        amenities = await client.extract_amenities(card)

        assert amenities["has_kids_club"] is True

    @pytest.mark.asyncio
    async def test_parse_single_property(self, mock_property_card, mock_page):
        """Test parsing a complete property card."""
        client = BookingClient()

        card = await mock_property_card(
            name="Family Apartment Lisbon",
            price=95.0,
            rating=8.7,
            review_count=156,
            bedrooms=2,
            has_kitchen=True,
        )

        property_data = await client._parse_single_property(card, mock_page)

        assert property_data is not None
        assert property_data["name"] == "Family Apartment Lisbon"
        assert property_data["price_per_night"] == 95.0
        assert property_data["rating"] == 8.7
        assert property_data["review_count"] == 156
        assert property_data["bedrooms"] == 2
        assert property_data["has_kitchen"] is True
        assert property_data["type"] == "apartment"
        assert "booking.com" in property_data["url"]

    def test_filter_family_friendly(self):
        """Test filtering properties for family-friendly options."""
        client = BookingClient()

        properties = [
            {
                "name": "Family Apartment",
                "price_per_night": 80.0,
                "rating": 8.5,
                "bedrooms": 2,
                "type": "apartment",
                "has_kitchen": True,
            },
            {
                "name": "Expensive Hotel",
                "price_per_night": 200.0,  # Too expensive
                "rating": 9.0,
                "bedrooms": 2,
                "type": "hotel",
                "has_kitchen": False,
            },
            {
                "name": "Low Rated Apartment",
                "price_per_night": 60.0,
                "rating": 6.5,  # Too low rating
                "bedrooms": 2,
                "type": "apartment",
                "has_kitchen": True,
            },
            {
                "name": "Small Studio",
                "price_per_night": 70.0,
                "rating": 8.0,
                "bedrooms": 1,  # Not enough bedrooms
                "type": "apartment",
                "has_kitchen": True,
            },
            {
                "name": "Good Apartment",
                "price_per_night": 120.0,
                "rating": 8.8,
                "bedrooms": 3,
                "type": "apartment",
                "has_kitchen": True,
            },
        ]

        filtered = client.filter_family_friendly(
            properties,
            min_bedrooms=2,
            max_price=150.0,
            min_rating=7.5,
        )

        # Should keep only Family Apartment and Good Apartment
        assert len(filtered) == 2
        assert all(p["family_friendly"] for p in filtered)
        assert filtered[0]["name"] == "Family Apartment"
        assert filtered[1]["name"] == "Good Apartment"

    def test_filter_family_friendly_no_price(self):
        """Test filtering skips properties without price."""
        client = BookingClient()

        properties = [
            {
                "name": "No Price Property",
                "price_per_night": None,
                "rating": 9.0,
                "bedrooms": 2,
            }
        ]

        filtered = client.filter_family_friendly(properties)
        assert len(filtered) == 0

    @pytest.mark.asyncio
    async def test_parse_property_cards(self, mock_page, mock_property_card):
        """Test parsing multiple property cards."""
        client = BookingClient()

        # Create mock cards
        cards = [
            await mock_property_card(name=f"Property {i}", price=80.0 + i * 10)
            for i in range(5)
        ]

        mock_page.query_selector_all = AsyncMock(return_value=cards)

        properties = await client.parse_property_cards(mock_page, limit=3)

        # Should only get 3 properties due to limit
        assert len(properties) == 3
        assert properties[0]["name"] == "Property 0"
        assert properties[0]["price_per_night"] == 80.0

    @pytest.mark.asyncio
    async def test_save_to_database(self):
        """Test saving properties to database."""
        client = BookingClient()

        properties = [
            {
                "destination_city": "Lisbon",
                "name": "Test Apartment",
                "type": "apartment",
                "bedrooms": 2,
                "price_per_night": 80.0,
                "family_friendly": True,
                "has_kitchen": True,
                "has_kids_club": False,
                "rating": 8.5,
                "review_count": 100,
                "source": "booking",
                "url": "https://booking.com/test",
                "image_url": "https://example.com/image.jpg",
                "scraped_at": datetime.now(),
            }
        ]

        # Mock database session
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        saved_count = await client.save_to_database(properties, session=mock_session)

        assert saved_count == 1
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_to_database_with_string_date(self):
        """Test saving properties with ISO format scraped_at."""
        client = BookingClient()

        properties = [
            {
                "destination_city": "Barcelona",
                "name": "Test Hotel",
                "type": "hotel",
                "price_per_night": 100.0,
                "family_friendly": True,
                "has_kitchen": False,
                "has_kids_club": True,
                "source": "booking",
                "scraped_at": "2025-11-15T10:00:00",
            }
        ]

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.close = AsyncMock()

        saved_count = await client.save_to_database(properties, session=mock_session)

        assert saved_count == 1

    @pytest.mark.asyncio
    async def test_save_to_database_empty_list(self):
        """Test saving empty properties list."""
        client = BookingClient()

        saved_count = await client.save_to_database([])

        assert saved_count == 0

    @pytest.mark.asyncio
    async def test_random_delay(self):
        """Test random delay functionality."""
        import time

        client = BookingClient(rate_limit_seconds=0.1)

        start = time.time()
        await client._random_delay(min_seconds=0.1)
        elapsed = time.time() - start

        # Should wait at least 0.1 seconds
        assert elapsed >= 0.1
        # Should not wait more than 10 seconds (safety check)
        assert elapsed < 10.0

    @pytest.mark.asyncio
    async def test_save_screenshot(self, mock_page, tmp_path):
        """Test screenshot saving."""
        client = BookingClient(screenshots_dir=tmp_path)

        await client._save_screenshot(mock_page, "test")

        mock_page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test BookingClient as async context manager."""
        with patch.object(BookingClient, "start", new_callable=AsyncMock):
            with patch.object(BookingClient, "close", new_callable=AsyncMock):
                async with BookingClient() as client:
                    assert client is not None


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_search_booking(self):
        """Test search_booking convenience function."""
        from app.scrapers.booking_scraper import search_booking

        with patch.object(BookingClient, "start", new_callable=AsyncMock):
            with patch.object(BookingClient, "close", new_callable=AsyncMock):
                with patch.object(
                    BookingClient,
                    "search",
                    new_callable=AsyncMock,
                    return_value=[
                        {
                            "name": "Test",
                            "price_per_night": 80.0,
                            "rating": 8.5,
                            "bedrooms": 2,
                            "type": "apartment",
                            "has_kitchen": True,
                        }
                    ],
                ):
                    with patch.object(
                        BookingClient,
                        "save_to_database",
                        new_callable=AsyncMock,
                        return_value=1,
                    ):
                        properties = await search_booking(
                            "Lisbon",
                            date(2025, 12, 20),
                            date(2025, 12, 27),
                            save_to_db=True,
                        )

                        assert len(properties) > 0
