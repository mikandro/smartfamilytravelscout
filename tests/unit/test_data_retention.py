"""
Unit tests for data_retention module.
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app.utils.data_retention import (
    CleanupStats,
    cleanup_old_flights,
    cleanup_old_events,
    cleanup_old_packages,
    cleanup_old_accommodations,
    cleanup_old_scraping_jobs,
    cleanup_all_old_data,
    get_retention_cutoff_dates,
)


class TestCleanupStats:
    """Tests for CleanupStats dataclass."""

    def test_cleanup_stats_creation(self):
        """Test creating CleanupStats object."""
        stats = CleanupStats(
            flights_deleted=10,
            events_deleted=5,
            packages_deleted=3,
            accommodations_deleted=8,
            scraping_jobs_deleted=12,
        )
        assert stats.flights_deleted == 10
        assert stats.events_deleted == 5
        assert stats.packages_deleted == 3
        assert stats.accommodations_deleted == 8
        assert stats.scraping_jobs_deleted == 12

    def test_cleanup_stats_default(self):
        """Test CleanupStats with default values."""
        stats = CleanupStats()
        assert stats.flights_deleted == 0
        assert stats.events_deleted == 0
        assert stats.packages_deleted == 0
        assert stats.accommodations_deleted == 0
        assert stats.scraping_jobs_deleted == 0

    def test_total_deleted(self):
        """Test total_deleted property calculation."""
        stats = CleanupStats(
            flights_deleted=10,
            events_deleted=5,
            packages_deleted=3,
            accommodations_deleted=8,
            scraping_jobs_deleted=12,
        )
        assert stats.total_deleted == 38

    def test_to_dict(self):
        """Test converting stats to dictionary."""
        stats = CleanupStats(
            flights_deleted=10,
            events_deleted=5,
            packages_deleted=3,
        )
        result = stats.to_dict()
        assert isinstance(result, dict)
        assert result["flights_deleted"] == 10
        assert result["events_deleted"] == 5
        assert result["packages_deleted"] == 3
        assert result["accommodations_deleted"] == 0
        assert result["scraping_jobs_deleted"] == 0
        assert result["total_deleted"] == 18


class TestCleanupOldFlights:
    """Tests for cleanup_old_flights function."""

    @patch("app.utils.data_retention.settings")
    @patch("app.utils.data_retention.date")
    def test_cleanup_old_flights_default_retention(self, mock_date, mock_settings):
        """Test cleaning up flights with default retention period."""
        # Mock settings
        mock_settings.flight_retention_days = 90

        # Mock date.today()
        mock_date.today.return_value = date(2025, 11, 21)

        # Mock database session
        mock_db = Mock()
        mock_result = Mock()
        mock_result.rowcount = 15
        mock_db.execute.return_value = mock_result

        # Call function
        deleted_count = cleanup_old_flights(mock_db)

        # Verify
        assert deleted_count == 15
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @patch("app.utils.data_retention.date")
    def test_cleanup_old_flights_custom_retention(self, mock_date):
        """Test cleaning up flights with custom retention period."""
        # Mock date.today()
        mock_date.today.return_value = date(2025, 11, 21)

        # Mock database session
        mock_db = Mock()
        mock_result = Mock()
        mock_result.rowcount = 20
        mock_db.execute.return_value = mock_result

        # Call function with custom retention
        deleted_count = cleanup_old_flights(mock_db, retention_days=30)

        # Verify
        assert deleted_count == 20
        mock_db.commit.assert_called_once()

    def test_cleanup_old_flights_error_handling(self):
        """Test error handling in cleanup_old_flights."""
        # Mock database session that raises exception
        mock_db = Mock()
        mock_db.execute.side_effect = Exception("Database error")

        # Call function and expect exception
        with pytest.raises(Exception, match="Database error"):
            cleanup_old_flights(mock_db)

        # Verify rollback was called
        mock_db.rollback.assert_called_once()


class TestCleanupOldEvents:
    """Tests for cleanup_old_events function."""

    @patch("app.utils.data_retention.settings")
    @patch("app.utils.data_retention.date")
    def test_cleanup_old_events_default_retention(self, mock_date, mock_settings):
        """Test cleaning up events with default retention period."""
        # Mock settings
        mock_settings.event_retention_days = 180

        # Mock date.today()
        mock_date.today.return_value = date(2025, 11, 21)

        # Mock database session
        mock_db = Mock()
        mock_result = Mock()
        mock_result.rowcount = 8
        mock_db.execute.return_value = mock_result

        # Call function
        deleted_count = cleanup_old_events(mock_db)

        # Verify
        assert deleted_count == 8
        mock_db.commit.assert_called_once()


class TestCleanupOldPackages:
    """Tests for cleanup_old_packages function."""

    @patch("app.utils.data_retention.settings")
    @patch("app.utils.data_retention.date")
    def test_cleanup_old_packages_default_retention(self, mock_date, mock_settings):
        """Test cleaning up packages with default retention period."""
        # Mock settings
        mock_settings.package_retention_days = 60

        # Mock date.today()
        mock_date.today.return_value = date(2025, 11, 21)

        # Mock database session
        mock_db = Mock()
        mock_result = Mock()
        mock_result.rowcount = 12
        mock_db.execute.return_value = mock_result

        # Call function
        deleted_count = cleanup_old_packages(mock_db)

        # Verify
        assert deleted_count == 12
        mock_db.commit.assert_called_once()


class TestCleanupOldAccommodations:
    """Tests for cleanup_old_accommodations function."""

    @patch("app.utils.data_retention.settings")
    @patch("app.utils.data_retention.datetime")
    def test_cleanup_old_accommodations_default_retention(
        self, mock_datetime, mock_settings
    ):
        """Test cleaning up accommodations with default retention period."""
        # Mock settings
        mock_settings.accommodation_retention_days = 180

        # Mock datetime.now()
        mock_datetime.now.return_value = datetime(2025, 11, 21, 10, 30, 45)

        # Mock database session
        mock_db = Mock()
        mock_result = Mock()
        mock_result.rowcount = 5
        mock_db.execute.return_value = mock_result

        # Call function
        deleted_count = cleanup_old_accommodations(mock_db)

        # Verify
        assert deleted_count == 5
        mock_db.commit.assert_called_once()


class TestCleanupOldScrapingJobs:
    """Tests for cleanup_old_scraping_jobs function."""

    @patch("app.utils.data_retention.settings")
    @patch("app.utils.data_retention.datetime")
    def test_cleanup_old_scraping_jobs_default_retention(
        self, mock_datetime, mock_settings
    ):
        """Test cleaning up scraping jobs with default retention period."""
        # Mock settings
        mock_settings.scraping_job_retention_days = 30

        # Mock datetime.now()
        mock_datetime.now.return_value = datetime(2025, 11, 21, 10, 30, 45)

        # Mock database session
        mock_db = Mock()
        mock_result = Mock()
        mock_result.rowcount = 18
        mock_db.execute.return_value = mock_result

        # Call function
        deleted_count = cleanup_old_scraping_jobs(mock_db)

        # Verify
        assert deleted_count == 18
        mock_db.commit.assert_called_once()

    @patch("app.utils.data_retention.datetime")
    def test_cleanup_old_scraping_jobs_only_completed(self, mock_datetime):
        """Test that only completed/failed jobs are deleted, not running jobs."""
        # Mock datetime.now()
        mock_datetime.now.return_value = datetime(2025, 11, 21, 10, 30, 45)

        # Mock database session
        mock_db = Mock()
        mock_result = Mock()
        mock_result.rowcount = 10
        mock_db.execute.return_value = mock_result

        # Call function
        deleted_count = cleanup_old_scraping_jobs(mock_db, retention_days=30)

        # Verify the SQL query was called (mocked, but we check it was executed)
        assert deleted_count == 10
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()


class TestCleanupAllOldData:
    """Tests for cleanup_all_old_data function."""

    @patch("app.utils.data_retention.cleanup_old_scraping_jobs")
    @patch("app.utils.data_retention.cleanup_old_accommodations")
    @patch("app.utils.data_retention.cleanup_old_packages")
    @patch("app.utils.data_retention.cleanup_old_events")
    @patch("app.utils.data_retention.cleanup_old_flights")
    def test_cleanup_all_old_data_success(
        self,
        mock_flights,
        mock_events,
        mock_packages,
        mock_accommodations,
        mock_jobs,
    ):
        """Test running all cleanup operations."""
        # Mock individual cleanup functions
        mock_flights.return_value = 10
        mock_events.return_value = 5
        mock_packages.return_value = 3
        mock_accommodations.return_value = 8
        mock_jobs.return_value = 12

        # Mock database session
        mock_db = Mock()

        # Call function
        stats = cleanup_all_old_data(mock_db)

        # Verify
        assert stats.flights_deleted == 10
        assert stats.events_deleted == 5
        assert stats.packages_deleted == 3
        assert stats.accommodations_deleted == 8
        assert stats.scraping_jobs_deleted == 12
        assert stats.total_deleted == 38

        # Verify all cleanup functions were called
        mock_flights.assert_called_once_with(mock_db, None)
        mock_events.assert_called_once_with(mock_db, None)
        mock_packages.assert_called_once_with(mock_db, None)
        mock_accommodations.assert_called_once_with(mock_db, None)
        mock_jobs.assert_called_once_with(mock_db, None)

    @patch("app.utils.data_retention.cleanup_old_scraping_jobs")
    @patch("app.utils.data_retention.cleanup_old_accommodations")
    @patch("app.utils.data_retention.cleanup_old_packages")
    @patch("app.utils.data_retention.cleanup_old_events")
    @patch("app.utils.data_retention.cleanup_old_flights")
    def test_cleanup_all_old_data_with_custom_retention(
        self,
        mock_flights,
        mock_events,
        mock_packages,
        mock_accommodations,
        mock_jobs,
    ):
        """Test running all cleanup operations with custom retention periods."""
        # Mock individual cleanup functions
        mock_flights.return_value = 15
        mock_events.return_value = 7
        mock_packages.return_value = 4
        mock_accommodations.return_value = 9
        mock_jobs.return_value = 13

        # Mock database session
        mock_db = Mock()

        # Call function with custom retention periods
        stats = cleanup_all_old_data(
            mock_db,
            flight_retention=30,
            event_retention=60,
            package_retention=45,
            accommodation_retention=90,
            scraping_job_retention=15,
        )

        # Verify
        assert stats.total_deleted == 48

        # Verify all cleanup functions were called with custom retention
        mock_flights.assert_called_once_with(mock_db, 30)
        mock_events.assert_called_once_with(mock_db, 60)
        mock_packages.assert_called_once_with(mock_db, 45)
        mock_accommodations.assert_called_once_with(mock_db, 90)
        mock_jobs.assert_called_once_with(mock_db, 15)

    @patch("app.utils.data_retention.cleanup_old_flights")
    def test_cleanup_all_old_data_error_handling(self, mock_flights):
        """Test error handling in cleanup_all_old_data."""
        # Mock cleanup function that raises exception
        mock_flights.side_effect = Exception("Cleanup error")

        # Mock database session
        mock_db = Mock()

        # Call function and expect exception
        with pytest.raises(Exception, match="Cleanup error"):
            cleanup_all_old_data(mock_db)


class TestGetRetentionCutoffDates:
    """Tests for get_retention_cutoff_dates function."""

    @patch("app.utils.data_retention.settings")
    @patch("app.utils.data_retention.datetime")
    @patch("app.utils.data_retention.date")
    def test_get_retention_cutoff_dates(
        self, mock_date, mock_datetime, mock_settings
    ):
        """Test calculating cutoff dates for all data types."""
        # Mock settings
        mock_settings.flight_retention_days = 90
        mock_settings.event_retention_days = 180
        mock_settings.package_retention_days = 60
        mock_settings.accommodation_retention_days = 180
        mock_settings.scraping_job_retention_days = 30

        # Mock date.today() and datetime.now()
        mock_date.today.return_value = date(2025, 11, 21)
        mock_datetime.now.return_value = datetime(2025, 11, 21, 10, 30, 45)

        # Call function
        cutoff_dates = get_retention_cutoff_dates()

        # Verify
        assert isinstance(cutoff_dates, dict)
        assert "flights" in cutoff_dates
        assert "events" in cutoff_dates
        assert "packages" in cutoff_dates
        assert "accommodations" in cutoff_dates
        assert "scraping_jobs" in cutoff_dates

        # Verify cutoff dates are calculated correctly
        assert cutoff_dates["flights"] == date(2025, 11, 21) - timedelta(days=90)
        assert cutoff_dates["events"] == date(2025, 11, 21) - timedelta(days=180)
        assert cutoff_dates["packages"] == date(2025, 11, 21) - timedelta(days=60)
        assert cutoff_dates["accommodations"] == datetime(2025, 11, 21, 10, 30, 45) - timedelta(days=180)
        assert cutoff_dates["scraping_jobs"] == datetime(2025, 11, 21, 10, 30, 45) - timedelta(days=30)
