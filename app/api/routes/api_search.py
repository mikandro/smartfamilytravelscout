"""
API routes for triggering search operations.
Returns JSON responses for programmatic access.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.api.schemas.search import SearchRequest, SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/search", response_model=SearchResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_search(
    search_request: SearchRequest,
    db: AsyncSession = Depends(get_async_session),
) -> SearchResponse:
    """
    Trigger a new search operation.

    This endpoint queues a background task to scrape flights for the specified
    origin and destination. The task runs asynchronously via Celery.

    Returns immediately with task status information.
    For synchronous results, use the flight search endpoint instead.
    """
    try:
        # Validate airport codes (basic validation)
        if len(search_request.origin) != 3 or len(search_request.destination) != 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Airport codes must be 3-letter IATA codes (e.g., MUC, LIS)",
            )

        # Import Airport model to validate airports exist
        from app.models import Airport
        from sqlalchemy import select

        # Check if airports exist
        origin_result = await db.execute(
            select(Airport).where(Airport.iata_code == search_request.origin.upper())
        )
        origin_airport = origin_result.scalar_one_or_none()

        if not origin_airport:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Origin airport '{search_request.origin}' not found",
            )

        dest_result = await db.execute(
            select(Airport).where(Airport.iata_code == search_request.destination.upper())
        )
        dest_airport = dest_result.scalar_one_or_none()

        if not dest_airport:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Destination airport '{search_request.destination}' not found",
            )

        # Try to import and queue Celery task
        try:
            from app.tasks.scheduled_tasks import scrape_flights_task

            # Queue the task
            task = scrape_flights_task.delay(
                origin=search_request.origin.upper(),
                destination=search_request.destination.upper(),
                scraper=search_request.scraper,
            )

            return SearchResponse(
                status="queued",
                message=f"Search queued for {search_request.origin} to {search_request.destination}",
                task_id=task.id,
            )

        except ImportError:
            # Celery not available - fall back to synchronous execution
            logger.warning("Celery not available, falling back to synchronous scraping")

            # Import orchestrator for synchronous execution
            from app.orchestration.flight_orchestrator import FlightOrchestrator
            from app.database import get_sync_session

            # Use sync database session for orchestrator
            sync_db = get_sync_session()
            try:
                orchestrator = FlightOrchestrator(sync_db)

                # Run scraping synchronously
                results = orchestrator.scrape_all_sources(
                    origin=search_request.origin.upper(),
                    destination=search_request.destination.upper(),
                )

                results_count = sum(len(r) for r in results.values())

                return SearchResponse(
                    status="completed",
                    message=f"Search completed synchronously. Found {results_count} flights.",
                    results_count=results_count,
                )
            finally:
                sync_db.close()

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error triggering search: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error triggering search: {str(e)}",
        )
