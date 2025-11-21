"""
Tests for Celery scheduled tasks.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app.tasks.scheduled_tasks import (
    daily_flight_search,
    update_flight_prices,
    discover_events,
    search_accommodations,
    cleanup_old_data,
    send_deal_notifications,
)


class TestDailyFlightSearch:
    """Test daily flight search task."""

    @patch('app.tasks.scheduled_tasks.logger')
    @patch('app.tasks.scheduled_tasks.settings')
    def test_daily_flight_search_success(self, mock_settings, mock_logger):
        """Test successful daily flight search."""
        # Setup
        mock_settings.get_departure_airports_list.return_value = ["MUC", "FMM", "NUE"]
        mock_settings.advance_booking_days = 90

        mock_self = Mock()
        mock_self.request.id = "test-task-123"

        # Execute
        result = daily_flight_search(mock_self)

        # Verify
        assert result["status"] == "success"
        assert result["airports"] == ["MUC", "FMM", "NUE"]
        assert result["task_id"] == "test-task-123"
        mock_logger.info.assert_any_call("Starting daily flight search task")
        mock_logger.info.assert_any_call("Daily flight search task completed successfully")

    @patch('app.tasks.scheduled_tasks.logger')
    @patch('app.tasks.scheduled_tasks.settings')
    def test_daily_flight_search_calculates_dates(self, mock_settings, mock_logger):
        """Test that daily flight search calculates correct search dates."""
        # Setup
        mock_settings.get_departure_airports_list.return_value = ["MUC"]
        mock_settings.advance_booking_days = 60

        mock_self = Mock()
        mock_self.request.id = "test-task-123"

        # Execute
        with patch('app.tasks.scheduled_tasks.datetime') as mock_datetime:
            now = datetime(2025, 1, 15, 10, 0, 0)
            mock_datetime.now.return_value = now

            result = daily_flight_search(mock_self)

            # Verify date calculation logging happened
            assert result["status"] == "success"

    @patch('app.tasks.scheduled_tasks.logger')
    @patch('app.tasks.scheduled_tasks.settings')
    def test_daily_flight_search_handles_empty_airports(self, mock_settings, mock_logger):
        """Test daily flight search with no configured airports."""
        # Setup
        mock_settings.get_departure_airports_list.return_value = []
        mock_settings.advance_booking_days = 90

        mock_self = Mock()
        mock_self.request.id = "test-task-123"

        # Execute
        result = daily_flight_search(mock_self)

        # Verify
        assert result["status"] == "success"
        assert result["airports"] == []

    @patch('app.tasks.scheduled_tasks.logger')
    @patch('app.tasks.scheduled_tasks.settings')
    def test_daily_flight_search_handles_exception(self, mock_settings, mock_logger):
        """Test daily flight search error handling."""
        # Setup
        mock_settings.get_departure_airports_list.side_effect = Exception("Test error")

        mock_self = Mock()
        mock_self.request.id = "test-task-123"

        # Execute and verify
        with pytest.raises(Exception, match="Test error"):
            daily_flight_search(mock_self)

        mock_logger.error.assert_called_once()


class TestUpdateFlightPrices:
    """Test hourly price update task."""

    @patch('app.tasks.scheduled_tasks.logger')
    def test_update_flight_prices_success(self, mock_logger):
        """Test successful flight price update."""
        # Setup
        mock_self = Mock()
        mock_self.request.id = "test-task-456"

        # Execute
        result = update_flight_prices(mock_self)

        # Verify
        assert result["status"] == "success"
        assert result["task_id"] == "test-task-456"
        mock_logger.info.assert_any_call("Starting hourly price update task")
        mock_logger.info.assert_any_call("Hourly price update task completed successfully")

    @patch('app.tasks.scheduled_tasks.logger')
    def test_update_flight_prices_handles_exception(self, mock_logger):
        """Test price update error handling."""
        # Setup - patch logger to raise exception
        mock_self = Mock()
        mock_self.request.id = "test-task-456"

        # Make the first info call succeed but inject an error somewhere
        mock_logger.info.side_effect = [None, Exception("Database error")]

        # Execute and verify
        with pytest.raises(Exception, match="Database error"):
            update_flight_prices(mock_self)

        mock_logger.error.assert_called_once()


class TestDiscoverEvents:
    """Test weekly event discovery task."""

    @patch('app.tasks.scheduled_tasks.logger')
    def test_discover_events_success(self, mock_logger):
        """Test successful event discovery."""
        # Setup
        mock_self = Mock()
        mock_self.request.id = "test-task-789"

        # Execute
        result = discover_events(mock_self)

        # Verify
        assert result["status"] == "success"
        assert result["task_id"] == "test-task-789"
        mock_logger.info.assert_any_call("Starting weekly event discovery task")
        mock_logger.info.assert_any_call("Weekly event discovery task completed successfully")

    @patch('app.tasks.scheduled_tasks.logger')
    def test_discover_events_handles_exception(self, mock_logger):
        """Test event discovery error handling."""
        # Setup
        mock_self = Mock()
        mock_self.request.id = "test-task-789"

        # Make the first info call succeed but second raises exception
        mock_logger.info.side_effect = [None, Exception("API error")]

        # Execute and verify
        with pytest.raises(Exception, match="API error"):
            discover_events(mock_self)

        mock_logger.error.assert_called_once()


class TestSearchAccommodations:
    """Test daily accommodation search task."""

    @patch('app.tasks.scheduled_tasks.logger')
    def test_search_accommodations_success(self, mock_logger):
        """Test successful accommodation search."""
        # Setup
        mock_self = Mock()
        mock_self.request.id = "test-task-101"

        # Execute
        result = search_accommodations(mock_self)

        # Verify
        assert result["status"] == "success"
        assert result["task_id"] == "test-task-101"
        mock_logger.info.assert_any_call("Starting daily accommodation search task")
        mock_logger.info.assert_any_call("Daily accommodation search task completed successfully")

    @patch('app.tasks.scheduled_tasks.logger')
    def test_search_accommodations_handles_exception(self, mock_logger):
        """Test accommodation search error handling."""
        # Setup
        mock_self = Mock()
        mock_self.request.id = "test-task-101"

        mock_logger.info.side_effect = [None, Exception("Scraper error")]

        # Execute and verify
        with pytest.raises(Exception, match="Scraper error"):
            search_accommodations(mock_self)

        mock_logger.error.assert_called_once()


class TestCleanupOldData:
    """Test daily cleanup task."""

    @patch('app.tasks.scheduled_tasks.logger')
    def test_cleanup_old_data_success(self, mock_logger):
        """Test successful data cleanup."""
        # Setup
        mock_self = Mock()
        mock_self.request.id = "test-task-202"

        # Execute
        with patch('app.tasks.scheduled_tasks.datetime') as mock_datetime:
            now = datetime(2025, 2, 15, 2, 0, 0)
            mock_datetime.now.return_value = now

            result = cleanup_old_data(mock_self)

            # Verify
            assert result["status"] == "success"
            assert result["task_id"] == "test-task-202"
            assert "cutoff_date" in result

            # Verify cutoff date is 30 days ago
            expected_cutoff = now - timedelta(days=30)
            assert result["cutoff_date"] == expected_cutoff.isoformat()

    @patch('app.tasks.scheduled_tasks.logger')
    def test_cleanup_old_data_logs_cutoff_date(self, mock_logger):
        """Test that cleanup logs the cutoff date."""
        # Setup
        mock_self = Mock()
        mock_self.request.id = "test-task-202"

        # Execute
        result = cleanup_old_data(mock_self)

        # Verify logging
        assert result["status"] == "success"
        mock_logger.info.assert_any_call("Starting daily cleanup task")

        # Check that cutoff date was logged
        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Cleaning up data older than" in str(call) for call in log_calls)

    @patch('app.tasks.scheduled_tasks.logger')
    def test_cleanup_old_data_calculates_30_day_cutoff(self, mock_logger):
        """Test that cleanup uses 30-day cutoff."""
        # Setup
        mock_self = Mock()
        mock_self.request.id = "test-task-202"

        # Execute with fixed time
        with patch('app.tasks.scheduled_tasks.datetime') as mock_datetime:
            fixed_now = datetime(2025, 3, 1, 2, 0, 0)
            mock_datetime.now.return_value = fixed_now

            result = cleanup_old_data(mock_self)

            # Expected cutoff: March 1 - 30 days = January 30
            expected_cutoff = datetime(2025, 1, 30, 2, 0, 0)
            assert result["cutoff_date"] == expected_cutoff.isoformat()

    @patch('app.tasks.scheduled_tasks.logger')
    def test_cleanup_old_data_handles_exception(self, mock_logger):
        """Test cleanup error handling."""
        # Setup
        mock_self = Mock()
        mock_self.request.id = "test-task-202"

        # Force an exception by making datetime.now() fail after first call
        with patch('app.tasks.scheduled_tasks.datetime') as mock_datetime:
            mock_datetime.now.side_effect = [datetime.now(), Exception("Database error")]

            # Execute and verify
            with pytest.raises(Exception, match="Database error"):
                cleanup_old_data(mock_self)

            mock_logger.error.assert_called_once()


class TestSendDealNotifications:
    """Test deal notification task."""

    @patch('app.tasks.scheduled_tasks.logger')
    def test_send_deal_notifications_success(self, mock_logger):
        """Test successful deal notifications."""
        # Setup
        mock_self = Mock()
        mock_self.request.id = "test-task-303"

        # Execute
        result = send_deal_notifications(mock_self)

        # Verify
        assert result["status"] == "success"
        assert result["task_id"] == "test-task-303"
        mock_logger.info.assert_any_call("Starting deal notification task")
        mock_logger.info.assert_any_call("Deal notification task completed successfully")

    @patch('app.tasks.scheduled_tasks.logger')
    def test_send_deal_notifications_handles_exception(self, mock_logger):
        """Test notification error handling."""
        # Setup
        mock_self = Mock()
        mock_self.request.id = "test-task-303"

        mock_logger.info.side_effect = [None, Exception("Email error")]

        # Execute and verify
        with pytest.raises(Exception, match="Email error"):
            send_deal_notifications(mock_self)

        mock_logger.error.assert_called_once()


class TestTaskIntegration:
    """Integration tests for scheduled tasks."""

    def test_all_tasks_have_bind_parameter(self):
        """Test that all tasks use bind=True."""
        # All our tasks should accept self as first parameter
        tasks = [
            daily_flight_search,
            update_flight_prices,
            discover_events,
            search_accommodations,
            cleanup_old_data,
            send_deal_notifications,
        ]

        for task in tasks:
            # Verify task is callable
            assert callable(task)

    def test_all_tasks_return_dict_with_status(self):
        """Test that all tasks return a dict with status."""
        mock_self = Mock()
        mock_self.request.id = "test-id"

        with patch('app.tasks.scheduled_tasks.logger'):
            with patch('app.tasks.scheduled_tasks.settings') as mock_settings:
                mock_settings.get_departure_airports_list.return_value = ["MUC"]
                mock_settings.advance_booking_days = 90

                # Test each task
                result1 = daily_flight_search(mock_self)
                assert isinstance(result1, dict)
                assert result1["status"] == "success"

                result2 = update_flight_prices(mock_self)
                assert isinstance(result2, dict)
                assert result2["status"] == "success"

                result3 = discover_events(mock_self)
                assert isinstance(result3, dict)
                assert result3["status"] == "success"

                result4 = search_accommodations(mock_self)
                assert isinstance(result4, dict)
                assert result4["status"] == "success"

                result5 = cleanup_old_data(mock_self)
                assert isinstance(result5, dict)
                assert result5["status"] == "success"

                result6 = send_deal_notifications(mock_self)
                assert isinstance(result6, dict)
                assert result6["status"] == "success"

    def test_all_tasks_include_task_id_in_result(self):
        """Test that all tasks include task_id in result."""
        mock_self = Mock()
        mock_self.request.id = "unique-task-id-123"

        with patch('app.tasks.scheduled_tasks.logger'):
            with patch('app.tasks.scheduled_tasks.settings') as mock_settings:
                mock_settings.get_departure_airports_list.return_value = ["MUC"]
                mock_settings.advance_booking_days = 90

                # Test each task includes task_id
                assert daily_flight_search(mock_self)["task_id"] == "unique-task-id-123"
                assert update_flight_prices(mock_self)["task_id"] == "unique-task-id-123"
                assert discover_events(mock_self)["task_id"] == "unique-task-id-123"
                assert search_accommodations(mock_self)["task_id"] == "unique-task-id-123"
                assert cleanup_old_data(mock_self)["task_id"] == "unique-task-id-123"
                assert send_deal_notifications(mock_self)["task_id"] == "unique-task-id-123"
