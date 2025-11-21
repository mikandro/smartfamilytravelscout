"""
Unit tests for GracefulTask and graceful shutdown functionality.
"""

import signal
import pytest
from unittest.mock import Mock, patch, MagicMock

from app.tasks.celery_app import GracefulTask, cleanup_scraping_job


class TestGracefulTask:
    """Test cases for GracefulTask base class."""

    def test_graceful_task_instantiation(self):
        """Test that GracefulTask can be instantiated."""
        task = GracefulTask()
        assert task is not None
        assert hasattr(task, 'check_shutdown')
        assert hasattr(task, 'is_shutdown_requested')

    def test_is_shutdown_requested_default(self):
        """Test that shutdown is not requested by default."""
        task = GracefulTask()
        assert task.is_shutdown_requested() is False

    def test_check_shutdown_when_not_requested(self):
        """Test that check_shutdown does nothing when shutdown not requested."""
        task = GracefulTask()
        # Should not raise any exception
        task.check_shutdown()

    def test_check_shutdown_when_requested(self):
        """Test that check_shutdown raises SystemExit when shutdown requested."""
        task = GracefulTask()
        task._shutdown_requested = True

        with pytest.raises(SystemExit):
            task.check_shutdown()

    def test_shutdown_flag_can_be_set(self):
        """Test that shutdown flag can be set and checked."""
        task = GracefulTask()
        assert task._shutdown_requested is False

        # Set the flag
        task._shutdown_requested = True
        assert task.is_shutdown_requested() is True


class TestCleanupScrapingJob:
    """Test cases for cleanup_scraping_job utility function."""

    @patch('app.database.get_sync_session')
    def test_cleanup_scraping_job_marks_as_interrupted(self, mock_get_session):
        """Test that cleanup marks running job as interrupted."""
        # Mock database session
        mock_db = MagicMock()
        mock_get_session.return_value = mock_db

        # Mock scraping job
        mock_job = MagicMock()
        mock_job.status = "running"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        # Call cleanup
        cleanup_scraping_job(123, "Test error message")

        # Verify job was updated
        assert mock_job.status == "interrupted"
        assert mock_job.error_message == "Test error message"
        assert mock_job.completed_at is not None
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('app.database.get_sync_session')
    def test_cleanup_scraping_job_skips_non_running(self, mock_get_session):
        """Test that cleanup skips jobs that are not running."""
        # Mock database session
        mock_db = MagicMock()
        mock_get_session.return_value = mock_db

        # Mock scraping job that's already completed
        mock_job = MagicMock()
        mock_job.status = "completed"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_job

        # Call cleanup
        cleanup_scraping_job(123)

        # Verify job was NOT updated
        assert mock_job.status == "completed"
        mock_db.commit.assert_not_called()
        mock_db.close.assert_called_once()

    @patch('app.database.get_sync_session')
    def test_cleanup_scraping_job_handles_missing_job(self, mock_get_session):
        """Test that cleanup handles missing job gracefully."""
        # Mock database session
        mock_db = MagicMock()
        mock_get_session.return_value = mock_db

        # Mock no job found
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Call cleanup - should not raise exception
        cleanup_scraping_job(999)

        mock_db.close.assert_called_once()

    @patch('app.database.get_sync_session')
    @patch('app.tasks.celery_app.logger')
    def test_cleanup_scraping_job_handles_exception(self, mock_logger, mock_get_session):
        """Test that cleanup handles database exceptions gracefully."""
        # Mock database session that raises exception
        mock_db = MagicMock()
        mock_get_session.return_value = mock_db
        mock_db.query.side_effect = Exception("Database error")

        # Call cleanup - should not raise exception
        cleanup_scraping_job(123)

        # Verify error was logged
        mock_logger.error.assert_called_once()


class TestScrapingJobModel:
    """Test cases for ScrapingJob model enhancements."""

    def test_scraping_job_supports_interrupted_status(self):
        """Test that ScrapingJob model supports 'interrupted' status."""
        from app.models.scraping_job import ScrapingJob
        from datetime import datetime

        # Create a scraping job with interrupted status
        job = ScrapingJob(
            job_type="flights",
            source="test_scraper",
            status="interrupted",
            items_scraped=5,
            error_message="Task interrupted by shutdown",
            started_at=datetime.now()
        )

        assert job.status == "interrupted"
        assert job.is_interrupted is True
        assert job.is_running is False
        assert job.is_completed is False
        assert job.is_failed is False
