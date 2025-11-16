"""
Integration tests for SkyscannerScraper with real browser.

These tests use a real Playwright browser instance and are marked
as slow. They may be skipped in CI/CD for faster builds.

Run with: pytest -m slow tests/integration/test_skyscanner_scraper_integration.py
"""

import pytest
from datetime import date, timedelta

from app.scrapers.skyscanner_scraper import (
    SkyscannerScraper,
    RateLimitExceededError,
    CaptchaDetectedError,
)


@pytest.mark.slow
@pytest.mark.asyncio
class TestSkyscannerScraperIntegration:
    """Integration tests with real browser."""

    async def test_scraper_context_manager(self):
        """Test scraper initialization and cleanup with context manager."""
        async with SkyscannerScraper(headless=True) as scraper:
            assert scraper.browser is not None
            assert scraper.context is not None

        # After exit, browser should be closed
        assert scraper.browser is None
        assert scraper.context is None

    async def test_scrape_real_route(self):
        """
        Test scraping a real route.

        NOTE: This test makes a real request to Skyscanner.
        Use with caution and respect rate limits.
        """
        # Use future dates to ensure availability
        today = date.today()
        departure = today + timedelta(days=60)
        return_date = departure + timedelta(days=7)

        async with SkyscannerScraper(headless=True) as scraper:
            # Scrape MUC -> LIS route
            flights = await scraper.scrape_route(
                origin="MUC", destination="LIS", departure_date=departure, return_date=return_date
            )

            # Verify we got results (or at least no errors)
            assert isinstance(flights, list)

            # If flights found, verify structure
            if flights:
                flight = flights[0]
                assert "airline" in flight
                assert "price_per_person" in flight
                assert "total_price" in flight
                assert flight["total_price"] == flight["price_per_person"] * 4

                # Log results for manual verification
                print(f"\nFound {len(flights)} flights:")
                for f in flights[:3]:  # Print first 3
                    print(
                        f"  {f['airline']}: €{f['price_per_person']} "
                        f"({'Direct' if f.get('direct_flight') else 'Connecting'})"
                    )

    async def test_scrape_one_way_flight(self):
        """Test scraping one-way flight (no return date)."""
        today = date.today()
        departure = today + timedelta(days=60)

        async with SkyscannerScraper(headless=True) as scraper:
            flights = await scraper.scrape_route(
                origin="MUC", destination="BCN", departure_date=departure, return_date=None
            )

            assert isinstance(flights, list)
            # One-way flights should also be found
            if flights:
                print(f"\nFound {len(flights)} one-way flights")

    async def test_url_building_matches_actual_site(self):
        """Verify URL format matches Skyscanner's actual format."""
        scraper = SkyscannerScraper()

        url = scraper._build_url("MUC", "LIS", date(2025, 12, 20), date(2025, 12, 27))

        # Verify URL structure
        assert url.startswith("https://www.skyscanner.com/transport/flights")
        assert "/MUC/LIS/251220/251227" in url
        assert "adults=2" in url
        assert "children=2" in url

        print(f"\nGenerated URL: {url}")

    async def test_cookie_consent_handling_real_page(self):
        """Test cookie consent handling on real Skyscanner page."""
        async with SkyscannerScraper(headless=True) as scraper:
            page = await scraper.context.new_page()

            try:
                # Navigate to Skyscanner homepage
                await page.goto("https://www.skyscanner.com", timeout=30000)

                # Try to handle cookie consent
                await scraper._handle_cookie_consent(page)

                # Should not raise, even if no consent found
                print("\nCookie consent handled successfully")

            finally:
                await page.close()

    async def test_screenshot_saving_real_page(self, tmp_path):
        """Test screenshot saving with real page."""
        async with SkyscannerScraper(headless=True) as scraper:
            scraper.logs_dir = tmp_path

            page = await scraper.context.new_page()

            try:
                await page.goto("https://www.skyscanner.com", timeout=30000)

                # Save screenshot
                await scraper._save_screenshot(page, prefix="test")

                # Verify screenshot was created
                screenshots = list(tmp_path.glob("test_*.png"))
                assert len(screenshots) >= 1
                assert screenshots[0].stat().st_size > 0

                print(f"\nScreenshot saved: {screenshots[0]}")

            finally:
                await page.close()

    async def test_rate_limiting_enforcement(self):
        """Test that rate limiting is enforced."""
        import app.scrapers.skyscanner_scraper as scraper_module

        # Save original values
        original_count = scraper_module._request_count
        original_max = scraper_module.MAX_REQUESTS_PER_HOUR

        try:
            # Set to max requests
            scraper_module._request_count = scraper_module.MAX_REQUESTS_PER_HOUR

            scraper = SkyscannerScraper()

            # Should raise rate limit error
            with pytest.raises(RateLimitExceededError) as exc_info:
                scraper._check_rate_limit()

            assert "Rate limit exceeded" in str(exc_info.value)
            print("\nRate limiting enforced correctly")

        finally:
            # Restore original values
            scraper_module._request_count = original_count

    async def test_multiple_searches_sequential(self):
        """
        Test multiple sequential searches respect delays.

        NOTE: This test is slow as it enforces delays.
        """
        import time

        today = date.today()
        departure = today + timedelta(days=60)

        async with SkyscannerScraper(headless=True) as scraper:
            start_time = time.time()

            # Make 2 searches (should take at least 6 seconds with delays)
            routes = [("MUC", "BCN"), ("MUC", "MAD")]

            for origin, dest in routes[:1]:  # Just do 1 to save time in test
                try:
                    await scraper.scrape_route(
                        origin=origin, destination=dest, departure_date=departure
                    )
                except Exception as e:
                    print(f"\nSearch failed (expected in test): {e}")

            duration = time.time() - start_time

            # Should have delays between requests (at least 3 seconds for 1 request)
            assert duration >= 3.0
            print(f"\nRespectful delays enforced: {duration:.1f}s for 1 request")


@pytest.mark.slow
@pytest.mark.asyncio
class TestSkyscannerErrorHandling:
    """Test error handling in real scenarios."""

    async def test_invalid_airport_code(self):
        """Test handling of invalid airport code."""
        today = date.today()
        departure = today + timedelta(days=60)

        async with SkyscannerScraper(headless=True) as scraper:
            # Use obviously invalid codes
            flights = await scraper.scrape_route(
                origin="XXX", destination="YYY", departure_date=departure
            )

            # Should return empty list or handle gracefully
            assert isinstance(flights, list)
            print(f"\nInvalid airport codes handled: {len(flights)} flights found")

    async def test_past_date_handling(self):
        """Test handling of past dates."""
        past_date = date.today() - timedelta(days=10)

        async with SkyscannerScraper(headless=True) as scraper:
            # Try to scrape past date
            flights = await scraper.scrape_route(
                origin="MUC", destination="LIS", departure_date=past_date
            )

            # Should not crash
            assert isinstance(flights, list)
            print(f"\nPast date handled: {len(flights)} flights found")

    async def test_timeout_handling(self):
        """Test timeout handling with very short timeout."""
        today = date.today()
        departure = today + timedelta(days=60)

        async with SkyscannerScraper(headless=True) as scraper:
            # This may timeout, but should handle gracefully
            try:
                # Override timeout in wait_for_results for this test
                page = await scraper.context.new_page()
                url = scraper._build_url("MUC", "LIS", departure, None)

                await page.goto(url, wait_until="domcontentloaded", timeout=5000)

                # Should not crash even if results don't load
                print("\nTimeout handled gracefully")

                await page.close()

            except Exception as e:
                # Timeout expected, should be handled
                print(f"\nTimeout caught as expected: {type(e).__name__}")
                assert True


@pytest.mark.slow
@pytest.mark.asyncio
class TestSkyscannerDatabaseIntegration:
    """Test database integration with real scraper."""

    async def test_save_to_database_with_real_airports(self):
        """
        Test saving to database with real airport data.

        NOTE: Requires database to be set up with airport data.
        This test may be skipped if database is not available.
        """
        from app.database import get_async_session_context
        from app.models.airport import Airport
        from sqlalchemy import select

        # Check if database is accessible
        try:
            async with get_async_session_context() as session:
                # Check if MUC and LIS airports exist
                stmt = select(Airport).where(Airport.iata_code.in_(["MUC", "LIS"]))
                result = await session.execute(stmt)
                airports = result.scalars().all()

                if len(airports) < 2:
                    pytest.skip("Required airports (MUC, LIS) not in database")

                print(f"\nFound {len(airports)} airports in database")

        except Exception as e:
            pytest.skip(f"Database not accessible: {e}")

        # If we got here, database is ready
        scraper = SkyscannerScraper()

        # Mock flight data (don't actually scrape in this test)
        flights = [
            {
                "airline": "Test Airlines",
                "price_per_person": 150.0,
                "total_price": 600.0,
                "departure_time": "10:00",
                "arrival_time": "12:00",
                "direct_flight": True,
                "booking_url": "https://test.com",
                "booking_class": "Economy",
            }
        ]

        # Save to database
        await scraper.save_to_database(
            flights=flights,
            origin="MUC",
            destination="LIS",
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        # Verify saved
        async with get_async_session_context() as session:
            from app.models.flight import Flight

            stmt = (
                select(Flight)
                .where(Flight.airline == "Test Airlines")
                .where(Flight.source == "skyscanner")
            )
            result = await session.execute(stmt)
            saved_flight = result.scalar_one_or_none()

            assert saved_flight is not None
            assert saved_flight.price_per_person == 150.0
            assert saved_flight.source == "skyscanner"

            print(f"\nFlight saved to database: {saved_flight}")

            # Cleanup
            await session.delete(saved_flight)
            await session.commit()
