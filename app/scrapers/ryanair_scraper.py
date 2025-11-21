"""
Ryanair flight scraper using Playwright with maximum stealth.

This scraper implements very conservative scraping practices to avoid detection:
- Realistic user behavior simulation
- Conservative delays (5-10 seconds between actions)
- Rate limiting (max 5 searches per day)
- Error handling and screenshot logging
- CAPTCHA detection and graceful abort

Target: https://www.ryanair.com/
"""

import asyncio
import json
import random
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

from app.utils.logging_config import get_logger
from app.scrapers.base import BaseWebScraper
from app.scrapers.exceptions import (
    RateLimitError,
    CaptchaError,
    TimeoutError as ScraperTimeoutError,
    ParsingError,
)

logger = get_logger(__name__)


class RyanairScraper(BaseWebScraper):
    """
    Scraper for Ryanair flights with anti-detection measures.

    Features:
    - Stealth mode to avoid detection
    - Realistic human-like behavior
    - Conservative rate limiting (5 searches/day)
    - Popup handling (cookies, chat, ads)
    - Fare calendar parsing for price discovery
    - Error screenshots and logging
    """

    SCRAPER_NAME = "ryanair"
    SCRAPER_TYPE = "web"
    REQUIRES_API_KEY = False
    DEFAULT_TIMEOUT = 60

    BASE_URL = "https://www.ryanair.com"
    MAX_DAILY_SEARCHES = 5
    RATE_LIMIT_FILE = "/tmp/ryanair_rate_limit.json"

    # User agents that look residential/real
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    ]

    def __init__(
        self,
        log_dir: str = "/home/user/smartfamilytravelscout/logs/ryanair",
        headless: bool = True,
        timeout: Optional[int] = None,
    ):
        """
        Initialize Ryanair scraper with stealth configuration.

        Args:
            log_dir: Directory to save error screenshots
            headless: Run browser in headless mode
            timeout: Request timeout in seconds
        """
        super().__init__(headless=headless, slow_mo=0, timeout=timeout)

        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        """Context manager entry."""
        await self._init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

    async def _init_browser(self) -> None:
        """Initialize Playwright browser with stealth configuration."""
        logger.info("Initializing browser with stealth mode...")

        playwright = await async_playwright().start()

        # Launch browser with stealth args
        self.browser = await playwright.chromium.launch(
            headless=True,  # Set to False for debugging
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certificate-errors",
                "--ignore-certificate-errors-spki-list",
                "--disable-gpu",
            ],
        )

        # Create context with realistic settings
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=random.choice(self.USER_AGENTS),
            locale="en-GB",
            timezone_id="Europe/London",
            permissions=["geolocation"],
            geolocation={"latitude": 48.1351, "longitude": 11.5820},  # Munich coordinates
            color_scheme="light",
            device_scale_factor=1,
            has_touch=False,
            is_mobile=False,
            java_script_enabled=True,
        )

        # Create page
        self.page = await self.context.new_page()

        # Apply stealth mode
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(self.page)

        # Additional stealth: override navigator.webdriver
        await self.page.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Mock Chrome runtime
            window.chrome = {
                runtime: {}
            };

            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-GB', 'en', 'en-US']
            });
        """
        )

        logger.info("Browser initialized with stealth mode")

    async def close(self) -> None:
        """Close browser and cleanup."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Browser closed")

    async def _check_rate_limit(self) -> None:
        """
        Check if rate limit has been exceeded.

        Raises:
            RateLimitExceeded: If daily limit is exceeded
        """
        rate_file = Path(self.RATE_LIMIT_FILE)

        # Load existing rate limit data
        if rate_file.exists():
            with open(rate_file, "r") as f:
                data = json.load(f)
        else:
            data = {"date": None, "count": 0}

        today = str(date.today())

        # Reset counter if it's a new day
        if data["date"] != today:
            data = {"date": today, "count": 0}

        # Check limit
        if data["count"] >= self.MAX_DAILY_SEARCHES:
            logger.warning(f"Rate limit exceeded: {data['count']}/{self.MAX_DAILY_SEARCHES}")
            raise RateLimitError(
                f"Daily rate limit exceeded ({self.MAX_DAILY_SEARCHES} searches/day).",
                scraper_name=self.SCRAPER_NAME,
                retry_after=86400,  # 24 hours
                limit_type="daily",
                current_count=data["count"],
                max_count=self.MAX_DAILY_SEARCHES,
            )

        # Increment counter
        data["count"] += 1

        # Save
        with open(rate_file, "w") as f:
            json.dump(data, f)

        logger.info(f"Rate limit check: {data['count']}/{self.MAX_DAILY_SEARCHES} searches today")

    async def _save_screenshot(self, name: str) -> str:
        """
        Save screenshot for debugging.

        Args:
            name: Screenshot name/identifier

        Returns:
            Path to saved screenshot
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{name}.png"
        filepath = self.log_dir / filename

        if self.page:
            await self.page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"Screenshot saved: {filepath}")

        return str(filepath)

    async def _detect_captcha(self) -> bool:
        """
        Detect if CAPTCHA is present on the page.

        Returns:
            True if CAPTCHA detected, False otherwise
        """
        if not self.page:
            return False

        # Check for common CAPTCHA indicators
        captcha_selectors = [
            'iframe[src*="captcha"]',
            'iframe[src*="recaptcha"]',
            '[class*="captcha"]',
            '[id*="captcha"]',
            ".g-recaptcha",
            "#px-captcha",
        ]

        for selector in captcha_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    logger.warning(f"CAPTCHA detected: {selector}")
                    return True
            except Exception:
                pass

        # Check page content for CAPTCHA text
        try:
            content = await self.page.content()
            if any(
                keyword in content.lower()
                for keyword in ["captcha", "verify you are human", "security check"]
            ):
                logger.warning("CAPTCHA detected in page content")
                return True
        except Exception:
            pass

        return False

    async def _human_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """
        Add realistic human-like delay.

        Args:
            min_seconds: Minimum delay in seconds
            max_seconds: Maximum delay in seconds
        """
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def _type_like_human(self, selector: str, text: str) -> None:
        """
        Type text with human-like delays.

        Args:
            selector: Element selector
            text: Text to type
        """
        if not self.page:
            return

        element = await self.page.wait_for_selector(selector, timeout=10000)
        if element:
            # Click to focus
            await element.click()
            await self._human_delay(0.2, 0.5)

            # Type with random delays
            for char in text:
                await element.type(char, delay=random.uniform(50, 150))

            await self._human_delay(0.3, 0.7)

    async def _scroll_randomly(self) -> None:
        """Scroll page randomly to simulate human behavior."""
        if not self.page:
            return

        # Random scroll down
        scroll_amount = random.randint(100, 500)
        await self.page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await self._human_delay(0.5, 1.5)

        # Sometimes scroll back up
        if random.random() > 0.5:
            await self.page.evaluate(f"window.scrollBy(0, -{scroll_amount // 2})")
            await self._human_delay(0.3, 0.8)

    async def handle_popups(self, page: Page) -> None:
        """
        Handle cookie consent, chat widgets, and marketing popups.

        Args:
            page: Playwright page instance
        """
        logger.info("Handling popups...")

        # Wait a bit for popups to appear
        await self._human_delay(2, 3)

        # Cookie consent - multiple possible selectors
        cookie_selectors = [
            'button:has-text("Accept all")',
            'button:has-text("Accept All")',
            'button:has-text("Yes, I agree")',
            'button[data-ref="cookie.accept-all"]',
            '.cookie-popup-with-overlay__button',
            '#truste-consent-button',
            'button.cookie-consent-accept',
        ]

        for selector in cookie_selectors:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    logger.info(f"Accepting cookies: {selector}")
                    await button.click()
                    await self._human_delay(1, 2)
                    break
            except Exception as e:
                logger.debug(f"Cookie selector {selector} not found: {e}")

        # Close chat widget if present
        chat_selectors = [
            'button[aria-label="Close chat"]',
            '.chat-close-button',
            '#chat-widget-close',
        ]

        for selector in chat_selectors:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    logger.info(f"Closing chat: {selector}")
                    await button.click()
                    await self._human_delay(0.5, 1)
                    break
            except Exception:
                pass

        # Close marketing popups
        popup_selectors = [
            'button[aria-label="Close"]',
            '.popup-close',
            '.modal-close',
            'button.close',
        ]

        for selector in popup_selectors:
            try:
                buttons = await page.query_selector_all(selector)
                for button in buttons:
                    if await button.is_visible():
                        logger.info(f"Closing popup: {selector}")
                        await button.click()
                        await self._human_delay(0.5, 1)
            except Exception:
                pass

        logger.info("Popup handling completed")

    async def navigate_search(
        self,
        page: Page,
        origin: str,
        destination: str,
        outbound_date: date,
        return_date: date,
    ) -> None:
        """
        Fill search form and submit with realistic human behavior.

        Args:
            page: Playwright page instance
            origin: Origin airport code (e.g., 'FMM')
            destination: Destination airport code (e.g., 'BCN')
            outbound_date: Departure date
            return_date: Return date
        """
        logger.info(
            f"Navigating search: {origin} → {destination}, "
            f"{outbound_date} to {return_date}"
        )

        # Wait for search form to be visible
        await page.wait_for_load_state("networkidle")
        await self._human_delay(2, 4)

        # Origin airport
        try:
            logger.info("Selecting origin airport...")

            # Click origin input
            origin_input = await page.wait_for_selector(
                'input[placeholder*="Departure"],'
                'input[data-ref="input-button__input"],'
                'input#input-button__departure',
                timeout=10000,
            )
            await origin_input.click()
            await self._human_delay(1, 2)

            # Type origin code
            await origin_input.fill("")  # Clear first
            await self._type_like_human(
                'input[placeholder*="Departure"],'
                'input[data-ref="input-button__input"],'
                'input#input-button__departure',
                origin,
            )
            await self._human_delay(1, 2)

            # Wait for dropdown and select first option
            dropdown_option = await page.wait_for_selector(
                f'span[data-ref="airport-item__name"]:has-text("{origin}"),'
                f'div.airport-item:has-text("{origin}")',
                timeout=5000,
            )
            await dropdown_option.click()
            await self._human_delay(1, 2)

            logger.info(f"Origin selected: {origin}")

        except Exception as e:
            logger.error(f"Error selecting origin: {e}")
            await self._save_screenshot("error_origin_selection")
            raise

        # Destination airport
        try:
            logger.info("Selecting destination airport...")

            # Click destination input
            dest_input = await page.wait_for_selector(
                'input[placeholder*="Destination"],'
                'input#input-button__destination',
                timeout=10000,
            )
            await dest_input.click()
            await self._human_delay(1, 2)

            # Type destination code
            await dest_input.fill("")  # Clear first
            await self._type_like_human(
                'input[placeholder*="Destination"],' 'input#input-button__destination',
                destination,
            )
            await self._human_delay(1, 2)

            # Wait for dropdown and select first option
            dropdown_option = await page.wait_for_selector(
                f'span[data-ref="airport-item__name"]:has-text("{destination}"),'
                f'div.airport-item:has-text("{destination}")',
                timeout=5000,
            )
            await dropdown_option.click()
            await self._human_delay(1, 2)

            logger.info(f"Destination selected: {destination}")

        except Exception as e:
            logger.error(f"Error selecting destination: {e}")
            await self._save_screenshot("error_destination_selection")
            raise

        # Dates
        try:
            logger.info("Selecting dates...")

            # Click date picker
            date_input = await page.wait_for_selector(
                'div[data-ref="input-button__dates"],' 'button[aria-label*="travel dates"]',
                timeout=10000,
            )
            await date_input.click()
            await self._human_delay(1, 2)

            # Select outbound date
            outbound_selector = (
                f'div[data-id="{outbound_date.strftime("%Y-%m-%d")}"],'
                f'button[data-id="{outbound_date.strftime("%Y-%m-%d")}"]'
            )
            outbound_day = await page.wait_for_selector(outbound_selector, timeout=10000)
            await outbound_day.click()
            await self._human_delay(1, 2)

            # Select return date
            return_selector = (
                f'div[data-id="{return_date.strftime("%Y-%m-%d")}"],'
                f'button[data-id="{return_date.strftime("%Y-%m-%d")}"]'
            )
            return_day = await page.wait_for_selector(return_selector, timeout=10000)
            await return_day.click()
            await self._human_delay(1, 2)

            logger.info(f"Dates selected: {outbound_date} to {return_date}")

        except Exception as e:
            logger.error(f"Error selecting dates: {e}")
            await self._save_screenshot("error_date_selection")
            raise

        # Passengers (2 adults, 2 children)
        try:
            logger.info("Selecting passengers...")

            # Click passengers dropdown
            passengers_button = await page.wait_for_selector(
                'div[data-ref="input-button__passengers"],'
                'button[aria-label*="Passengers"]',
                timeout=10000,
            )
            await passengers_button.click()
            await self._human_delay(1, 2)

            # Add one more adult (default is 1)
            adult_plus = await page.query_selector(
                'ry-counter[data-ref="passengers-picker__adults"] button[aria-label*="Add"]'
            )
            if adult_plus:
                await adult_plus.click()
                await self._human_delay(0.5, 1)

            # Add 2 children
            child_plus = await page.query_selector(
                'ry-counter[data-ref="passengers-picker__children"] button[aria-label*="Add"]'
            )
            if child_plus:
                await child_plus.click()
                await self._human_delay(0.5, 1)
                await child_plus.click()
                await self._human_delay(0.5, 1)

            # Close passengers dropdown
            done_button = await page.query_selector('button:has-text("Done")')
            if done_button:
                await done_button.click()
                await self._human_delay(1, 2)

            logger.info("Passengers selected: 2 adults, 2 children")

        except Exception as e:
            logger.warning(f"Error selecting passengers (continuing anyway): {e}")
            await self._save_screenshot("warning_passenger_selection")

        # Submit search
        try:
            logger.info("Submitting search...")

            # Scroll to search button
            await self._scroll_randomly()

            # Click search button
            search_button = await page.wait_for_selector(
                'button[data-ref="flight-search-widget__cta"],'
                'button:has-text("Search"),'
                'button.flight-search-widget__start-search',
                timeout=10000,
            )
            await search_button.click()

            logger.info("Search submitted, waiting for results...")

            # Wait for results page to load
            await page.wait_for_load_state("networkidle", timeout=60000)
            await self._human_delay(5, 8)  # Conservative delay

        except Exception as e:
            logger.error(f"Error submitting search: {e}")
            await self._save_screenshot("error_search_submit")
            raise

    async def parse_fare_calendar(self, page: Page) -> List[Dict]:
        """
        Extract prices from fare calendar (month view).

        The fare calendar shows the cheapest prices across different dates,
        which is better for price discovery than direct date search.

        Args:
            page: Playwright page instance

        Returns:
            List of flight dictionaries with prices, dates, and details
        """
        logger.info("Parsing fare calendar...")

        flights = []

        try:
            # Check if we're on the results page
            await page.wait_for_load_state("networkidle")

            # Look for fare cards or flight options
            flight_cards_selectors = [
                'flight-card',
                '[data-ref="flight-card"]',
                '.flight-card',
                'ry-price-breakdown',
            ]

            flight_elements = None
            for selector in flight_cards_selectors:
                flight_elements = await page.query_selector_all(selector)
                if flight_elements:
                    logger.info(f"Found {len(flight_elements)} flights using selector: {selector}")
                    break

            if not flight_elements:
                logger.warning("No flight cards found, trying alternative parsing...")
                await self._save_screenshot("no_flights_found")

                # Try to parse from page content
                content = await page.content()

                # Extract any price patterns (e.g., €49.99, 49.99)
                price_pattern = r'€?\s*(\d+[.,]\d{2})'
                prices = re.findall(price_pattern, content)

                if prices:
                    logger.info(f"Found {len(prices)} prices in page content")
                    # Return basic price information
                    return [
                        {
                            "price": float(price.replace(",", ".")),
                            "currency": "EUR",
                            "departure_date": None,
                            "departure_time": None,
                            "return_date": None,
                            "return_time": None,
                            "flight_number": None,
                            "direct": True,
                            "booking_class": "Regular",
                        }
                        for price in prices[:5]  # Limit to first 5
                    ]

                return []

            # Parse each flight card
            for idx, card in enumerate(flight_elements[:10]):  # Limit to first 10
                try:
                    flight_data = {}

                    # Extract price
                    price_element = await card.query_selector(
                        '.price-display__price,'
                        '[data-ref="price"],'
                        'span.price,'
                        'ry-price-breakdown'
                    )

                    if price_element:
                        price_text = await price_element.inner_text()
                        # Extract numeric price
                        price_match = re.search(r'(\d+[.,]\d{2})', price_text)
                        if price_match:
                            flight_data["price"] = float(price_match.group(1).replace(",", "."))
                            flight_data["currency"] = "EUR"

                    # Extract times
                    time_elements = await card.query_selector_all(
                        '.time,' '[data-ref="time"],' 'span[class*="time"]'
                    )

                    if len(time_elements) >= 2:
                        dep_time = await time_elements[0].inner_text()
                        arr_time = await time_elements[1].inner_text()

                        flight_data["departure_time"] = self._parse_time(dep_time)
                        flight_data["arrival_time"] = self._parse_time(arr_time)

                    # Extract flight number
                    flight_num_element = await card.query_selector(
                        '[data-ref="flight-number"],' 'span[class*="flight-number"]'
                    )
                    if flight_num_element:
                        flight_data["flight_number"] = await flight_num_element.inner_text()

                    # Direct flight indicator
                    direct_element = await card.query_selector(':has-text("Direct")')
                    flight_data["direct"] = direct_element is not None

                    # Booking class
                    class_element = await card.query_selector(
                        '[data-ref="fare-class"],' 'span[class*="fare"]'
                    )
                    if class_element:
                        flight_data["booking_class"] = await class_element.inner_text()
                    else:
                        flight_data["booking_class"] = "Regular"

                    # Only add if we got a price
                    if "price" in flight_data:
                        flights.append(flight_data)
                        logger.info(f"Parsed flight {idx + 1}: €{flight_data.get('price')}")

                except Exception as e:
                    logger.warning(f"Error parsing flight card {idx}: {e}")
                    continue

            logger.info(f"Successfully parsed {len(flights)} flights")

        except Exception as e:
            logger.error(f"Error parsing fare calendar: {e}")
            await self._save_screenshot("error_fare_parsing")
            raise

        return flights

    def _parse_time(self, time_str: str) -> Optional[str]:
        """
        Parse time string to time object.

        Args:
            time_str: Time string (e.g., '08:30', '8:30 AM')

        Returns:
            Time string in HH:MM format or None
        """
        try:
            # Remove whitespace and convert to uppercase
            time_str = time_str.strip().upper()

            # Match HH:MM format
            match = re.match(r'(\d{1,2}):(\d{2})', time_str)
            if match:
                hours = int(match.group(1))
                minutes = int(match.group(2))

                # Handle AM/PM if present
                if 'PM' in time_str and hours != 12:
                    hours += 12
                elif 'AM' in time_str and hours == 12:
                    hours = 0

                # Validate time ranges
                if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                    return None

                return f"{hours:02d}:{minutes:02d}"

        except Exception:
            pass

        return None

    async def scrape_route(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date,
    ) -> List[Dict]:
        """
        Scrape Ryanair flights for a specific route.

        This is the main entry point for scraping. It handles:
        - Rate limiting
        - Browser initialization
        - Navigation and form filling
        - Popup handling
        - Result parsing
        - Error handling and screenshots
        - CAPTCHA detection

        Args:
            origin: Origin airport code (e.g., 'FMM', 'MUC')
            destination: Destination airport code (e.g., 'BCN', 'PMI')
            departure_date: Outbound flight date
            return_date: Return flight date

        Returns:
            List of flight dictionaries containing prices, times, and details

        Raises:
            RateLimitExceeded: If daily rate limit is exceeded
            CaptchaDetected: If CAPTCHA is encountered
            Exception: For other scraping errors
        """
        logger.info(
            f"Starting scrape: {origin} → {destination}, "
            f"{departure_date} to {return_date}"
        )

        # Check rate limit
        await self._check_rate_limit()

        try:
            # Initialize browser if not already done
            if not self.browser:
                await self._init_browser()

            if not self.page:
                raise Exception("Page not initialized")

            # Navigate to homepage
            logger.info(f"Navigating to {self.BASE_URL}...")
            await self.page.goto(self.BASE_URL, wait_until="networkidle", timeout=60000)
            await self._human_delay(3, 5)

            # Save initial screenshot
            await self._save_screenshot("initial_page")

            # Check for CAPTCHA
            if await self._detect_captcha():
                screenshot_path = await self._save_screenshot("captcha_detected")
                raise CaptchaError(
                    "CAPTCHA detected, aborting to avoid detection",
                    scraper_name=self.SCRAPER_NAME,
                    captcha_type="unknown",
                    page_url=self.BASE_URL,
                    screenshot_path=screenshot_path,
                )

            # Handle popups
            await self.handle_popups(self.page)

            # Navigate search form
            await self.navigate_search(self.page, origin, destination, departure_date, return_date)

            # Check for CAPTCHA after submission
            if await self._detect_captcha():
                screenshot_path = await self._save_screenshot("captcha_detected_after_search")
                raise CaptchaError(
                    "CAPTCHA detected after search, aborting",
                    scraper_name=self.SCRAPER_NAME,
                    captcha_type="unknown",
                    page_url=self.page.url if self.page else None,
                    screenshot_path=screenshot_path,
                )

            # Parse results
            flights = await self.parse_fare_calendar(self.page)

            # Add metadata
            for flight in flights:
                flight["origin"] = origin
                flight["destination"] = destination
                flight["departure_date"] = departure_date
                flight["return_date"] = return_date
                flight["source"] = "ryanair"
                flight["scraped_at"] = datetime.utcnow()

                # Construct booking URL
                flight["booking_url"] = self._construct_booking_url(
                    origin, destination, departure_date, return_date
                )

            # Save success screenshot
            await self._save_screenshot("success_results")

            logger.info(f"Scraping completed successfully: {len(flights)} flights found")

            return flights

        except (RateLimitError, CaptchaError):
            # Re-raise expected scraper errors
            raise

        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            await self._save_screenshot("error_general")
            # Wrap as ParsingError if it looks like a parsing issue
            if "parse" in str(e).lower() or "selector" in str(e).lower():
                raise ParsingError(
                    f"Failed to parse Ryanair page: {str(e)}",
                    scraper_name=self.SCRAPER_NAME,
                    original_error=e,
                )
            raise

        finally:
            # Add conservative delay before closing
            await self._human_delay(5, 10)

    async def scrape_flights(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date] = None,
        **kwargs,
    ) -> List[Dict]:
        """
        Scrape flights for the given route and dates (base class interface).

        This method implements the BaseScraper interface and delegates to scrape_route.

        Args:
            origin: Origin airport IATA code (e.g., 'FMM')
            destination: Destination airport IATA code (e.g., 'BCN')
            departure_date: Departure date
            return_date: Return date
            **kwargs: Additional parameters (ignored)

        Returns:
            List of standardized flight dictionaries

        Raises:
            RateLimitError: When daily rate limit is exceeded
            CaptchaError: When CAPTCHA is detected
            ParsingError: When page parsing fails
        """
        # Validate inputs
        origin = self._validate_airport_code(origin, "origin")
        destination = self._validate_airport_code(destination, "destination")

        # Default return date to 7 days after departure if not provided
        if return_date is None:
            return_date = departure_date + timedelta(days=7)

        self._validate_dates(departure_date, return_date)

        return await self.scrape_route(origin, destination, departure_date, return_date)

    def _construct_booking_url(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: date,
    ) -> str:
        """
        Construct Ryanair booking URL.

        Args:
            origin: Origin airport code
            destination: Destination airport code
            departure_date: Departure date
            return_date: Return date

        Returns:
            Booking URL
        """
        # Format dates as YYYY-MM-DD
        dep_str = departure_date.strftime("%Y-%m-%d")
        ret_str = return_date.strftime("%Y-%m-%d")

        # Construct URL (Ryanair format)
        url = (
            f"{self.BASE_URL}/gb/en/trip/flights/select?"
            f"adults=2&teens=0&children=2&infants=0"
            f"&dateOut={dep_str}&dateIn={ret_str}"
            f"&originIata={origin}&destinationIata={destination}"
            f"&isConnectedFlight=false&isReturn=true"
            f"&discount=0&promoCode="
        )

        return url


# Convenience function for quick testing
async def quick_test():
    """Quick test function for development."""
    scraper = RyanairScraper()

    try:
        flights = await scraper.scrape_route(
            origin="FMM",
            destination="BCN",
            departure_date=date(2025, 12, 20),
            return_date=date(2025, 12, 27),
        )

        print(f"\nFound {len(flights)} flights:")
        for flight in flights:
            print(f"  - €{flight.get('price')} - {flight.get('departure_time', 'N/A')}")

    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(quick_test())
