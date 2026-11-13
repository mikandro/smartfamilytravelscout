"""
Dated local events for the weekend planner ("only this weekend").

Places are evergreen; events happen on particular days (children's theatre, a
Christmas market, a family workshop). They are scraped from local sources,
stored in the shared ``events`` table under the home city, and offered to the
planner for the days of the coming weekend.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.scraping_job import ScrapingJob
from app.utils.event_deduplication import generate_deduplication_hash

logger = logging.getLogger(__name__)

#: Sources the weekend planner reads. Trip events for other cities never match
#: because they are filtered by home city as well.
LOCAL_SOURCES = ("muenchen.de",)

#: An event whose run lasts longer than this is "ongoing" (an exhibition, a
#: market open for weeks) rather than something to catch this weekend.
ONGOING_AFTER_DAYS = 21


@dataclass
class RefreshResult:
    """Outcome of one scrape-and-store run."""

    source: str
    scraped: int
    created: int
    updated: int


def is_ongoing(event: Event, weekend_start: date) -> bool:
    """True when the event keeps running well beyond this weekend."""
    return event.end_date is not None and event.end_date > weekend_start + timedelta(
        days=ONGOING_AFTER_DAYS
    )


async def save_local_events(db: AsyncSession, events: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    """
    Insert or refresh scraped local events.

    Events are matched on the shared deduplication hash (title, venue, day,
    city). An existing row gets the fresh showtimes, run end date, URL and
    price, and the description when the new one is longer.

    Args:
        db: Database session (caller owns lifecycle and commit).
        events: Event dicts as returned by a local scraper.

    Returns:
        ``{"created": n, "updated": n}``
    """
    counts = {"created": 0, "updated": 0}
    seen: set = set()

    for data in events:
        dedup_hash = generate_deduplication_hash(
            title=data["title"],
            event_date=data["event_date"],
            destination_city=data["destination_city"],
            venue=data.get("venue"),
        )
        if dedup_hash in seen:
            continue
        seen.add(dedup_hash)

        result = await db.execute(select(Event).where(Event.deduplication_hash == dedup_hash))
        existing = result.scalars().first()

        if existing is None:
            db.add(
                Event(
                    destination_city=data["destination_city"],
                    title=data["title"][:200],
                    venue=(data.get("venue") or None) and data["venue"][:200],
                    event_date=data["event_date"],
                    end_date=data.get("end_date"),
                    category=data["category"],
                    description=data.get("description"),
                    price_range=data.get("price_range") or "varies",
                    source=data["source"],
                    url=data.get("url"),
                    showtimes=list(data.get("showtimes") or []) or None,
                    deduplication_hash=dedup_hash,
                    scraped_at=datetime.now(timezone.utc),
                )
            )
            counts["created"] += 1
            continue

        existing.showtimes = list(data.get("showtimes") or []) or existing.showtimes
        existing.end_date = data.get("end_date") or existing.end_date
        existing.url = data.get("url") or existing.url
        if data.get("price_range") and data["price_range"] != "varies":
            existing.price_range = data["price_range"]
        if len(data.get("description") or "") > len(existing.description or ""):
            existing.description = data["description"]
        existing.scraped_at = datetime.now(timezone.utc)
        counts["updated"] += 1

    await db.flush()
    return counts


async def load_weekend_events(db: AsyncSession, *, city: str, days: Sequence[date]) -> List[Event]:
    """Stored local events in ``city`` that take place on any of ``days``."""
    if not days:
        return []
    result = await db.execute(
        select(Event)
        .where(Event.destination_city == city)
        .where(Event.source.in_(LOCAL_SOURCES))
        .where(Event.event_date.in_(list(days)))
        .order_by(Event.event_date, Event.title)
    )
    return list(result.scalars().all())


async def refresh_local_events(
    db: AsyncSession,
    *,
    city: str,
    start_date: date,
    end_date: date,
    scraper: Optional[Any] = None,
) -> RefreshResult:
    """
    Scrape local events for a date range and store them.

    The run is recorded in ``scraping_jobs`` (type ``local_events``) so that
    ``scout stats`` shows it alongside the other scrapers.

    Args:
        db: Database session (caller owns lifecycle and commit).
        city: Home city name stored on the events.
        start_date: First day to collect.
        end_date: Last day to collect.
        scraper: Optional scraper instance (for tests). Defaults to
            ``MuenchenEventsScraper``.

    Raises:
        Exception: Whatever the scraper raises; the job is marked failed first.
    """
    from app.scrapers.muenchen_scraper import MuenchenEventsScraper

    scraper = scraper or MuenchenEventsScraper(city_name=city)
    source = scraper.SOURCE_NAME

    job = ScrapingJob(
        job_type="local_events",
        source=source,
        status="running",
        items_scraped=0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    await db.flush()

    try:
        try:
            scraped = await scraper.scrape_events(start_date, end_date)
        finally:
            await scraper.close()
        # A savepoint: if storing fails half-way, the rows are rolled back but
        # the session stays usable and the failed job below is still recorded.
        async with db.begin_nested():
            counts = await save_local_events(db, scraped)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:1000]
        job.completed_at = datetime.now(timezone.utc)
        await db.flush()
        logger.error("Local event scrape from %s failed: %s", source, exc)
        raise

    job.status = "completed"
    job.items_scraped = len(scraped)
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info(
        "Local events from %s: %d scraped, %d created, %d updated",
        source,
        len(scraped),
        counts["created"],
        counts["updated"],
    )
    return RefreshResult(
        source=source, scraped=len(scraped), created=counts["created"], updated=counts["updated"]
    )
