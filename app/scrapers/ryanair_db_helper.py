"""
Database helper for saving Ryanair scraped flights to the database.

This module provides functions to:
- Save scraped flights to the database
- Look up airport IDs from IATA codes
- Calculate total prices for family (2 adults + 2 children)
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.airport import Airport
from app.models.flight import Flight
from app.scrapers.ryanair_scraper import RyanairScraper
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def get_airport_id(db: AsyncSession, iata_code: str) -> Optional[int]:
    """
    Get airport ID from IATA code.

    Args:
        db: Database session
        iata_code: IATA airport code (e.g., 'FMM', 'BCN')

    Returns:
        Airport ID or None if not found
    """
    stmt = select(Airport.id).where(Airport.iata_code == iata_code.upper())
    result = await db.execute(stmt)
    airport_id = result.scalar_one_or_none()

    if not airport_id:
        logger.warning(f"Airport not found: {iata_code}")

    return airport_id


async def save_scraped_flights(
    db: AsyncSession,
    scraped_data: List[Dict],
) -> List[Flight]:
    """
    Save scraped Ryanair flights to database.

    Args:
        db: Database session
        scraped_data: List of scraped flight dictionaries from RyanairScraper

    Returns:
        List of saved Flight objects
    """
    saved_flights = []

    for flight_data in scraped_data:
        try:
            # Get airport IDs
            origin_id = await get_airport_id(db, flight_data["origin"])
            destination_id = await get_airport_id(db, flight_data["destination"])

            if not origin_id or not destination_id:
                logger.error(
                    f"Skipping flight: Airport not found "
                    f"({flight_data['origin']} or {flight_data['destination']})"
                )
                continue

            # Calculate total price (2 adults + 2 children)
            # Ryanair usually charges same price for adults and children
            price_per_person = flight_data.get("price", 0.0)
            total_price = price_per_person * 4

            # Parse times if available
            departure_time = None
            if flight_data.get("departure_time"):
                try:
                    departure_time = datetime.strptime(
                        flight_data["departure_time"], "%H:%M"
                    ).time()
                except (ValueError, TypeError):
                    logger.warning(f"Invalid departure time: {flight_data.get('departure_time')}")

            return_time = None
            if flight_data.get("return_time"):
                try:
                    return_time = datetime.strptime(flight_data["return_time"], "%H:%M").time()
                except (ValueError, TypeError):
                    logger.warning(f"Invalid return time: {flight_data.get('return_time')}")

            # Create Flight object
            flight = Flight(
                origin_airport_id=origin_id,
                destination_airport_id=destination_id,
                airline="Ryanair",
                departure_date=flight_data["departure_date"],
                departure_time=departure_time,
                return_date=flight_data.get("return_date"),
                return_time=return_time,
                price_per_person=price_per_person,
                total_price=total_price,
                booking_class=flight_data.get("booking_class", "Regular"),
                direct_flight=flight_data.get("direct", True),
                source="ryanair",
                booking_url=flight_data.get("booking_url"),
                scraped_at=flight_data.get("scraped_at", datetime.utcnow()),
            )

            db.add(flight)
            saved_flights.append(flight)

            logger.info(
                f"Saved flight: {flight_data['origin']} → {flight_data['destination']} "
                f"at €{price_per_person}/person"
            )

        except Exception as e:
            logger.error(f"Error saving flight: {e}")
            continue

    # Commit all flights
    try:
        await db.commit()
        logger.info(f"Successfully saved {len(saved_flights)} flights to database")
    except Exception as e:
        logger.error(f"Error committing flights: {e}")
        await db.rollback()
        raise

    return saved_flights


async def scrape_and_save_route(
    db: AsyncSession,
    origin: str,
    destination: str,
    departure_date,
    return_date,
) -> List[Flight]:
    """
    Scrape Ryanair route and save to database.

    This is a convenience function that combines scraping and saving.

    Args:
        db: Database session
        origin: Origin airport IATA code
        destination: Destination airport IATA code
        departure_date: Departure date
        return_date: Return date

    Returns:
        List of saved Flight objects
    """
    logger.info(f"Scraping and saving: {origin} → {destination}")

    scraper = RyanairScraper()

    try:
        # Scrape flights
        flights_data = await scraper.scrape_route(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
        )

        if not flights_data:
            logger.warning("No flights found")
            return []

        # Save to database
        saved_flights = await save_scraped_flights(db, flights_data)

        return saved_flights

    finally:
        await scraper.close()


# Example usage
async def example_usage():
    """Example of how to use the scraper with database."""
    from datetime import date

    from app.database import SessionLocal

    async with SessionLocal() as db:
        flights = await scrape_and_save_route(
            db=db,
            origin="FMM",
            destination="BCN",
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        print(f"Saved {len(flights)} flights to database")
        for flight in flights:
            print(f"  - {flight.route}: €{flight.price_per_person}/person")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
