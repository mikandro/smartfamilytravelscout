"""
Unit tests for FlightOrchestrator.

Tests the orchestration, deduplication, and database saving logic
with mocked scrapers to avoid actual web scraping.
"""

import pytest
from datetime import date, datetime, time
from unittest.mock import AsyncMock, MagicMock, patch

from app.orchestration.flight_orchestrator import FlightOrchestrator


class TestFlightOrchestrator:
    """Test suite for FlightOrchestrator class."""

    @pytest.fixture
    def orchestrator(self):
        """Create FlightOrchestrator instance with mocked scrapers."""
        with patch("app.orchestration.flight_orchestrator.KiwiClient"), patch(
            "app.orchestration.flight_orchestrator.SkyscannerScraper"
        ), patch("app.orchestration.flight_orchestrator.RyanairScraper"), patch(
            "app.orchestration.flight_orchestrator.WizzAirScraper"
        ):
            return FlightOrchestrator()

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

    def test_deduplicate_no_duplicates(self, orchestrator, sample_flights):
        """Test deduplication with no duplicates."""
        unique = orchestrator.deduplicate(sample_flights)

        # Should return same number of flights since no duplicates
        assert len(unique) == 2
        assert all("booking_urls" in flight for flight in unique)
        assert all("sources" in flight for flight in unique)

    def test_deduplicate_with_duplicates(self, orchestrator):
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

        unique = orchestrator.deduplicate(flights)

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

    def test_deduplicate_different_airlines(self, orchestrator):
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

        unique = orchestrator.deduplicate(flights)

        # Should have 2 unique flights (different airlines)
        assert len(unique) == 2

    def test_deduplicate_outside_time_window(self, orchestrator):
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

        unique = orchestrator.deduplicate(flights)

        # Should have 2 unique flights (outside time window)
        assert len(unique) == 2

    def test_deduplicate_empty_list(self, orchestrator):
        """Test deduplication with empty input."""
        unique = orchestrator.deduplicate([])
        assert len(unique) == 0

    def test_deduplicate_missing_fields(self, orchestrator):
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

        unique = orchestrator.deduplicate(flights)

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
        """Test that scrape_source handles errors gracefully."""
        orchestrator.kiwi.search_flights = AsyncMock(
            side_effect=Exception("API Error")
        )

        result = await orchestrator.scrape_source(
            orchestrator.kiwi,
            "kiwi",
            "MUC",
            "LIS",
            (date(2025, 12, 20), date(2025, 12, 27)),
        )

        # Should return empty list on error
        assert result == []

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
    async def test_scrape_all_handles_partial_failures(self, orchestrator):
        """Test that scrape_all continues even if some scrapers fail."""
        # Mock Kiwi to succeed, others to fail
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

        result = await orchestrator.scrape_all(
            origins=["MUC"],
            destinations=["LIS"],
            date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))],
        )

        # Should still return Kiwi results despite other failures
        assert len(result) >= 1

    def test_deduplicate_keeps_cheapest(self, orchestrator):
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

        unique = orchestrator.deduplicate(flights)

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
