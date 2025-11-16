"""
Celery application configuration for distributed task queue.
"""

import logging
from celery import Celery
from celery.schedules import crontab

from app.config import settings

logger = logging.getLogger(__name__)

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
    task_time_limit=1800,  # 30 minutes hard limit
    task_soft_time_limit=1500,  # 25 minutes soft limit
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
