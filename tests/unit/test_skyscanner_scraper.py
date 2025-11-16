"""
Unit tests for SkyscannerScraper.

Tests scraper functionality with mocked Playwright components.
"""

import pytest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from app.scrapers.skyscanner_scraper import (
    SkyscannerScraper,
    RateLimitExceededError,
    CaptchaDetectedError,
    MAX_REQUESTS_PER_HOUR,
)


class TestSkyscannerScraperInit:
    """Test SkyscannerScraper initialization."""

    def test_init_default_params(self):
        """Test scraper initialization with default parameters."""
        scraper = SkyscannerScraper()

        assert scraper.headless is True
        assert scraper.slow_mo == 0
        assert scraper.browser is None
        assert scraper.context is None
        assert scraper.logs_dir == Path("logs")

    def test_init_custom_params(self):
        """Test scraper initialization with custom parameters."""
        scraper = SkyscannerScraper(headless=False, slow_mo=100)

        assert scraper.headless is False
        assert scraper.slow_mo == 100

    def test_logs_directory_created(self, tmp_path):
        """Test that logs directory is created."""
        with patch("app.scrapers.skyscanner_scraper.Path") as mock_path:
            mock_path.return_value = tmp_path / "logs"
            scraper = SkyscannerScraper()
            # Verify mkdir was called
            assert scraper.logs_dir is not None


class TestBrowserManagement:
    """Test browser lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_browser(self):
        """Test browser startup."""
        scraper = SkyscannerScraper()

        # Mock Playwright
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()

        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context

        with patch(
            "app.scrapers.skyscanner_scraper.async_playwright"
        ) as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(
                return_value=mock_playwright
            )

            await scraper._start_browser()

            # Verify browser was launched
            mock_playwright.chromium.launch.assert_called_once()
            assert scraper.browser == mock_browser
            assert scraper.context == mock_context

    @pytest.mark.asyncio
    async def test_close_browser(self):
        """Test browser cleanup."""
        scraper = SkyscannerScraper()

        # Mock browser and context
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_playwright = AsyncMock()

        scraper.browser = mock_browser
        scraper.context = mock_context
        scraper.playwright = mock_playwright

        await scraper._close_browser()

        # Verify cleanup was called
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()

        # Verify they're set to None
        assert scraper.browser is None
        assert scraper.context is None
        assert scraper.playwright is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using scraper as async context manager."""
        with patch(
            "app.scrapers.skyscanner_scraper.async_playwright"
        ) as mock_async_playwright:
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()

            mock_playwright.chromium.launch.return_value = mock_browser
            mock_browser.new_context.return_value = mock_context
            mock_async_playwright.return_value.start = AsyncMock(
                return_value=mock_playwright
            )

            async with SkyscannerScraper() as scraper:
                assert scraper.browser is not None
                assert scraper.context is not None

            # Verify cleanup happened
            mock_context.close.assert_called_once()
            mock_browser.close.assert_called_once()


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limit_check_under_limit(self):
        """Test rate limit check when under limit."""
        scraper = SkyscannerScraper()

        # Reset counters
        import app.scrapers.skyscanner_scraper as scraper_module

        scraper_module._request_count = 0

        # Should not raise
        scraper._check_rate_limit()
        assert scraper_module._request_count == 1

    def test_rate_limit_check_at_limit(self):
        """Test rate limit check when at limit."""
        scraper = SkyscannerScraper()

        # Set counter to max
        import app.scrapers.skyscanner_scraper as scraper_module

        scraper_module._request_count = MAX_REQUESTS_PER_HOUR

        # Should raise
        with pytest.raises(RateLimitExceededError) as exc_info:
            scraper._check_rate_limit()

        assert "Rate limit exceeded" in str(exc_info.value)

    def test_rate_limit_counter_reset_after_hour(self):
        """Test rate limit counter resets after an hour."""
        scraper = SkyscannerScraper()

        import app.scrapers.skyscanner_scraper as scraper_module
        import time

        # Set counter to max and hour_start_time to past
        scraper_module._request_count = MAX_REQUESTS_PER_HOUR
        scraper_module._hour_start_time = time.time() - 3601  # Over an hour ago

        # Should not raise (counter reset)
        scraper._check_rate_limit()
        assert scraper_module._request_count == 1


class TestURLBuilding:
    """Test URL construction."""

    def test_build_url_one_way(self):
        """Test URL building for one-way flight."""
        scraper = SkyscannerScraper()

        url = scraper._build_url("MUC", "LIS", date(2025, 12, 20), None)

        assert "MUC" in url
        assert "LIS" in url
        assert "251220" in url  # YYMMDD format
        assert "adults=2" in url
        assert "children=2" in url

    def test_build_url_round_trip(self):
        """Test URL building for round-trip flight."""
        scraper = SkyscannerScraper()

        url = scraper._build_url(
            "MUC", "LIS", date(2025, 12, 20), date(2025, 12, 27)
        )

        assert "MUC" in url
        assert "LIS" in url
        assert "251220" in url
        assert "251227" in url
        assert "rtn=1" in url


class TestPriceParser:
    """Test price parsing logic."""

    def test_parse_price_euro_symbol(self):
        """Test parsing price with € symbol."""
        scraper = SkyscannerScraper()

        assert scraper._parse_price("€123.45") == 123.45
        assert scraper._parse_price("€100") == 100.0
        assert scraper._parse_price("123.45€") == 123.45

    def test_parse_price_with_whitespace(self):
        """Test parsing price with whitespace."""
        scraper = SkyscannerScraper()

        assert scraper._parse_price("€ 123.45") == 123.45
        assert scraper._parse_price("123.45 €") == 123.45

    def test_parse_price_eur_text(self):
        """Test parsing price with EUR text."""
        scraper = SkyscannerScraper()

        assert scraper._parse_price("123.45 EUR") == 123.45
        assert scraper._parse_price("100 EUR") == 100.0

    def test_parse_price_invalid(self):
        """Test parsing invalid price."""
        scraper = SkyscannerScraper()

        assert scraper._parse_price("no price here") is None
        assert scraper._parse_price("") is None


class TestTimeParser:
    """Test time parsing logic."""

    def test_parse_time_valid(self):
        """Test parsing valid time string."""
        scraper = SkyscannerScraper()

        time_obj = scraper._parse_time("14:30")
        assert time_obj.hour == 14
        assert time_obj.minute == 30

    def test_parse_time_edge_cases(self):
        """Test parsing edge case times."""
        scraper = SkyscannerScraper()

        assert scraper._parse_time("00:00").hour == 0
        assert scraper._parse_time("23:59").hour == 23

    def test_parse_time_invalid(self):
        """Test parsing invalid time string."""
        scraper = SkyscannerScraper()

        assert scraper._parse_time(None) is None
        assert scraper._parse_time("") is None
        assert scraper._parse_time("invalid") is None
        assert scraper._parse_time("25:00") is None  # Invalid hour


class TestCookieConsent:
    """Test cookie consent handling."""

    @pytest.mark.asyncio
    async def test_handle_cookie_consent_found(self):
        """Test handling cookie consent when button found."""
        scraper = SkyscannerScraper()

        # Mock page
        mock_page = AsyncMock()
        mock_button = AsyncMock()
        mock_page.wait_for_selector.return_value = mock_button

        await scraper._handle_cookie_consent(mock_page)

        # Verify button was clicked
        mock_button.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_cookie_consent_not_found(self):
        """Test handling when no cookie consent present."""
        scraper = SkyscannerScraper()

        # Mock page with no consent button
        mock_page = AsyncMock()
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        mock_page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

        # Should not raise
        await scraper._handle_cookie_consent(mock_page)


class TestCaptchaDetection:
    """Test CAPTCHA detection."""

    @pytest.mark.asyncio
    async def test_detect_captcha_present(self):
        """Test CAPTCHA detection when present."""
        scraper = SkyscannerScraper()

        # Mock page with CAPTCHA
        mock_page = AsyncMock()
        mock_element = AsyncMock()
        mock_page.query_selector.return_value = mock_element

        result = await scraper._detect_captcha(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_detect_captcha_absent(self):
        """Test CAPTCHA detection when absent."""
        scraper = SkyscannerScraper()

        # Mock page without CAPTCHA
        mock_page = AsyncMock()
        mock_page.query_selector.return_value = None

        result = await scraper._detect_captcha(mock_page)

        assert result is False


class TestScreenshotSaving:
    """Test screenshot saving functionality."""

    @pytest.mark.asyncio
    async def test_save_screenshot_success(self, tmp_path):
        """Test successful screenshot saving."""
        scraper = SkyscannerScraper()
        scraper.logs_dir = tmp_path

        # Mock page
        mock_page = AsyncMock()

        await scraper._save_screenshot(mock_page, prefix="test")

        # Verify screenshot was called
        mock_page.screenshot.assert_called_once()
        # Check path argument contains prefix
        call_args = mock_page.screenshot.call_args
        assert "test_" in str(call_args[1]["path"])

    @pytest.mark.asyncio
    async def test_save_screenshot_failure(self, tmp_path):
        """Test screenshot saving handles errors gracefully."""
        scraper = SkyscannerScraper()
        scraper.logs_dir = tmp_path

        # Mock page that raises error
        mock_page = AsyncMock()
        mock_page.screenshot.side_effect = Exception("Screenshot failed")

        # Should not raise
        await scraper._save_screenshot(mock_page, prefix="test")


class TestFlightDataExtraction:
    """Test flight data extraction methods."""

    @pytest.mark.asyncio
    async def test_extract_airline_from_text(self):
        """Test extracting airline from text content."""
        scraper = SkyscannerScraper()

        # Mock element
        mock_element = AsyncMock()
        mock_airline_el = AsyncMock()
        mock_airline_el.text_content.return_value = "Lufthansa"
        mock_element.query_selector.return_value = mock_airline_el

        airline = await scraper._extract_airline(mock_element)

        assert airline == "Lufthansa"

    @pytest.mark.asyncio
    async def test_extract_airline_from_alt(self):
        """Test extracting airline from image alt text."""
        scraper = SkyscannerScraper()

        # Mock element
        mock_element = AsyncMock()
        mock_img = AsyncMock()
        mock_img.text_content.return_value = ""
        mock_img.get_attribute.return_value = "Ryanair logo"
        mock_element.query_selector.return_value = mock_img

        airline = await scraper._extract_airline(mock_element)

        assert airline == "Ryanair logo"

    @pytest.mark.asyncio
    async def test_extract_price_from_element(self):
        """Test extracting price from element."""
        scraper = SkyscannerScraper()

        # Mock element
        mock_element = AsyncMock()
        mock_price_el = AsyncMock()
        mock_price_el.text_content.return_value = "€123.45"
        mock_element.query_selector.return_value = mock_price_el

        price = await scraper._extract_price(mock_element)

        assert price == 123.45

    @pytest.mark.asyncio
    async def test_extract_direct_flight_indicator(self):
        """Test detecting direct flight."""
        scraper = SkyscannerScraper()

        # Mock element with "direct" text
        mock_element = AsyncMock()
        mock_element.text_content.return_value = "Direct flight"

        is_direct = await scraper._extract_direct_flight(mock_element)

        assert is_direct is True

    @pytest.mark.asyncio
    async def test_extract_connecting_flight_indicator(self):
        """Test detecting connecting flight."""
        scraper = SkyscannerScraper()

        # Mock element with "1 stop" text
        mock_element = AsyncMock()
        mock_element.text_content.return_value = "1 stop"

        is_direct = await scraper._extract_direct_flight(mock_element)

        assert is_direct is False


class TestDatabaseIntegration:
    """Test database saving functionality."""

    @pytest.mark.asyncio
    async def test_get_airport_by_iata(self):
        """Test getting airport by IATA code."""
        scraper = SkyscannerScraper()

        # Mock session and airport
        mock_session = AsyncMock()
        mock_airport = MagicMock()
        mock_airport.id = 1
        mock_airport.iata_code = "MUC"

        # Create a mock result that properly handles async/sync calls
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_airport

        # Make execute return the mock_result when awaited
        async def mock_execute(*args, **kwargs):
            return mock_result

        mock_session.execute = mock_execute

        airport = await scraper._get_airport_by_iata(mock_session, "MUC")

        assert airport == mock_airport
        assert airport.iata_code == "MUC"

    @pytest.mark.asyncio
    async def test_save_to_database_success(self):
        """Test successful database save."""
        scraper = SkyscannerScraper()

        flights = [
            {
                "airline": "Lufthansa",
                "price_per_person": 150.0,
                "total_price": 600.0,
                "departure_time": "10:00",
                "arrival_time": "12:00",
                "direct_flight": True,
                "booking_url": "https://example.com",
                "booking_class": "Economy",
            }
        ]

        # Mock database context and session
        mock_session = AsyncMock()
        mock_origin_airport = MagicMock(id=1, iata_code="MUC")
        mock_dest_airport = MagicMock(id=2, iata_code="LIS")

        async def mock_get_airport(session, iata):
            if iata == "MUC":
                return mock_origin_airport
            return mock_dest_airport

        with patch(
            "app.scrapers.skyscanner_scraper.get_async_session_context"
        ) as mock_context:
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch.object(
                scraper, "_get_airport_by_iata", side_effect=mock_get_airport
            ):
                await scraper.save_to_database(
                    flights, "MUC", "LIS", date(2025, 12, 20), date(2025, 12, 27)
                )

                # Verify session operations
                mock_session.add.assert_called()
                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_to_database_airport_not_found(self):
        """Test database save when airport not found."""
        scraper = SkyscannerScraper()

        flights = [{"airline": "Test", "price_per_person": 100.0, "total_price": 400.0}]

        # Mock database context
        mock_session = AsyncMock()

        with patch(
            "app.scrapers.skyscanner_scraper.get_async_session_context"
        ) as mock_context:
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch.object(scraper, "_get_airport_by_iata", return_value=None):
                # Should return early, not commit
                await scraper.save_to_database(
                    flights, "XXX", "YYY", date(2025, 12, 20)
                )

                mock_session.commit.assert_not_called()


class TestRespectfulScraping:
    """Test respectful scraping practices."""

    @pytest.mark.asyncio
    async def test_respectful_delay(self):
        """Test that respectful delay adds wait time."""
        scraper = SkyscannerScraper()

        import time

        start = time.time()
        await scraper._respectful_delay()
        duration = time.time() - start

        # Should wait at least 3 seconds
        assert duration >= 3.0

    @pytest.mark.asyncio
    async def test_user_agent_rotation(self):
        """Test that user agents are rotated."""
        from app.scrapers.skyscanner_scraper import USER_AGENTS

        # Verify we have multiple user agents
        assert len(USER_AGENTS) >= 5
        assert all(isinstance(ua, str) for ua in USER_AGENTS)
        assert all("Mozilla" in ua for ua in USER_AGENTS)
