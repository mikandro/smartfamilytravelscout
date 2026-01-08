"""
Example usage of the Ryanair scraper.

This script demonstrates various ways to use the RyanairScraper:
1. Basic scraping (standalone)
2. Scraping with database integration
3. Handling errors and rate limits
4. Processing scraped data

IMPORTANT: Run this during off-peak hours (2-6 AM local time) to avoid detection.
"""

import asyncio
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scrapers.ryanair_scraper import (
    CaptchaDetected,
    RateLimitExceeded,
    RyanairScraper,
)
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def example_1_basic_scraping():
    """
    Example 1: Basic scraping without database.

    This shows how to scrape flights and work with the raw data.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Basic Scraping")
    print("=" * 60 + "\n")

    scraper = RyanairScraper()

    try:
        # Scrape FMM to Barcelona
        flights = await scraper.scrape_route(
            origin="FMM",  # Memmingen (budget airport near Munich)
            destination="BCN",  # Barcelona
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        print(f"\nFound {len(flights)} flight options:\n")

        for i, flight in enumerate(flights, 1):
            print(f"Flight {i}:")
            print(f"  Price: €{flight.get('price', 'N/A')}")
            print(f"  Departure: {flight.get('departure_time', 'N/A')}")
            print(f"  Return: {flight.get('return_time', 'N/A')}")
            print(f"  Direct: {flight.get('direct', 'N/A')}")
            print(f"  Booking: {flight.get('booking_url', 'N/A')}")
            print()

        return flights

    except RateLimitExceeded as e:
        print(f"\n⚠️  Rate limit exceeded: {e}")
        print("Please try again tomorrow.")

    except CaptchaDetected as e:
        print(f"\n⚠️  CAPTCHA detected: {e}")
        print("The scraper is working correctly by detecting and avoiding CAPTCHAs.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Scraping failed")

    finally:
        await scraper.close()


async def example_2_multiple_routes():
    """
    Example 2: Scrape multiple routes.

    Demonstrates scraping multiple destinations while respecting rate limits.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Multiple Routes")
    print("=" * 60 + "\n")

    routes = [
        ("FMM", "BCN", "Barcelona"),  # Memmingen to Barcelona
        ("FMM", "PMI", "Palma de Mallorca"),  # Memmingen to Palma
        ("MUC", "LIS", "Lisbon"),  # Munich to Lisbon
    ]

    # Dates for next month
    departure = date.today() + timedelta(days=30)
    return_date = departure + timedelta(days=7)

    scraper = RyanairScraper()
    all_results = {}

    try:
        for origin, dest, name in routes:
            print(f"\nScraping {origin} → {dest} ({name})...")

            try:
                flights = await scraper.scrape_route(
                    origin=origin,
                    destination=dest,
                    departure_date=departure,
                    return_date=return_date,
                )

                all_results[name] = flights
                print(f"  ✓ Found {len(flights)} options")

                # Find cheapest
                if flights:
                    cheapest = min(flights, key=lambda f: f.get("price", float("inf")))
                    print(f"  💰 Cheapest: €{cheapest.get('price')}")

            except RateLimitExceeded:
                print(f"  ⚠️  Rate limit reached at {name}")
                break

            except Exception as e:
                print(f"  ❌ Error for {name}: {e}")
                continue

        # Summary
        print("\n" + "-" * 60)
        print("SUMMARY")
        print("-" * 60)

        for destination, flights in all_results.items():
            if flights:
                cheapest = min(flights, key=lambda f: f.get("price", float("inf")))
                print(f"{destination:20s}: €{cheapest.get('price'):6.2f}")
            else:
                print(f"{destination:20s}: No flights found")

    finally:
        await scraper.close()


async def example_3_with_database():
    """
    Example 3: Scrape and save to database.

    Shows how to integrate scraping with database storage.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Scraping with Database")
    print("=" * 60 + "\n")

    try:
        from app.database import get_async_session_context
        from app.scrapers.ryanair_db_helper import scrape_and_save_route

        async with get_async_session_context() as db:
            flights = await scrape_and_save_route(
                db=db,
                origin="FMM",
                destination="BCN",
                departure_date=date(2025, 12, 20),
                return_date=date(2025, 12, 27),
            )

            print(f"\n✓ Saved {len(flights)} flights to database")

            for flight in flights:
                print(f"  - {flight.route}: €{flight.price_per_person}/person")

    except ImportError:
        print("⚠️  Database not configured. Skipping this example.")
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception("Database integration failed")


async def example_4_error_handling():
    """
    Example 4: Robust error handling.

    Shows how to handle various error conditions gracefully.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Error Handling")
    print("=" * 60 + "\n")

    scraper = RyanairScraper()

    try:
        print("Attempting to scrape with comprehensive error handling...\n")

        flights = await scraper.scrape_route(
            origin="FMM",
            destination="BCN",
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        if flights:
            print(f"✓ Success! Found {len(flights)} flights")
        else:
            print("⚠️  No flights found for this route/date combination")

    except RateLimitExceeded as e:
        print("⚠️  RATE LIMIT EXCEEDED")
        print(f"   {e}")
        print("   Recommendation: Wait until tomorrow")

    except CaptchaDetected as e:
        print("⚠️  CAPTCHA DETECTED")
        print(f"   {e}")
        print("   Recommendation: The scraper correctly detected anti-bot measures")
        print("   and aborted to avoid triggering further security.")

    except TimeoutError as e:
        print("⏱️  TIMEOUT")
        print(f"   {e}")
        print("   Recommendation: Try again later or check your internet connection")

    except Exception as e:
        print("❌ UNEXPECTED ERROR")
        print(f"   {e}")
        print(f"   Error type: {type(e).__name__}")
        logger.exception("Unexpected error during scraping")

    finally:
        await scraper.close()
        print("\n✓ Browser closed cleanly")


async def example_5_check_rate_limit():
    """
    Example 5: Check rate limit status.

    Shows how to check remaining scrapes for today.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Rate Limit Status")
    print("=" * 60 + "\n")

    import json
    from pathlib import Path

    rate_file = Path("/tmp/ryanair_rate_limit.json")

    if rate_file.exists():
        with open(rate_file, "r") as f:
            data = json.load(f)

        today = str(date.today())

        if data.get("date") == today:
            used = data.get("count", 0)
            remaining = RyanairScraper.MAX_DAILY_SEARCHES - used

            print(f"Today's date: {today}")
            print(f"Searches used: {used}/{RyanairScraper.MAX_DAILY_SEARCHES}")
            print(f"Searches remaining: {remaining}")

            if remaining > 0:
                print(f"\n✓ You can make {remaining} more search(es) today")
            else:
                print("\n⚠️  Daily limit reached. Please try again tomorrow.")
        else:
            print(f"Last scraped: {data.get('date', 'Never')}")
            print(f"✓ You can make {RyanairScraper.MAX_DAILY_SEARCHES} searches today")
    else:
        print("✓ No scraping history found.")
        print(f"You can make {RyanairScraper.MAX_DAILY_SEARCHES} searches today")


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("RYANAIR SCRAPER - EXAMPLE USAGE")
    print("=" * 60)
    print("\nThis script demonstrates various ways to use the Ryanair scraper.")
    print("The scraper implements aggressive anti-detection measures and")
    print("rate limiting to avoid triggering Ryanair's security systems.")
    print("\n⚠️  IMPORTANT: Run during off-peak hours (2-6 AM) for best results")
    print("=" * 60)

    # Check current time
    current_hour = datetime.now().hour
    if 2 <= current_hour < 6:
        print("\n✓ Good timing! Running during off-peak hours.")
    else:
        print(
            f"\n⚠️  Warning: Current time is {datetime.now().strftime('%H:%M')} "
            f"(off-peak is 2-6 AM)"
        )
        print("   Consider running during off-peak hours to reduce detection risk.")

    # Check rate limit first
    await example_5_check_rate_limit()

    # Ask user which example to run
    print("\n" + "-" * 60)
    print("Select an example to run:")
    print("-" * 60)
    print("1. Basic scraping (single route)")
    print("2. Multiple routes")
    print("3. Scraping with database integration")
    print("4. Error handling demonstration")
    print("5. Rate limit status (already shown above)")
    print("0. Exit")
    print("-" * 60)

    choice = input("\nEnter your choice (0-5): ").strip()

    if choice == "1":
        await example_1_basic_scraping()
    elif choice == "2":
        await example_2_multiple_routes()
    elif choice == "3":
        await example_3_with_database()
    elif choice == "4":
        await example_4_error_handling()
    elif choice == "5":
        await example_5_check_rate_limit()
    elif choice == "0":
        print("\nGoodbye!")
    else:
        print("\n❌ Invalid choice. Please run again and select 0-5.")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user. Exiting...")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        logger.exception("Fatal error in example script")
