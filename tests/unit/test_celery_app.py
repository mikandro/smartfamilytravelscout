"""
Tests for Celery application configuration.
"""

import pytest
from unittest.mock import Mock, patch
from celery.schedules import crontab

from app.tasks.celery_app import celery_app, debug_task


class TestCeleryConfiguration:
    """Test Celery app configuration."""

    def test_celery_app_name(self):
        """Test that Celery app has correct name."""
        assert celery_app.main == "smartfamilytravelscout"

    def test_celery_app_broker_configured(self):
        """Test that broker URL is configured."""
        assert celery_app.conf.broker_url is not None

    def test_celery_app_backend_configured(self):
        """Test that result backend is configured."""
        assert celery_app.conf.result_backend is not None

    def test_task_serializer_json(self):
        """Test that task serializer is JSON."""
        assert celery_app.conf.task_serializer == "json"

    def test_accept_content_json(self):
        """Test that accepted content is JSON."""
        assert "json" in celery_app.conf.accept_content

    def test_result_serializer_json(self):
        """Test that result serializer is JSON."""
        assert celery_app.conf.result_serializer == "json"

    def test_timezone_configured(self):
        """Test that timezone is configured."""
        assert celery_app.conf.timezone is not None

    def test_utc_enabled(self):
        """Test that UTC is enabled."""
        assert celery_app.conf.enable_utc is True

    def test_result_expires(self):
        """Test that results expire after 1 hour."""
        assert celery_app.conf.result_expires == 3600

    def test_task_track_started(self):
        """Test that task tracking is enabled."""
        assert celery_app.conf.task_track_started is True

    def test_task_time_limits(self):
        """Test that task time limits are configured."""
        assert celery_app.conf.task_time_limit == 1800  # 30 minutes
        assert celery_app.conf.task_soft_time_limit == 1500  # 25 minutes

    def test_task_acks_late(self):
        """Test that tasks are acknowledged after completion."""
        assert celery_app.conf.task_acks_late is True

    def test_worker_prefetch_multiplier(self):
        """Test that worker prefetch multiplier is set."""
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_worker_max_tasks_per_child(self):
        """Test that worker max tasks per child is set."""
        assert celery_app.conf.worker_max_tasks_per_child == 1000

    def test_broker_connection_retry_configured(self):
        """Test that broker connection retry is configured."""
        assert celery_app.conf.broker_connection_retry is True
        assert celery_app.conf.broker_connection_max_retries == 10


class TestBeatSchedule:
    """Test Celery beat schedule configuration."""

    def test_beat_schedule_exists(self):
        """Test that beat schedule is configured."""
        assert celery_app.conf.beat_schedule is not None
        assert len(celery_app.conf.beat_schedule) > 0

    def test_daily_flight_search_schedule(self):
        """Test that daily flight search is scheduled."""
        schedule = celery_app.conf.beat_schedule.get("daily-flight-search")
        assert schedule is not None
        assert schedule["task"] == "app.tasks.scheduled_tasks.daily_flight_search"
        assert isinstance(schedule["schedule"], crontab)
        assert schedule["options"]["queue"] == "scheduled"

    def test_hourly_price_update_schedule(self):
        """Test that hourly price update is scheduled."""
        schedule = celery_app.conf.beat_schedule.get("hourly-price-update")
        assert schedule is not None
        assert schedule["task"] == "app.tasks.scheduled_tasks.update_flight_prices"
        assert isinstance(schedule["schedule"], crontab)
        assert schedule["options"]["queue"] == "scheduled"

    def test_weekly_event_discovery_schedule(self):
        """Test that weekly event discovery is scheduled."""
        schedule = celery_app.conf.beat_schedule.get("weekly-event-discovery")
        assert schedule is not None
        assert schedule["task"] == "app.tasks.scheduled_tasks.discover_events"
        assert isinstance(schedule["schedule"], crontab)
        assert schedule["options"]["queue"] == "scheduled"

    def test_daily_accommodation_search_schedule(self):
        """Test that daily accommodation search is scheduled."""
        schedule = celery_app.conf.beat_schedule.get("daily-accommodation-search")
        assert schedule is not None
        assert schedule["task"] == "app.tasks.scheduled_tasks.search_accommodations"
        assert isinstance(schedule["schedule"], crontab)
        assert schedule["options"]["queue"] == "scheduled"

    def test_daily_cleanup_schedule(self):
        """Test that daily cleanup is scheduled."""
        schedule = celery_app.conf.beat_schedule.get("daily-cleanup")
        assert schedule is not None
        assert schedule["task"] == "app.tasks.scheduled_tasks.cleanup_old_data"
        assert isinstance(schedule["schedule"], crontab)
        assert schedule["options"]["queue"] == "maintenance"

    def test_all_schedules_have_task_name(self):
        """Test that all schedules have a task name."""
        for name, schedule in celery_app.conf.beat_schedule.items():
            assert "task" in schedule
            assert schedule["task"].startswith("app.tasks.")

    def test_all_schedules_have_crontab(self):
        """Test that all schedules have a crontab schedule."""
        for name, schedule in celery_app.conf.beat_schedule.items():
            assert "schedule" in schedule
            assert isinstance(schedule["schedule"], crontab)


class TestTaskRouting:
    """Test Celery task routing configuration."""

    def test_task_routes_configured(self):
        """Test that task routes are configured."""
        assert celery_app.conf.task_routes is not None

    def test_scheduled_tasks_route(self):
        """Test that scheduled tasks route to scheduled queue."""
        routes = celery_app.conf.task_routes
        assert "app.tasks.scheduled_tasks.*" in routes
        assert routes["app.tasks.scheduled_tasks.*"]["queue"] == "scheduled"

    def test_scraper_tasks_route(self):
        """Test that scraper tasks route to scrapers queue."""
        routes = celery_app.conf.task_routes
        assert "app.tasks.scraper_tasks.*" in routes
        assert routes["app.tasks.scraper_tasks.*"]["queue"] == "scrapers"

    def test_ai_tasks_route(self):
        """Test that AI tasks route to ai queue."""
        routes = celery_app.conf.task_routes
        assert "app.tasks.ai_tasks.*" in routes
        assert routes["app.tasks.ai_tasks.*"]["queue"] == "ai"

    def test_notification_tasks_route(self):
        """Test that notification tasks route to notifications queue."""
        routes = celery_app.conf.task_routes
        assert "app.tasks.notification_tasks.*" in routes
        assert routes["app.tasks.notification_tasks.*"]["queue"] == "notifications"

    def test_default_queue_configured(self):
        """Test that default queue is configured."""
        assert celery_app.conf.task_default_queue == "default"
        assert celery_app.conf.task_default_exchange == "default"
        assert celery_app.conf.task_default_routing_key == "default"


class TestDebugTask:
    """Test the debug task."""

    @patch('app.tasks.celery_app.logger')
    def test_debug_task_executes(self, mock_logger):
        """Test that debug task executes successfully."""
        # Create a mock request
        mock_self = Mock()
        mock_self.request = Mock()
        mock_self.request.id = "test-task-id"

        # Execute task
        result = debug_task(mock_self)

        # Verify
        assert result == "Task executed successfully"
        mock_logger.info.assert_called_once()

    def test_debug_task_is_registered(self):
        """Test that debug task is registered with Celery."""
        assert "debug_task" in celery_app.tasks or "app.tasks.celery_app.debug_task" in celery_app.tasks


class TestCeleryIncludes:
    """Test that Celery includes the right task modules."""

    def test_scheduled_tasks_included(self):
        """Test that scheduled_tasks module is included."""
        assert "app.tasks.scheduled_tasks" in celery_app.conf.include


class TestCelerySignals:
    """Test Celery signal handlers."""

    @patch('app.tasks.celery_app.logger')
    def test_setup_periodic_tasks_signal(self, mock_logger):
        """Test setup_periodic_tasks signal handler."""
        from app.tasks.celery_app import setup_periodic_tasks

        # Call the signal handler
        setup_periodic_tasks(sender=None)

        # Verify logging
        mock_logger.info.assert_called_once_with("Celery periodic tasks configured")

    @patch('app.tasks.celery_app.logger')
    def test_setup_queues_signal(self, mock_logger):
        """Test setup_queues signal handler."""
        from app.tasks.celery_app import setup_queues

        # Call the signal handler
        setup_queues(sender=None)

        # Verify logging
        mock_logger.info.assert_called_once_with("Celery queues configured")
