"""
Standardized exception hierarchy for all scrapers.

This module defines a unified exception hierarchy that all scrapers must use
to ensure consistent error handling across the application.

Exception Hierarchy:
    ScraperError (base)
    ├── RateLimitError
    ├── AuthenticationError
    ├── CaptchaError
    ├── TimeoutError
    ├── ParsingError
    └── NetworkError

Usage:
    >>> from app.scrapers.exceptions import RateLimitError
    >>> raise RateLimitError("Daily rate limit exceeded", retry_after=3600)
"""

from typing import Optional


class ScraperError(Exception):
    """
    Base exception for all scraper-related errors.

    All scraper exceptions should inherit from this class to enable
    consistent error handling in the orchestrator.

    Attributes:
        message: Human-readable error description
        scraper_name: Name of the scraper that raised the error
        recoverable: Whether the error is recoverable (can retry)
        original_error: Original exception if this wraps another error
    """

    def __init__(
        self,
        message: str,
        scraper_name: Optional[str] = None,
        recoverable: bool = False,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize base scraper error.

        Args:
            message: Error message
            scraper_name: Name of the scraper (e.g., 'kiwi', 'skyscanner')
            recoverable: Whether the error is recoverable with retry
            original_error: Original exception if wrapping another error
        """
        self.message = message
        self.scraper_name = scraper_name
        self.recoverable = recoverable
        self.original_error = original_error

        # Build full error message
        full_message = message
        if scraper_name:
            full_message = f"[{scraper_name}] {message}"

        super().__init__(full_message)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"scraper_name={self.scraper_name!r}, "
            f"recoverable={self.recoverable})"
        )


class RateLimitError(ScraperError):
    """
    Raised when API or scraper rate limit is exceeded.

    This error is recoverable - the operation can be retried after
    the specified wait time.

    Attributes:
        retry_after: Number of seconds to wait before retrying
        limit_type: Type of rate limit ('hourly', 'daily', 'monthly')
        current_count: Current request count
        max_count: Maximum allowed requests
    """

    def __init__(
        self,
        message: str,
        scraper_name: Optional[str] = None,
        retry_after: Optional[int] = None,
        limit_type: Optional[str] = None,
        current_count: Optional[int] = None,
        max_count: Optional[int] = None,
    ):
        """
        Initialize rate limit error.

        Args:
            message: Error message
            scraper_name: Name of the scraper
            retry_after: Seconds to wait before retry (None if unknown)
            limit_type: Type of limit ('hourly', 'daily', 'monthly')
            current_count: Current request count
            max_count: Maximum allowed requests
        """
        super().__init__(
            message=message,
            scraper_name=scraper_name,
            recoverable=True,  # Rate limit errors are always recoverable
        )
        self.retry_after = retry_after
        self.limit_type = limit_type
        self.current_count = current_count
        self.max_count = max_count

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"scraper_name={self.scraper_name!r}, "
            f"retry_after={self.retry_after}, "
            f"limit_type={self.limit_type!r})"
        )


class AuthenticationError(ScraperError):
    """
    Raised when authentication or API key validation fails.

    This error is NOT recoverable without user intervention (fixing API key).

    Examples:
        - Invalid API key
        - Expired API key
        - Missing API key
        - Unauthorized access
    """

    def __init__(
        self,
        message: str,
        scraper_name: Optional[str] = None,
        api_key_hint: Optional[str] = None,
    ):
        """
        Initialize authentication error.

        Args:
            message: Error message
            scraper_name: Name of the scraper
            api_key_hint: Hint about which API key is problematic
        """
        super().__init__(
            message=message,
            scraper_name=scraper_name,
            recoverable=False,  # Requires user intervention
        )
        self.api_key_hint = api_key_hint


class CaptchaError(ScraperError):
    """
    Raised when CAPTCHA is detected during web scraping.

    This error is recoverable - can retry with different strategy
    (stealth mode, longer delays, etc.) but success is not guaranteed.

    Attributes:
        captcha_type: Type of CAPTCHA detected ('recaptcha', 'hcaptcha', etc.)
        page_url: URL where CAPTCHA was encountered
        screenshot_path: Path to screenshot of CAPTCHA page
    """

    def __init__(
        self,
        message: str,
        scraper_name: Optional[str] = None,
        captcha_type: Optional[str] = None,
        page_url: Optional[str] = None,
        screenshot_path: Optional[str] = None,
    ):
        """
        Initialize CAPTCHA error.

        Args:
            message: Error message
            scraper_name: Name of the scraper
            captcha_type: Type of CAPTCHA ('recaptcha', 'hcaptcha', etc.)
            page_url: URL where CAPTCHA appeared
            screenshot_path: Path to saved screenshot
        """
        super().__init__(
            message=message,
            scraper_name=scraper_name,
            recoverable=True,  # Can retry with different strategy
        )
        self.captcha_type = captcha_type
        self.page_url = page_url
        self.screenshot_path = screenshot_path


class TimeoutError(ScraperError):
    """
    Raised when a request or operation times out.

    This error is recoverable - can retry the operation.

    Attributes:
        timeout_seconds: Timeout value that was exceeded
        operation: Description of the operation that timed out
    """

    def __init__(
        self,
        message: str,
        scraper_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize timeout error.

        Args:
            message: Error message
            scraper_name: Name of the scraper
            timeout_seconds: Timeout value in seconds
            operation: Description of timed-out operation
            original_error: Original timeout exception
        """
        super().__init__(
            message=message,
            scraper_name=scraper_name,
            recoverable=True,  # Timeouts are recoverable
            original_error=original_error,
        )
        self.timeout_seconds = timeout_seconds
        self.operation = operation


class ParsingError(ScraperError):
    """
    Raised when parsing/extracting data from response fails.

    This error may or may not be recoverable depending on whether
    the website structure changed or just this particular response
    was malformed.

    Attributes:
        response_data: Sample of the response data that failed to parse
        expected_format: Description of expected data format
        parsing_step: Which parsing step failed
    """

    def __init__(
        self,
        message: str,
        scraper_name: Optional[str] = None,
        recoverable: bool = False,
        response_data: Optional[str] = None,
        expected_format: Optional[str] = None,
        parsing_step: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize parsing error.

        Args:
            message: Error message
            scraper_name: Name of the scraper
            recoverable: Whether retry might succeed
            response_data: Sample of problematic response
            expected_format: Description of expected format
            parsing_step: Step that failed
            original_error: Original parsing exception
        """
        super().__init__(
            message=message,
            scraper_name=scraper_name,
            recoverable=recoverable,
            original_error=original_error,
        )
        self.response_data = response_data
        self.expected_format = expected_format
        self.parsing_step = parsing_step


class NetworkError(ScraperError):
    """
    Raised when network-related errors occur.

    This error is recoverable - network issues are usually transient.

    Examples:
        - Connection timeout
        - Connection refused
        - DNS resolution failure
        - Network unreachable

    Attributes:
        status_code: HTTP status code if applicable
        url: URL that was being accessed
    """

    def __init__(
        self,
        message: str,
        scraper_name: Optional[str] = None,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        """
        Initialize network error.

        Args:
            message: Error message
            scraper_name: Name of the scraper
            status_code: HTTP status code if applicable
            url: URL being accessed
            original_error: Original network exception
        """
        super().__init__(
            message=message,
            scraper_name=scraper_name,
            recoverable=True,  # Network errors are usually transient
            original_error=original_error,
        )
        self.status_code = status_code
        self.url = url


# Convenience function for logging errors consistently
def log_scraper_error(logger, error: ScraperError) -> None:
    """
    Log a scraper error with consistent formatting.

    Args:
        logger: Logger instance
        error: ScraperError instance

    Example:
        >>> from app.scrapers.exceptions import log_scraper_error
        >>> try:
        ...     # scraping code
        ... except RateLimitError as e:
        ...     log_scraper_error(logger, e)
    """
    error_details = {
        "scraper": error.scraper_name,
        "recoverable": error.recoverable,
        "error_type": error.__class__.__name__,
    }

    # Add specific attributes based on error type
    if isinstance(error, RateLimitError):
        error_details["retry_after"] = error.retry_after
        error_details["limit_type"] = error.limit_type
    elif isinstance(error, CaptchaError):
        error_details["captcha_type"] = error.captcha_type
        error_details["screenshot"] = error.screenshot_path
    elif isinstance(error, TimeoutError):
        error_details["timeout_seconds"] = error.timeout_seconds
        error_details["operation"] = error.operation
    elif isinstance(error, NetworkError):
        error_details["status_code"] = error.status_code
        error_details["url"] = error.url

    logger.error(
        f"{error.message} | Details: {error_details}",
        exc_info=error.original_error if error.original_error else True,
    )
