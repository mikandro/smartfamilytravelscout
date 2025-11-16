"""
Example usage of the Itinerary Generator.

This script demonstrates how to generate detailed 3-day family itineraries
for high-scoring trip packages.

Usage:
    python examples/itinerary_generator_example.py
"""

import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from redis.asyncio import Redis

from app.ai import ClaudeClient
from app.ai.itinerary_generator import ItineraryGenerator
from app.config import settings
from app.database import AsyncSessionLocal
from app.models.accommodation import Accommodation
from app.models.trip_package import TripPackage


async def create_sample_trip_package(db) -> TripPackage:
    """Create a sample trip package for testing."""
    print("\n📦 Creating sample trip package...")

    # Create sample accommodation
    accommodation = Accommodation(
        destination_city="Lisbon",
        name="Family Apartment in Alfama",
        type="airbnb",
        bedrooms=2,
        price_per_night=85.00,
        family_friendly=True,
        has_kitchen=True,
        has_kids_club=False,
        rating=9.2,
        review_count=145,
        source="airbnb",
        url="https://airbnb.com/rooms/12345",
    )

    db.add(accommodation)
    await db.flush()

    # Create trip package
    departure_date = date.today() + timedelta(days=30)
    return_date = departure_date + timedelta(days=3)

    trip = TripPackage(
        package_type="family",
        flights_json={
            "outbound": {"flight_number": "TP123", "price": 400.00},
            "return": {"flight_number": "TP456", "price": 400.00},
        },
        accommodation_id=accommodation.id,
        events_json={
            "events": [
                {
                    "title": "Lisbon Oceanarium Family Tour",
                    "event_date": str(departure_date + timedelta(days=1)),
                    "category": "family",
                },
                {
                    "title": "Tram 28 Historic Ride",
                    "event_date": str(departure_date + timedelta(days=2)),
                    "category": "cultural",
                },
                {
                    "title": "Kids Beach Day at Cascais",
                    "event_date": str(departure_date + timedelta(days=2)),
                    "category": "family",
                },
            ]
        },
        destination_city="Lisbon",
        departure_date=departure_date,
        return_date=return_date,
        num_nights=3,
        total_price=1045.00,
        ai_score=85.5,
        ai_reasoning="Excellent value for money, great family activities, perfect weather.",
    )

    db.add(trip)
    await db.commit()
    await db.refresh(trip)
    await db.refresh(accommodation)

    trip.accommodation = accommodation

    print(f"✓ Created trip to {trip.destination_city}")
    print(f"  Dates: {trip.departure_date} to {trip.return_date}")
    print(f"  Score: {trip.ai_score}/100")
    print(f"  Price: €{trip.total_price}")

    return trip


async def example_basic_generation():
    """Example: Generate a basic itinerary."""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Basic Itinerary Generation")
    print("=" * 60)

    redis = Redis.from_url(str(settings.redis_url))

    async with AsyncSessionLocal() as db:
        # Setup clients
        claude_client = ClaudeClient(
            api_key=settings.anthropic_api_key,
            redis_client=redis,
            db_session=db,
        )

        generator = ItineraryGenerator(
            claude_client=claude_client,
            db_session=db,
            min_score_threshold=70.0,
        )

        # Create sample trip
        trip = await create_sample_trip_package(db)

        # Generate itinerary
        print("\n🗓️  Generating itinerary...")
        itinerary = await generator.generate_itinerary(
            trip_package=trip,
            save_to_db=True,
        )

        # Display results
        print("\n✅ Itinerary generated successfully!")
        print(f"\n📍 Destination: {trip.destination_city}")
        print(f"📅 Duration: {trip.duration_days} days")

        # Show day-by-day summary
        for day_num in range(1, 4):
            day_key = f"day_{day_num}"
            if day_key in itinerary:
                day = itinerary[day_key]
                print(f"\n--- Day {day_num} ---")
                print(f"☀️  Morning: {day['morning'][:100]}...")
                print(f"🌤️  Afternoon: {day['afternoon'][:100]}...")
                print(f"🌙 Evening: {day['evening'][:100]}...")
                print(f"🍽️  Breakfast: {day.get('breakfast_spot', 'N/A')}")
                print(f"🍽️  Lunch: {day.get('lunch_spot', 'N/A')}")
                print(f"🍽️  Dinner: {day.get('dinner_spot', 'N/A')}")

        # Show tips
        if "tips" in itinerary:
            print(f"\n💡 Tips ({len(itinerary['tips'])} total):")
            for i, tip in enumerate(itinerary["tips"][:3], 1):
                print(f"  {i}. {tip}")

        # Show packing essentials
        if "packing_essentials" in itinerary:
            print(f"\n🎒 Packing Essentials ({len(itinerary['packing_essentials'])} items):")
            for item in itinerary["packing_essentials"][:5]:
                print(f"  • {item}")

    await redis.close()


async def example_batch_generation():
    """Example: Generate itineraries for multiple trips."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Batch Itinerary Generation")
    print("=" * 60)

    redis = Redis.from_url(str(settings.redis_url))

    async with AsyncSessionLocal() as db:
        # Setup
        claude_client = ClaudeClient(
            api_key=settings.anthropic_api_key,
            redis_client=redis,
            db_session=db,
        )

        generator = ItineraryGenerator(
            claude_client=claude_client,
            db_session=db,
        )

        # Create multiple sample trips
        trips = []
        for i in range(3):
            trip = await create_sample_trip_package(db)
            trips.append(trip)

        # Generate itineraries in batch
        print(f"\n🗓️  Generating {len(trips)} itineraries...")

        results = await generator.generate_batch(
            trip_packages=trips,
            save_to_db=True,
            skip_errors=True,
        )

        print(f"\n✅ Generated {len(results)} itineraries successfully!")

        for trip_id, itinerary in results.items():
            print(f"  • Trip {trip_id}: {len(itinerary)} sections")

    await redis.close()


async def example_itinerary_summary():
    """Example: Get a brief summary of an itinerary."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Itinerary Summary")
    print("=" * 60)

    redis = Redis.from_url(str(settings.redis_url))

    async with AsyncSessionLocal() as db:
        # Setup
        claude_client = ClaudeClient(
            api_key=settings.anthropic_api_key,
            redis_client=redis,
            db_session=db,
        )

        generator = ItineraryGenerator(
            claude_client=claude_client,
            db_session=db,
        )

        # Create and generate
        trip = await create_sample_trip_package(db)
        await generator.generate_itinerary(trip_package=trip, save_to_db=True)

        # Get summary
        summary = await generator.get_itinerary_summary(trip)

        print("\n📋 Itinerary Summary:")
        print(summary)

    await redis.close()


async def example_force_generation():
    """Example: Force generate itinerary for low-scoring trip."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Force Generation (Low Score Trip)")
    print("=" * 60)

    redis = Redis.from_url(str(settings.redis_url))

    async with AsyncSessionLocal() as db:
        # Setup
        claude_client = ClaudeClient(
            api_key=settings.anthropic_api_key,
            redis_client=redis,
            db_session=db,
        )

        generator = ItineraryGenerator(
            claude_client=claude_client,
            db_session=db,
            min_score_threshold=70.0,
        )

        # Create low-scoring trip
        trip = await create_sample_trip_package(db)
        trip.ai_score = 65.0  # Below threshold
        await db.commit()

        print(f"\n⚠️  Trip score: {trip.ai_score} (below threshold: 70)")

        try:
            # This will fail without force
            print("\n🚫 Attempting generation without force flag...")
            await generator.generate_itinerary(trip_package=trip, force=False)
        except Exception as e:
            print(f"✓ Expected error: {str(e)[:80]}...")

        # Now try with force
        print("\n✅ Attempting generation WITH force flag...")
        itinerary = await generator.generate_itinerary(
            trip_package=trip, force=True, save_to_db=True
        )

        print(f"✓ Itinerary generated successfully (forced)!")
        print(f"  Sections: {len(itinerary)}")

    await redis.close()


async def example_json_export():
    """Example: Export itinerary as JSON."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: JSON Export")
    print("=" * 60)

    redis = Redis.from_url(str(settings.redis_url))

    async with AsyncSessionLocal() as db:
        # Setup
        claude_client = ClaudeClient(
            api_key=settings.anthropic_api_key,
            redis_client=redis,
            db_session=db,
        )

        generator = ItineraryGenerator(
            claude_client=claude_client,
            db_session=db,
        )

        # Create and generate
        trip = await create_sample_trip_package(db)
        itinerary = await generator.generate_itinerary(trip_package=trip)

        # Export as JSON
        json_output = json.dumps(itinerary, indent=2, default=str)

        print("\n📄 Itinerary JSON:")
        print(json_output[:500])
        print("...")
        print(f"\n✓ Full JSON is {len(json_output)} characters")

        # Save to file
        output_file = Path("/tmp/itinerary_example.json")
        output_file.write_text(json_output)
        print(f"✓ Saved to: {output_file}")

    await redis.close()


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("ITINERARY GENERATOR EXAMPLES")
    print("=" * 60)
    print("Generating detailed 3-day family itineraries")
    print("Optimized for families with young children (ages 3 & 6)")
    print("=" * 60)

    try:
        # Run examples (comment out to run specific ones)
        await example_basic_generation()
        # await example_batch_generation()
        # await example_itinerary_summary()
        # await example_force_generation()
        # await example_json_export()

        print("\n" + "=" * 60)
        print("✅ EXAMPLES COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Check for API key
    if not hasattr(settings, "anthropic_api_key") or not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not found in environment")
        print("Please set ANTHROPIC_API_KEY in your .env file")
        sys.exit(1)

    # Run examples
    asyncio.run(main())
