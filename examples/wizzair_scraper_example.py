"""
Example usage of the WizzAir flight scraper.

This script demonstrates how to:
1. Search for flights using the WizzAir API
2. Save flights to the database
3. Handle errors and rate limiting

Prerequisites:
- Database must be set up and running
- Airports (MUC, CHI, etc.) must exist in the database
"""

import asyncio
import logging
from datetime import date, timedelta

from app.database import get_async_session_context
from app.scrapers import WizzAirRateLimitError, WizzAirScraper, scrape_wizzair_flights

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def example_1_simple_search():
    """Example 1: Simple flight search without saving to database."""
    logger.info("=" * 60)
    logger.info("Example 1: Simple Flight Search (API only)")
    logger.info("=" * 60)

    scraper = WizzAirScraper()

    # Search for round-trip flights from Munich to Chisinau
    departure_date = date.today() + timedelta(days=60)
    return_date = departure_date + timedelta(days=7)

    try:
        flights = await scraper.search_flights(
            origin="MUC",  # Munich
            destination="CHI",  # Chisinau, Moldova
            departure_date=departure_date,
            return_date=return_date,
            adult_count=2,
            child_count=2,
        )

        logger.info(f"Found {len(flights)} flight combinations")

        # Display the first few results
        for i, flight in enumerate(flights[:3], 1):
            logger.info(f"\nFlight {i}:")
            logger.info(f"  Route: {flight['origin']} -> {flight['destination']}")
            logger.info(f"  Departure: {flight['departure_date']} at {flight['departure_time']}")
            if flight.get("return_date"):
                logger.info(f"  Return: {flight['return_date']} at {flight['return_time']}")
            logger.info(f"  Price: €{flight['price']:.2f} per person")
            logger.info(f"  Total (4 people): €{flight['price'] * 4:.2f}")

    except WizzAirRateLimitError as e:
        logger.error(f"Rate limit exceeded: {e}")
        logger.info("Please wait 60 seconds before retrying")
    except Exception as e:
        logger.error(f"Error searching flights: {e}")


async def example_2_search_and_save():
    """Example 2: Search flights and save to database."""
    logger.info("=" * 60)
    logger.info("Example 2: Search and Save to Database")
    logger.info("=" * 60)

    departure_date = date.today() + timedelta(days=60)
    return_date = departure_date + timedelta(days=7)

    try:
        async with get_async_session_context() as db:
            # Use the convenience function to search and save in one step
            saved_flights = await scrape_wizzair_flights(
                db=db,
                origin="MUC",
                destination="CHI",
                departure_date=departure_date,
                return_date=return_date,
                adult_count=2,
                child_count=2,
            )

            logger.info(f"Successfully saved {len(saved_flights)} flights to database")

            # Display saved flights
            for flight in saved_flights:
                logger.info(
                    f"Saved: {flight.route} on {flight.departure_date}, "
                    f"€{flight.price_per_person:.2f}/person"
                )

    except Exception as e:
        logger.error(f"Error saving flights: {e}")


async def example_3_one_way_flight():
    """Example 3: Search for one-way flights."""
    logger.info("=" * 60)
    logger.info("Example 3: One-Way Flight Search")
    logger.info("=" * 60)

    scraper = WizzAirScraper()
    departure_date = date.today() + timedelta(days=30)

    try:
        flights = await scraper.search_flights(
            origin="VIE",  # Vienna
            destination="CHI",  # Chisinau
            departure_date=departure_date,
            return_date=None,  # One-way
            adult_count=1,
            child_count=0,
        )

        logger.info(f"Found {len(flights)} one-way flights")

        for i, flight in enumerate(flights[:5], 1):
            logger.info(
                f"{i}. {flight['origin']} -> {flight['destination']} "
                f"on {flight['departure_date']}, €{flight['price']:.2f}"
            )

    except Exception as e:
        logger.error(f"Error: {e}")


async def example_4_multiple_routes():
    """Example 4: Search multiple routes in parallel."""
    logger.info("=" * 60)
    logger.info("Example 4: Multiple Routes (Parallel Search)")
    logger.info("=" * 60)

    scraper = WizzAirScraper()
    departure_date = date.today() + timedelta(days=60)
    return_date = departure_date + timedelta(days=7)

    # Define routes to search
    routes = [
        ("MUC", "CHI", "Munich -> Chisinau"),
        ("VIE", "CHI", "Vienna -> Chisinau"),
        ("BTS", "CHI", "Bratislava -> Chisinau"),
    ]

    # Search all routes in parallel
    tasks = []
    for origin, dest, name in routes:
        task = scraper.search_flights(
            origin=origin,
            destination=dest,
            departure_date=departure_date,
            return_date=return_date,
        )
        tasks.append((name, task))

    # Wait for all searches to complete
    for route_name, task in tasks:
        try:
            flights = await task
            if flights:
                cheapest = min(flights, key=lambda f: f["price"])
                logger.info(
                    f"{route_name}: {len(flights)} flights found, "
                    f"cheapest: €{cheapest['price']:.2f}/person"
                )
            else:
                logger.info(f"{route_name}: No flights found")
        except Exception as e:
            logger.error(f"{route_name}: Error - {e}")


async def example_5_error_handling():
    """Example 5: Demonstrate error handling."""
    logger.info("=" * 60)
    logger.info("Example 5: Error Handling")
    logger.info("=" * 60)

    scraper = WizzAirScraper(timeout=5)  # Short timeout for demo

    try:
        # This might fail due to network issues, rate limiting, etc.
        flights = await scraper.search_flights(
            origin="XXX",  # Invalid airport code
            destination="YYY",
            departure_date=date.today() + timedelta(days=30),
        )
        logger.info(f"Found {len(flights)} flights")

    except WizzAirRateLimitError as e:
        logger.error(f"Rate limit error: {e}")
        logger.info("Recommended action: Wait 60 seconds and retry")

    except Exception as e:
        logger.error(f"General error: {type(e).__name__}: {e}")
        logger.info("Recommended action: Check logs and retry")


async def main():
    """Run all examples."""
    logger.info("WizzAir Scraper Examples")
    logger.info("=" * 60)

    # Run examples sequentially
    await example_1_simple_search()
    print("\n")

    # Uncomment to run other examples:
    # await example_2_search_and_save()  # Requires database
    # print("\n")

    await example_3_one_way_flight()
    print("\n")

    await example_4_multiple_routes()
    print("\n")

    await example_5_error_handling()


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
