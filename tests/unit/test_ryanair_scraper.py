"""
Unit tests for RyanairScraper.

These tests use mocked Playwright pages to avoid hitting the live Ryanair site.
"""

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.scrapers.ryanair_scraper import CaptchaDetected, RateLimitExceeded, RyanairScraper


class TestRyanairScraper:
    """Test suite for RyanairScraper."""

    @pytest.fixture
    def scraper(self):
        """Create a scraper instance for testing."""
        return RyanairScraper(log_dir="/tmp/test_ryanair_logs")

    @pytest.fixture
    def mock_page(self):
        """Create a mock Playwright page."""
        page = AsyncMock()
        page.goto = AsyncMock()
        page.wait_for_selector = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.query_selector = AsyncMock()
        page.query_selector_all = AsyncMock(return_value=[])
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.add_init_script = AsyncMock()
        page.evaluate = AsyncMock()
        page.close = AsyncMock()

        return page

    @pytest.fixture
    def mock_browser(self, mock_page):
        """Create a mock Playwright browser."""
        context = AsyncMock()
        context.new_page = AsyncMock(return_value=mock_page)
        context.close = AsyncMock()

        browser = AsyncMock()
        browser.new_context = AsyncMock(return_value=context)
        browser.close = AsyncMock()

        return browser

    @pytest.fixture
    def mock_playwright(self, mock_browser):
        """Create a mock Playwright instance."""
        playwright = MagicMock()
        playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        playwright.start = AsyncMock(return_value=playwright)

        return playwright

    async def test_init(self, scraper):
        """Test scraper initialization."""
        assert scraper.BASE_URL == "https://www.ryanair.com"
        assert scraper.MAX_DAILY_SEARCHES == 5
        assert scraper.log_dir.exists()

    async def test_rate_limit_check_new_day(self, scraper, tmp_path):
        """Test rate limit check on a new day."""
        # Create temp rate limit file
        rate_file = tmp_path / "rate_limit.json"
        scraper.RATE_LIMIT_FILE = str(rate_file)

        # Should not raise on first check
        await scraper._check_rate_limit()

        # Check that file was created
        assert rate_file.exists()

        # Check content
        with open(rate_file, "r") as f:
            data = json.load(f)

        assert data["date"] == str(date.today())
        assert data["count"] == 1

    async def test_rate_limit_exceeded(self, scraper, tmp_path):
        """Test rate limit exceeded raises exception."""
        # Create temp rate limit file with max count
        rate_file = tmp_path / "rate_limit.json"
        scraper.RATE_LIMIT_FILE = str(rate_file)

        # Pre-populate with max searches
        with open(rate_file, "w") as f:
            json.dump({"date": str(date.today()), "count": 5}, f)

        # Should raise RateLimitExceeded
        with pytest.raises(RateLimitExceeded):
            await scraper._check_rate_limit()

    async def test_rate_limit_reset_new_day(self, scraper, tmp_path):
        """Test rate limit resets on new day."""
        # Create temp rate limit file with yesterday's date
        rate_file = tmp_path / "rate_limit.json"
        scraper.RATE_LIMIT_FILE = str(rate_file)

        # Pre-populate with yesterday
        yesterday = str(date.today().replace(day=1))  # Use day 1 as "yesterday"
        with open(rate_file, "w") as f:
            json.dump({"date": yesterday, "count": 5}, f)

        # Should not raise (new day resets counter)
        await scraper._check_rate_limit()

        # Check that count was reset
        with open(rate_file, "r") as f:
            data = json.load(f)

        assert data["date"] == str(date.today())
        assert data["count"] == 1

    async def test_detect_captcha_by_selector(self, scraper, mock_page):
        """Test CAPTCHA detection by selector."""
        scraper.page = mock_page

        # Mock CAPTCHA element found
        captcha_element = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=captcha_element)

        # Should detect CAPTCHA
        assert await scraper._detect_captcha() is True

    async def test_detect_captcha_by_content(self, scraper, mock_page):
        """Test CAPTCHA detection by page content."""
        scraper.page = mock_page

        # No CAPTCHA element, but content has CAPTCHA text
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.content = AsyncMock(return_value="Please verify you are human")

        # Should detect CAPTCHA
        assert await scraper._detect_captcha() is True

    async def test_no_captcha_detected(self, scraper, mock_page):
        """Test no CAPTCHA detected."""
        scraper.page = mock_page

        # No CAPTCHA element or content
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.content = AsyncMock(return_value="<html><body>Normal page</body></html>")

        # Should not detect CAPTCHA
        assert await scraper._detect_captcha() is False

    async def test_human_delay(self, scraper):
        """Test human-like delay."""
        import time

        start = time.time()
        await scraper._human_delay(0.1, 0.2)
        elapsed = time.time() - start

        # Should take between 0.1 and 0.2 seconds
        assert 0.1 <= elapsed <= 0.3  # Small margin for execution time

    async def test_type_like_human(self, scraper, mock_page):
        """Test human-like typing."""
        scraper.page = mock_page

        # Mock element
        element = AsyncMock()
        element.click = AsyncMock()
        element.type = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(return_value=element)

        # Type text
        await scraper._type_like_human("input", "test")

        # Should have clicked and typed
        element.click.assert_called_once()
        assert element.type.call_count == 4  # 4 characters

    async def test_scroll_randomly(self, scraper, mock_page):
        """Test random scrolling."""
        scraper.page = mock_page

        await scraper._scroll_randomly()

        # Should have called evaluate (for scrolling)
        assert mock_page.evaluate.called

    async def test_handle_popups_cookie_consent(self, scraper, mock_page):
        """Test handling cookie consent popup."""
        # Mock cookie button
        cookie_button = AsyncMock()
        cookie_button.is_visible = AsyncMock(return_value=True)
        cookie_button.click = AsyncMock()

        mock_page.query_selector = AsyncMock(return_value=cookie_button)

        await scraper.handle_popups(mock_page)

        # Should have clicked cookie button
        cookie_button.click.assert_called()

    async def test_parse_time_valid(self, scraper):
        """Test time parsing with valid input."""
        assert scraper._parse_time("08:30") == "08:30"
        assert scraper._parse_time("8:30") == "08:30"
        assert scraper._parse_time("8:30 PM") == "20:30"
        assert scraper._parse_time("12:00 AM") == "00:00"
        assert scraper._parse_time("12:00 PM") == "12:00"

    async def test_parse_time_invalid(self, scraper):
        """Test time parsing with invalid input."""
        assert scraper._parse_time("invalid") is None
        assert scraper._parse_time("") is None
        assert scraper._parse_time("25:00") is None

    async def test_construct_booking_url(self, scraper):
        """Test booking URL construction."""
        url = scraper._construct_booking_url(
            origin="FMM",
            destination="BCN",
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        # Check URL components
        assert "FMM" in url
        assert "BCN" in url
        assert "2025-12-20" in url
        assert "2025-12-27" in url
        assert "adults=2" in url
        assert "children=2" in url
        assert "ryanair.com" in url

    async def test_parse_fare_calendar_with_flights(self, scraper, mock_page):
        """Test parsing fare calendar with flight results."""
        # Mock flight cards
        card1 = AsyncMock()
        card2 = AsyncMock()

        # Mock price elements
        price_elem1 = AsyncMock()
        price_elem1.inner_text = AsyncMock(return_value="€49.99")

        price_elem2 = AsyncMock()
        price_elem2.inner_text = AsyncMock(return_value="€79.50")

        # Mock time elements
        time_elem1_dep = AsyncMock()
        time_elem1_dep.inner_text = AsyncMock(return_value="08:30")

        time_elem1_arr = AsyncMock()
        time_elem1_arr.inner_text = AsyncMock(return_value="10:45")

        # Configure card1
        async def card1_query_selector(selector):
            if "price" in selector.lower():
                return price_elem1
            elif "flight-number" in selector.lower():
                return None
            elif ":has-text" in selector:
                return AsyncMock()  # Direct flight
            return None

        async def card1_query_selector_all(selector):
            if "time" in selector.lower():
                return [time_elem1_dep, time_elem1_arr]
            return []

        card1.query_selector = AsyncMock(side_effect=card1_query_selector)
        card1.query_selector_all = AsyncMock(side_effect=card1_query_selector_all)

        # Configure card2 similarly
        async def card2_query_selector(selector):
            if "price" in selector.lower():
                return price_elem2
            return None

        async def card2_query_selector_all(selector):
            if "time" in selector.lower():
                return []
            return []

        card2.query_selector = AsyncMock(side_effect=card2_query_selector)
        card2.query_selector_all = AsyncMock(side_effect=card2_query_selector_all)

        # Mock page to return flight cards
        mock_page.query_selector_all = AsyncMock(return_value=[card1, card2])

        flights = await scraper.parse_fare_calendar(mock_page)

        # Should have parsed 2 flights
        assert len(flights) == 2
        assert flights[0]["price"] == 49.99
        assert flights[0]["departure_time"] == "08:30"
        assert flights[0]["direct"] is True
        assert flights[1]["price"] == 79.50

    async def test_parse_fare_calendar_no_flights(self, scraper, mock_page):
        """Test parsing fare calendar with no results."""
        # No flight cards found
        mock_page.query_selector_all = AsyncMock(return_value=[])
        mock_page.content = AsyncMock(return_value="<html>No flights</html>")

        flights = await scraper.parse_fare_calendar(mock_page)

        # Should return empty list
        assert len(flights) == 0

    async def test_parse_fare_calendar_with_prices_in_content(self, scraper, mock_page):
        """Test parsing fare calendar from page content."""
        # No flight cards, but prices in content
        mock_page.query_selector_all = AsyncMock(return_value=[])
        mock_page.content = AsyncMock(
            return_value="<html>Flights: €49.99, €79.50, €99.00</html>"
        )

        flights = await scraper.parse_fare_calendar(mock_page)

        # Should have extracted prices from content
        assert len(flights) >= 3
        assert any(f["price"] == 49.99 for f in flights)
        assert any(f["price"] == 79.50 for f in flights)

    @patch("app.scrapers.ryanair_scraper.async_playwright")
    async def test_scrape_route_rate_limit_check(self, mock_async_playwright, scraper, tmp_path):
        """Test that scrape_route checks rate limit."""
        # Set up rate limit to be exceeded
        rate_file = tmp_path / "rate_limit.json"
        scraper.RATE_LIMIT_FILE = str(rate_file)

        with open(rate_file, "w") as f:
            json.dump({"date": str(date.today()), "count": 5}, f)

        # Should raise RateLimitExceeded before even initializing browser
        with pytest.raises(RateLimitExceeded):
            await scraper.scrape_route(
                origin="FMM",
                destination="BCN",
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
            )

    async def test_close(self, scraper, mock_page, mock_browser):
        """Test closing browser."""
        # Set up scraper with mocks
        scraper.page = mock_page
        scraper.context = AsyncMock()
        scraper.browser = mock_browser

        await scraper.close()

        # Should close all components
        mock_page.close.assert_called_once()
        scraper.context.close.assert_called_once()
        mock_browser.close.assert_called_once()

    async def test_save_screenshot(self, scraper, mock_page, tmp_path):
        """Test screenshot saving."""
        scraper.page = mock_page
        scraper.log_dir = tmp_path

        filepath = await scraper._save_screenshot("test")

        # Should have saved screenshot
        mock_page.screenshot.assert_called_once()
        assert "test" in filepath
        assert filepath.endswith(".png")


class TestRyanairScraperIntegration:
    """Integration tests for RyanairScraper (require network access)."""

    @pytest.mark.skip(reason="Integration test - requires network and may trigger CAPTCHA")
    async def test_scrape_route_live(self):
        """Test scraping against live Ryanair site."""
        scraper = RyanairScraper()

        try:
            flights = await scraper.scrape_route(
                origin="FMM",
                destination="BCN",
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
            )

            # Should return some flights (or empty list if none available)
            assert isinstance(flights, list)

            # If flights found, check structure
            if flights:
                flight = flights[0]
                assert "price" in flight or "currency" in flight
                assert "source" in flight
                assert flight["source"] == "ryanair"

        except CaptchaDetected:
            # Expected - CAPTCHA detection is working
            pytest.skip("CAPTCHA detected - scraper working as intended")

        except RateLimitExceeded:
            # Expected - rate limiting is working
            pytest.skip("Rate limit exceeded - scraper working as intended")

        finally:
            await scraper.close()
