"""
Custom exceptions for SmartFamilyTravelScout application.

This module defines application-specific exceptions for better error handling
and monitoring throughout the system.
"""


class SmartTravelScoutException(Exception):
    """Base exception class for all SmartFamilyTravelScout exceptions."""

    pass


class ScraperException(SmartTravelScoutException):
    """Base exception for scraper-related errors."""

    pass


class ScraperFailureThresholdExceeded(ScraperException):
    """
    Exception raised when too many scrapers fail during orchestration.

    This exception signals that the scraper failure rate has exceeded the
    configured threshold, indicating a critical system issue that requires
    immediate attention.

    Attributes:
        total_scrapers: Total number of scrapers attempted
        failed_scrapers: Number of scrapers that failed
        failure_rate: Calculated failure rate (0.0 to 1.0)
        threshold: Configured failure threshold (0.0 to 1.0)
        message: Detailed error message
    """

    def __init__(
        self,
        total_scrapers: int,
        failed_scrapers: int,
        failure_rate: float,
        threshold: float,
        message: str = None,
    ):
        """
        Initialize the exception with failure statistics.

        Args:
            total_scrapers: Total number of scrapers attempted
            failed_scrapers: Number of scrapers that failed
            failure_rate: Calculated failure rate (0.0 to 1.0)
            threshold: Configured failure threshold (0.0 to 1.0)
            message: Optional custom error message
        """
        self.total_scrapers = total_scrapers
        self.failed_scrapers = failed_scrapers
        self.failure_rate = failure_rate
        self.threshold = threshold

        if message is None:
            message = (
                f"Scraper failure threshold exceeded: "
                f"{failed_scrapers}/{total_scrapers} scrapers failed "
                f"({failure_rate:.1%} failure rate, threshold: {threshold:.1%})"
            )

        self.message = message
        super().__init__(self.message)

    def __str__(self):
        """Return detailed error message."""
        return self.message


class ConfigurationException(SmartTravelScoutException):
    """Exception raised for configuration errors."""

    pass


class DatabaseException(SmartTravelScoutException):
    """Exception raised for database-related errors."""

    pass


class AIServiceException(SmartTravelScoutException):
    """Exception raised for AI service (Claude API) errors."""

    pass


class NotificationException(SmartTravelScoutException):
    """Exception raised for notification/email errors."""

    pass
