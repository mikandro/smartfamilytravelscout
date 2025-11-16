"""
Example script demonstrating EventBrite API integration.

This script shows how to:
1. Search for events in a city
2. Categorize events
3. Save events to database
4. Track API usage

Usage:
    python examples/eventbrite_example.py
"""

import asyncio
import os
from datetime import date, timedelta

from app.scrapers.eventbrite_scraper import EventBriteClient


async def main():
    """Main example function."""
    # Get API key from environment
    api_key = os.getenv("EVENTBRITE_API_KEY")
    if not api_key:
        print("ERROR: EVENTBRITE_API_KEY not set in environment")
        print("Please set your EventBrite API key:")
        print("  export EVENTBRITE_API_KEY=your_api_key_here")
        return

    # Initialize client
    print("=" * 60)
    print("EventBrite API Integration Example")
    print("=" * 60)
    print()

    # Search parameters
    city = "Prague"
    start_date = date.today() + timedelta(days=30)  # 30 days from now
    end_date = start_date + timedelta(days=10)  # 10-day window

    print(f"Searching for events in {city}")
    print(f"Date range: {start_date} to {end_date}")
    print()

    # Use client as async context manager
    async with EventBriteClient(api_key=api_key) as client:
        # Example 1: Search for family events
        print("Example 1: Searching for family events...")
        print("-" * 60)

        family_events = await client.search_events(
            city=city,
            start_date=start_date,
            end_date=end_date,
            categories=["family"],
            max_results=5,
        )

        print(f"Found {len(family_events)} family events:")
        for i, event in enumerate(family_events, 1):
            print(f"\n{i}. {event['title']}")
            print(f"   Date: {event['event_date']}")
            print(f"   Category: {event['category']}")
            print(f"   Price: {event['price_range']}")
            print(f"   URL: {event['url']}")

        print("\n" + "=" * 60)
        print()

        # Example 2: Search for all event types
        print("Example 2: Searching for all event types...")
        print("-" * 60)

        all_events = await client.search_events(
            city=city,
            start_date=start_date,
            end_date=end_date,
            max_results=10,
        )

        print(f"Found {len(all_events)} events total")
        print()

        # Categorize and count
        categories = {}
        for event in all_events:
            cat = event["category"]
            categories[cat] = categories.get(cat, 0) + 1

        print("Event breakdown by category:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count} events")

        print("\n" + "=" * 60)
        print()

        # Example 3: Price analysis
        print("Example 3: Price range analysis...")
        print("-" * 60)

        price_ranges = {}
        for event in all_events:
            price = event["price_range"]
            price_ranges[price] = price_ranges.get(price, 0) + 1

        print("Events by price range:")
        for price, count in sorted(price_ranges.items()):
            print(f"  {price}: {count} events")

        print("\n" + "=" * 60)
        print()

        # Example 4: Save to database (optional)
        print("Example 4: Saving events to database...")
        print("-" * 60)

        # Uncomment to actually save to database
        # saved_count = await client.save_to_database(all_events)
        # print(f"Saved {saved_count} new events to database")

        print("Database saving is commented out in this example.")
        print("Uncomment the lines above to save events.")

        print("\n" + "=" * 60)
        print()

        # Example 5: API usage tracking
        print("Example 5: API usage tracking...")
        print("-" * 60)

        calls_made = client.get_call_count()
        global_calls = EventBriteClient.get_global_call_count()

        print(f"API calls made by this client: {calls_made}")
        print(f"Total API calls today: {global_calls}")
        print(f"Remaining calls today: {1000 - global_calls}")

        if global_calls > 900:
            print("\n⚠️  WARNING: Approaching daily rate limit!")

        print("\n" + "=" * 60)
        print()

    print("✓ Example completed successfully!")
    print()
    print("Next steps:")
    print("  1. Review the categorized events above")
    print("  2. Uncomment database saving in Example 4")
    print("  3. Integrate with AI scoring for relevance")
    print("  4. Add to scheduled tasks for automatic scraping")
    print()


if __name__ == "__main__":
    asyncio.run(main())
