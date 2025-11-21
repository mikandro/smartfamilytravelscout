"""
Progress tracking utilities for scraping jobs.

This module provides helper functions for emitting progress updates
during scraping operations.
"""

import logging
from typing import Optional

from app.websocket import websocket_manager, ScrapingEvent, ScrapingEventType

logger = logging.getLogger(__name__)


async def emit_job_started(job_id: int, job_type: str, source: str, message: str = ""):
    """
    Emit a job started event.

    Args:
        job_id: Scraping job ID
        job_type: Type of job (flights, accommodations, etc.)
        source: Source name
        message: Optional message
    """
    event = ScrapingEvent(
        job_id=job_id,
        event_type=ScrapingEventType.JOB_STARTED,
        status="running",
        progress=0.0,
        results_count=0,
        message=message or f"Started {job_type} scraping from {source}",
        metadata={"job_type": job_type, "source": source},
    )
    await websocket_manager.broadcast_event(event)
    logger.debug(f"Emitted job_started event for job {job_id}")


async def emit_job_progress(
    job_id: int,
    progress: Optional[float] = None,
    results_count: int = 0,
    message: str = "",
    metadata: Optional[dict] = None,
):
    """
    Emit a job progress event.

    Args:
        job_id: Scraping job ID
        progress: Progress percentage (0-100), or None if unknown
        results_count: Number of items scraped so far
        message: Progress message
        metadata: Additional metadata
    """
    event = ScrapingEvent(
        job_id=job_id,
        event_type=ScrapingEventType.JOB_PROGRESS,
        status="running",
        progress=progress,
        results_count=results_count,
        message=message,
        metadata=metadata or {},
    )
    await websocket_manager.broadcast_event(event)
    logger.debug(f"Emitted job_progress event for job {job_id}: {message}")


async def emit_job_completed(job_id: int, results_count: int, message: str = ""):
    """
    Emit a job completed event.

    Args:
        job_id: Scraping job ID
        results_count: Final number of items scraped
        message: Completion message
    """
    event = ScrapingEvent(
        job_id=job_id,
        event_type=ScrapingEventType.JOB_COMPLETED,
        status="completed",
        progress=100.0,
        results_count=results_count,
        message=message or f"Job completed successfully with {results_count} results",
    )
    await websocket_manager.broadcast_event(event)
    logger.debug(f"Emitted job_completed event for job {job_id}")


async def emit_job_failed(job_id: int, error_message: str):
    """
    Emit a job failed event.

    Args:
        job_id: Scraping job ID
        error_message: Error message
    """
    event = ScrapingEvent(
        job_id=job_id,
        event_type=ScrapingEventType.JOB_FAILED,
        status="failed",
        progress=0.0,
        results_count=0,
        message=f"Job failed: {error_message}",
        metadata={"error": error_message},
    )
    await websocket_manager.broadcast_event(event)
    logger.debug(f"Emitted job_failed event for job {job_id}")


async def emit_scraper_started(job_id: int, scraper_name: str, route: str):
    """
    Emit a scraper started event.

    Args:
        job_id: Scraping job ID
        scraper_name: Name of the scraper (e.g., "kiwi", "skyscanner")
        route: Route being scraped (e.g., "MUC->LIS")
    """
    event = ScrapingEvent(
        job_id=job_id,
        event_type=ScrapingEventType.SCRAPER_STARTED,
        status="running",
        results_count=0,
        message=f"Started {scraper_name} scraper for {route}",
        metadata={"scraper": scraper_name, "route": route},
    )
    await websocket_manager.broadcast_event(event)
    logger.debug(f"Emitted scraper_started event for {scraper_name} on job {job_id}")


async def emit_scraper_completed(
    job_id: int, scraper_name: str, route: str, results_count: int
):
    """
    Emit a scraper completed event.

    Args:
        job_id: Scraping job ID
        scraper_name: Name of the scraper
        route: Route that was scraped
        results_count: Number of results from this scraper
    """
    event = ScrapingEvent(
        job_id=job_id,
        event_type=ScrapingEventType.SCRAPER_COMPLETED,
        status="running",
        results_count=results_count,
        message=f"Completed {scraper_name} scraper for {route}: {results_count} results",
        metadata={"scraper": scraper_name, "route": route, "count": results_count},
    )
    await websocket_manager.broadcast_event(event)
    logger.debug(f"Emitted scraper_completed event for {scraper_name} on job {job_id}")


async def emit_scraper_failed(job_id: int, scraper_name: str, route: str, error: str):
    """
    Emit a scraper failed event.

    Args:
        job_id: Scraping job ID
        scraper_name: Name of the scraper
        route: Route that was being scraped
        error: Error message
    """
    event = ScrapingEvent(
        job_id=job_id,
        event_type=ScrapingEventType.SCRAPER_FAILED,
        status="running",
        results_count=0,
        message=f"Failed {scraper_name} scraper for {route}: {error}",
        metadata={"scraper": scraper_name, "route": route, "error": error},
    )
    await websocket_manager.broadcast_event(event)
    logger.debug(f"Emitted scraper_failed event for {scraper_name} on job {job_id}")


async def emit_results_updated(job_id: int, results_count: int, progress: Optional[float] = None):
    """
    Emit a results updated event.

    Args:
        job_id: Scraping job ID
        results_count: Updated number of results
        progress: Optional progress percentage
    """
    event = ScrapingEvent(
        job_id=job_id,
        event_type=ScrapingEventType.RESULTS_UPDATED,
        status="running",
        progress=progress,
        results_count=results_count,
        message=f"Results updated: {results_count} items scraped",
    )
    await websocket_manager.broadcast_event(event)
    logger.debug(f"Emitted results_updated event for job {job_id}: {results_count} results")
