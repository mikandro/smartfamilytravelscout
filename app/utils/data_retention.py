"""
Data retention utilities for cleaning up old data.

Implements retention policies to prevent indefinite database growth
by removing outdated flights, events, packages, accommodations, and scraping jobs.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict

from sqlalchemy import and_, delete
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Accommodation,
    Event,
    Flight,
    ScrapingJob,
    TripPackage,
)

logger = logging.getLogger(__name__)


@dataclass
class CleanupStats:
    """Statistics from a cleanup operation."""

    flights_deleted: int = 0
    events_deleted: int = 0
    packages_deleted: int = 0
    accommodations_deleted: int = 0
    scraping_jobs_deleted: int = 0

    @property
    def total_deleted(self) -> int:
        """Total number of records deleted."""
        return (
            self.flights_deleted
            + self.events_deleted
            + self.packages_deleted
            + self.accommodations_deleted
            + self.scraping_jobs_deleted
        )

    def to_dict(self) -> Dict[str, int]:
        """Convert stats to dictionary."""
        return {
            "flights_deleted": self.flights_deleted,
            "events_deleted": self.events_deleted,
            "packages_deleted": self.packages_deleted,
            "accommodations_deleted": self.accommodations_deleted,
            "scraping_jobs_deleted": self.scraping_jobs_deleted,
            "total_deleted": self.total_deleted,
        }


def cleanup_old_flights(db: Session, retention_days: int | None = None) -> int:
    """
    Delete flights with departure dates older than retention period.

    Args:
        db: Database session (sync)
        retention_days: Days to retain after departure date. If None, uses config.

    Returns:
        Number of flights deleted

    Examples:
        >>> db = get_sync_session()
        >>> deleted_count = cleanup_old_flights(db, retention_days=90)
        >>> logger.info(f"Deleted {deleted_count} old flights")
    """
    if retention_days is None:
        retention_days = settings.flight_retention_days

    cutoff_date = date.today() - timedelta(days=retention_days)

    logger.info(
        f"Cleaning up flights with departure dates before {cutoff_date} "
        f"(retention: {retention_days} days)"
    )

    try:
        # Delete flights with departure dates before cutoff
        stmt = delete(Flight).where(Flight.departure_date < cutoff_date)
        result = db.execute(stmt)
        db.commit()

        deleted_count = result.rowcount or 0
        logger.info(f"Deleted {deleted_count} old flights")
        return deleted_count

    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up flights: {e}")
        raise


def cleanup_old_events(db: Session, retention_days: int | None = None) -> int:
    """
    Delete events with event dates older than retention period.

    Args:
        db: Database session (sync)
        retention_days: Days to retain after event date. If None, uses config.

    Returns:
        Number of events deleted

    Examples:
        >>> db = get_sync_session()
        >>> deleted_count = cleanup_old_events(db, retention_days=180)
        >>> logger.info(f"Deleted {deleted_count} old events")
    """
    if retention_days is None:
        retention_days = settings.event_retention_days

    cutoff_date = date.today() - timedelta(days=retention_days)

    logger.info(
        f"Cleaning up events with dates before {cutoff_date} "
        f"(retention: {retention_days} days)"
    )

    try:
        # Delete events with event dates before cutoff
        # For multi-day events, use end_date if available, otherwise event_date
        stmt = delete(Event).where(
            and_(
                Event.event_date < cutoff_date,
                # If end_date exists, it must also be before cutoff
                (Event.end_date.is_(None) | (Event.end_date < cutoff_date)),
            )
        )
        result = db.execute(stmt)
        db.commit()

        deleted_count = result.rowcount or 0
        logger.info(f"Deleted {deleted_count} old events")
        return deleted_count

    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up events: {e}")
        raise


def cleanup_old_packages(db: Session, retention_days: int | None = None) -> int:
    """
    Delete trip packages with departure dates older than retention period.

    Args:
        db: Database session (sync)
        retention_days: Days to retain after departure date. If None, uses config.

    Returns:
        Number of trip packages deleted

    Examples:
        >>> db = get_sync_session()
        >>> deleted_count = cleanup_old_packages(db, retention_days=60)
        >>> logger.info(f"Deleted {deleted_count} old packages")
    """
    if retention_days is None:
        retention_days = settings.package_retention_days

    cutoff_date = date.today() - timedelta(days=retention_days)

    logger.info(
        f"Cleaning up trip packages with departure dates before {cutoff_date} "
        f"(retention: {retention_days} days)"
    )

    try:
        # Delete packages with departure dates before cutoff
        stmt = delete(TripPackage).where(TripPackage.departure_date < cutoff_date)
        result = db.execute(stmt)
        db.commit()

        deleted_count = result.rowcount or 0
        logger.info(f"Deleted {deleted_count} old trip packages")
        return deleted_count

    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up packages: {e}")
        raise


def cleanup_old_accommodations(db: Session, retention_days: int | None = None) -> int:
    """
    Delete accommodations scraped older than retention period.

    Args:
        db: Database session (sync)
        retention_days: Days to retain after scraping. If None, uses config.

    Returns:
        Number of accommodations deleted

    Examples:
        >>> db = get_sync_session()
        >>> deleted_count = cleanup_old_accommodations(db, retention_days=180)
        >>> logger.info(f"Deleted {deleted_count} old accommodations")
    """
    if retention_days is None:
        retention_days = settings.accommodation_retention_days

    cutoff_datetime = datetime.now() - timedelta(days=retention_days)

    logger.info(
        f"Cleaning up accommodations scraped before {cutoff_datetime} "
        f"(retention: {retention_days} days)"
    )

    try:
        # Delete accommodations scraped before cutoff
        stmt = delete(Accommodation).where(Accommodation.scraped_at < cutoff_datetime)
        result = db.execute(stmt)
        db.commit()

        deleted_count = result.rowcount or 0
        logger.info(f"Deleted {deleted_count} old accommodations")
        return deleted_count

    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up accommodations: {e}")
        raise


def cleanup_old_scraping_jobs(db: Session, retention_days: int | None = None) -> int:
    """
    Delete completed scraping jobs older than retention period.

    Only deletes completed or failed jobs, not running jobs.

    Args:
        db: Database session (sync)
        retention_days: Days to retain after completion. If None, uses config.

    Returns:
        Number of scraping jobs deleted

    Examples:
        >>> db = get_sync_session()
        >>> deleted_count = cleanup_old_scraping_jobs(db, retention_days=30)
        >>> logger.info(f"Deleted {deleted_count} old scraping jobs")
    """
    if retention_days is None:
        retention_days = settings.scraping_job_retention_days

    cutoff_datetime = datetime.now() - timedelta(days=retention_days)

    logger.info(
        f"Cleaning up scraping jobs completed before {cutoff_datetime} "
        f"(retention: {retention_days} days)"
    )

    try:
        # Delete completed/failed jobs with completion time before cutoff
        # Do not delete running jobs
        stmt = delete(ScrapingJob).where(
            and_(
                ScrapingJob.status.in_(["completed", "failed"]),
                ScrapingJob.completed_at.isnot(None),
                ScrapingJob.completed_at < cutoff_datetime,
            )
        )
        result = db.execute(stmt)
        db.commit()

        deleted_count = result.rowcount or 0
        logger.info(f"Deleted {deleted_count} old scraping jobs")
        return deleted_count

    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up scraping jobs: {e}")
        raise


def cleanup_all_old_data(
    db: Session,
    flight_retention: int | None = None,
    event_retention: int | None = None,
    package_retention: int | None = None,
    accommodation_retention: int | None = None,
    scraping_job_retention: int | None = None,
) -> CleanupStats:
    """
    Run all data retention cleanup operations.

    Args:
        db: Database session (sync)
        flight_retention: Days to retain flights. If None, uses config.
        event_retention: Days to retain events. If None, uses config.
        package_retention: Days to retain packages. If None, uses config.
        accommodation_retention: Days to retain accommodations. If None, uses config.
        scraping_job_retention: Days to retain scraping jobs. If None, uses config.

    Returns:
        CleanupStats with counts of deleted records

    Examples:
        >>> db = get_sync_session()
        >>> stats = cleanup_all_old_data(db)
        >>> logger.info(f"Total deleted: {stats.total_deleted} records")
        >>> logger.info(f"Flights: {stats.flights_deleted}, Events: {stats.events_deleted}")
    """
    logger.info("Starting data retention cleanup")
    stats = CleanupStats()

    try:
        # Clean up each data type
        stats.flights_deleted = cleanup_old_flights(db, flight_retention)
        stats.events_deleted = cleanup_old_events(db, event_retention)
        stats.packages_deleted = cleanup_old_packages(db, package_retention)
        stats.accommodations_deleted = cleanup_old_accommodations(db, accommodation_retention)
        stats.scraping_jobs_deleted = cleanup_old_scraping_jobs(db, scraping_job_retention)

        logger.info(
            f"Data retention cleanup completed. Total deleted: {stats.total_deleted} records. "
            f"Details: {stats.to_dict()}"
        )

        return stats

    except Exception as e:
        logger.error(f"Data retention cleanup failed: {e}")
        raise


def get_retention_cutoff_dates() -> Dict[str, date | datetime]:
    """
    Get the cutoff dates for each data type based on current retention settings.

    Returns:
        Dictionary mapping data type to cutoff date/datetime

    Examples:
        >>> cutoffs = get_retention_cutoff_dates()
        >>> cutoffs['flights']  # date object
        datetime.date(2025, 8, 23)
        >>> cutoffs['accommodations']  # datetime object
        datetime.datetime(2025, 5, 25, 10, 30, 45)
    """
    today = date.today()
    now = datetime.now()

    return {
        "flights": today - timedelta(days=settings.flight_retention_days),
        "events": today - timedelta(days=settings.event_retention_days),
        "packages": today - timedelta(days=settings.package_retention_days),
        "accommodations": now - timedelta(days=settings.accommodation_retention_days),
        "scraping_jobs": now - timedelta(days=settings.scraping_job_retention_days),
    }
