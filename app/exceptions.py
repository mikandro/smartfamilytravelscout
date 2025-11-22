"""
Custom exceptions for SmartFamilyTravelScout application.

This module provides:
1. Base exception hierarchy for application-wide error handling
2. Informative exceptions with actionable guidance (Issue #57)

The informative exceptions include:
- Clear explanation of what went wrong
- Specific remediation instructions
- Relevant configuration details
- Troubleshooting commands
"""

from typing import Optional


# ============================================================================
# Base Exception Hierarchy (for application-wide error handling)
# ============================================================================


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


# ============================================================================
# Informative Exceptions with Actionable Guidance (Issue #57)
# ============================================================================


class InformativeException(SmartTravelScoutException):
    """Base class for informative exceptions with actionable guidance."""

    def __init__(self, message: str, remediation: Optional[str] = None,
                 details: Optional[str] = None, commands: Optional[list[str]] = None):
        """
        Initialize an informative exception.

        Args:
            message: Clear explanation of what went wrong
            remediation: Specific remediation instructions
            details: Relevant configuration or context details
            commands: List of troubleshooting commands to try
        """
        self.message = message
        self.remediation = remediation
        self.details = details
        self.commands = commands or []

        # Build comprehensive error message
        full_message = f"\n{'=' * 80}\n"
        full_message += f"ERROR: {message}\n"

        if details:
            full_message += f"\nDETAILS:\n{details}\n"

        if remediation:
            full_message += f"\nHOW TO FIX:\n{remediation}\n"

        if commands:
            full_message += f"\nTROUBLESHOOTING COMMANDS:\n"
            for cmd in commands:
                full_message += f"  $ {cmd}\n"

        full_message += f"{'=' * 80}\n"

        super().__init__(full_message)


class DatabaseConnectionError(InformativeException, DatabaseException):
    """Raised when database connection fails."""

    def __init__(self, connection_type: str = "unknown", error_details: str = ""):
        message = "Database connection failed"

        details = f"Connection type: {connection_type}"
        if error_details:
            details += f"\nError: {error_details}"

        remediation = """
1. Ensure PostgreSQL is running
2. Verify DATABASE_URL in your .env file is correct
3. Check network connectivity to the database server
4. Verify database credentials are valid
        """.strip()

        commands = [
            "docker-compose up -d postgres",
            "docker-compose ps postgres",
            "docker-compose logs postgres",
            "psql $DATABASE_URL -c 'SELECT 1;'",
        ]

        super().__init__(message, remediation, details, commands)


class APIKeyMissingError(InformativeException, ConfigurationException):
    """Raised when required API key is missing."""

    def __init__(self, service: str, env_var: str, optional: bool = False,
                 fallback_info: Optional[str] = None):
        if optional:
            message = f"{service} API key not configured (optional)"
        else:
            message = f"{service} API key is required but not configured"

        details = f"Environment variable: {env_var}"

        if optional and fallback_info:
            remediation = f"""
{service} will not be used in this session.

OPTIONAL: To enable {service}, add to your .env file:
  {env_var}=your_api_key_here

{fallback_info}
            """.strip()
        else:
            remediation = f"""
1. Obtain an API key from {service}
2. Add it to your .env file:
   {env_var}=your_api_key_here
3. Restart the application
            """.strip()

        commands = [
            f"echo '{env_var}=your_key_here' >> .env",
            "docker-compose restart app",
        ]

        super().__init__(message, remediation, details, commands)


class ScraperInitializationError(InformativeException, ScraperException):
    """Raised when scraper fails to initialize properly."""

    def __init__(self, scraper_name: str, component: str, error_details: str = ""):
        message = f"{scraper_name} scraper failed to initialize {component}"

        details = f"Component: {component}"
        if error_details:
            details += f"\nError: {error_details}"

        remediation = """
1. Ensure Playwright browsers are installed
2. Check if the website structure has changed
3. Verify network connectivity
4. Try with a different scraper
        """.strip()

        commands = [
            "poetry run playwright install chromium",
            "poetry run playwright install-deps",
            f"poetry run scout test-scraper {scraper_name.lower()} --origin MUC --dest BCN",
        ]

        super().__init__(message, remediation, details, commands)


class ConfigurationError(InformativeException, ConfigurationException):
    """Raised when configuration is invalid or missing."""

    def __init__(self, config_item: str, expected: str, actual: str = ""):
        message = f"Invalid configuration for {config_item}"

        details = f"Expected: {expected}"
        if actual:
            details += f"\nActual: {actual}"

        remediation = f"""
1. Check your .env file for correct configuration
2. Refer to .env.example for the correct format
3. Ensure all required environment variables are set
        """.strip()

        commands = [
            "cat .env.example",
            "diff .env.example .env",
        ]

        super().__init__(message, remediation, details, commands)


class DataValidationError(InformativeException):
    """Raised when data fails validation checks."""

    def __init__(self, data_type: str, field: str, validation_issue: str,
                 record_id: Optional[str] = None):
        message = f"Data validation failed for {data_type}"

        details = f"Field: {field}\nIssue: {validation_issue}"
        if record_id:
            details += f"\nRecord ID: {record_id}"

        remediation = """
1. Check the data source for inconsistencies
2. Verify the scraper is extracting data correctly
3. Review recent changes to data models or scrapers
        """.strip()

        commands = []
        if record_id:
            commands.append(f"poetry run scout db query --table {data_type} --id {record_id}")

        super().__init__(message, remediation, details, commands)


class SMTPConfigurationError(InformativeException, NotificationException):
    """Raised when SMTP configuration is invalid."""

    def __init__(self, issue: str, smtp_details: Optional[dict] = None):
        message = "SMTP email configuration error"

        details = f"Issue: {issue}"
        if smtp_details:
            details += "\n\nCurrent configuration:"
            for key, value in smtp_details.items():
                # Mask password
                if 'password' in key.lower():
                    value = "***" if value else "(not set)"
                details += f"\n  {key}: {value}"

        remediation = """
1. Verify SMTP settings in your .env file:
   - SMTP_HOST (e.g., smtp.gmail.com)
   - SMTP_PORT (usually 587 for TLS, 465 for SSL)
   - SMTP_USER (your email address)
   - SMTP_PASSWORD (app-specific password recommended)
   - SMTP_FROM (sender email address)

2. For Gmail, enable 2FA and create an app-specific password

3. Test SMTP connection
        """.strip()

        commands = [
            "poetry run scout email test",
            "docker-compose logs app | grep SMTP",
        ]

        super().__init__(message, remediation, details, commands)


class PlaywrightNotInstalledError(InformativeException, ScraperException):
    """Raised when Playwright is not installed but required."""

    def __init__(self, scraper_name: str):
        message = "Playwright browsers are not installed"

        details = f"Required by: {scraper_name} scraper"

        remediation = """
1. Install Playwright browsers:
   $ poetry run playwright install chromium

2. Install system dependencies:
   $ poetry run playwright install-deps

3. Alternatively, use API-based scrapers that don't require browsers
        """.strip()

        commands = [
            "poetry run playwright install chromium",
            "poetry run playwright install-deps",
            "poetry run scout scrape --scraper kiwi --origin MUC --dest BCN",
        ]

        super().__init__(message, remediation, details, commands)


class ScrapingError(InformativeException, ScraperException):
    """Raised when scraping fails with actionable context."""

    def __init__(self, scraper_name: str, reason: str, url: Optional[str] = None,
                 http_status: Optional[int] = None, timeout: Optional[int] = None):
        message = f"{scraper_name} scraping failed"

        details = f"Reason: {reason}"
        if url:
            details += f"\nURL: {url}"
        if http_status:
            details += f"\nHTTP Status: {http_status}"
        if timeout:
            details += f"\nTimeout: {timeout}s"

        remediation = """
1. Check if the website is accessible
2. Verify the website structure hasn't changed
3. Try using a different scraper
4. Check network connectivity and firewall settings
        """.strip()

        commands = [
            f"curl -I {url}" if url else "# No URL available",
            f"poetry run scout test-scraper {scraper_name.lower()} --origin MUC --dest BCN",
            "poetry run scout scrape --origin MUC --dest BCN",  # Use default scrapers
        ]

        super().__init__(message, remediation, details, commands)
