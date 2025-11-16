"""
Example script demonstrating Skyscanner web scraper usage.

This script shows how to:
1. Initialize the SkyscannerScraper
2. Scrape flights for a specific route
3. Save results to the database
4. Handle errors gracefully

Usage:
    poetry run python examples/skyscanner_example.py
"""

import asyncio
import logging
from datetime import date, timedelta

from app.scrapers import SkyscannerScraper, RateLimitExceededError, CaptchaDetectedError

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


async def example_basic_scrape():
    """Basic example: Scrape a single route."""
    logger.info("=" * 60)
    logger.info("EXAMPLE 1: Basic Scrape")
    logger.info("=" * 60)

    # Use future dates (60 days from now)
    today = date.today()
    departure = today + timedelta(days=60)
    return_date = departure + timedelta(days=7)

    logger.info(f"Searching for flights:")
    logger.info(f"  Route: MUC → LIS")
    logger.info(f"  Departure: {departure}")
    logger.info(f"  Return: {return_date}")

    # Initialize scraper and scrape route
    async with SkyscannerScraper(headless=True) as scraper:
        try:
            flights = await scraper.scrape_route(
                origin="MUC", destination="LIS", departure_date=departure, return_date=return_date
            )

            logger.info(f"\n✓ Found {len(flights)} flights!")

            # Display results
            if flights:
                logger.info("\nTop 5 flights:")
                for i, flight in enumerate(flights[:5], 1):
                    logger.info(
                        f"  {i}. {flight['airline']}: €{flight['price_per_person']:.2f} per person "
                        f"({'Direct' if flight.get('direct_flight') else 'With stops'})"
                    )

                    if flight.get("departure_time") and flight.get("arrival_time"):
                        logger.info(
                            f"     Times: {flight['departure_time']} → {flight['arrival_time']}"
                        )

                # Save to database
                logger.info("\nSaving flights to database...")
                await scraper.save_to_database(
                    flights=flights,
                    origin="MUC",
                    destination="LIS",
                    departure_date=departure,
                    return_date=return_date,
                )
                logger.info("✓ Flights saved to database!")

        except CaptchaDetectedError:
            logger.error("❌ CAPTCHA detected. Please try again later.")
        except RateLimitExceededError as e:
            logger.error(f"❌ Rate limit exceeded: {e}")
        except Exception as e:
            logger.error(f"❌ Error scraping flights: {e}", exc_info=True)


async def example_one_way_flight():
    """Example: Scrape one-way flights."""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 2: One-Way Flight")
    logger.info("=" * 60)

    today = date.today()
    departure = today + timedelta(days=45)

    logger.info(f"Searching for one-way flights:")
    logger.info(f"  Route: MUC → BCN")
    logger.info(f"  Departure: {departure}")

    async with SkyscannerScraper(headless=True) as scraper:
        try:
            flights = await scraper.scrape_route(
                origin="MUC",
                destination="BCN",
                departure_date=departure,
                return_date=None,  # No return date = one-way
            )

            logger.info(f"\n✓ Found {len(flights)} one-way flights!")

            if flights:
                # Find cheapest flight
                cheapest = min(flights, key=lambda f: f["price_per_person"])
                logger.info(f"\nCheapest flight:")
                logger.info(
                    f"  {cheapest['airline']}: €{cheapest['price_per_person']:.2f} per person"
                )

        except Exception as e:
            logger.error(f"❌ Error: {e}")


async def example_multiple_routes():
    """Example: Scrape multiple routes with rate limiting."""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 3: Multiple Routes (with delays)")
    logger.info("=" * 60)

    today = date.today()
    departure = today + timedelta(days=60)

    # Multiple destination options
    routes = [
        ("MUC", "LIS", "Lisbon"),
        ("MUC", "BCN", "Barcelona"),
        ("MUC", "MAD", "Madrid"),
    ]

    async with SkyscannerScraper(headless=True) as scraper:
        all_results = []

        for origin, dest, city_name in routes[:2]:  # Limit to 2 to avoid rate limits
            logger.info(f"\nSearching for flights to {city_name}...")

            try:
                flights = await scraper.scrape_route(
                    origin=origin, destination=dest, departure_date=departure
                )

                logger.info(f"  ✓ Found {len(flights)} flights to {city_name}")

                if flights:
                    cheapest_price = min(f["price_per_person"] for f in flights)
                    logger.info(f"  Cheapest: €{cheapest_price:.2f} per person")

                    all_results.append(
                        {"destination": city_name, "flights": flights, "cheapest": cheapest_price}
                    )

            except RateLimitExceededError as e:
                logger.warning(f"  ⚠ Rate limit hit: {e}")
                break
            except Exception as e:
                logger.error(f"  ❌ Error: {e}")

        # Compare destinations
        if all_results:
            logger.info("\n" + "=" * 60)
            logger.info("PRICE COMPARISON:")
            logger.info("=" * 60)

            for result in sorted(all_results, key=lambda r: r["cheapest"]):
                logger.info(
                    f"  {result['destination']}: from €{result['cheapest']:.2f} per person"
                )


async def example_error_handling():
    """Example: Demonstrate error handling."""
    logger.info("\n" + "=" * 60)
    logger.info("EXAMPLE 4: Error Handling")
    logger.info("=" * 60)

    scraper = SkyscannerScraper(headless=True)

    # Example 1: Invalid airport code
    logger.info("\nTest 1: Invalid airport code")
    try:
        async with scraper:
            flights = await scraper.scrape_route(
                origin="XXX", destination="YYY", departure_date=date.today() + timedelta(days=60)
            )
            logger.info(f"  Result: {len(flights)} flights (may be 0)")
    except Exception as e:
        logger.error(f"  ❌ Error: {e}")

    # Example 2: Rate limiting
    logger.info("\nTest 2: Rate limiting check")
    try:
        # Check current rate limit status
        scraper._check_rate_limit()
        logger.info("  ✓ Rate limit OK")
    except RateLimitExceededError as e:
        logger.warning(f"  ⚠ {e}")


async def main():
    """Run all examples."""
    logger.info("\n")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + " " * 10 + "Skyscanner Web Scraper Examples" + " " * 16 + "║")
    logger.info("╚" + "═" * 58 + "╝")

    try:
        # Run examples
        await example_basic_scrape()
        await example_one_way_flight()
        await example_multiple_routes()
        await example_error_handling()

        logger.info("\n" + "=" * 60)
        logger.info("All examples completed!")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.info("\n\nExamples interrupted by user.")
    except Exception as e:
        logger.error(f"\nFatal error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
