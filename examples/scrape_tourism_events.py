#!/usr/bin/env python3
"""
Example script for scraping tourism events from official tourism websites.

This script demonstrates how to use the tourism scrapers to find local events
not on EventBrite and save them to the database.

Usage:
    python examples/scrape_tourism_events.py
"""

import asyncio
import logging
from datetime import date, timedelta

from app.database import get_async_session_context
from app.scrapers import (
    BarcelonaTourismScraper,
    LisbonTourismScraper,
    PragueTourismScraper,
    save_events_to_db,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def scrape_all_cities():
    """
    Scrape events from all supported cities and save to database.
    """
    # Define date range (next 30 days)
    start_date = date.today()
    end_date = start_date + timedelta(days=30)

    logger.info(f"Scraping events from {start_date} to {end_date}")

    # Initialize scrapers
    scrapers = [
        LisbonTourismScraper(),
        PragueTourismScraper(),
        BarcelonaTourismScraper(),
    ]

    all_events = []

    try:
        # Scrape events from each city
        for scraper in scrapers:
            logger.info(f"Starting scraper for {scraper.CITY_NAME}...")

            try:
                async with scraper:
                    events = await scraper.scrape_events(start_date, end_date)
                    logger.info(f"Found {len(events)} events in {scraper.CITY_NAME}")
                    all_events.extend(events)

            except Exception as e:
                logger.error(f"Error scraping {scraper.CITY_NAME}: {e}", exc_info=True)
                continue

        # Save events to database
        if all_events:
            logger.info(f"Saving {len(all_events)} total events to database...")

            async with get_async_session_context() as session:
                saved_count = await save_events_to_db(
                    all_events,
                    session,
                    deduplicate=True
                )

            logger.info(f"Successfully saved {saved_count} events to database")
        else:
            logger.warning("No events found to save")

    except Exception as e:
        logger.error(f"Error in scraping process: {e}", exc_info=True)
        raise

    return all_events


async def scrape_single_city(city: str, days_ahead: int = 30):
    """
    Scrape events from a single city.

    Args:
        city: City name ('lisbon', 'prague', or 'barcelona')
        days_ahead: Number of days ahead to scrape (default: 30)
    """
    start_date = date.today()
    end_date = start_date + timedelta(days=days_ahead)

    # Map city names to scrapers
    scraper_map = {
        'lisbon': LisbonTourismScraper,
        'prague': PragueTourismScraper,
        'barcelona': BarcelonaTourismScraper,
    }

    scraper_class = scraper_map.get(city.lower())
    if not scraper_class:
        raise ValueError(f"Unknown city: {city}. Choose from: {list(scraper_map.keys())}")

    logger.info(f"Scraping {city.capitalize()} events from {start_date} to {end_date}")

    async with scraper_class() as scraper:
        events = await scraper.scrape_events(start_date, end_date)

    logger.info(f"Found {len(events)} events")

    # Print events
    for event in events:
        logger.info(
            f"  - {event['title']} on {event['event_date']} "
            f"({event['category']}, {event['price_range']})"
        )

    # Save to database
    if events:
        async with get_async_session_context() as session:
            saved_count = await save_events_to_db(events, session, deduplicate=True)

        logger.info(f"Saved {saved_count} events to database")

    return events


async def main():
    """Main entry point."""
    import sys

    if len(sys.argv) > 1:
        # Scrape specific city
        city = sys.argv[1]
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        await scrape_single_city(city, days)
    else:
        # Scrape all cities
        await scrape_all_cities()


if __name__ == "__main__":
    asyncio.run(main())
