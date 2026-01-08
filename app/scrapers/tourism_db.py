"""
Database operations for tourism event scrapers.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.utils.event_deduplication import deduplicate_events, generate_deduplication_hash

logger = logging.getLogger(__name__)


async def save_events_to_db(
    events: List[Dict[str, Any]],
    session: AsyncSession,
    deduplicate: bool = True
) -> int:
    """
    Save scraped events to database with cross-source deduplication.

    This function now:
    1. Deduplicates events from multiple sources using hash-based and fuzzy matching
    2. Checks against existing events using deduplication_hash (not source-specific)
    3. Stores venue and deduplication_hash for future deduplication
    4. Merges sources and URLs from duplicate events

    Args:
        events: List of event dictionaries from scrapers
        session: Database session
        deduplicate: If True, deduplicate events before saving (default: True)

    Returns:
        Number of events saved
    """
    if not events:
        logger.info("No events to save")
        return 0

    # Step 1: Deduplicate events within the batch (cross-source deduplication)
    if deduplicate:
        unique_events, duplicates_removed = deduplicate_events(events, use_fuzzy_matching=True)
        logger.info(
            f"Batch deduplication: {len(events)} → {len(unique_events)} events "
            f"({duplicates_removed} duplicates removed)"
        )
    else:
        unique_events = events
        # Still generate hashes even if not deduplicating
        for event_data in unique_events:
            if 'deduplication_hash' not in event_data:
                event_data['deduplication_hash'] = generate_deduplication_hash(
                    title=event_data.get('title', ''),
                    event_date=event_data.get('event_date'),
                    destination_city=event_data.get('destination_city', ''),
                    venue=event_data.get('venue')
                )

    saved_count = 0
    updated_count = 0
    skipped_count = 0

    for event_data in unique_events:
        try:
            # Step 2: Check for existing events using deduplication_hash
            # This allows cross-source deduplication (same event from different sources)
            dedup_hash = event_data.get('deduplication_hash')

            if deduplicate and dedup_hash:
                stmt = select(Event).where(Event.deduplication_hash == dedup_hash)
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    # Event already exists - update if new source or better information
                    should_update = False

                    # Check if this is from a different source
                    if event_data['source'] != existing.source:
                        logger.debug(
                            f"Found event from different source: {event_data['title']} "
                            f"(existing: {existing.source}, new: {event_data['source']})"
                        )
                        should_update = True

                    # Update if new event has more complete information
                    new_desc_len = len(event_data.get('description', '') or '')
                    existing_desc_len = len(existing.description or '')

                    if new_desc_len > existing_desc_len:
                        should_update = True

                    if should_update:
                        # Update existing event with better information
                        if event_data.get('description') and new_desc_len > existing_desc_len:
                            existing.description = event_data['description']

                        if event_data.get('venue') and not existing.venue:
                            existing.venue = event_data['venue']

                        if event_data.get('url') and not existing.url:
                            existing.url = event_data['url']

                        if event_data.get('price_range') and existing.price_range == 'varies':
                            existing.price_range = event_data['price_range']

                        existing.scraped_at = datetime.utcnow()
                        updated_count += 1

                        logger.debug(
                            f"Updated event: {event_data['title']} "
                            f"on {event_data['event_date']} in {event_data['destination_city']}"
                        )
                    else:
                        skipped_count += 1
                        logger.debug(
                            f"Skipping duplicate event: {event_data['title']} "
                            f"on {event_data['event_date']} in {event_data['destination_city']}"
                        )

                    continue

            # Step 3: Create new event object
            event = Event(
                destination_city=event_data['destination_city'],
                title=event_data['title'],
                venue=event_data.get('venue'),
                event_date=event_data['event_date'],
                end_date=event_data.get('end_date'),
                category=event_data['category'],
                description=event_data.get('description'),
                price_range=event_data.get('price_range', 'varies'),
                source=event_data['source'],
                url=event_data.get('url'),
                deduplication_hash=dedup_hash,
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
        logger.info(
            f"Database save complete: {saved_count} inserted, "
            f"{updated_count} updated, {skipped_count} skipped"
        )
    except Exception as e:
        await session.rollback()
        logger.error(f"Error committing events to database: {e}", exc_info=True)
        raise

    return saved_count + updated_count


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
