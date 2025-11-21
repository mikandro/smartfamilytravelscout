"""
Celery application configuration for distributed task queue.
"""

import logging
import signal
from typing import Any
from celery import Celery, Task
from celery.schedules import crontab

from app.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Cleanup Utilities
# ============================================================================


def cleanup_scraping_job(job_id: int, error_message: str = "Task interrupted by shutdown signal") -> None:
    """
    Mark a scraping job as interrupted in the database.

    This function should be called during task cleanup to ensure
    scraping jobs are properly marked as interrupted rather than
    left in 'running' state.

    Args:
        job_id: ID of the scraping job to clean up
        error_message: Optional error message to store with the job
    """
    from datetime import datetime
    from app.database import get_sync_session
    from app.models.scraping_job import ScrapingJob

    try:
        db = get_sync_session()
        try:
            job = db.query(ScrapingJob).filter(ScrapingJob.id == job_id).first()
            if job and job.status == "running":
                job.status = "interrupted"
                job.error_message = error_message
                job.completed_at = datetime.now()
                db.commit()
                logger.info(f"Marked scraping job {job_id} as interrupted")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error cleaning up scraping job {job_id}: {e}", exc_info=True)


# ============================================================================
# Graceful Task Base Class
# ============================================================================


class GracefulTask(Task):
    """
    Custom Celery Task class that handles graceful shutdown.

    This task intercepts SIGTERM signals and allows for cleanup
    before termination, preventing data corruption during deployments.

    Usage:
        @celery_app.task(base=GracefulTask, bind=True)
        def my_task(self):
            # Task implementation
            pass
    """

    _shutdown_requested = False
    _original_sigterm_handler = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """
        Execute task with graceful shutdown handling.

        Sets up SIGTERM signal handler before task execution and
        restores original handler after completion.
        """
        def signal_handler(signum: int, frame: Any) -> None:
            """Handle SIGTERM signal gracefully."""
            logger.warning(
                f"Task {self.request.id} ({self.name}) received shutdown signal (SIGTERM). "
                f"Attempting graceful shutdown..."
            )
            self._shutdown_requested = True

            # Call cleanup hook if implemented by subclass
            if hasattr(self, 'on_shutdown'):
                try:
                    self.on_shutdown()
                except Exception as e:
                    logger.error(f"Error during task cleanup: {e}", exc_info=True)

            # Raise SystemExit to terminate task execution
            raise SystemExit("Task terminated by SIGTERM signal")

        # Store original SIGTERM handler
        self._original_sigterm_handler = signal.signal(signal.SIGTERM, signal_handler)

        try:
            # Execute the task
            return super().__call__(*args, **kwargs)
        finally:
            # Restore original SIGTERM handler
            if self._original_sigterm_handler is not None:
                signal.signal(signal.SIGTERM, self._original_sigterm_handler)

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_requested

    def check_shutdown(self) -> None:
        """
        Check if shutdown is requested and raise SystemExit if true.

        Call this method periodically in long-running tasks to
        allow for earlier termination.
        """
        if self._shutdown_requested:
            raise SystemExit("Task terminated due to shutdown request")


# Create Celery instance
celery_app = Celery(
    "smartfamilytravelscout",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.scheduled_tasks",
        # Add more task modules here as needed
        # "app.tasks.scraper_tasks",
        # "app.tasks.ai_tasks",
        # "app.tasks.notification_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.timezone,
    enable_utc=True,
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,
    # Task execution settings
    task_track_started=True,
    task_time_limit=300,  # 5 minutes hard limit (for graceful shutdown)
    task_soft_time_limit=270,  # 4.5 minutes soft limit (warning before hard limit)
    task_acks_late=True,  # Acknowledge tasks after completion
    task_reject_on_worker_lost=True,
    # Worker settings
    worker_prefetch_multiplier=1,  # Fetch one task at a time
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    worker_disable_rate_limits=False,
    # Broker settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    # Beat scheduler settings
    beat_schedule={
        # Daily flight search at 6 AM UTC
        "daily-flight-search": {
            "task": "app.tasks.scheduled_tasks.daily_flight_search",
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": "scheduled"},
        },
        # Hourly price updates
        "hourly-price-update": {
            "task": "app.tasks.scheduled_tasks.update_flight_prices",
            "schedule": crontab(minute=0),
            "options": {"queue": "scheduled"},
        },
        # Weekly event discovery on Sundays at 8 AM UTC
        "weekly-event-discovery": {
            "task": "app.tasks.scheduled_tasks.discover_events",
            "schedule": crontab(hour=8, minute=0, day_of_week=0),
            "options": {"queue": "scheduled"},
        },
        # Daily accommodation search at 7 AM UTC
        "daily-accommodation-search": {
            "task": "app.tasks.scheduled_tasks.search_accommodations",
            "schedule": crontab(hour=7, minute=0),
            "options": {"queue": "scheduled"},
        },
        # Clean old data at 2 AM UTC daily
        "daily-cleanup": {
            "task": "app.tasks.scheduled_tasks.cleanup_old_data",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "maintenance"},
        },
    },
    # Task routing
    task_routes={
        "app.tasks.scheduled_tasks.*": {"queue": "scheduled"},
        "app.tasks.scraper_tasks.*": {"queue": "scrapers"},
        "app.tasks.ai_tasks.*": {"queue": "ai"},
        "app.tasks.notification_tasks.*": {"queue": "notifications"},
    },
    # Task default queue
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
)


# Task event handlers
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery functionality."""
    logger.info(f"Request: {self.request!r}")
    return f"Task executed successfully"


# Celery signals
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup periodic tasks after Celery configuration."""
    logger.info("Celery periodic tasks configured")


@celery_app.on_after_finalize.connect
def setup_queues(sender, **kwargs):
    """Setup queues after Celery finalization."""
    logger.info("Celery queues configured")


if __name__ == "__main__":
    celery_app.start()
