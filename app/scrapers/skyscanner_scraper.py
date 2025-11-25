"""
Skyscanner web scraper using Playwright.

This scraper extracts flight information from Skyscanner's website
using browser automation. It implements respectful scraping practices
including rate limiting, user agent rotation, and error handling.
"""

import asyncio
import logging
import random
import time
from datetime import date, datetime, time as time_type
from pathlib import Path
from typing import Dict, List, Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)
from playwright_stealth.stealth import Stealth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session_context
from app.models.airport import Airport
from app.models.flight import Flight
from app.utils.rate_limiter import (
    RedisRateLimiter,
    RateLimitExceededError,
    get_skyscanner_rate_limiter,
)
from app.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)

# Track last request time for respectful delays (separate from rate limiting)
_last_request_time: float = 0

# User agents for rotation (real browser UAs)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]


class CaptchaDetectedError(Exception):
    """Raised when CAPTCHA is detected."""

    pass


class SkyscannerScraper:
    """
    Skyscanner web scraper using Playwright for browser automation.

    Implements respectful scraping practices:
    - Random delays between requests (3-7 seconds)
    - User agent rotation
    - Rate limiting (max 10 searches per hour)
    - Error handling with screenshots
    - Cookie consent handling
    - Stealth mode to avoid bot detection
    """

    def __init__(
        self,
        headless: bool = True,
        slow_mo: int = 0,
        rate_limiter: Optional[RedisRateLimiter] = None,
    ):
        """
        Initialize Skyscanner scraper.

        Args:
            headless: Run browser in headless mode (default: True)
            slow_mo: Slow down operations by specified ms (useful for debugging)
            rate_limiter: Custom rate limiter instance (optional)
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.stealth = Stealth()  # Initialize stealth mode
        self.rate_limiter = rate_limiter or get_skyscanner_rate_limiter()

        # Create logs directory for screenshots
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)

        logger.info(
            f"SkyscannerScraper initialized with stealth mode (headless={headless}, slow_mo={slow_mo})"
        )

    async def _create_isolated_context(self):
        """
        Create an isolated browser context for a single scraping operation.

        This ensures that each scrape has its own isolated environment with:
        - Fresh cookies and session storage
        - Randomized user agent
        - Proper viewport settings
        - Stealth mode enabled

        Returns:
            Tuple of (playwright, browser, context) that should be cleaned up after use
        """
        logger.info("Creating isolated browser context...")

        # Start playwright
        playwright = await async_playwright().start()

        # Random user agent for this scrape
        user_agent = random.choice(USER_AGENTS)
        logger.debug(f"Using user agent: {user_agent[:50]}...")

        # Launch browser with anti-detection args
        browser = await playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        # Create fresh context with randomized settings
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="Europe/Vienna",
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
            },
        )

        # Apply stealth mode to the context
        await self.stealth.apply_stealth_async(context)
        logger.debug("Stealth mode applied to isolated browser context")

        logger.info("Isolated browser context created successfully")
        return playwright, browser, context

    def _check_rate_limit(self):
        """
        Check if rate limit is exceeded.

        Raises:
            RateLimitExceededError: If rate limit is exceeded
        """
        if not self.rate_limiter.is_allowed():
            status = self.rate_limiter.get_status()
            raise RateLimitExceededError(
                f"Rate limit exceeded. {status['current_count']} requests in last hour. "
                f"{status['remaining']} requests remaining."
            )

        # Record the request
        self.rate_limiter.record_request()
        status = self.rate_limiter.get_status()
        logger.debug(
            f"Rate limit check: {status['current_count']}/{status['max_requests']}"
        )

    async def _respectful_delay(self):
        """
        Add random delay between requests (3-7 seconds).

        Ensures respectful scraping by spacing out requests.
        """
        global _last_request_time

        current_time = time.time()
        time_since_last = current_time - _last_request_time

        # Minimum 3 seconds between requests
        if time_since_last < 3:
            wait_time = 3 - time_since_last
            logger.debug(f"Waiting {wait_time:.1f}s before next request...")
            await asyncio.sleep(wait_time)

        # Add random delay (3-7 seconds total)
        delay = random.uniform(3, 7)
        logger.debug(f"Respectful delay: {delay:.1f}s")
        await asyncio.sleep(delay)

        _last_request_time = time.time()

    async def _handle_cookie_consent(self, page: Page):
        """
        Handle cookie consent popup if present.

        Args:
            page: Playwright page instance
        """
        try:
            # Common Skyscanner cookie consent selectors
            consent_selectors = [
                'button[id*="accept"]',
                'button[class*="accept"]',
                'button:has-text("Accept")',
                'button:has-text("Accept all")',
                'button:has-text("I accept")',
                '#acceptCookieButton',
                '[data-testid="accept-cookies"]',
            ]

            # Try each selector with short timeout
            for selector in consent_selectors:
                try:
                    button = await page.wait_for_selector(
                        selector, timeout=2000, state="visible"
                    )
                    if button:
                        await button.click()
                        logger.info(f"Clicked cookie consent: {selector}")
                        await asyncio.sleep(1)  # Wait for popup to close
                        return
                except PlaywrightTimeoutError:
                    continue

            logger.debug("No cookie consent popup found")

        except Exception as e:
            logger.warning(f"Error handling cookie consent: {e}")

    async def _detect_captcha(self, page: Page) -> bool:
        """
        Detect if CAPTCHA is present on the page.

        Args:
            page: Playwright page instance

        Returns:
            True if CAPTCHA detected, False otherwise
        """
        try:
            # Common CAPTCHA indicators
            captcha_selectors = [
                'iframe[src*="recaptcha"]',
                'iframe[src*="captcha"]',
                '[class*="captcha"]',
                '[id*="captcha"]',
                'text="Please verify you are human"',
                'text="Security check"',
            ]

            for selector in captcha_selectors:
                element = await page.query_selector(selector)
                if element:
                    logger.warning(f"CAPTCHA detected: {selector}")
                    return True

            return False

        except Exception as e:
            logger.warning(f"Error detecting CAPTCHA: {e}")
            return False

    async def _save_screenshot(self, page: Page, prefix: str = "error"):
        """
        Save screenshot for debugging.

        Args:
            page: Playwright page instance
            prefix: Filename prefix (default: "error")
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.logs_dir / f"{prefix}_{timestamp}.png"
            await page.screenshot(path=str(filename), full_page=True)
            logger.info(f"Screenshot saved: {filename}")
        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")

    @retry_with_backoff(max_attempts=2, backoff_seconds=5)
    async def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date] = None,
    ) -> List[Dict]:
        """
        Scrape flights for a specific route using an isolated browser context.

        Each scraping operation gets its own isolated context to prevent
        cookie/session leakage between requests.

        Args:
            origin: Origin airport IATA code (e.g., "MUC")
            destination: Destination airport IATA code (e.g., "LIS")
            departure_date: Departure date
            return_date: Return date (optional, for round-trip)

        Returns:
            List of flight dictionaries with standardized format

        Raises:
            RateLimitExceededError: If rate limit is exceeded
            CaptchaDetectedError: If CAPTCHA is detected
            PlaywrightTimeoutError: If page load times out
        """
        # Check rate limit
        self._check_rate_limit()

        # Build Skyscanner URL
        url = self._build_url(origin, destination, departure_date, return_date)
        logger.info(f"Scraping route: {origin} → {destination} ({url})")

        # Create isolated browser context for this scrape
        playwright, browser, context = await self._create_isolated_context()

        try:
            # Create new page in isolated context
            page = await context.new_page()

            try:
                # Respectful delay before request
                await self._respectful_delay()

                # Navigate to URL
                logger.debug(f"Navigating to {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Handle cookie consent
                await self._handle_cookie_consent(page)

                # Check for CAPTCHA
                if await self._detect_captcha(page):
                    await self._save_screenshot(page, prefix="captcha")
                    raise CaptchaDetectedError(
                        "CAPTCHA detected. Aborting scrape. Screenshot saved."
                    )

                # Wait for results to load
                await self._wait_for_results(page)

                # Parse flight cards
                flights = await self.parse_flight_cards(page)

                logger.info(f"Successfully scraped {len(flights)} flights")
                return flights

            except PlaywrightTimeoutError as e:
                logger.error(f"Timeout loading page: {e}")
                await self._save_screenshot(page, prefix="timeout")
                raise

            except Exception as e:
                logger.error(f"Error scraping route: {e}", exc_info=True)
                await self._save_screenshot(page, prefix="error")
                raise

            finally:
                await page.close()

        finally:
            # Always cleanup browser context and playwright instance
            logger.debug("Cleaning up isolated browser context")
            try:
                await context.close()
            except Exception as e:
                logger.warning(f"Error closing context: {e}")

            try:
                await browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")

            try:
                await playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")

            logger.debug("Isolated browser context cleaned up")

    def _build_url(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date] = None,
    ) -> str:
        """
        Build Skyscanner URL for flight search.

        Args:
            origin: Origin airport IATA code
            destination: Destination airport IATA code
            departure_date: Departure date
            return_date: Return date (optional)

        Returns:
            Skyscanner search URL
        """
        # Format dates as YYMMDD (Skyscanner format)
        dep_str = departure_date.strftime("%y%m%d")
        ret_str = return_date.strftime("%y%m%d") if return_date else ""

        # Build URL
        base_url = "https://www.skyscanner.com/transport/flights"
        url = f"{base_url}/{origin}/{destination}/{dep_str}"

        if ret_str:
            url += f"/{ret_str}"

        # Add query params for family search (2 adults, 2 children)
        url += "/?adults=2&children=2&adultsv2=2&childrenv2=8|12&infants=0&cabinclass=economy&rtn=1"

        return url

    async def _wait_for_results(self, page: Page, timeout: int = 30000):
        """
        Wait for flight results to load.

        Args:
            page: Playwright page instance
            timeout: Maximum wait time in milliseconds

        Raises:
            PlaywrightTimeoutError: If results don't load in time
        """
        logger.debug("Waiting for flight results to load...")

        try:
            # Wait for loading spinner to disappear
            loading_selectors = [
                '[class*="loading"]',
                '[class*="spinner"]',
                '[data-testid="loading"]',
            ]

            for selector in loading_selectors:
                try:
                    await page.wait_for_selector(selector, state="hidden", timeout=5000)
                    logger.debug(f"Loading spinner disappeared: {selector}")
                except PlaywrightTimeoutError:
                    continue

            # Wait for flight cards to appear (multiple possible selectors)
            result_selectors = [
                '[data-testid*="flight"]',
                '[class*="FlightCard"]',
                '[class*="flight-card"]',
                '[data-test*="flight"]',
                'li[role="listitem"]',
            ]

            for selector in result_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=10000)
                    logger.debug(f"Flight results loaded: {selector}")
                    await asyncio.sleep(2)  # Extra wait for dynamic content
                    return
                except PlaywrightTimeoutError:
                    continue

            # Check for "no results" message
            no_results_text = [
                "No flights found",
                "No results",
                "Try different dates",
                "We couldn't find any flights",
            ]

            page_content = await page.content()
            for text in no_results_text:
                if text.lower() in page_content.lower():
                    logger.warning(f"No results found: '{text}' detected")
                    return

            logger.warning("Could not confirm results loaded, proceeding anyway")

        except PlaywrightTimeoutError:
            logger.warning("Timeout waiting for results, proceeding anyway")

    async def parse_flight_cards(self, page: Page) -> List[Dict]:
        """
        Extract flight data from loaded page.

        Uses multiple selector strategies with fallbacks to handle
        Skyscanner's dynamic layout.

        Args:
            page: Playwright page instance with loaded results

        Returns:
            List of flight dictionaries with standardized format
        """
        logger.debug("Parsing flight cards...")

        flights = []

        try:
            # Strategy 1: Find container elements first
            container_selectors = [
                '[data-testid*="flight"]',
                '[class*="FlightCard"]',
                '[class*="flight-card"]',
                'li[role="listitem"]',
                '[data-test*="flight"]',
            ]

            flight_elements = []
            for selector in container_selectors:
                flight_elements = await page.query_selector_all(selector)
                if flight_elements:
                    logger.debug(
                        f"Found {len(flight_elements)} flight elements: {selector}"
                    )
                    break

            if not flight_elements:
                logger.warning("No flight card elements found")
                return []

            # Parse each flight element
            for idx, element in enumerate(flight_elements[:20]):  # Limit to 20
                try:
                    flight_data = await self._parse_single_flight(element, page)
                    if flight_data:
                        flights.append(flight_data)
                        logger.debug(f"Parsed flight {idx + 1}: {flight_data['airline']}")
                except Exception as e:
                    logger.warning(f"Error parsing flight element {idx}: {e}")
                    continue

            logger.info(f"Successfully parsed {len(flights)} flights")

        except Exception as e:
            logger.error(f"Error parsing flight cards: {e}", exc_info=True)

        return flights

    async def _parse_single_flight(
        self, element, page: Page
    ) -> Optional[Dict]:
        """
        Parse a single flight card element.

        Args:
            element: Flight card element
            page: Playwright page instance

        Returns:
            Flight data dictionary or None if parsing fails
        """
        try:
            # Extract airline - multiple strategies
            airline = await self._extract_airline(element)

            # Extract price - multiple strategies
            price = await self._extract_price(element)

            # Extract times - multiple strategies
            departure_time, arrival_time = await self._extract_times(element)

            # Extract stops/direct flight
            direct_flight = await self._extract_direct_flight(element)

            # Extract booking URL
            booking_url = await self._extract_booking_url(element, page)

            # Validate required fields
            if not airline or price is None:
                logger.debug(
                    f"Skipping flight - missing required data (airline={airline}, price={price})"
                )
                return None

            # Build standardized flight data
            flight_data = {
                "airline": airline[:50],  # Truncate to model limit
                "price_per_person": price,
                "total_price": price * 4,  # Family of 4
                "departure_time": departure_time,
                "arrival_time": arrival_time,
                "direct_flight": direct_flight,
                "booking_url": booking_url,
                "booking_class": "Economy",  # Default
            }

            return flight_data

        except Exception as e:
            logger.warning(f"Error parsing single flight: {e}")
            return None

    async def _extract_airline(self, element) -> Optional[str]:
        """Extract airline name from flight element."""
        selectors = [
            '[class*="airline"]',
            '[data-testid*="airline"]',
            '[class*="carrier"]',
            "img[alt]",  # Airline logo alt text
            '[class*="operator"]',
        ]

        for selector in selectors:
            try:
                el = await element.query_selector(selector)
                if el:
                    # Try text content first
                    text = await el.text_content()
                    if text and text.strip():
                        return text.strip()

                    # Try alt attribute (for images)
                    alt = await el.get_attribute("alt")
                    if alt and alt.strip():
                        return alt.strip()
            except Exception:
                continue

        # Fallback: Look for common airline keywords
        try:
            text = await element.text_content()
            airlines = [
                "Lufthansa",
                "Ryanair",
                "Wizz Air",
                "TAP",
                "easyJet",
                "British Airways",
                "KLM",
                "Air France",
            ]
            for airline in airlines:
                if airline.lower() in text.lower():
                    return airline
        except Exception:
            pass

        return "Unknown"

    async def _extract_price(self, element) -> Optional[float]:
        """Extract price from flight element."""
        selectors = [
            '[data-testid*="price"]',
            '[class*="price"]',
            '[class*="Price"]',
            'span[aria-label*="price"]',
            '[data-test*="price"]',
        ]

        for selector in selectors:
            try:
                el = await element.query_selector(selector)
                if el:
                    text = await el.text_content()
                    if text:
                        # Extract numeric value
                        price = self._parse_price(text)
                        if price:
                            return price
            except Exception:
                continue

        # Fallback: Search all text for price pattern
        try:
            text = await element.text_content()
            price = self._parse_price(text)
            if price:
                return price
        except Exception:
            pass

        return None

    def _parse_price(self, text: str) -> Optional[float]:
        """
        Parse price from text string.

        Args:
            text: Text containing price (e.g., "€123.45", "$100")

        Returns:
            Price as float or None if not found
        """
        import re

        # Remove whitespace
        text = text.replace(" ", "").replace("\n", "")

        # Match price patterns: €123, €123.45, 123€, etc.
        patterns = [
            r"€(\d+(?:[.,]\d{2})?)",
            r"(\d+(?:[.,]\d{2})?)\s*€",
            r"\$(\d+(?:[.,]\d{2})?)",
            r"(\d+(?:[.,]\d{2})?)\s*EUR",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    price_str = match.group(1).replace(",", ".")
                    return float(price_str)
                except (ValueError, IndexError):
                    continue

        return None

    async def _extract_times(self, element) -> tuple[Optional[str], Optional[str]]:
        """Extract departure and arrival times."""
        selectors = [
            '[class*="time"]',
            '[data-testid*="time"]',
            '[class*="depart"]',
            '[class*="arrival"]',
        ]

        times = []
        for selector in selectors:
            try:
                els = await element.query_selector_all(selector)
                for el in els:
                    text = await el.text_content()
                    if text:
                        # Look for time pattern (HH:MM)
                        import re

                        match = re.search(r"(\d{1,2}:\d{2})", text)
                        if match:
                            times.append(match.group(1))
                            if len(times) >= 2:
                                break
                if len(times) >= 2:
                    break
            except Exception:
                continue

        # Return first two times found (departure, arrival)
        departure = times[0] if len(times) > 0 else None
        arrival = times[1] if len(times) > 1 else None

        return departure, arrival

    async def _extract_direct_flight(self, element) -> bool:
        """Determine if flight is direct (no stops)."""
        try:
            text = await element.text_content()
            text_lower = text.lower()

            # Check for direct flight indicators
            if "direct" in text_lower or "nonstop" in text_lower:
                return True

            # Check for stops indicators
            if "stop" in text_lower or "layover" in text_lower:
                return False

            # Default to direct if unclear
            return True

        except Exception:
            return True

    async def _extract_booking_url(self, element, page: Page) -> Optional[str]:
        """Extract booking URL from flight element."""
        try:
            # Look for link element
            link = await element.query_selector("a[href]")
            if link:
                href = await link.get_attribute("href")
                if href:
                    # Make absolute URL if relative
                    if href.startswith("/"):
                        href = f"https://www.skyscanner.com{href}"
                    return href
        except Exception:
            pass

        # Fallback: Use current page URL
        try:
            return page.url
        except Exception:
            pass

        return None

    async def scrape_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date] = None,
    ) -> List[Dict]:
        """
        Alias for scrape_route() to maintain consistent interface with other scrapers.

        Args:
            origin: Origin airport IATA code (e.g., "MUC")
            destination: Destination airport IATA code (e.g., "LIS")
            departure_date: Departure date
            return_date: Return date (optional, for round-trip)

        Returns:
            List of flight dictionaries with standardized format
        """
        return await self.scrape_route(origin, destination, departure_date, return_date)

    async def save_to_database(
        self,
        flights: List[Dict],
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date] = None,
    ):
        """
        Save scraped flights to database.

        Args:
            flights: List of flight dictionaries
            origin: Origin airport IATA code
            destination: Destination airport IATA code
            departure_date: Departure date
            return_date: Return date (optional)
        """
        if not flights:
            logger.info("No flights to save")
            return

        logger.info(f"Saving {len(flights)} flights to database...")

        async with get_async_session_context() as session:
            try:
                # Get airport IDs
                origin_airport = await self._get_airport_by_iata(session, origin)
                dest_airport = await self._get_airport_by_iata(session, destination)

                if not origin_airport or not dest_airport:
                    logger.error(
                        f"Airport not found: origin={origin}, destination={destination}"
                    )
                    return

                # Create Flight objects
                saved_count = 0
                for flight_data in flights:
                    try:
                        # Parse times
                        departure_time = self._parse_time(
                            flight_data.get("departure_time")
                        )
                        arrival_time = self._parse_time(flight_data.get("arrival_time"))

                        # Create Flight instance
                        flight = Flight(
                            origin_airport_id=origin_airport.id,
                            destination_airport_id=dest_airport.id,
                            airline=flight_data["airline"],
                            departure_date=departure_date,
                            departure_time=departure_time,
                            return_date=return_date,
                            return_time=None,  # Not available from scraping
                            price_per_person=flight_data["price_per_person"],
                            total_price=flight_data["total_price"],
                            booking_class=flight_data.get("booking_class", "Economy"),
                            direct_flight=flight_data.get("direct_flight", True),
                            source="skyscanner",
                            booking_url=flight_data.get("booking_url"),
                        )

                        session.add(flight)
                        saved_count += 1

                    except Exception as e:
                        logger.warning(f"Error creating flight object: {e}")
                        continue

                # Commit all flights
                await session.commit()
                logger.info(f"Successfully saved {saved_count} flights to database")

            except Exception as e:
                await session.rollback()
                logger.error(f"Error saving flights to database: {e}", exc_info=True)
                raise

    async def _get_airport_by_iata(
        self, session: AsyncSession, iata_code: str
    ) -> Optional[Airport]:
        """
        Get airport by IATA code.

        Args:
            session: Database session
            iata_code: IATA airport code (e.g., "MUC")

        Returns:
            Airport model or None if not found
        """
        stmt = select(Airport).where(Airport.iata_code == iata_code.upper())
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    def _parse_time(self, time_str: Optional[str]) -> Optional[time_type]:
        """
        Parse time string to time object.

        Args:
            time_str: Time string (e.g., "14:30")

        Returns:
            time object or None
        """
        if not time_str:
            return None

        try:
            # Parse HH:MM format
            parts = time_str.split(":")
            if len(parts) == 2:
                hour = int(parts[0])
                minute = int(parts[1])
                return time_type(hour=hour, minute=minute)
        except (ValueError, IndexError):
            pass

        return None
