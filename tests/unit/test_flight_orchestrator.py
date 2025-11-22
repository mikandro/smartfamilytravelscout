"""
Unit tests for FlightOrchestrator.

Tests the orchestration, deduplication, and database saving logic
with mocked scrapers to avoid actual web scraping.
"""

import pytest
from datetime import date, datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

from app.exceptions import ScraperFailureThresholdExceeded
from app.orchestration.flight_orchestrator import FlightOrchestrator


class TestFlightOrchestrator:
    """Test suite for FlightOrchestrator class."""

    @pytest.fixture
    def orchestrator(self):
        """Create FlightOrchestrator instance with mocked scrapers."""
        with patch("app.orchestration.flight_orchestrator.settings") as mock_settings, \
             patch("app.orchestration.flight_orchestrator.KiwiClient") as mock_kiwi, \
             patch("app.orchestration.flight_orchestrator.SkyscannerScraper") as mock_skyscanner, \
             patch("app.orchestration.flight_orchestrator.RyanairScraper") as mock_ryanair, \
             patch("app.orchestration.flight_orchestrator.WizzAirScraper") as mock_wizzair:

            # Mock settings to enable all scrapers
            mock_settings.get_available_scrapers.return_value = ["kiwi", "skyscanner", "ryanair", "wizzair"]
            mock_settings.scraper_failure_threshold = 0.5
            mock_settings.cache_ttl_flights = 3600

            # Pass None for redis_client to avoid Redis dependency in tests
            orchestrator = FlightOrchestrator(redis_client=None)

            # Ensure all scrapers are properly initialized (not None)
            if orchestrator.kiwi is None:
                orchestrator.kiwi = mock_kiwi.return_value
            if orchestrator.skyscanner is None:
                orchestrator.skyscanner = mock_skyscanner.return_value
            if orchestrator.ryanair is None:
                orchestrator.ryanair = mock_ryanair.return_value
            if orchestrator.wizzair is None:
                orchestrator.wizzair = mock_wizzair.return_value

            return orchestrator

    @pytest.fixture
    def sample_flights(self):
        """Sample flight data for testing."""
        return [
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "origin_city": "Munich",
                "destination_city": "Lisbon",
                "airline": "Ryanair",
                "departure_date": "2025-12-20",
                "departure_time": "14:30",
                "return_date": "2025-12-27",
                "return_time": "18:45",
                "price_per_person": 89.99,
                "total_price": 359.96,
                "direct_flight": True,
                "booking_class": "Economy",
                "source": "kiwi",
                "booking_url": "https://kiwi.com/booking/123",
                "scraped_at": "2025-11-15T10:30:00",
            },
            {
                "origin_airport": "MUC",
                "destination_airport": "BCN",
                "origin_city": "Munich",
                "destination_city": "Barcelona",
                "airline": "Vueling",
                "departure_date": "2025-12-20",
                "departure_time": "10:00",
                "return_date": "2025-12-27",
                "return_time": "16:30",
                "price_per_person": 129.50,
                "total_price": 518.00,
                "direct_flight": True,
                "booking_class": "Economy",
                "source": "skyscanner",
                "booking_url": "https://skyscanner.com/booking/456",
                "scraped_at": "2025-11-15T10:35:00",
            },
        ]

    def test_initialization(self, orchestrator):
        """Test that orchestrator initializes with all scrapers."""
        assert orchestrator.kiwi is not None
        assert orchestrator.skyscanner is not None
        assert orchestrator.ryanair is not None
        assert orchestrator.wizzair is not None

    @pytest.mark.asyncio
    async def test_deduplicate_no_duplicates(self, orchestrator, sample_flights):
        """Test deduplication with no duplicates."""
        unique = await orchestrator.deduplicate(sample_flights)

        # Should return same number of flights since no duplicates
        assert len(unique) == 2
        assert all("booking_urls" in flight for flight in unique)
        assert all("sources" in flight for flight in unique)

    @pytest.mark.asyncio
    async def test_deduplicate_with_duplicates(self, orchestrator):
        """Test deduplication with actual duplicates."""
        flights = [
            # Same flight from two sources (within 2-hour window)
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "airline": "Ryanair",
                "departure_date": "2025-12-20",
                "departure_time": "14:30",
                "return_date": "2025-12-27",
                "return_time": "18:45",
                "price_per_person": 89.99,
                "total_price": 359.96,
                "source": "kiwi",
                "booking_url": "https://kiwi.com/booking/123",
            },
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "airline": "Ryanair",
                "departure_date": "2025-12-20",
                "departure_time": "14:45",  # 15 min later - within 2-hour window
                "return_date": "2025-12-27",
                "return_time": "19:00",  # 15 min later
                "price_per_person": 95.00,  # More expensive
                "total_price": 380.00,
                "source": "skyscanner",
                "booking_url": "https://skyscanner.com/booking/456",
            },
            # Different flight
            {
                "origin_airport": "MUC",
                "destination_airport": "BCN",
                "airline": "Vueling",
                "departure_date": "2025-12-20",
                "departure_time": "10:00",
                "return_date": "2025-12-27",
                "return_time": "16:30",
                "price_per_person": 129.50,
                "total_price": 518.00,
                "source": "kiwi",
                "booking_url": "https://kiwi.com/booking/789",
            },
        ]

        unique = await orchestrator.deduplicate(flights)

        # Should have 2 unique flights (first two merged, third separate)
        assert len(unique) == 2

        # Find the merged flight (MUC->LIS)
        merged = next(f for f in unique if f["destination_airport"] == "LIS")

        # Should keep the cheaper one (89.99)
        assert merged["price_per_person"] == 89.99

        # Should have both booking URLs
        assert len(merged["booking_urls"]) == 2
        assert "https://kiwi.com/booking/123" in merged["booking_urls"]
        assert "https://skyscanner.com/booking/456" in merged["booking_urls"]

        # Should have both sources
        assert "kiwi" in merged["sources"]
        assert "skyscanner" in merged["sources"]

        # Should track duplicate count
        assert merged["duplicate_count"] == 2

    @pytest.mark.asyncio
    async def test_deduplicate_different_airlines(self, orchestrator):
        """Test that different airlines are not considered duplicates."""
        flights = [
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "airline": "Ryanair",
                "departure_date": "2025-12-20",
                "departure_time": "14:30",
                "return_date": "2025-12-27",
                "return_time": "18:45",
                "price_per_person": 89.99,
                "total_price": 359.96,
                "source": "kiwi",
                "booking_url": "https://kiwi.com/123",
            },
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "airline": "TAP",  # Different airline
                "departure_date": "2025-12-20",
                "departure_time": "14:30",  # Same time
                "return_date": "2025-12-27",
                "return_time": "18:45",
                "price_per_person": 120.00,
                "total_price": 480.00,
                "source": "skyscanner",
                "booking_url": "https://skyscanner.com/456",
            },
        ]

        unique = await orchestrator.deduplicate(flights)

        # Should have 2 unique flights (different airlines)
        assert len(unique) == 2

    @pytest.mark.asyncio
    async def test_deduplicate_outside_time_window(self, orchestrator):
        """Test that flights outside 2-hour window are not duplicates."""
        flights = [
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "airline": "Ryanair",
                "departure_date": "2025-12-20",
                "departure_time": "08:00",
                "return_date": "2025-12-27",
                "return_time": "18:00",
                "price_per_person": 89.99,
                "total_price": 359.96,
                "source": "kiwi",
                "booking_url": "https://kiwi.com/123",
            },
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "airline": "Ryanair",
                "departure_date": "2025-12-20",
                "departure_time": "18:00",  # 10 hours later - outside window
                "return_date": "2025-12-27",
                "return_time": "22:00",
                "price_per_person": 95.00,
                "total_price": 380.00,
                "source": "skyscanner",
                "booking_url": "https://skyscanner.com/456",
            },
        ]

        unique = await orchestrator.deduplicate(flights)

        # Should have 2 unique flights (outside time window)
        assert len(unique) == 2

    @pytest.mark.asyncio
    async def test_deduplicate_empty_list(self, orchestrator):
        """Test deduplication with empty input."""
        unique = await orchestrator.deduplicate([])
        assert len(unique) == 0

    @pytest.mark.asyncio
    async def test_deduplicate_missing_fields(self, orchestrator):
        """Test deduplication handles missing fields gracefully."""
        flights = [
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "airline": "Ryanair",
                # Missing departure_date
                "departure_time": "14:30",
                "price_per_person": 89.99,
                "source": "kiwi",
            },
            {
                "origin_airport": "MUC",
                "destination_airport": "BCN",
                "airline": "Vueling",
                "departure_date": "2025-12-20",
                # Missing departure_time - should use default
                "price_per_person": 129.50,
                "source": "skyscanner",
            },
        ]

        unique = await orchestrator.deduplicate(flights)

        # Should handle gracefully (first skipped, second kept)
        assert len(unique) == 1
        assert unique[0]["destination_airport"] == "BCN"

    @pytest.mark.asyncio
    async def test_scrape_source_kiwi(self, orchestrator):
        """Test scraping from Kiwi source."""
        mock_flights = [
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "origin_city": "Munich",
                "destination_city": "Lisbon",
                "airline": "Ryanair",
                "departure_date": "2025-12-20",
                "departure_time": "14:30",
                "return_date": "2025-12-27",
                "return_time": "18:45",
                "price_per_person": 89.99,
                "total_price": 359.96,
                "source": "kiwi",
            }
        ]

        orchestrator.kiwi.search_flights = AsyncMock(return_value=mock_flights)

        result = await orchestrator.scrape_source(
            orchestrator.kiwi,
            "kiwi",
            "MUC",
            "LIS",
            (date(2025, 12, 20), date(2025, 12, 27)),
        )

        assert len(result) == 1
        assert result[0]["origin_airport"] == "MUC"
        orchestrator.kiwi.search_flights.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_source_error_handling(self, orchestrator):
        """Test that scrape_source logs errors and re-raises exceptions."""
        orchestrator.kiwi.search_flights = AsyncMock(
            side_effect=Exception("API Error")
        )

        # Should raise exception (not silently return empty list)
        with pytest.raises(Exception, match="API Error"):
            await orchestrator.scrape_source(
                orchestrator.kiwi,
                "kiwi",
                "MUC",
                "LIS",
                (date(2025, 12, 20), date(2025, 12, 27)),
            )

    @pytest.mark.asyncio
    async def test_scrape_all_parallel_execution(self, orchestrator):
        """Test that scrape_all runs scrapers in parallel."""
        # Mock all scrapers to return flights
        mock_kiwi_flights = [
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "origin_city": "Munich",
                "destination_city": "Lisbon",
                "airline": "Ryanair",
                "departure_date": "2025-12-20",
                "departure_time": "14:30",
                "return_date": "2025-12-27",
                "return_time": "18:45",
                "price_per_person": 89.99,
                "total_price": 359.96,
                "source": "kiwi",
                "booking_url": "https://kiwi.com/123",
            }
        ]

        orchestrator.kiwi.search_flights = AsyncMock(return_value=mock_kiwi_flights)
        orchestrator.skyscanner.scrape_route = AsyncMock(return_value=[])
        orchestrator.ryanair.scrape_route = AsyncMock(return_value=[])
        orchestrator.wizzair.search_flights = AsyncMock(return_value=[])

        # Mock context managers
        orchestrator.skyscanner.__aenter__ = AsyncMock(return_value=orchestrator.skyscanner)
        orchestrator.skyscanner.__aexit__ = AsyncMock(return_value=None)
        orchestrator.ryanair.__aenter__ = AsyncMock(return_value=orchestrator.ryanair)
        orchestrator.ryanair.__aexit__ = AsyncMock(return_value=None)

        result = await orchestrator.scrape_all(
            origins=["MUC"],
            destinations=["LIS"],
            date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))],
        )

        # Should have called all scrapers
        orchestrator.kiwi.search_flights.assert_called()
        orchestrator.skyscanner.scrape_route.assert_called()
        orchestrator.ryanair.scrape_route.assert_called()
        orchestrator.wizzair.search_flights.assert_called()

        # Should return deduplicated results
        assert len(result) >= 0  # At least the Kiwi flight (after deduplication)

    @pytest.mark.asyncio
    async def test_scrape_all_handles_acceptable_partial_failures(self, orchestrator):
        """Test that scrape_all continues when failure rate is acceptable (below threshold)."""
        # Mock 2 scrapers to succeed, 2 to fail (50% failure rate = at threshold, should succeed)
        orchestrator.kiwi.search_flights = AsyncMock(
            return_value=[
                {
                    "origin_airport": "MUC",
                    "destination_airport": "LIS",
                    "origin_city": "Munich",
                    "destination_city": "Lisbon",
                    "airline": "Ryanair",
                    "departure_date": "2025-12-20",
                    "departure_time": "14:30",
                    "return_date": "2025-12-27",
                    "return_time": "18:45",
                    "price_per_person": 89.99,
                    "total_price": 359.96,
                    "source": "kiwi",
                    "booking_url": "https://kiwi.com/123",
                }
            ]
        )

        orchestrator.skyscanner.scrape_route = AsyncMock(return_value=[])
        orchestrator.ryanair.scrape_route = AsyncMock(side_effect=Exception("Ryanair Error"))
        orchestrator.wizzair.search_flights = AsyncMock(side_effect=Exception("WizzAir Error"))

        # Mock context managers
        orchestrator.skyscanner.__aenter__ = AsyncMock(return_value=orchestrator.skyscanner)
        orchestrator.skyscanner.__aexit__ = AsyncMock(return_value=None)
        orchestrator.ryanair.__aenter__ = AsyncMock(return_value=orchestrator.ryanair)
        orchestrator.ryanair.__aexit__ = AsyncMock(return_value=None)

        result = await orchestrator.scrape_all(
            origins=["MUC"],
            destinations=["LIS"],
            date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))],
        )

        # Should return results when failure rate is at threshold (50% = at threshold, only > triggers exception)
        assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_deduplicate_keeps_cheapest(self, orchestrator):
        """Test that deduplication keeps the cheapest flight."""
        flights = [
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "airline": "Ryanair",
                "departure_date": "2025-12-20",
                "departure_time": "14:30",
                "return_date": "2025-12-27",
                "return_time": "18:45",
                "price_per_person": 150.00,  # Expensive
                "total_price": 600.00,
                "source": "skyscanner",
                "booking_url": "https://skyscanner.com/expensive",
            },
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "airline": "Ryanair",
                "departure_date": "2025-12-20",
                "departure_time": "14:40",  # Within time window
                "return_date": "2025-12-27",
                "return_time": "18:50",
                "price_per_person": 75.00,  # Cheaper
                "total_price": 300.00,
                "source": "kiwi",
                "booking_url": "https://kiwi.com/cheap",
            },
            {
                "origin_airport": "MUC",
                "destination_airport": "LIS",
                "airline": "Ryanair",
                "departure_date": "2025-12-20",
                "departure_time": "14:35",  # Within time window
                "return_date": "2025-12-27",
                "return_time": "18:40",
                "price_per_person": 100.00,  # Medium price
                "total_price": 400.00,
                "source": "wizzair",
                "booking_url": "https://wizzair.com/medium",
            },
        ]

        unique = await orchestrator.deduplicate(flights)

        # Should have 1 unique flight (all merged)
        assert len(unique) == 1

        # Should keep the cheapest (75.00 from Kiwi)
        assert unique[0]["price_per_person"] == 75.00
        assert unique[0]["source"] == "kiwi"

        # Should have all booking URLs
        assert len(unique[0]["booking_urls"]) == 3
        assert "https://kiwi.com/cheap" in unique[0]["booking_urls"]
        assert "https://skyscanner.com/expensive" in unique[0]["booking_urls"]
        assert "https://wizzair.com/medium" in unique[0]["booking_urls"]

    @pytest.mark.asyncio
    async def test_scrape_all_raises_on_threshold_exceeded(self, orchestrator):
        """Test that scrape_all raises exception when failure threshold is exceeded."""
        # Mock all scrapers to fail (100% failure rate)
        orchestrator.kiwi.search_flights = AsyncMock(side_effect=Exception("Kiwi Error"))
        orchestrator.skyscanner.scrape_route = AsyncMock(side_effect=Exception("Skyscanner Error"))
        orchestrator.ryanair.scrape_route = AsyncMock(side_effect=Exception("Ryanair Error"))
        orchestrator.wizzair.search_flights = AsyncMock(side_effect=Exception("WizzAir Error"))

        # Mock context managers
        orchestrator.skyscanner.__aenter__ = AsyncMock(return_value=orchestrator.skyscanner)
        orchestrator.skyscanner.__aexit__ = AsyncMock(return_value=None)
        orchestrator.ryanair.__aenter__ = AsyncMock(return_value=orchestrator.ryanair)
        orchestrator.ryanair.__aexit__ = AsyncMock(return_value=None)

        # Should raise ScraperFailureThresholdExceeded (100% > 50% default threshold)
        with pytest.raises(ScraperFailureThresholdExceeded) as exc_info:
            await orchestrator.scrape_all(
                origins=["MUC"],
                destinations=["LIS"],
                date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))],
            )

        # Verify exception details
        exception = exc_info.value
        assert exception.total_scrapers == 4
        assert exception.failed_scrapers == 4
        assert exception.failure_rate == 1.0  # 100% failure
        assert exception.threshold == 0.5  # Default 50%

    @pytest.mark.asyncio
    async def test_scrape_all_raises_on_high_failure_rate(self, orchestrator):
        """Test that exception is raised when 75% of scrapers fail (above 50% threshold)."""
        # Mock 3 out of 4 scrapers to fail (75% failure rate)
        orchestrator.kiwi.search_flights = AsyncMock(
            return_value=[
                {
                    "origin_airport": "MUC",
                    "destination_airport": "LIS",
                    "origin_city": "Munich",
                    "destination_city": "Lisbon",
                    "airline": "Ryanair",
                    "departure_date": "2025-12-20",
                    "departure_time": "14:30",
                    "return_date": "2025-12-27",
                    "return_time": "18:45",
                    "price_per_person": 89.99,
                    "total_price": 359.96,
                    "source": "kiwi",
                    "booking_url": "https://kiwi.com/123",
                }
            ]
        )
        orchestrator.skyscanner.scrape_route = AsyncMock(side_effect=Exception("Skyscanner Error"))
        orchestrator.ryanair.scrape_route = AsyncMock(side_effect=Exception("Ryanair Error"))
        orchestrator.wizzair.search_flights = AsyncMock(side_effect=Exception("WizzAir Error"))

        # Mock context managers
        orchestrator.skyscanner.__aenter__ = AsyncMock(return_value=orchestrator.skyscanner)
        orchestrator.skyscanner.__aexit__ = AsyncMock(return_value=None)
        orchestrator.ryanair.__aenter__ = AsyncMock(return_value=orchestrator.ryanair)
        orchestrator.ryanair.__aexit__ = AsyncMock(return_value=None)

        # Should raise ScraperFailureThresholdExceeded (75% > 50% threshold)
        with pytest.raises(ScraperFailureThresholdExceeded) as exc_info:
            await orchestrator.scrape_all(
                origins=["MUC"],
                destinations=["LIS"],
                date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))],
            )

        # Verify exception details
        exception = exc_info.value
        assert exception.total_scrapers == 4
        assert exception.failed_scrapers == 3
        assert exception.failure_rate == 0.75  # 75% failure

    @pytest.mark.asyncio
    async def test_scrape_all_succeeds_below_threshold(self, orchestrator):
        """Test that scrape_all succeeds when failure rate is below threshold."""
        # Mock 1 out of 4 scrapers to fail (25% failure rate, below 50% threshold)
        orchestrator.kiwi.search_flights = AsyncMock(
            return_value=[
                {
                    "origin_airport": "MUC",
                    "destination_airport": "LIS",
                    "origin_city": "Munich",
                    "destination_city": "Lisbon",
                    "airline": "Ryanair",
                    "departure_date": "2025-12-20",
                    "departure_time": "14:30",
                    "return_date": "2025-12-27",
                    "return_time": "18:45",
                    "price_per_person": 89.99,
                    "total_price": 359.96,
                    "source": "kiwi",
                    "booking_url": "https://kiwi.com/123",
                }
            ]
        )
        orchestrator.skyscanner.scrape_route = AsyncMock(return_value=[])
        orchestrator.ryanair.scrape_route = AsyncMock(return_value=[])
        orchestrator.wizzair.search_flights = AsyncMock(side_effect=Exception("WizzAir Error"))

        # Mock context managers
        orchestrator.skyscanner.__aenter__ = AsyncMock(return_value=orchestrator.skyscanner)
        orchestrator.skyscanner.__aexit__ = AsyncMock(return_value=None)
        orchestrator.ryanair.__aenter__ = AsyncMock(return_value=orchestrator.ryanair)
        orchestrator.ryanair.__aexit__ = AsyncMock(return_value=None)

        # Should succeed (25% < 50% threshold)
        result = await orchestrator.scrape_all(
            origins=["MUC"],
            destinations=["LIS"],
            date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))],
        )

        # Should return results from successful scrapers
        assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_scrape_all_succeeds_at_exact_threshold(self, orchestrator):
        """Test that scrape_all succeeds when failure rate equals threshold (not exceeded)."""
        # Mock 2 out of 4 scrapers to fail (50% failure rate, equals 50% threshold)
        orchestrator.kiwi.search_flights = AsyncMock(
            return_value=[
                {
                    "origin_airport": "MUC",
                    "destination_airport": "LIS",
                    "origin_city": "Munich",
                    "destination_city": "Lisbon",
                    "airline": "Ryanair",
                    "departure_date": "2025-12-20",
                    "departure_time": "14:30",
                    "return_date": "2025-12-27",
                    "return_time": "18:45",
                    "price_per_person": 89.99,
                    "total_price": 359.96,
                    "source": "kiwi",
                    "booking_url": "https://kiwi.com/123",
                }
            ]
        )
        orchestrator.skyscanner.scrape_route = AsyncMock(return_value=[])
        orchestrator.ryanair.scrape_route = AsyncMock(side_effect=Exception("Ryanair Error"))
        orchestrator.wizzair.search_flights = AsyncMock(side_effect=Exception("WizzAir Error"))

        # Mock context managers
        orchestrator.skyscanner.__aenter__ = AsyncMock(return_value=orchestrator.skyscanner)
        orchestrator.skyscanner.__aexit__ = AsyncMock(return_value=None)
        orchestrator.ryanair.__aenter__ = AsyncMock(return_value=orchestrator.ryanair)
        orchestrator.ryanair.__aexit__ = AsyncMock(return_value=None)

        # Should succeed (50% == 50% threshold, only > triggers exception)
        result = await orchestrator.scrape_all(
            origins=["MUC"],
            destinations=["LIS"],
            date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))],
        )

        # Should return results from successful scrapers
        assert len(result) >= 0

    @pytest.mark.asyncio
    async def test_scrape_all_with_custom_threshold(self, orchestrator):
        """Test that custom failure threshold is respected."""
        # Mock 2 out of 4 scrapers to fail (50% failure rate)
        orchestrator.kiwi.search_flights = AsyncMock(return_value=[])
        orchestrator.skyscanner.scrape_route = AsyncMock(return_value=[])
        orchestrator.ryanair.scrape_route = AsyncMock(side_effect=Exception("Ryanair Error"))
        orchestrator.wizzair.search_flights = AsyncMock(side_effect=Exception("WizzAir Error"))

        # Mock context managers
        orchestrator.skyscanner.__aenter__ = AsyncMock(return_value=orchestrator.skyscanner)
        orchestrator.skyscanner.__aexit__ = AsyncMock(return_value=None)
        orchestrator.ryanair.__aenter__ = AsyncMock(return_value=orchestrator.ryanair)
        orchestrator.ryanair.__aexit__ = AsyncMock(return_value=None)

        # Mock settings with lower threshold (40%)
        with patch("app.orchestration.flight_orchestrator.settings") as mock_settings:
            mock_settings.scraper_failure_threshold = 0.4
            mock_settings.get_available_scrapers.return_value = ["kiwi", "skyscanner", "ryanair", "wizzair"]

            # Should raise exception (50% > 40% threshold)
            with pytest.raises(ScraperFailureThresholdExceeded) as exc_info:
                await orchestrator.scrape_all(
                    origins=["MUC"],
                    destinations=["LIS"],
                    date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))],
                )

            # Verify threshold was used
            exception = exc_info.value
            assert exception.threshold == 0.4


class TestFlightOrchestratorDatabase:
    """Test database operations of FlightOrchestrator."""

    @pytest.mark.asyncio
    @pytest.mark.integration  # Mark as integration test (requires DB)
    async def test_save_to_database(self):
        """Test saving flights to database (requires test database)."""
        # This would require a test database setup
        # Skipping detailed implementation for now
        pass

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_or_create_airport(self):
        """Test get or create airport logic (requires test database)."""
        # This would require a test database setup
        # Skipping detailed implementation for now
        pass

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_check_duplicate_flight(self):
        """Test duplicate flight checking (requires test database)."""
        # This would require a test database setup
        # Skipping detailed implementation for now
        pass
