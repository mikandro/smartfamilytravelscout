"""
WebSocket routes for real-time scraping updates.
"""

import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.scraping_job import ScrapingJob
from app.websocket import websocket_manager, ScrapingEvent, ScrapingEventType

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_db() -> AsyncSession:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        yield session


@router.websocket("/ws/scraping/{job_id}")
async def websocket_scraping_updates(websocket: WebSocket, job_id: int):
    """
    WebSocket endpoint for real-time scraping job updates.

    This endpoint allows clients to subscribe to real-time updates for a specific
    scraping job. Updates are sent as JSON messages with the following structure:

    ```json
    {
        "job_id": 123,
        "event_type": "job_progress",
        "status": "running",
        "progress": 45.5,
        "results_count": 42,
        "message": "Scraping in progress...",
        "metadata": {},
        "timestamp": "2025-11-21T10:30:00"
    }
    ```

    **Event Types:**
    - `job_started`: Scraping job has started
    - `job_progress`: Progress update with current status
    - `job_completed`: Job completed successfully
    - `job_failed`: Job failed with error
    - `scraper_started`: Individual scraper started
    - `scraper_completed`: Individual scraper completed
    - `scraper_failed`: Individual scraper failed
    - `results_updated`: Results count updated

    **Usage Example (JavaScript):**
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/ws/scraping/123');

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log(`Job ${data.job_id}: ${data.message}`);
        console.log(`Progress: ${data.progress}%`);
        console.log(`Results: ${data.results_count}`);
    };

    ws.onerror = (error) => console.error('WebSocket error:', error);
    ws.onclose = () => console.log('WebSocket closed');
    ```

    Args:
        websocket: WebSocket connection
        job_id: ID of the scraping job to monitor

    Raises:
        WebSocketDisconnect: When client disconnects
    """
    # Initialize Redis if not already done
    await websocket_manager.initialize_redis()

    # Connect the WebSocket
    await websocket_manager.connect(websocket, job_id)
    logger.info(f"Client connected to scraping job {job_id}")

    try:
        # Check if job exists and send initial status
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ScrapingJob).where(ScrapingJob.id == job_id))
            job = result.scalar_one_or_none()

            if job:
                # Send initial status
                initial_event = ScrapingEvent(
                    job_id=job_id,
                    event_type=ScrapingEventType.JOB_PROGRESS,
                    status=job.status,
                    progress=100.0 if job.is_completed else (0.0 if job.status == "pending" else None),
                    results_count=job.items_scraped,
                    message=f"Connected to job {job_id}",
                    metadata={
                        "job_type": job.job_type,
                        "source": job.source,
                        "started_at": job.started_at.isoformat() if job.started_at else None,
                        "completed_at": job.completed_at.isoformat()
                        if job.completed_at
                        else None,
                    },
                )
                await websocket.send_json(initial_event.to_dict())
            else:
                # Job not found, send error
                error_event = ScrapingEvent(
                    job_id=job_id,
                    event_type=ScrapingEventType.JOB_FAILED,
                    status="failed",
                    progress=0.0,
                    results_count=0,
                    message=f"Job {job_id} not found",
                )
                await websocket.send_json(error_event.to_dict())

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive messages from client (e.g., ping/pong for keepalive)
                data = await websocket.receive_text()

                # Handle client messages (optional)
                if data == "ping":
                    await websocket.send_text("pong")

            except WebSocketDisconnect:
                logger.info(f"Client disconnected from job {job_id}")
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}", exc_info=True)
                break

    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}", exc_info=True)

    finally:
        # Disconnect and clean up
        await websocket_manager.disconnect(websocket, job_id)
        logger.info(f"WebSocket connection closed for job {job_id}")


@router.get("/ws/scraping/{job_id}/status")
async def get_scraping_job_status(job_id: int, db: AsyncSession = Depends(get_db)):
    """
    Get current status of a scraping job (HTTP endpoint).

    This is a REST alternative to the WebSocket endpoint for clients that
    want to poll job status instead of receiving real-time updates.

    Args:
        job_id: ID of the scraping job
        db: Database session

    Returns:
        Job status information

    Raises:
        HTTPException: If job not found
    """
    result = await db.execute(select(ScrapingJob).where(ScrapingJob.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail=f"Scraping job {job_id} not found")

    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "source": job.source,
        "status": job.status,
        "items_scraped": job.items_scraped,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "duration_seconds": job.duration_seconds,
        "is_running": job.is_running,
        "is_completed": job.is_completed,
        "is_failed": job.is_failed,
    }


@router.get("/ws/stats")
async def get_websocket_stats():
    """
    Get WebSocket connection statistics.

    Returns:
        Statistics about active WebSocket connections
    """
    return {
        "total_connections": websocket_manager.get_connection_count(),
        "active_jobs": len(websocket_manager.active_connections),
        "redis_connected": websocket_manager.redis_client is not None,
    }
