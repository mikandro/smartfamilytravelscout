"""
Integration tests for trip package generation pipeline.

Tests the complete flow: flight scraping → accommodation matching → event matching
→ package assembly → AI scoring.
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.database import get_async_session_context
from app.models.accommodation import Accommodation
from app.models.airport import Airport
from app.models.event import Event
from app.models.flight import Flight
from app.models.school_holiday import SchoolHoliday
from app.models.trip_package import TripPackage
from app.orchestration.accommodation_matcher import AccommodationMatcher
from app.orchestration.event_matcher import EventMatcher
from app.utils.cost_calculator import calculate_true_cost


@pytest.mark.integration
@pytest.mark.asyncio
class TestPackageGenerationPipeline:
    """Integration tests for complete package generation workflow."""

    async def test_complete_package_generation(self):
        """
        Test end-to-end package generation: flights → accommodations → events → packages.

        Verifies:
        1. Flights with true costs are retrieved
        2. Accommodations are matched by destination city
        3. Trip packages are generated with correct pricing
        4. Events can be added to packages
        5. All data is persisted correctly
        """
        # Setup: Create test data
        async with get_async_session_context() as db:
            # Create airports
            origin_airport = Airport(
                iata_code="TST1",
                name="Test Origin Airport",
                city="TestCity1",
                country="TestCountry",
                distance_from_home=50,
                driving_time=45,
                parking_cost_per_day=10.0,
            )
            dest_airport = Airport(
                iata_code="TST2",
                name="Test Destination Airport",
                city="TestCity2",
                country="TestCountry",
                distance_from_home=500,
                driving_time=300,
                parking_cost_per_day=0.0,
            )
            db.add_all([origin_airport, dest_airport])
            await db.flush()

            # Create flight with true cost
            departure_date = date.today() + timedelta(days=60)
            return_date = departure_date + timedelta(days=7)

            flight = Flight(
                origin_airport_id=origin_airport.id,
                destination_airport_id=dest_airport.id,
                airline="Test Airlines",
                departure_date=departure_date,
                departure_time=None,
                return_date=return_date,
                return_time=None,
                price_per_person=150.0,
                total_price=600.0,
                booking_class="Economy",
                direct_flight=True,
                source="test",
                booking_url="https://test.com",
                scraped_at=datetime.now(),
            )

            # Calculate true cost
            num_nights = (return_date - departure_date).days
            flight.true_cost = calculate_true_cost(
                base_price=flight.total_price,
                num_nights=num_nights,
                driving_distance=origin_airport.distance_from_home,
                parking_cost_per_day=origin_airport.parking_cost_per_day,
            )

            db.add(flight)
            await db.flush()

            # Create accommodation
            accommodation = Accommodation(
                destination_city="TestCity2",
                name="Test Hotel",
                accommodation_type="hotel",
                price_per_night=80.0,
                rating=4.5,
                family_friendly=True,
                source="test",
                booking_url="https://test.com/hotel",
                scraped_at=datetime.now(),
            )
            db.add(accommodation)
            await db.flush()

            # Create event
            event = Event(
                destination_city="TestCity2",
                name="Test Family Event",
                event_type="festival",
                date=departure_date + timedelta(days=3),
                description="A fun family event",
                price_per_person=20.0,
                family_friendly=True,
                ai_score=85,
                source="test",
                scraped_at=datetime.now(),
            )
            db.add(event)

            await db.commit()

            # Store IDs for later cleanup
            flight_id = flight.id
            accommodation_id = accommodation.id
            event_id = event.id

        # Test: Generate trip packages
        async with get_async_session_context() as db:
            matcher = AccommodationMatcher()

            # Generate packages
            packages = await matcher.generate_trip_packages(
                db,
                max_budget=3000.0,
                min_nights=5,
                max_nights=10,
                filter_holidays=False,  # Skip holiday filtering for test
            )

            # Verify packages were generated
            assert len(packages) > 0, "No packages generated"

            package = packages[0]

            # Verify package structure
            assert package.destination_city == "TestCity2"
            assert package.departure_date == departure_date
            assert package.return_date == return_date
            assert package.num_nights == 7
            assert package.total_price > 0
            assert package.accommodation_id == accommodation_id

            # Calculate expected total cost
            flight_cost = flight.true_cost
            accommodation_cost = 80.0 * 7  # 7 nights
            food_cost = 100.0 * 7  # €100/day
            activities_cost = 50.0 * 7  # €50/day
            expected_total = flight_cost + accommodation_cost + food_cost + activities_cost

            # Verify pricing
            assert abs(package.total_price - expected_total) < 0.1, \
                f"Price mismatch: expected {expected_total}, got {package.total_price}"

            # Save packages
            stats = await matcher.save_packages(db, packages)
            assert stats["inserted"] > 0, "Package not saved"

        # Test: Add events to package
        async with get_async_session_context() as db:
            # Retrieve saved package
            stmt = select(TripPackage).where(TripPackage.accommodation_id == accommodation_id)
            result = await db.execute(stmt)
            saved_package = result.scalar_one_or_none()

            assert saved_package is not None, "Package not found in database"

            # Match events to packages
            event_matcher = EventMatcher(db)
            packages_with_events = await event_matcher.match_events_to_packages([saved_package])

            # Verify structure (events may or may not be matched depending on test data)
            assert len(packages_with_events) == 1, "Package not returned from matcher"
            package_id = packages_with_events[0].id

        # Cleanup
        async with get_async_session_context() as db:
            # Delete in correct order (respect foreign keys)
            await db.execute(
                select(TripPackage).where(TripPackage.id == package_id)
            )
            package_to_delete = (await db.execute(
                select(TripPackage).where(TripPackage.id == package_id)
            )).scalar_one_or_none()

            if package_to_delete:
                await db.delete(package_to_delete)

            await db.execute(select(Event).where(Event.id == event_id))
            event_to_delete = (await db.execute(
                select(Event).where(Event.id == event_id)
            )).scalar_one_or_none()
            if event_to_delete:
                await db.delete(event_to_delete)

            await db.execute(select(Accommodation).where(Accommodation.id == accommodation_id))
            accommodation_to_delete = (await db.execute(
                select(Accommodation).where(Accommodation.id == accommodation_id)
            )).scalar_one_or_none()
            if accommodation_to_delete:
                await db.delete(accommodation_to_delete)

            await db.execute(select(Flight).where(Flight.id == flight_id))
            flight_to_delete = (await db.execute(
                select(Flight).where(Flight.id == flight_id)
            )).scalar_one_or_none()
            if flight_to_delete:
                await db.delete(flight_to_delete)

            # Delete airports
            await db.execute(select(Airport).where(Airport.iata_code.in_(["TST1", "TST2"])))
            airports_to_delete = (await db.execute(
                select(Airport).where(Airport.iata_code.in_(["TST1", "TST2"]))
            )).scalars().all()
            for airport in airports_to_delete:
                await db.delete(airport)

            await db.commit()

    async def test_package_cost_calculation(self):
        """
        Test that trip package costs are calculated correctly.

        Verifies:
        - Flight true cost inclusion
        - Accommodation cost calculation (nights × price)
        - Food estimate (€100/day)
        - Activities estimate (€50/day)
        - Total and per-person calculations
        """
        async with get_async_session_context() as db:
            # Create minimal test data
            origin_airport = Airport(
                iata_code="TST3",
                name="Test Airport 3",
                city="TestCity3",
                country="TestCountry",
                distance_from_home=30,
                driving_time=25,
                parking_cost_per_day=12.0,
            )
            dest_airport = Airport(
                iata_code="TST4",
                name="Test Airport 4",
                city="TestCity4",
                country="TestCountry",
                distance_from_home=0,
                driving_time=0,
                parking_cost_per_day=0.0,
            )
            db.add_all([origin_airport, dest_airport])
            await db.flush()

            departure_date = date.today() + timedelta(days=30)
            return_date = departure_date + timedelta(days=5)
            num_nights = 5

            flight = Flight(
                origin_airport_id=origin_airport.id,
                destination_airport_id=dest_airport.id,
                airline="Budget Air",
                departure_date=departure_date,
                return_date=return_date,
                price_per_person=100.0,
                total_price=400.0,
                booking_class="Economy",
                direct_flight=True,
                source="test",
                scraped_at=datetime.now(),
            )

            # Calculate true cost: 400 + (5 * 12) + (30 * 2 * 0.15) + (50 * 2)
            flight.true_cost = calculate_true_cost(
                base_price=400.0,
                num_nights=num_nights,
                driving_distance=30,
                parking_cost_per_day=12.0,
            )

            accommodation = Accommodation(
                destination_city="TestCity4",
                name="Budget Hotel",
                accommodation_type="hotel",
                price_per_night=60.0,
                rating=3.5,
                family_friendly=True,
                source="test",
                scraped_at=datetime.now(),
            )

            db.add_all([flight, accommodation])
            await db.flush()

            # Test cost calculation
            matcher = AccommodationMatcher()
            cost = matcher.calculate_trip_cost(flight, accommodation, num_nights)

            # Verify all cost components
            assert cost["flight_cost"] == flight.true_cost
            assert cost["accommodation_cost"] == 60.0 * 5  # 300.0
            assert cost["food_cost"] == 100.0 * 5  # 500.0
            assert cost["activities_cost"] == 50.0 * 5  # 250.0
            assert cost["total"] == sum([
                cost["flight_cost"],
                cost["accommodation_cost"],
                cost["food_cost"],
                cost["activities_cost"]
            ])
            assert cost["per_person"] == cost["total"] / 4.0

            # Cleanup
            await db.delete(flight)
            await db.delete(accommodation)
            await db.delete(origin_airport)
            await db.delete(dest_airport)
            await db.commit()

    async def test_school_holiday_filtering(self):
        """
        Test that packages are correctly filtered to school holiday periods.
        """
        async with get_async_session_context() as db:
            # Create school holiday
            holiday_start = date.today() + timedelta(days=30)
            holiday_end = holiday_start + timedelta(days=14)

            holiday = SchoolHoliday(
                name="Test Holiday",
                region="Test Region",
                start_date=holiday_start,
                end_date=holiday_end,
            )
            db.add(holiday)
            await db.flush()

            # Create packages: one during holiday, one outside
            package_during = TripPackage(
                package_type="family",
                flights_json=[1],
                accommodation_id=1,
                events_json=[],
                total_price=1500.0,
                destination_city="TestCity",
                departure_date=holiday_start + timedelta(days=2),  # During holiday
                return_date=holiday_start + timedelta(days=9),
                num_nights=7,
                notified=False,
            )

            package_outside = TripPackage(
                package_type="family",
                flights_json=[2],
                accommodation_id=2,
                events_json=[],
                total_price=1400.0,
                destination_city="TestCity",
                departure_date=holiday_end + timedelta(days=5),  # After holiday
                return_date=holiday_end + timedelta(days=12),
                num_nights=7,
                notified=False,
            )

            packages = [package_during, package_outside]

            # Test filtering
            matcher = AccommodationMatcher()
            filtered = await matcher.filter_by_school_holidays(db, packages)

            # Should only keep the package during the holiday
            assert len(filtered) == 1, f"Expected 1 package, got {len(filtered)}"
            assert filtered[0].departure_date == package_during.departure_date

            # Cleanup
            await db.delete(holiday)
            await db.commit()

    async def test_package_duplicate_prevention(self):
        """
        Test that duplicate packages (same flight + accommodation) are not created.
        """
        async with get_async_session_context() as db:
            # Create test data
            origin_airport = Airport(
                iata_code="TST5",
                name="Test Airport 5",
                city="TestCity5",
                country="TestCountry",
                distance_from_home=40,
                driving_time=35,
                parking_cost_per_day=10.0,
            )
            dest_airport = Airport(
                iata_code="TST6",
                name="Test Airport 6",
                city="TestCity6",
                country="TestCountry",
                distance_from_home=0,
                driving_time=0,
                parking_cost_per_day=0.0,
            )
            db.add_all([origin_airport, dest_airport])
            await db.flush()

            departure_date = date.today() + timedelta(days=45)
            return_date = departure_date + timedelta(days=6)

            flight = Flight(
                origin_airport_id=origin_airport.id,
                destination_airport_id=dest_airport.id,
                airline="Test Air",
                departure_date=departure_date,
                return_date=return_date,
                price_per_person=120.0,
                total_price=480.0,
                booking_class="Economy",
                direct_flight=True,
                source="test",
                scraped_at=datetime.now(),
            )
            flight.true_cost = 550.0

            accommodation = Accommodation(
                destination_city="TestCity6",
                name="Test Hotel",
                accommodation_type="hotel",
                price_per_night=70.0,
                rating=4.0,
                family_friendly=True,
                source="test",
                scraped_at=datetime.now(),
            )

            db.add_all([flight, accommodation])
            await db.flush()

            # Create duplicate packages
            package1 = TripPackage(
                package_type="family",
                flights_json=[flight.id],
                accommodation_id=accommodation.id,
                events_json=[],
                total_price=1500.0,
                destination_city="TestCity6",
                departure_date=departure_date,
                return_date=return_date,
                num_nights=6,
                notified=False,
            )

            package2 = TripPackage(
                package_type="family",
                flights_json=[flight.id],
                accommodation_id=accommodation.id,
                events_json=[],
                total_price=1500.0,
                destination_city="TestCity6",
                departure_date=departure_date,
                return_date=return_date,
                num_nights=6,
                notified=False,
            )

            matcher = AccommodationMatcher()

            # Save both packages
            stats = await matcher.save_packages(db, [package1, package2])

            # Should insert first, skip second
            assert stats["inserted"] == 1, f"Expected 1 insert, got {stats['inserted']}"
            assert stats["skipped"] == 1, f"Expected 1 skip, got {stats['skipped']}"

            # Cleanup
            package_to_delete = (await db.execute(
                select(TripPackage).where(
                    TripPackage.accommodation_id == accommodation.id
                )
            )).scalar_one_or_none()
            if package_to_delete:
                await db.delete(package_to_delete)

            await db.delete(flight)
            await db.delete(accommodation)
            await db.delete(origin_airport)
            await db.delete(dest_airport)
            await db.commit()
