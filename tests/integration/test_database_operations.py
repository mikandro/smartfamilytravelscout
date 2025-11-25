"""
Integration tests for database operations.

Tests model relationships, cascade deletes, index usage, and transaction handling.
"""

import pytest
from datetime import date, datetime, timedelta

from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload

from app.database import get_async_session_context
from app.models.accommodation import Accommodation
from app.models.airport import Airport
from app.models.event import Event
from app.models.flight import Flight
from app.models.trip_package import TripPackage
from app.models.price_history import PriceHistory
from app.models.scraping_job import ScrapingJob


@pytest.mark.integration
@pytest.mark.asyncio
class TestDatabaseOperations:
    """Integration tests for database operations and relationships."""

    async def test_airport_flight_cascade_delete(self):
        """
        Test that deleting an airport cascades to related flights.

        Verifies CASCADE DELETE on Airport → Flight relationship.
        """
        async with get_async_session_context() as db:
            # Create airports
            origin = Airport(
                iata_code="TSTC1",
                name="Test Cascade Airport 1",
                city="TestCity",
                country="TestCountry",
                distance_from_home=50,
                driving_time=45,
                parking_cost_per_day=10.0,
            )
            destination = Airport(
                iata_code="TSTC2",
                name="Test Cascade Airport 2",
                city="TestCity2",
                country="TestCountry",
                distance_from_home=500,
                driving_time=300,
                parking_cost_per_day=0.0,
            )
            db.add_all([origin, destination])
            await db.flush()

            origin_id = origin.id
            destination_id = destination.id

            # Create flights
            flight1 = Flight(
                origin_airport_id=origin_id,
                destination_airport_id=destination_id,
                airline="Test Airlines",
                departure_date=date.today() + timedelta(days=30),
                return_date=date.today() + timedelta(days=37),
                price_per_person=150.0,
                total_price=600.0,
                booking_class="Economy",
                direct_flight=True,
                source="test",
                scraped_at=datetime.now(),
            )

            flight2 = Flight(
                origin_airport_id=origin_id,
                destination_airport_id=destination_id,
                airline="Another Airlines",
                departure_date=date.today() + timedelta(days=35),
                return_date=date.today() + timedelta(days=42),
                price_per_person=180.0,
                total_price=720.0,
                booking_class="Economy",
                direct_flight=False,
                source="test",
                scraped_at=datetime.now(),
            )

            db.add_all([flight1, flight2])
            await db.commit()

            # Verify flights exist
            count_stmt = select(func.count()).select_from(Flight).where(
                Flight.origin_airport_id == origin_id
            )
            count = await db.scalar(count_stmt)
            assert count == 2, "Flights not created"

            # Delete origin airport (should cascade to flights)
            await db.delete(origin)
            await db.commit()

            # Verify flights were deleted
            count_after = await db.scalar(count_stmt)
            assert count_after == 0, "Flights not deleted with airport (CASCADE failed)"

            # Cleanup remaining airport
            dest_to_delete = await db.get(Airport, destination_id)
            if dest_to_delete:
                await db.delete(dest_to_delete)
                await db.commit()

    async def test_trip_package_accommodation_set_null(self):
        """
        Test that deleting an accommodation sets trip_package.accommodation_id to NULL.

        Verifies SET NULL on Accommodation → TripPackage relationship.
        """
        async with get_async_session_context() as db:
            # Create accommodation
            accommodation = Accommodation(
                destination_city="TestCity",
                name="Test Hotel",
                accommodation_type="hotel",
                price_per_night=80.0,
                rating=4.5,
                family_friendly=True,
                source="test",
                scraped_at=datetime.now(),
            )
            db.add(accommodation)
            await db.flush()

            accommodation_id = accommodation.id

            # Create trip package
            package = TripPackage(
                package_type="family",
                flights_json=[1, 2],
                accommodation_id=accommodation_id,
                events_json=[],
                total_price=1500.0,
                destination_city="TestCity",
                departure_date=date.today() + timedelta(days=30),
                return_date=date.today() + timedelta(days=37),
                num_nights=7,
                notified=False,
            )
            db.add(package)
            await db.commit()

            package_id = package.id

            # Verify package has accommodation
            verify_stmt = select(TripPackage).where(TripPackage.id == package_id)
            result = await db.execute(verify_stmt)
            verified_package = result.scalar_one()
            assert verified_package.accommodation_id == accommodation_id

            # Delete accommodation
            await db.delete(accommodation)
            await db.commit()

            # Refresh package and verify accommodation_id is NULL
            refreshed = await db.get(TripPackage, package_id)
            assert refreshed is not None, "Package should still exist"
            assert refreshed.accommodation_id is None, "accommodation_id not set to NULL"

            # Cleanup
            await db.delete(refreshed)
            await db.commit()

    async def test_relationship_eager_loading(self):
        """
        Test that relationships can be eager-loaded efficiently using selectinload.
        """
        async with get_async_session_context() as db:
            # Create test data with relationships
            origin = Airport(
                iata_code="TSTE1",
                name="Test Eager 1",
                city="TestCity1",
                country="TestCountry",
                distance_from_home=50,
                driving_time=45,
                parking_cost_per_day=10.0,
            )
            destination = Airport(
                iata_code="TSTE2",
                name="Test Eager 2",
                city="TestCity2",
                country="TestCountry",
                distance_from_home=0,
                driving_time=0,
                parking_cost_per_day=0.0,
            )
            db.add_all([origin, destination])
            await db.flush()

            flight = Flight(
                origin_airport_id=origin.id,
                destination_airport_id=destination.id,
                airline="Test Airlines",
                departure_date=date.today() + timedelta(days=30),
                return_date=date.today() + timedelta(days=37),
                price_per_person=150.0,
                total_price=600.0,
                booking_class="Economy",
                direct_flight=True,
                source="test",
                scraped_at=datetime.now(),
            )
            db.add(flight)
            await db.commit()

            flight_id = flight.id

            # Query with eager loading
            stmt = (
                select(Flight)
                .where(Flight.id == flight_id)
                .options(
                    selectinload(Flight.origin_airport),
                    selectinload(Flight.destination_airport),
                )
            )
            result = await db.execute(stmt)
            loaded_flight = result.scalar_one()

            # Access relationships without additional queries
            assert loaded_flight.origin_airport.iata_code == "TSTE1"
            assert loaded_flight.destination_airport.iata_code == "TSTE2"
            assert loaded_flight.origin_airport.city == "TestCity1"
            assert loaded_flight.destination_airport.city == "TestCity2"

            # Cleanup
            await db.delete(loaded_flight)
            await db.delete(origin)
            await db.delete(destination)
            await db.commit()

    async def test_transaction_rollback(self):
        """
        Test that database transactions roll back correctly on errors.
        """
        async with get_async_session_context() as db:
            # Create airport
            airport = Airport(
                iata_code="TSTR1",
                name="Test Rollback Airport",
                city="TestCity",
                country="TestCountry",
                distance_from_home=50,
                driving_time=45,
                parking_cost_per_day=10.0,
            )
            db.add(airport)
            await db.flush()

            airport_id = airport.id

        # Try to create duplicate airport (should fail)
        try:
            async with get_async_session_context() as db:
                duplicate = Airport(
                    iata_code="TSTR1",  # Same IATA code - should violate unique constraint
                    name="Duplicate Airport",
                    city="TestCity",
                    country="TestCountry",
                    distance_from_home=60,
                    driving_time=50,
                    parking_cost_per_day=12.0,
                )
                db.add(duplicate)
                await db.commit()  # This should raise an exception

            assert False, "Should have raised integrity error"

        except Exception:
            # Expected - unique constraint violation
            pass

        # Verify original airport still exists
        async with get_async_session_context() as db:
            verify_stmt = select(Airport).where(Airport.iata_code == "TSTR1")
            result = await db.execute(verify_stmt)
            airports = result.scalars().all()

            # Should have exactly one airport (rollback prevented duplicate)
            assert len(airports) == 1, f"Expected 1 airport, found {len(airports)}"

            # Cleanup
            await db.delete(airports[0])
            await db.commit()

    async def test_index_performance_on_common_queries(self):
        """
        Test that indexes improve query performance on common filters.

        Note: This test verifies that queries use indexes via EXPLAIN.
        """
        async with get_async_session_context() as db:
            # Create test data
            origin = Airport(
                iata_code="TSTIDX1",
                name="Test Index Airport",
                city="TestCity",
                country="TestCountry",
                distance_from_home=50,
                driving_time=45,
                parking_cost_per_day=10.0,
            )
            destination = Airport(
                iata_code="TSTIDX2",
                name="Test Index Dest",
                city="TestCity2",
                country="TestCountry",
                distance_from_home=0,
                driving_time=0,
                parking_cost_per_day=0.0,
            )
            db.add_all([origin, destination])
            await db.flush()

            # Create multiple flights for index testing
            target_date = date.today() + timedelta(days=30)

            for i in range(5):
                flight = Flight(
                    origin_airport_id=origin.id,
                    destination_airport_id=destination.id,
                    airline=f"Airline {i}",
                    departure_date=target_date + timedelta(days=i),
                    return_date=target_date + timedelta(days=i + 7),
                    price_per_person=100.0 + i * 10,
                    total_price=400.0 + i * 40,
                    booking_class="Economy",
                    direct_flight=True,
                    source="test",
                    scraped_at=datetime.now(),
                )
                db.add(flight)

            await db.commit()

            # Test query with indexed columns
            # (departure_date, destination_airport_id, source, ai_score typically indexed)
            stmt = select(Flight).where(
                Flight.departure_date >= target_date,
                Flight.destination_airport_id == destination.id,
                Flight.source == "test"
            )

            # Execute query
            result = await db.execute(stmt)
            flights = result.scalars().all()

            assert len(flights) == 5, f"Expected 5 flights, got {len(flights)}"

            # Check query plan uses index (optional - requires raw SQL)
            explain_query = text(f"""
                EXPLAIN (FORMAT JSON)
                SELECT * FROM flights
                WHERE departure_date >= '{target_date}'
                AND destination_airport_id = {destination.id}
                AND source = 'test'
            """)

            result = await db.execute(explain_query)
            plan = result.scalar()

            # Verify index usage (plan should mention "Index Scan" not "Seq Scan")
            # Note: This is a basic check - actual index names may vary
            assert "Index" in str(plan) or "Bitmap" in str(plan), \
                "Query might not be using indexes efficiently"

            # Cleanup
            for flight in flights:
                await db.delete(flight)
            await db.delete(origin)
            await db.delete(destination)
            await db.commit()

    async def test_concurrent_updates_handling(self):
        """
        Test that concurrent updates to the same record are handled correctly.
        """
        async with get_async_session_context() as db:
            # Create a flight
            origin = Airport(
                iata_code="TSTCU1",
                name="Test Concurrent Airport",
                city="TestCity",
                country="TestCountry",
                distance_from_home=50,
                driving_time=45,
                parking_cost_per_day=10.0,
            )
            destination = Airport(
                iata_code="TSTCU2",
                name="Test Concurrent Dest",
                city="TestCity2",
                country="TestCountry",
                distance_from_home=0,
                driving_time=0,
                parking_cost_per_day=0.0,
            )
            db.add_all([origin, destination])
            await db.flush()

            flight = Flight(
                origin_airport_id=origin.id,
                destination_airport_id=destination.id,
                airline="Test Airlines",
                departure_date=date.today() + timedelta(days=30),
                return_date=date.today() + timedelta(days=37),
                price_per_person=150.0,
                total_price=600.0,
                booking_class="Economy",
                direct_flight=True,
                source="test",
                scraped_at=datetime.now(),
            )
            db.add(flight)
            await db.commit()

            flight_id = flight.id

        # Simulate concurrent updates in separate sessions
        async with get_async_session_context() as db1:
            flight1 = await db1.get(Flight, flight_id)
            flight1.price_per_person = 140.0

            # Start another session before committing first
            async with get_async_session_context() as db2:
                flight2 = await db2.get(Flight, flight_id)
                flight2.price_per_person = 145.0

                # Commit second session first
                await db2.commit()

            # Commit first session (last write wins)
            await db1.commit()

        # Verify final state
        async with get_async_session_context() as db:
            final_flight = await db.get(Flight, flight_id)

            # Last commit should win
            assert final_flight.price_per_person == 140.0, \
                f"Expected 140.0, got {final_flight.price_per_person}"

            # Cleanup
            await db.delete(final_flight)
            origin_to_delete = await db.get(Airport, origin.id)
            dest_to_delete = await db.get(Airport, destination.id)
            if origin_to_delete:
                await db.delete(origin_to_delete)
            if dest_to_delete:
                await db.delete(dest_to_delete)
            await db.commit()

    async def test_bulk_insert_performance(self):
        """
        Test bulk insertion of multiple records for efficiency.
        """
        import time

        async with get_async_session_context() as db:
            # Create airports
            origin = Airport(
                iata_code="TSTBULK1",
                name="Test Bulk Airport",
                city="TestCity",
                country="TestCountry",
                distance_from_home=50,
                driving_time=45,
                parking_cost_per_day=10.0,
            )
            destination = Airport(
                iata_code="TSTBULK2",
                name="Test Bulk Dest",
                city="TestCity2",
                country="TestCountry",
                distance_from_home=0,
                driving_time=0,
                parking_cost_per_day=0.0,
            )
            db.add_all([origin, destination])
            await db.flush()

            # Bulk insert 100 flights
            flights = []
            target_date = date.today() + timedelta(days=30)

            start_time = time.time()

            for i in range(100):
                flight = Flight(
                    origin_airport_id=origin.id,
                    destination_airport_id=destination.id,
                    airline=f"Airline {i}",
                    departure_date=target_date + timedelta(days=i % 30),
                    return_date=target_date + timedelta(days=(i % 30) + 7),
                    price_per_person=100.0 + i,
                    total_price=400.0 + i * 4,
                    booking_class="Economy",
                    direct_flight=True,
                    source="test",
                    scraped_at=datetime.now(),
                )
                flights.append(flight)

            # Use add_all for bulk insert
            db.add_all(flights)
            await db.commit()

            elapsed = time.time() - start_time

            # Bulk insert should be fast (< 2 seconds for 100 records)
            assert elapsed < 2.0, f"Bulk insert too slow: {elapsed:.2f}s"

            # Verify all inserted
            count_stmt = select(func.count()).select_from(Flight).where(
                Flight.origin_airport_id == origin.id
            )
            count = await db.scalar(count_stmt)
            assert count == 100, f"Expected 100 flights, got {count}"

            # Cleanup
            for flight in flights:
                await db.delete(flight)
            await db.delete(origin)
            await db.delete(destination)
            await db.commit()

    async def test_jsonb_field_operations(self):
        """
        Test JSONB field operations (flights_json, events_json in TripPackage).
        """
        async with get_async_session_context() as db:
            # Create trip package with JSONB fields
            package = TripPackage(
                package_type="family",
                flights_json=[1, 2, 3],  # Array of flight IDs
                accommodation_id=None,
                events_json=[{"id": 10, "name": "Test Event"}],  # Array of event data
                total_price=1500.0,
                destination_city="TestCity",
                departure_date=date.today() + timedelta(days=30),
                return_date=date.today() + timedelta(days=37),
                num_nights=7,
                notified=False,
            )
            db.add(package)
            await db.commit()

            package_id = package.id

            # Query and verify JSONB fields
            retrieved = await db.get(TripPackage, package_id)

            assert isinstance(retrieved.flights_json, list)
            assert len(retrieved.flights_json) == 3
            assert retrieved.flights_json == [1, 2, 3]

            assert isinstance(retrieved.events_json, list)
            assert len(retrieved.events_json) == 1
            assert retrieved.events_json[0]["name"] == "Test Event"

            # Update JSONB fields
            retrieved.flights_json.append(4)
            retrieved.events_json.append({"id": 11, "name": "Another Event"})
            await db.commit()

            # Verify updates
            updated = await db.get(TripPackage, package_id)
            assert len(updated.flights_json) == 4
            assert len(updated.events_json) == 2

            # Cleanup
            await db.delete(updated)
            await db.commit()
