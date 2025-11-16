"""
Database operations for tourism event scrapers.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event

logger = logging.getLogger(__name__)


async def save_events_to_db(
    events: List[Dict[str, Any]],
    session: AsyncSession,
    deduplicate: bool = True
) -> int:
    """
    Save scraped events to database.

    Args:
        events: List of event dictionaries from scrapers
        session: Database session
        deduplicate: If True, skip events that already exist (based on title, city, date)

    Returns:
        Number of events saved
    """
    saved_count = 0

    for event_data in events:
        try:
            # Check for duplicates if requested
            if deduplicate:
                stmt = select(Event).where(
                    Event.destination_city == event_data['destination_city'],
                    Event.title == event_data['title'],
                    Event.event_date == event_data['event_date'],
                    Event.source == event_data['source']
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    logger.debug(
                        f"Skipping duplicate event: {event_data['title']} "
                        f"on {event_data['event_date']} in {event_data['destination_city']}"
                    )
                    continue

            # Create event object
            event = Event(
                destination_city=event_data['destination_city'],
                title=event_data['title'],
                event_date=event_data['event_date'],
                end_date=event_data.get('end_date'),
                category=event_data['category'],
                description=event_data.get('description'),
                price_range=event_data.get('price_range', 'varies'),
                source=event_data['source'],
                url=event_data.get('url'),
                scraped_at=datetime.utcnow(),
            )

            session.add(event)
            saved_count += 1

        except Exception as e:
            logger.error(f"Error saving event to database: {e}", exc_info=True)
            continue

    # Commit all events
    try:
        await session.commit()
        logger.info(f"Successfully saved {saved_count} events to database")
    except Exception as e:
        await session.rollback()
        logger.error(f"Error committing events to database: {e}", exc_info=True)
        raise

    return saved_count


async def get_events_by_city(
    city: str,
    session: AsyncSession,
    limit: int = 100
) -> List[Event]:
    """
    Get events for a specific city.

    Args:
        city: City name
        session: Database session
        limit: Maximum number of events to return

    Returns:
        List of Event objects
    """
    stmt = (
        select(Event)
        .where(Event.destination_city == city)
        .order_by(Event.event_date.asc())
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_events_by_source(
    source: str,
    session: AsyncSession,
    limit: int = 100
) -> List[Event]:
    """
    Get events from a specific source.

    Args:
        source: Source name (e.g., 'tourism_lisbon')
        session: Database session
        limit: Maximum number of events to return

    Returns:
        List of Event objects
    """
    stmt = (
        select(Event)
        .where(Event.source == source)
        .order_by(Event.event_date.asc())
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())
