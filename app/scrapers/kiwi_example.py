#!/usr/bin/env python3
"""
Example usage script for Kiwi.com API scraper.

This script demonstrates how to use the KiwiClient to search for flights
and save them to the database.

Usage:
    # Search specific route
    python -m app.scrapers.kiwi_example --origin MUC --destination LIS

    # Search anywhere from origin
    python -m app.scrapers.kiwi_example --origin MUC --anywhere

    # Check rate limit status
    python -m app.scrapers.kiwi_example --check-limit
"""

import asyncio
import logging
import os
from datetime import date, timedelta

from app.scrapers.kiwi_scraper import KiwiClient, RateLimiter
from app.utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


async def example_search_specific_route():
    """
    Example: Search for flights on a specific route.

    Searches for flights from Munich (MUC) to Lisbon (LIS)
    for a 7-day trip starting 60 days from now.
    """
    logger.info("=" * 80)
    logger.info("EXAMPLE 1: Search specific route (MUC → LIS)")
    logger.info("=" * 80)

    # Initialize client
    api_key = os.getenv("KIWI_API_KEY")
    if not api_key:
        logger.error("KIWI_API_KEY environment variable not set")
        return

    client = KiwiClient(api_key=api_key)

    # Define search parameters
    origin = "MUC"
    destination = "LIS"
    departure_date = date.today() + timedelta(days=60)
    return_date = departure_date + timedelta(days=7)

    logger.info(f"Searching: {origin} → {destination}")
    logger.info(f"Dates: {departure_date} to {return_date}")
    logger.info(f"Passengers: 2 adults + 2 children")

    # Search flights
    flights = await client.search_flights(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        adults=2,
        children=2,
    )

    logger.info(f"\n✓ Found {len(flights)} flights")

    # Display results
    if flights:
        logger.info("\nTop 5 flights:")
        for i, flight in enumerate(flights[:5], 1):
            logger.info(
                f"\n{i}. {flight['origin_airport']} → {flight['destination_airport']} "
                f"({flight['airline']})"
            )
            logger.info(f"   Departure: {flight['departure_date']} {flight['departure_time']}")
            logger.info(f"   Return: {flight['return_date']} {flight['return_time']}")
            logger.info(
                f"   Price: €{flight['price_per_person']}/person (€{flight['total_price']} total)"
            )
            logger.info(f"   Direct: {flight['direct_flight']}")
            logger.info(f"   Book: {flight['booking_url']}")

        # Save to database
        logger.info("\nSaving flights to database...")
        stats = await client.save_to_database(flights)
        logger.info(
            f"✓ Database save complete: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {stats['skipped']} skipped"
        )
    else:
        logger.warning("No flights found")


async def example_search_anywhere():
    """
    Example: Search for flights to anywhere from origin.

    Searches for flights from Munich (MUC) to any destination,
    useful for finding travel deals.
    """
    logger.info("\n" + "=" * 80)
    logger.info("EXAMPLE 2: Search anywhere from MUC")
    logger.info("=" * 80)

    # Initialize client
    api_key = os.getenv("KIWI_API_KEY")
    if not api_key:
        logger.error("KIWI_API_KEY environment variable not set")
        return

    client = KiwiClient(api_key=api_key)

    # Define search parameters
    origin = "MUC"
    departure_date = date.today() + timedelta(days=60)
    return_date = departure_date + timedelta(days=7)

    logger.info(f"Searching anywhere from: {origin}")
    logger.info(f"Dates: {departure_date} to {return_date}")

    # Search flights
    flights = await client.search_anywhere(
        origin=origin,
        departure_date=departure_date,
        return_date=return_date,
        limit=20,  # Limit to top 20 destinations
    )

    logger.info(f"\n✓ Found {len(flights)} destinations")

    # Display results grouped by destination
    if flights:
        destinations = {}
        for flight in flights:
            dest = flight["destination_city"]
            if dest not in destinations or flight["price_per_person"] < destinations[dest]["price_per_person"]:
                destinations[dest] = flight

        logger.info(f"\nTop 10 cheapest destinations:")
        sorted_dests = sorted(destinations.values(), key=lambda x: x["price_per_person"])

        for i, flight in enumerate(sorted_dests[:10], 1):
            logger.info(
                f"\n{i}. {flight['destination_city']} ({flight['destination_airport']}) - "
                f"€{flight['price_per_person']}/person"
            )
            logger.info(f"   Airline: {flight['airline']}")
            logger.info(f"   Direct: {flight['direct_flight']}")

        # Save to database
        logger.info("\nSaving flights to database...")
        stats = await client.save_to_database(flights)
        logger.info(
            f"✓ Database save complete: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {stats['skipped']} skipped"
        )
    else:
        logger.warning("No flights found")


async def example_multiple_airports():
    """
    Example: Search from multiple German airports.

    Searches from 4 German airports (MUC, FMM, NUE, SZG) to find
    the best deals to a destination.
    """
    logger.info("\n" + "=" * 80)
    logger.info("EXAMPLE 3: Search from multiple German airports")
    logger.info("=" * 80)

    # Initialize client
    api_key = os.getenv("KIWI_API_KEY")
    if not api_key:
        logger.error("KIWI_API_KEY environment variable not set")
        return

    client = KiwiClient(api_key=api_key)

    # German airports
    airports = ["MUC", "FMM", "NUE", "SZG"]
    destination = "BCN"  # Barcelona
    departure_date = date.today() + timedelta(days=60)
    return_date = departure_date + timedelta(days=7)

    all_flights = []

    logger.info(f"Searching from {len(airports)} airports to {destination}")
    logger.info(f"Airports: {', '.join(airports)}")

    # Search from each airport
    for origin in airports:
        logger.info(f"\nSearching from {origin}...")

        flights = await client.search_flights(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
        )

        logger.info(f"  Found {len(flights)} flights from {origin}")
        all_flights.extend(flights)

    # Find cheapest from each airport
    logger.info(f"\n✓ Total flights found: {len(all_flights)}")

    if all_flights:
        logger.info("\nCheapest flight from each airport:")

        airport_best = {}
        for flight in all_flights:
            origin = flight["origin_airport"]
            if origin not in airport_best or flight["price_per_person"] < airport_best[origin]["price_per_person"]:
                airport_best[origin] = flight

        for origin in airports:
            if origin in airport_best:
                flight = airport_best[origin]
                logger.info(
                    f"\n{origin}: €{flight['price_per_person']}/person "
                    f"({flight['airline']}, direct: {flight['direct_flight']})"
                )
            else:
                logger.info(f"\n{origin}: No flights found")

        # Save to database
        logger.info("\nSaving all flights to database...")
        stats = await client.save_to_database(all_flights)
        logger.info(
            f"✓ Database save complete: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {stats['skipped']} skipped"
        )


def check_rate_limit():
    """Check current rate limit status."""
    logger.info("\n" + "=" * 80)
    logger.info("RATE LIMIT STATUS")
    logger.info("=" * 80)

    rate_limiter = RateLimiter()
    remaining = rate_limiter.get_remaining_calls()
    used = 100 - remaining

    logger.info(f"API calls used this month: {used}/100")
    logger.info(f"Remaining calls: {remaining}/100")

    if remaining > 10:
        logger.info("✓ Plenty of API calls remaining")
    elif remaining > 0:
        logger.warning(f"⚠ Only {remaining} API calls remaining this month")
    else:
        logger.error("✗ Monthly rate limit exceeded!")


async def main():
    """Run example scripts."""
    import sys

    # Check command line arguments
    if "--check-limit" in sys.argv:
        check_rate_limit()
        return

    if "--anywhere" in sys.argv:
        await example_search_anywhere()
        return

    if "--multiple-airports" in sys.argv:
        await example_multiple_airports()
        return

    # Default: run all examples (WARNING: uses 3+ API calls)
    logger.info("Running all examples (will use multiple API calls)")
    logger.info("Use --check-limit to check rate limit without making calls")
    logger.info("Use --anywhere to search anywhere from MUC")
    logger.info("Use --multiple-airports to search from multiple airports\n")

    response = input("Continue with all examples? (y/n): ")
    if response.lower() != "y":
        logger.info("Cancelled")
        return

    await example_search_specific_route()
    await example_search_anywhere()
    # Uncomment to run all three (uses more API calls)
    # await example_multiple_airports()

    # Show final rate limit status
    check_rate_limit()


if __name__ == "__main__":
    asyncio.run(main())
