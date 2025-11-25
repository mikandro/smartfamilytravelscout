"""
Tourism board web scrapers for finding local events not on EventBrite.

This module provides base classes and utilities for scraping official tourism
websites to find family-friendly events, festivals, and cultural happenings.
"""

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser
from playwright.async_api import async_playwright, Browser, Page

from app.models.event import Event
from app.utils.date_utils import parse_date
from app.utils.retry import api_retry

logger = logging.getLogger(__name__)


class TourismDateParser:
    """Enhanced date parser for tourism websites with multiple format support."""

    # Common month names in different languages
    MONTH_NAMES = {
        # English
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,

        # Portuguese
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
        'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
        'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12,

        # Spanish
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,

        # Czech
        'ledna': 1, 'února': 2, 'března': 3, 'dubna': 4,
        'května': 5, 'června': 6, 'července': 7, 'srpna': 8,
        'září': 9, 'října': 10, 'listopadu': 11, 'prosince': 12,

        # German
        'januar': 1, 'februar': 2, 'märz': 3, 'april': 4,
        'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
        'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12,
    }

    @classmethod
    def parse_tourism_date(cls, date_str: str, reference_year: Optional[int] = None) -> Optional[date]:
        """
        Parse date strings from tourism websites in various formats.

        Supported formats:
        - Dec 20, 2025
        - 20 December 2025
        - 20.12.2025
        - 20/12/2025
        - 2025-12-20
        - 20 Dec
        - December 20

        Args:
            date_str: Date string to parse
            reference_year: Year to use if not specified in date string (defaults to current year)

        Returns:
            Parsed date object or None if parsing fails
        """
        if not date_str or not isinstance(date_str, str):
            return None

        date_str = date_str.strip()

        if reference_year is None:
            reference_year = datetime.now().year

        # Try basic parsing first (handles YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY)
        basic_date = parse_date(date_str)
        if basic_date:
            return basic_date

        # Try dateutil parser (very flexible)
        try:
            parsed = dateutil_parser.parse(date_str, fuzzy=True, default=datetime(reference_year, 1, 1))
            return parsed.date()
        except (ValueError, TypeError):
            pass

        # Try custom parsing with month names
        try:
            # Handle "20 December 2025" or "December 20, 2025"
            date_str_lower = date_str.lower()

            # Extract year if present
            year_match = re.search(r'\b(20\d{2})\b', date_str)
            year = int(year_match.group(1)) if year_match else reference_year

            # Extract day
            day_match = re.search(r'\b(\d{1,2})\b', date_str)
            if not day_match:
                return None
            day = int(day_match.group(1))

            # Extract month
            month = None
            for month_name, month_num in cls.MONTH_NAMES.items():
                if month_name in date_str_lower:
                    month = month_num
                    break

            if month and 1 <= day <= 31:
                return date(year, month, day)

        except (ValueError, AttributeError):
            pass

        logger.warning(f"Failed to parse date string: {date_str}")
        return None

    @classmethod
    def parse_date_range(cls, date_range_str: str) -> tuple[Optional[date], Optional[date]]:
        """
        Parse date range strings like "Dec 20-25, 2025" or "20-25 December 2025".

        Args:
            date_range_str: Date range string to parse

        Returns:
            Tuple of (start_date, end_date) or (None, None) if parsing fails
        """
        if not date_range_str:
            return None, None

        # Try to split on common separators
        separators = [' - ', ' – ', ' to ', ' до ', ' a ']
        for sep in separators:
            if sep in date_range_str.lower():
                parts = date_range_str.split(sep, 1)
                if len(parts) == 2:
                    start = cls.parse_tourism_date(parts[0].strip())
                    end = cls.parse_tourism_date(parts[1].strip())
                    return start, end

        # Try to parse as single date
        single_date = cls.parse_tourism_date(date_range_str)
        if single_date:
            return single_date, single_date

        return None, None


class BaseTourismScraper(ABC):
    """Base class for tourism board event scrapers."""

    BASE_URL: str = ""
    CITY_NAME: str = ""
    SOURCE_NAME: str = ""

    # Rate limiting
    REQUEST_DELAY = 1.0  # seconds between requests
    MAX_RETRIES = 3
    TIMEOUT = 30

    # Family-friendly event keywords
    FAMILY_KEYWORDS = [
        'family', 'children', 'kids', 'child', 'families',
        'família', 'criança', 'niños', 'familia',
        'děti', 'rodina', 'kinder', 'familie'
    ]

    # Event categorization keywords
    CATEGORY_KEYWORDS = {
        'family': ['family', 'children', 'kids', 'child', 'playground', 'fun'],
        'cultural': ['museum', 'art', 'exhibition', 'gallery', 'culture', 'história'],
        'outdoor': ['park', 'garden', 'outdoor', 'nature', 'hiking', 'beach'],
        'festival': ['festival', 'celebration', 'carnival', 'festa', 'feier'],
        'food': ['food', 'gastronomy', 'cuisine', 'restaurant', 'comida'],
        'music': ['music', 'concert', 'symphony', 'orchestra', 'jazz', 'rock'],
        'sports': ['sport', 'game', 'match', 'competition', 'race'],
    }

    def __init__(self):
        """Initialize the scraper."""
        self.date_parser = TourismDateParser()
        self._session: Optional[httpx.AsyncClient] = None
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _get_http_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session."""
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                timeout=self.TIMEOUT,
                follow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
        return self._session

    async def _get_playwright_browser(self) -> Browser:
        """Get or create Playwright browser for JavaScript-heavy sites."""
        if self._browser is None:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        return self._browser

    async def close(self):
        """Close connections and cleanup resources."""
        if self._session:
            await self._session.aclose()
            self._session = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    @api_retry(max_attempts=3, min_wait_seconds=2, max_wait_seconds=10)
    async def fetch_html(self, url: str, use_playwright: bool = False) -> Optional[str]:
        """
        Fetch HTML content from URL with automatic retry logic.

        Args:
            url: URL to fetch
            use_playwright: If True, use Playwright for JavaScript rendering

        Returns:
            HTML content or None if fetch fails

        Raises:
            Exception: If all retry attempts fail
        """
        try:
            if use_playwright:
                browser = await self._get_playwright_browser()
                page = await browser.new_page()
                try:
                    await page.goto(url, wait_until='networkidle', timeout=self.TIMEOUT * 1000)
                    html = await page.content()
                    return html
                finally:
                    await page.close()
            else:
                session = await self._get_http_session()
                response = await session.get(url)
                response.raise_for_status()
                return response.text

        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def make_absolute_url(self, url: str) -> str:
        """Convert relative URL to absolute URL."""
        if not url:
            return ""
        return urljoin(self.BASE_URL, url)

    def categorize_event(self, title: str, description: str = "") -> str:
        """
        Categorize event based on title and description.

        Args:
            title: Event title
            description: Event description

        Returns:
            Category name (e.g., 'family', 'cultural', 'outdoor')
        """
        text = f"{title} {description}".lower()

        # Check for family-friendly first
        if any(keyword in text for keyword in self.FAMILY_KEYWORDS):
            return 'family'

        # Check other categories
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return category

        return 'cultural'  # Default category

    def extract_price_range(self, text: str) -> str:
        """
        Extract price range from text.

        Args:
            text: Text containing price information

        Returns:
            Price range string (e.g., 'free', '<€20', '€20-50')
        """
        text_lower = text.lower()

        # Check for free
        free_keywords = [
            'free', 'grátis', 'gratuito', 'gratuita', 'entrada gratuita',
            'zdarma', 'kostenlos', 'libre', 'lliure'
        ]
        if any(word in text_lower for word in free_keywords):
            return 'free'

        # Try to extract price numbers
        price_pattern = r'[€$£]\s*(\d+(?:\.\d{2})?)'
        prices = re.findall(price_pattern, text)

        if prices:
            prices_float = [float(p) for p in prices]
            max_price = max(prices_float)

            if max_price < 20:
                return '<€20'
            elif max_price < 50:
                return '€20-50'
            else:
                return '€50+'

        return 'varies'

    @abstractmethod
    async def scrape_events(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        Scrape events from tourism website.

        Args:
            start_date: Start date for event search
            end_date: End date for event search

        Returns:
            List of event dictionaries with standardized fields
        """
        raise NotImplementedError

    def create_event_dict(
        self,
        title: str,
        event_date: date,
        url: str,
        description: str = "",
        end_date: Optional[date] = None,
        price_range: str = "varies",
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create standardized event dictionary.

        Args:
            title: Event title
            event_date: Event start date
            url: Event URL
            description: Event description
            end_date: Event end date (for multi-day events)
            price_range: Price range string
            category: Event category (auto-detected if not provided)

        Returns:
            Standardized event dictionary
        """
        if category is None:
            category = self.categorize_event(title, description)

        return {
            'destination_city': self.CITY_NAME,
            'title': title.strip(),
            'event_date': event_date,
            'end_date': end_date,
            'category': category,
            'description': description.strip() if description else None,
            'price_range': price_range,
            'source': self.SOURCE_NAME,
            'url': self.make_absolute_url(url),
        }
