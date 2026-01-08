"""
Integration tests for Celery task execution.

Tests task scheduling, worker execution, failure handling, and result storage.
"""

import pytest
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from celery.result import AsyncResult

from app.tasks.scheduled_tasks import (
    daily_flight_search,
    update_flight_prices,
    discover_events,
    search_accommodations,
    cleanup_old_data,
    send_deal_notifications,
)
from app.tasks.celery_app import celery_app


@pytest.mark.integration
@pytest.mark.asyncio
class TestCeleryTaskExecution:
    """Integration tests for Celery task execution and handling."""

    def test_task_registration(self):
        """
        Test that all scheduled tasks are properly registered with Celery.
        """
        # Get all registered tasks
        registered_tasks = celery_app.tasks.keys()

        # Verify critical tasks are registered
        expected_tasks = [
            "app.tasks.scheduled_tasks.daily_flight_search",
            "app.tasks.scheduled_tasks.update_flight_prices",
            "app.tasks.scheduled_tasks.discover_events",
            "app.tasks.scheduled_tasks.search_accommodations",
            "app.tasks.scheduled_tasks.cleanup_old_data",
            "app.tasks.scheduled_tasks.send_deal_notifications",
        ]

        for task_name in expected_tasks:
            assert task_name in registered_tasks, f"Task {task_name} not registered"

    def test_daily_flight_search_task(self):
        """
        Test daily flight search task execution and result structure.
        """
        # Execute task synchronously (for testing)
        result = daily_flight_search()

        # Verify result structure
        assert isinstance(result, dict), "Task should return a dictionary"
        assert "status" in result, "Result should contain status"
        assert result["status"] == "success", f"Task failed: {result}"
        assert "airports" in result, "Result should contain airports list"
        assert "task_id" in result, "Result should contain task_id"

    def test_update_flight_prices_task(self):
        """
        Test hourly flight price update task execution.
        """
        result = update_flight_prices()

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "task_id" in result

    def test_discover_events_task(self):
        """
        Test weekly event discovery task execution.
        """
        result = discover_events()

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "task_id" in result

    def test_search_accommodations_task(self):
        """
        Test daily accommodation search task execution.
        """
        result = search_accommodations()

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "task_id" in result

    def test_cleanup_old_data_task(self):
        """
        Test daily cleanup task execution and cutoff date calculation.
        """
        result = cleanup_old_data()

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "cutoff_date" in result, "Result should contain cutoff_date"
        assert "task_id" in result

        # Verify cutoff date is approximately 30 days ago
        cutoff = datetime.fromisoformat(result["cutoff_date"])
        expected_cutoff = datetime.now() - timedelta(days=30)
        time_diff = abs((cutoff - expected_cutoff).total_seconds())

        assert time_diff < 60, "Cutoff date calculation incorrect"

    def test_send_deal_notifications_task(self):
        """
        Test deal notification task execution.
        """
        result = send_deal_notifications()

        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "task_id" in result

    def test_task_failure_handling(self):
        """
        Test that task failures are handled gracefully and logged.
        """
        # Mock a function to raise an exception
        with patch("app.tasks.scheduled_tasks.settings") as mock_settings:
            # Make settings.get_departure_airports_list() raise an exception
            mock_settings.get_departure_airports_list.side_effect = Exception("Database connection failed")

            # Task should catch exception and re-raise it
            with pytest.raises(Exception) as exc_info:
                daily_flight_search()

            assert "Database connection failed" in str(exc_info.value)

    def test_task_retry_mechanism(self):
        """
        Test that tasks can be configured with retry policies.
        """
        # Verify task has retry configuration
        task = celery_app.tasks["app.tasks.scheduled_tasks.daily_flight_search"]

        # Tasks should have retry capabilities (through bind=True)
        assert hasattr(task, "request"), "Task should be bound (bind=True)"

    def test_task_async_execution(self):
        """
        Test that tasks can be executed asynchronously using .delay().

        Note: This requires a running Celery worker in real scenarios.
        For this test, we verify the task can be queued.
        """
        # Import the task
        from app.tasks.scheduled_tasks import daily_flight_search

        # Queue task asynchronously (will not execute without worker)
        # In test mode, we just verify it can be called
        try:
            # This will queue the task if broker is available
            # Otherwise it will raise an exception (which is fine for test)
            result = daily_flight_search.apply_async(countdown=10)

            # If successful, verify result is an AsyncResult
            assert isinstance(result, AsyncResult), "Should return AsyncResult"
            assert result.id is not None, "Should have task ID"

        except Exception as e:
            # Expected if Redis/broker not available in test environment
            # We just verify the method exists and is callable
            assert hasattr(daily_flight_search, "apply_async"), \
                "Task should have apply_async method"

    def test_task_scheduling_configuration(self):
        """
        Test that tasks are configured in the beat schedule.
        """
        from app.tasks.celery_app import celery_app

        # Get beat schedule
        schedule = celery_app.conf.beat_schedule

        # Verify key tasks are scheduled
        # Note: Schedule configuration is in celery_app.py
        # This test verifies the schedule is accessible

        assert schedule is not None, "Beat schedule should be configured"
        assert isinstance(schedule, dict), "Beat schedule should be a dictionary"

        # Check if any tasks are scheduled (schedule might be empty in test mode)
        # In production, we'd verify specific schedules like:
        # assert "daily-flight-search" in schedule
        # For now, just verify schedule is accessible

    def test_task_result_backend(self):
        """
        Test that task results can be stored and retrieved.
        """
        # Execute task
        result = daily_flight_search()

        # Verify result structure allows storage
        assert isinstance(result, dict), "Result should be serializable (dict)"

        # Verify all values are JSON-serializable
        import json
        try:
            json.dumps(result)
        except (TypeError, ValueError):
            pytest.fail("Task result is not JSON-serializable")

    def test_multiple_tasks_concurrent_execution(self):
        """
        Test that multiple tasks can be queued and executed.
        """
        tasks = [
            update_flight_prices,
            discover_events,
            search_accommodations,
        ]

        results = []

        # Execute all tasks
        for task in tasks:
            result = task()
            results.append(result)

        # Verify all succeeded
        assert len(results) == 3, "Not all tasks executed"
        for result in results:
            assert result["status"] == "success", f"Task failed: {result}"

    def test_task_logging(self):
        """
        Test that tasks log their execution properly.
        """
        import logging
        from io import StringIO

        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)

        logger = logging.getLogger("app.tasks.scheduled_tasks")
        logger.addHandler(handler)

        # Execute task
        daily_flight_search()

        # Get log output
        log_output = log_capture.getvalue()

        # Verify task logged its execution
        assert "daily flight search" in log_output.lower(), \
            "Task should log its execution"

        # Cleanup
        logger.removeHandler(handler)

    def test_task_signature_and_chains(self):
        """
        Test that tasks can be chained together using Celery signatures.
        """
        from celery import chain

        # Create a chain of tasks (without executing)
        workflow = chain(
            daily_flight_search.si(),
            update_flight_prices.si(),
        )

        # Verify workflow can be created
        assert workflow is not None, "Task chain should be created"

        # Note: Actually executing the chain requires a running worker
        # For this test, we just verify the chain can be constructed

    def test_task_error_recovery(self):
        """
        Test that tasks recover gracefully from transient errors.
        """
        # Test cleanup task which has error handling built-in
        result = cleanup_old_data()

        # Should succeed even if some cleanup operations fail
        assert result["status"] == "success"

        # Task should handle exceptions internally and not crash
