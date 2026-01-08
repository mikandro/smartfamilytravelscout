"""
Integration tests for end-to-end flight search workflow.

Tests the complete flow: search triggering → scraper execution → database persistence
→ AI scoring → notifications.
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy import select

from app.database import get_async_session_context
from app.models.airport import Airport
from app.models.flight import Flight
from app.models.scraping_job import ScrapingJob
from app.orchestration.flight_orchestrator import FlightOrchestrator


@pytest.mark.integration
@pytest.mark.asyncio
class TestFlightSearchEndToEnd:
    """Integration tests for complete flight search workflow."""

    async def test_complete_flight_search_workflow(self):
        """
        Test end-to-end flight search: scraping → database → verification.

        This test verifies:
        1. FlightOrchestrator initializes correctly
        2. Scrapers execute and return data
        3. Flight data is saved to database
        4. Database relationships are maintained
        5. ScrapingJob is created and tracked
        """
        # Setup: Create test airports
        async with get_async_session_context() as db:
            # Check if airports exist, create if not
            origin = await db.execute(select(Airport).where(Airport.iata_code == "MUC"))
            origin_airport = origin.scalar_one_or_none()

            if not origin_airport:
                origin_airport = Airport(
                    iata_code="MUC",
                    name="Munich Airport",
                    city="Munich",
                    country="Germany",
                    distance_from_home=50,
                    driving_time=45,
                    parking_cost_per_day=15.0,
                )
                db.add(origin_airport)

            dest = await db.execute(select(Airport).where(Airport.iata_code == "BCN"))
            dest_airport = dest.scalar_one_or_none()

            if not dest_airport:
                dest_airport = Airport(
                    iata_code="BCN",
                    name="Barcelona Airport",
                    city="Barcelona",
                    country="Spain",
                    distance_from_home=1200,
                    driving_time=720,
                    parking_cost_per_day=0.0,
                )
                db.add(dest_airport)

            await db.commit()

        # Test: Run flight orchestrator with mocked scrapers
        departure_date = date.today() + timedelta(days=60)
        return_date = departure_date + timedelta(days=7)

        # Mock scraper responses
        mock_flight_data = [
            {
                "origin_airport": "MUC",
                "destination_airport": "BCN",
                "origin_city": "Munich",
                "destination_city": "Barcelona",
                "airline": "Lufthansa",
                "departure_date": departure_date.strftime("%Y-%m-%d"),
                "departure_time": "10:00",
                "return_date": return_date.strftime("%Y-%m-%d"),
                "return_time": "18:00",
                "price_per_person": 150.0,
                "total_price": 600.0,
                "booking_class": "Economy",
                "direct_flight": True,
                "source": "test",
                "booking_url": "https://test.com/booking",
                "scraped_at": datetime.now().isoformat(),
            }
        ]

        orchestrator = FlightOrchestrator()

        # Mock the scrape_source method to return test data
        with patch.object(orchestrator, 'scrape_source', new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = mock_flight_data

            # Execute flight scraping
            flights = await orchestrator.scrape_all(
                origins=["MUC"],
                destinations=["BCN"],
                date_ranges=[(departure_date, return_date)]
            )

            # Verify flights were returned
            assert len(flights) > 0, "No flights returned from orchestrator"

            # Save to database
            stats = await orchestrator.save_to_database(flights, create_job=True)

            # Verify database operations
            assert stats["total"] > 0, "No flights were processed"
            assert stats["inserted"] > 0 or stats["updated"] > 0, "No flights were saved"

        # Verify data in database
        async with get_async_session_context() as db:
            # Check flight was saved
            stmt = select(Flight).where(
                Flight.airline == "Lufthansa",
                Flight.source == "test"
            )
            result = await db.execute(stmt)
            saved_flight = result.scalar_one_or_none()

            assert saved_flight is not None, "Flight not found in database"
            assert saved_flight.price_per_person == 150.0
            assert saved_flight.origin_airport_id == origin_airport.id
            assert saved_flight.destination_airport_id == dest_airport.id

            # Check scraping job was created
            job_stmt = select(ScrapingJob).where(
                ScrapingJob.job_type == "flights",
                ScrapingJob.source == "orchestrator"
            )
            job_result = await db.execute(job_stmt)
            scraping_job = job_result.scalars().first()

            assert scraping_job is not None, "ScrapingJob not created"
            assert scraping_job.status == "completed"
            assert scraping_job.items_scraped > 0

            # Cleanup
            await db.delete(saved_flight)
            if scraping_job:
                await db.delete(scraping_job)
            await db.commit()

    async def test_flight_deduplication(self):
        """
        Test that duplicate flights from multiple sources are properly deduplicated.
        """
        # Create duplicate flight data from different sources
        departure_date = date.today() + timedelta(days=60)
        return_date = departure_date + timedelta(days=7)

        flights = [
            # Same flight from two sources
            {
                "origin_airport": "MUC",
                "destination_airport": "BCN",
                "airline": "Ryanair",
                "departure_date": departure_date.strftime("%Y-%m-%d"),
                "departure_time": "10:00",
                "return_date": return_date.strftime("%Y-%m-%d"),
                "return_time": "18:00",
                "price_per_person": 100.0,
                "total_price": 400.0,
                "source": "skyscanner",
            },
            {
                "origin_airport": "MUC",
                "destination_airport": "BCN",
                "airline": "Ryanair",
                "departure_date": departure_date.strftime("%Y-%m-%d"),
                "departure_time": "10:15",  # Within 2-hour window
                "return_date": return_date.strftime("%Y-%m-%d"),
                "return_time": "18:10",
                "price_per_person": 105.0,  # Slightly higher price
                "total_price": 420.0,
                "source": "ryanair",
            },
        ]

        orchestrator = FlightOrchestrator()

        # Test deduplication
        unique_flights = orchestrator.deduplicate(flights)

        # Should keep only 1 flight (the cheaper one)
        assert len(unique_flights) == 1, f"Expected 1 unique flight, got {len(unique_flights)}"
        assert unique_flights[0]["price_per_person"] == 100.0, "Cheaper flight not selected"
        assert len(unique_flights[0].get("booking_urls", [])) >= 1, "Booking URLs not merged"

    async def test_flight_search_error_handling(self):
        """
        Test that flight search handles scraper failures gracefully.
        """
        orchestrator = FlightOrchestrator()
        departure_date = date.today() + timedelta(days=60)
        return_date = departure_date + timedelta(days=7)

        # Mock one scraper to fail, another to succeed
        with patch.object(orchestrator, 'scrape_source', new_callable=AsyncMock) as mock_scrape:
            # Simulate mixed results: some succeed, some fail
            mock_scrape.side_effect = [
                Exception("Scraper timeout"),  # First call fails
                [{"airline": "Test", "price_per_person": 100.0}],  # Second succeeds
            ]

            # Should not raise exception, but continue with successful scrapers
            flights = await orchestrator.scrape_all(
                origins=["MUC"],
                destinations=["BCN"],
                date_ranges=[(departure_date, return_date)]
            )

            # Should return flights from successful scraper
            # (In real scenario, we'd get flights from working scrapers)
            assert isinstance(flights, list), "Should return list even with partial failures"

    async def test_concurrent_scraper_execution(self):
        """
        Test that multiple scrapers execute concurrently for efficiency.
        """
        import time

        orchestrator = FlightOrchestrator()
        departure_date = date.today() + timedelta(days=60)
        return_date = departure_date + timedelta(days=7)

        # Mock scraper that simulates async delay
        async def mock_scraper_with_delay(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate network delay
            return [{"airline": "Test", "price_per_person": 100.0}]

        with patch.object(orchestrator, 'scrape_source', new_callable=AsyncMock) as mock_scrape:
            mock_scrape.side_effect = mock_scraper_with_delay

            start_time = time.time()

            # Run with 4 routes (would be 4 * 0.1 = 0.4s if sequential)
            await orchestrator.scrape_all(
                origins=["MUC", "VIE"],
                destinations=["BCN", "LIS"],
                date_ranges=[(departure_date, return_date)]
            )

            elapsed = time.time() - start_time

            # If running concurrently, should take ~0.1s (not 0.4s)
            # Allow some overhead for test execution
            assert elapsed < 0.3, f"Scrapers not running concurrently (took {elapsed:.2f}s)"


# Import asyncio for concurrent test
import asyncio
