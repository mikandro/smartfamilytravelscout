"""
Base scraper class providing standardized interface for all scrapers.

This module defines the BaseScraper abstract class that all flight scrapers
must inherit from. It ensures consistent method signatures, error handling,
and logging across all scraper implementations.

Usage:
    >>> from app.scrapers.base import BaseScraper
    >>> class MyCustomScraper(BaseScraper):
    ...     async def scrape_flights(self, origin, destination, departure_date, return_date):
    ...         # Implementation here
    ...         pass
"""

import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, List, Optional

from app.scrapers.exceptions import ScraperError, log_scraper_error


class BaseScraper(ABC):
    """
    Abstract base class for all flight scrapers.

    All scraper implementations must inherit from this class and implement
    the required abstract methods. This ensures consistency across scrapers
    and makes the orchestrator's job easier.

    Class Attributes:
        SCRAPER_NAME: Unique identifier for the scraper (e.g., 'kiwi', 'skyscanner')
        SCRAPER_TYPE: Type of scraper ('api' or 'web')
        REQUIRES_API_KEY: Whether scraper needs an API key
        DEFAULT_TIMEOUT: Default timeout for requests in seconds

    Instance Attributes:
        logger: Logger instance for this scraper
        timeout: Request timeout in seconds

    Abstract Methods:
        scrape_flights: Main method to scrape flight data

    Provided Methods:
        _handle_error: Standardized error handling
        _validate_dates: Date validation helper
        _validate_airport_code: Airport code validation helper

    Example:
        >>> class MyAPIClient(BaseScraper):
        ...     SCRAPER_NAME = "myapi"
        ...     SCRAPER_TYPE = "api"
        ...     REQUIRES_API_KEY = True
        ...
        ...     async def scrape_flights(self, origin, destination, departure_date, return_date):
        ...         try:
        ...             # API call here
        ...             return flights
        ...         except Exception as e:
        ...             self._handle_error(e, "search_flights")
        ...             return []
    """

    # Class attributes - must be overridden by subclasses
    SCRAPER_NAME: str = "base"
    SCRAPER_TYPE: str = "unknown"  # 'api' or 'web'
    REQUIRES_API_KEY: bool = False
    DEFAULT_TIMEOUT: int = 30

    def __init__(self, timeout: Optional[int] = None):
        """
        Initialize base scraper.

        Args:
            timeout: Request timeout in seconds (uses DEFAULT_TIMEOUT if not specified)
        """
        self.timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        self.logger = logging.getLogger(f"{__name__}.{self.SCRAPER_NAME}")
        self.logger.info(
            f"{self.SCRAPER_NAME.capitalize()} scraper initialized "
            f"(type={self.SCRAPER_TYPE}, timeout={self.timeout}s)"
        )

    @abstractmethod
    async def scrape_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date] = None,
        **kwargs,
    ) -> List[Dict]:
        """
        Scrape flights for the given route and dates.

        This is the main method that must be implemented by all scrapers.
        It should return a list of flight dictionaries in standardized format.

        Args:
            origin: Origin airport IATA code (e.g., 'MUC')
            destination: Destination airport IATA code (e.g., 'LIS')
            departure_date: Departure date
            return_date: Return date (None for one-way flights)
            **kwargs: Additional scraper-specific parameters

        Returns:
            List of flight dictionaries in standardized format:
            [
                {
                    'origin_airport': str,
                    'destination_airport': str,
                    'origin_city': str,
                    'destination_city': str,
                    'airline': str,
                    'departure_date': str (YYYY-MM-DD),
                    'departure_time': str (HH:MM) or None,
                    'return_date': str (YYYY-MM-DD) or None,
                    'return_time': str (HH:MM) or None,
                    'price_per_person': float,
                    'total_price': float,
                    'direct_flight': bool,
                    'booking_class': str,
                    'source': str,
                    'booking_url': str or None,
                    'scraped_at': str (ISO format datetime),
                },
                ...
            ]

        Raises:
            ScraperError: Or any of its subclasses for specific error conditions
            - RateLimitError: When rate limit is exceeded
            - AuthenticationError: When API authentication fails
            - CaptchaError: When CAPTCHA is detected
            - TimeoutError: When request times out
            - ParsingError: When response parsing fails
            - NetworkError: When network issues occur

        Example:
            >>> scraper = MyScraper()
            >>> flights = await scraper.scrape_flights('MUC', 'LIS', date(2025, 12, 20), date(2025, 12, 27))
            >>> print(f"Found {len(flights)} flights")
        """
        pass

    def _handle_error(
        self,
        error: Exception,
        operation: str = "unknown",
        recoverable: bool = False,
    ) -> None:
        """
        Handle and log errors in a standardized way.

        This method should be called from within exception handlers to ensure
        consistent error logging and wrapping.

        Args:
            error: The caught exception
            operation: Description of the operation that failed
            recoverable: Whether the error is recoverable with retry

        Example:
            >>> try:
            ...     result = await api_call()
            ... except Exception as e:
            ...     self._handle_error(e, "api_call", recoverable=True)
            ...     return []
        """
        # If already a ScraperError, just log it
        if isinstance(error, ScraperError):
            log_scraper_error(self.logger, error)
            return

        # Otherwise, wrap in generic ScraperError
        wrapped_error = ScraperError(
            message=f"Error during {operation}: {str(error)}",
            scraper_name=self.SCRAPER_NAME,
            recoverable=recoverable,
            original_error=error,
        )
        log_scraper_error(self.logger, wrapped_error)

    def _validate_dates(
        self,
        departure_date: date,
        return_date: Optional[date] = None,
    ) -> None:
        """
        Validate that dates are reasonable.

        Args:
            departure_date: Departure date
            return_date: Return date (optional)

        Raises:
            ValueError: If dates are invalid
        """
        from datetime import datetime

        today = datetime.now().date()

        # Check departure date is not in the past
        if departure_date < today:
            raise ValueError(
                f"Departure date {departure_date} is in the past. "
                f"Must be today ({today}) or later."
            )

        # Check return date is after departure
        if return_date and return_date < departure_date:
            raise ValueError(
                f"Return date {return_date} is before departure date {departure_date}"
            )

        # Warn if dates are very far in the future (> 1 year)
        max_date = datetime(today.year + 1, today.month, today.day).date()
        if departure_date > max_date:
            self.logger.warning(
                f"Departure date {departure_date} is more than 1 year in the future. "
                f"Availability may be limited."
            )

    def _validate_airport_code(self, code: str, field_name: str = "airport") -> str:
        """
        Validate and normalize airport IATA code.

        Args:
            code: Airport IATA code (e.g., 'muc', 'MUC')
            field_name: Name of the field for error messages

        Returns:
            Normalized uppercase IATA code

        Raises:
            ValueError: If code is invalid
        """
        if not code:
            raise ValueError(f"{field_name} code cannot be empty")

        code = code.strip().upper()

        # IATA codes are always 3 characters
        if len(code) != 3:
            raise ValueError(
                f"Invalid {field_name} code '{code}'. IATA codes must be 3 characters."
            )

        # IATA codes are alphabetic
        if not code.isalpha():
            raise ValueError(
                f"Invalid {field_name} code '{code}'. IATA codes must be alphabetic."
            )

        return code

    def _normalize_flight_data(self, flight: Dict) -> Dict:
        """
        Ensure flight dictionary has all required fields.

        This method adds missing optional fields with default values
        to ensure consistent data structure.

        Args:
            flight: Flight dictionary (may be incomplete)

        Returns:
            Normalized flight dictionary with all fields
        """
        from datetime import datetime

        normalized = {
            "origin_airport": flight.get("origin_airport", ""),
            "destination_airport": flight.get("destination_airport", ""),
            "origin_city": flight.get("origin_city", flight.get("origin_airport", "")),
            "destination_city": flight.get(
                "destination_city", flight.get("destination_airport", "")
            ),
            "airline": flight.get("airline", "Unknown"),
            "departure_date": flight.get("departure_date", ""),
            "departure_time": flight.get("departure_time"),
            "return_date": flight.get("return_date"),
            "return_time": flight.get("return_time"),
            "price_per_person": flight.get("price_per_person", 0.0),
            "total_price": flight.get("total_price", 0.0),
            "direct_flight": flight.get("direct_flight", True),
            "booking_class": flight.get("booking_class", "Economy"),
            "source": flight.get("source", self.SCRAPER_NAME),
            "booking_url": flight.get("booking_url"),
            "scraped_at": flight.get("scraped_at", datetime.now().isoformat()),
        }

        return normalized

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"scraper_name={self.SCRAPER_NAME!r}, "
            f"type={self.SCRAPER_TYPE!r}, "
            f"timeout={self.timeout}s)"
        )


class BaseAPIScraper(BaseScraper):
    """
    Base class for API-based scrapers.

    Provides common functionality for scrapers that interact with REST APIs,
    such as API key management, request headers, and response handling.

    Additional Attributes:
        api_key: API key for authentication
        base_url: Base URL for API endpoints
    """

    SCRAPER_TYPE = "api"
    REQUIRES_API_KEY = True

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        """
        Initialize API-based scraper.

        Args:
            api_key: API key for authentication
            timeout: Request timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.api_key = api_key

        if self.REQUIRES_API_KEY and not self.api_key:
            self.logger.warning(
                f"{self.SCRAPER_NAME} requires an API key but none was provided. "
                f"Some operations may fail."
            )


class BaseWebScraper(BaseScraper):
    """
    Base class for web scraping-based scrapers.

    Provides common functionality for scrapers that use browser automation
    (Playwright, Selenium, etc.), such as browser lifecycle management,
    CAPTCHA detection, and rate limiting.

    Additional Attributes:
        headless: Whether to run browser in headless mode
        slow_mo: Milliseconds to slow down browser operations
    """

    SCRAPER_TYPE = "web"
    REQUIRES_API_KEY = False

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        timeout: Optional[int] = None,
    ):
        """
        Initialize web scraper.

        Args:
            headless: Run browser in headless mode
            slow_mo: Slow down browser operations by specified ms
            timeout: Request timeout in seconds
        """
        super().__init__(timeout=timeout)
        self.headless = headless
        self.slow_mo = slow_mo

    async def __aenter__(self):
        """Context manager entry - start browser."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup browser."""
        pass
