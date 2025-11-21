"""
Booking.com scraper for family-friendly accommodations.

This module provides a BookingClient class that uses Playwright to scrape
accommodation listings from Booking.com, specifically targeting family-friendly
properties with 2+ bedrooms, kitchens, and good ratings.
"""

import asyncio
import logging
import random
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout, async_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.accommodation import Accommodation

logger = logging.getLogger(__name__)

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]


class BookingClient:
    """
    Booking.com scraper for family-friendly accommodations.

    Searches for properties suitable for families (2 adults, 2 children ages 3 & 6)
    with at least 2 bedrooms, preferably with kitchens.
    """

    def __init__(
        self,
        headless: bool = True,
        screenshots_dir: Optional[Path] = None,
        rate_limit_seconds: float = 5.0,
    ):
        """
        Initialize the Booking.com scraper.

        Args:
            headless: Run browser in headless mode
            screenshots_dir: Directory to save error screenshots
            rate_limit_seconds: Minimum seconds between requests (4-8 recommended)
        """
        self.headless = headless
        self.screenshots_dir = screenshots_dir or Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
        self.rate_limit_seconds = rate_limit_seconds
        self.browser = None
        self.context = None
        self.playwright = None
        logger.info(f"BookingClient initialized (headless={headless})")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self) -> None:
        """Start the Playwright browser."""
        if self.browser:
            return

        logger.info("Starting Playwright browser...")
        self.playwright = await async_playwright().start()

        # Random user agent for this session
        user_agent = random.choice(USER_AGENTS)

        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

        self.context = await self.browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="Europe/Berlin",
        )

        # Add extra headers to avoid detection
        await self.context.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        })

        logger.info("Browser started successfully")

    async def close(self) -> None:
        """Close the browser and clean up resources."""
        if self.context:
            await self.context.close()
            self.context = None

        if self.browser:
            await self.browser.close()
            self.browser = None

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

        logger.info("Browser closed")

    async def _random_delay(self, min_seconds: Optional[float] = None) -> None:
        """Add a random delay to simulate human behavior."""
        min_sec = min_seconds or self.rate_limit_seconds
        max_sec = min_sec + 3
        delay = random.uniform(min_sec, max_sec)
        logger.debug(f"Waiting {delay:.2f} seconds...")
        await asyncio.sleep(delay)

    async def _save_screenshot(self, page: Page, name: str) -> None:
        """Save a screenshot for debugging."""
        try:
            filepath = self.screenshots_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"Screenshot saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")

    def _build_search_url(
        self,
        city: str,
        check_in: date,
        check_out: date,
        adults: int = 2,
        children_ages: Optional[List[int]] = None,
        no_rooms: int = 1,
    ) -> str:
        """
        Build the Booking.com search URL with family parameters.

        Args:
            city: Destination city name
            check_in: Check-in date
            check_out: Check-out date
            adults: Number of adults (default: 2)
            children_ages: List of children ages (default: [3, 6])
            no_rooms: Number of rooms (default: 1)

        Returns:
            Complete Booking.com search URL
        """
        if children_ages is None:
            children_ages = [3, 6]

        params = {
            "ss": city,
            "checkin": check_in.strftime("%Y-%m-%d"),
            "checkout": check_out.strftime("%Y-%m-%d"),
            "group_adults": adults,
            "group_children": len(children_ages),
            "no_rooms": no_rooms,
        }

        # Add age parameters for each child
        age_params = "&".join([f"age={age}" for age in children_ages])

        base_url = "https://www.booking.com/searchresults.html"
        param_string = "&".join([f"{k}={quote_plus(str(v))}" for k, v in params.items()])

        url = f"{base_url}?{param_string}&{age_params}"
        logger.info(f"Built search URL: {url}")
        return url

    async def _handle_cookie_consent(self, page: Page) -> None:
        """Handle cookie consent banner if it appears."""
        try:
            # Try multiple possible selectors for the accept button
            selectors = [
                "button#onetrust-accept-btn-handler",
                "button[data-testid='accept-cookie-banner']",
                "button:has-text('Accept')",
                "button:has-text('I agree')",
            ]

            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    await page.click(selector)
                    logger.info("Cookie consent accepted")
                    await asyncio.sleep(settings.scraper_action_delay)
                    return
                except PlaywrightTimeout:
                    continue

            logger.debug("No cookie consent banner found")

        except Exception as e:
            logger.debug(f"Cookie consent handling: {e}")

    async def _wait_for_results(self, page: Page) -> bool:
        """
        Wait for property cards to load on the page.

        Returns:
            True if results loaded successfully, False otherwise
        """
        try:
            # Wait for property cards to appear
            await page.wait_for_selector(
                "[data-testid='property-card'], .sr_item, .c4a4f1de3b",
                timeout=15000
            )
            logger.info("Property cards loaded")
            return True

        except PlaywrightTimeout:
            logger.error("Timeout waiting for property cards")
            await self._save_screenshot(page, "timeout_no_results")
            return False

    async def _scroll_to_load_more(self, page: Page, max_scrolls: int = 3) -> None:
        """
        Scroll the page to trigger lazy loading of more properties.

        Args:
            page: Playwright page object
            max_scrolls: Maximum number of scroll attempts
        """
        logger.info("Scrolling to load more properties...")

        for i in range(max_scrolls):
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(random.uniform(
                settings.scraper_page_load_delay * 0.75,
                settings.scraper_page_load_delay * 1.25
            ))

            # Scroll back up a bit (more human-like)
            await page.evaluate("window.scrollBy(0, -300)")
            await asyncio.sleep(random.uniform(
                settings.scraper_request_delay * 0.5,
                settings.scraper_request_delay * 1.0
            ))

        logger.info(f"Completed {max_scrolls} scroll cycles")

    async def parse_property_cards(self, page: Page, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Extract property data from search result cards.

        Args:
            page: Playwright page with search results
            limit: Maximum number of properties to extract

        Returns:
            List of property dictionaries with extracted data
        """
        logger.info("Parsing property cards...")
        properties = []

        try:
            # Get all property cards
            cards = await page.query_selector_all(
                "[data-testid='property-card'], .sr_item, .c4a4f1de3b"
            )

            logger.info(f"Found {len(cards)} property cards")

            for idx, card in enumerate(cards[:limit]):
                try:
                    property_data = await self._parse_single_property(card, page)
                    if property_data:
                        properties.append(property_data)
                        logger.debug(f"Parsed property {idx + 1}: {property_data.get('name', 'Unknown')}")

                except Exception as e:
                    logger.warning(f"Failed to parse property card {idx + 1}: {e}")
                    continue

            logger.info(f"Successfully parsed {len(properties)} properties")

        except Exception as e:
            logger.error(f"Error parsing property cards: {e}")
            await self._save_screenshot(page, "parse_error")

        return properties

    async def _parse_single_property(self, card, page: Page) -> Optional[Dict[str, Any]]:
        """
        Parse a single property card.

        Args:
            card: Playwright element handle for the property card
            page: Playwright page object

        Returns:
            Dictionary with property data or None if parsing fails
        """
        property_data: Dict[str, Any] = {}

        try:
            # Property name
            name_elem = await card.query_selector(
                "[data-testid='title'], .sr-hotel__name, h3, h2"
            )
            property_data["name"] = await name_elem.inner_text() if name_elem else "Unknown"
            property_data["name"] = property_data["name"].strip()

            # Property URL
            link_elem = await card.query_selector("a[data-testid='title-link'], a.hotel_name_link")
            if link_elem:
                href = await link_elem.get_attribute("href")
                property_data["url"] = f"https://www.booking.com{href}" if href and href.startswith("/") else href
            else:
                property_data["url"] = None

            # Price per night
            property_data["price_per_night"] = await self._extract_price(card)

            # Rating
            property_data["rating"] = await self._extract_rating(card)

            # Review count
            property_data["review_count"] = await self._extract_review_count(card)

            # Image URL
            property_data["image_url"] = await self._extract_image_url(card)

            # Property type (apartment vs hotel)
            property_data["type"] = await self._extract_property_type(card, property_data["name"])

            # Amenities
            amenities = await self.extract_amenities(card)
            property_data.update(amenities)

            # Bedrooms (try to extract from description)
            property_data["bedrooms"] = await self._extract_bedrooms(card)

            return property_data

        except Exception as e:
            logger.debug(f"Error parsing property: {e}")
            return None

    async def _extract_price(self, card) -> Optional[float]:
        """Extract price per night from property card."""
        try:
            # Try multiple price selectors
            price_selectors = [
                "[data-testid='price-and-discounted-price']",
                ".bui-price-display__value",
                ".prco-valign-middle-helper",
                ".prco-text-nowrap-helper",
            ]

            for selector in price_selectors:
                price_elem = await card.query_selector(selector)
                if price_elem:
                    price_text = await price_elem.inner_text()
                    # Extract numbers from price text
                    price_match = re.search(r"[\d,]+\.?\d*", price_text.replace(",", ""))
                    if price_match:
                        return float(price_match.group())

            return None

        except Exception as e:
            logger.debug(f"Error extracting price: {e}")
            return None

    async def _extract_rating(self, card) -> Optional[float]:
        """Extract rating from property card."""
        try:
            rating_selectors = [
                "[data-testid='review-score'] [aria-label]",
                ".bui-review-score__badge",
                ".review-score-badge",
            ]

            for selector in rating_selectors:
                rating_elem = await card.query_selector(selector)
                if rating_elem:
                    # Try aria-label first
                    aria_label = await rating_elem.get_attribute("aria-label")
                    if aria_label:
                        rating_match = re.search(r"(\d+\.?\d*)", aria_label)
                        if rating_match:
                            return float(rating_match.group(1))

                    # Try inner text
                    rating_text = await rating_elem.inner_text()
                    rating_match = re.search(r"(\d+\.?\d*)", rating_text)
                    if rating_match:
                        return float(rating_match.group(1))

            return None

        except Exception as e:
            logger.debug(f"Error extracting rating: {e}")
            return None

    async def _extract_review_count(self, card) -> Optional[int]:
        """Extract review count from property card."""
        try:
            review_selectors = [
                "[data-testid='review-score'] + div",
                ".bui-review-score__text",
                ".review-score-widget__subtext",
            ]

            for selector in review_selectors:
                review_elem = await card.query_selector(selector)
                if review_elem:
                    review_text = await review_elem.inner_text()
                    # Extract number of reviews
                    review_match = re.search(r"([\d,]+)", review_text.replace(",", ""))
                    if review_match:
                        return int(review_match.group(1))

            return None

        except Exception as e:
            logger.debug(f"Error extracting review count: {e}")
            return None

    async def _extract_image_url(self, card) -> Optional[str]:
        """Extract main image URL from property card."""
        try:
            img_elem = await card.query_selector("img[data-testid='image'], img")
            if img_elem:
                # Try src first, then data-src for lazy-loaded images
                src = await img_elem.get_attribute("src")
                if src and not src.startswith("data:"):
                    return src

                data_src = await img_elem.get_attribute("data-src")
                if data_src:
                    return data_src

            return None

        except Exception as e:
            logger.debug(f"Error extracting image: {e}")
            return None

    async def _extract_property_type(self, card, name: str) -> str:
        """Determine if property is apartment or hotel."""
        try:
            # Check property name and card text for type indicators
            card_text = await card.inner_text()
            combined_text = f"{name} {card_text}".lower()

            apartment_keywords = ["apartment", "flat", "studio", "residence", "suite"]
            hotel_keywords = ["hotel", "resort", "inn", "lodge"]

            for keyword in apartment_keywords:
                if keyword in combined_text:
                    return "apartment"

            for keyword in hotel_keywords:
                if keyword in combined_text:
                    return "hotel"

            return "hotel"  # Default to hotel

        except Exception as e:
            logger.debug(f"Error extracting property type: {e}")
            return "hotel"

    async def _extract_bedrooms(self, card) -> Optional[int]:
        """Extract number of bedrooms from property card."""
        try:
            card_text = await card.inner_text()

            # Look for bedroom count patterns
            bedroom_patterns = [
                r"(\d+)\s*bedroom",
                r"(\d+)\s*bed\s*(?:room)?",
                r"(\d+)-bedroom",
            ]

            for pattern in bedroom_patterns:
                match = re.search(pattern, card_text.lower())
                if match:
                    return int(match.group(1))

            # Check for "family room" which usually indicates larger room
            if "family room" in card_text.lower():
                return 2  # Assume family rooms have at least 2 bedrooms

            return None

        except Exception as e:
            logger.debug(f"Error extracting bedrooms: {e}")
            return None

    async def extract_amenities(self, property_card) -> Dict[str, bool]:
        """
        Extract amenity information from property card.

        Args:
            property_card: Playwright element handle for property card

        Returns:
            Dictionary with amenity flags (has_kitchen, has_kids_club, etc.)
        """
        amenities = {
            "has_kitchen": False,
            "has_kids_club": False,
        }

        try:
            card_text = await property_card.inner_text()
            card_text_lower = card_text.lower()

            # Check for kitchen
            kitchen_keywords = ["kitchen", "kitchenette", "cooking facilities"]
            amenities["has_kitchen"] = any(kw in card_text_lower for kw in kitchen_keywords)

            # Check for kids club/facilities
            kids_keywords = ["kids club", "children's club", "playground", "kids' activities"]
            amenities["has_kids_club"] = any(kw in card_text_lower for kw in kids_keywords)

        except Exception as e:
            logger.debug(f"Error extracting amenities: {e}")

        return amenities

    def filter_family_friendly(
        self,
        properties: List[Dict[str, Any]],
        min_bedrooms: int = 2,
        max_price: float = 150.0,
        min_rating: float = 7.5,
    ) -> List[Dict[str, Any]]:
        """
        Filter properties to keep only family-friendly options.

        Args:
            properties: List of property dictionaries
            min_bedrooms: Minimum number of bedrooms (default: 2)
            max_price: Maximum price per night in EUR (default: 150)
            min_rating: Minimum rating score (default: 7.5)

        Returns:
            Filtered list of family-friendly properties
        """
        logger.info(f"Filtering {len(properties)} properties for family-friendly options...")

        family_friendly = []

        for prop in properties:
            # Skip if no price
            if not prop.get("price_per_night"):
                continue

            # Check price
            if prop["price_per_night"] > max_price:
                continue

            # Check rating
            if prop.get("rating") and prop["rating"] < min_rating:
                continue

            # Check bedrooms (allow if unknown, as we can check details later)
            bedrooms = prop.get("bedrooms")
            if bedrooms and bedrooms < min_bedrooms:
                continue

            # Prefer apartments and properties with kitchens
            score = 0
            if prop.get("type") == "apartment":
                score += 1
            if prop.get("has_kitchen"):
                score += 2
            if bedrooms and bedrooms >= min_bedrooms:
                score += 2
            if prop.get("rating", 0) >= 8.5:
                score += 1

            # Only include if it has some family-friendly characteristics
            if score >= 1 or bedrooms:
                prop["family_friendly"] = True
                family_friendly.append(prop)

        logger.info(f"Filtered to {len(family_friendly)} family-friendly properties")
        return family_friendly

    async def search(
        self,
        city: str,
        check_in: date,
        check_out: date,
        adults: int = 2,
        children_ages: Optional[List[int]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search for family accommodations on Booking.com.

        Args:
            city: Destination city name
            check_in: Check-in date
            check_out: Check-out date
            adults: Number of adults (default: 2)
            children_ages: List of children ages (default: [3, 6])
            limit: Maximum number of properties to return (default: 20)

        Returns:
            List of property dictionaries with extracted data
        """
        if not self.browser:
            await self.start()

        if children_ages is None:
            children_ages = [3, 6]

        logger.info(
            f"Searching Booking.com for {city} "
            f"({check_in} to {check_out}, {adults} adults, {len(children_ages)} children)"
        )

        # Build search URL
        url = self._build_search_url(city, check_in, check_out, adults, children_ages)

        # Create new page
        page = await self.context.new_page()

        try:
            # Navigate to search results
            logger.info("Loading search results page...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Handle cookie consent
            await self._handle_cookie_consent(page)

            # Wait for results to load
            if not await self._wait_for_results(page):
                logger.error("Failed to load search results")
                return []

            # Random delay before scrolling
            await self._random_delay(2.0)

            # Scroll to load more properties
            await self._scroll_to_load_more(page, max_scrolls=3)

            # Parse property cards
            properties = await self.parse_property_cards(page, limit=limit)

            # Add destination city to each property
            for prop in properties:
                prop["destination_city"] = city
                prop["source"] = "booking"
                prop["scraped_at"] = datetime.now().isoformat()

            logger.info(f"Search complete: found {len(properties)} properties")

            return properties

        except Exception as e:
            logger.error(f"Error during search: {e}")
            await self._save_screenshot(page, "search_error")
            raise

        finally:
            await page.close()
            # Rate limiting
            await self._random_delay()

    async def save_to_database(
        self,
        properties: List[Dict[str, Any]],
        session: Optional[AsyncSession] = None,
    ) -> int:
        """
        Save scraped properties to the database.

        Args:
            properties: List of property dictionaries to save
            session: Optional database session (creates new one if not provided)

        Returns:
            Number of properties saved
        """
        if not properties:
            logger.warning("No properties to save")
            return 0

        should_close = session is None
        if session is None:
            session = AsyncSessionLocal()

        try:
            saved_count = 0

            for prop_data in properties:
                try:
                    # Convert scraped_at to datetime if it's a string
                    if isinstance(prop_data.get("scraped_at"), str):
                        prop_data["scraped_at"] = datetime.fromisoformat(
                            prop_data["scraped_at"].replace("Z", "+00:00")
                        )

                    # Create Accommodation instance
                    accommodation = Accommodation(
                        destination_city=prop_data.get("destination_city", "Unknown"),
                        name=prop_data.get("name", "Unknown"),
                        type=prop_data.get("type", "hotel"),
                        bedrooms=prop_data.get("bedrooms"),
                        price_per_night=prop_data.get("price_per_night", 0.0),
                        family_friendly=prop_data.get("family_friendly", False),
                        has_kitchen=prop_data.get("has_kitchen", False),
                        has_kids_club=prop_data.get("has_kids_club", False),
                        rating=prop_data.get("rating"),
                        review_count=prop_data.get("review_count"),
                        source=prop_data.get("source", "booking"),
                        url=prop_data.get("url"),
                        image_url=prop_data.get("image_url"),
                        scraped_at=prop_data.get("scraped_at", datetime.now()),
                    )

                    session.add(accommodation)
                    saved_count += 1

                except Exception as e:
                    logger.error(f"Error saving property '{prop_data.get('name')}': {e}")
                    continue

            await session.commit()
            logger.info(f"Successfully saved {saved_count} properties to database")

            return saved_count

        except Exception as e:
            await session.rollback()
            logger.error(f"Database error: {e}")
            raise

        finally:
            if should_close:
                await session.close()


# Convenience function for quick searches
async def search_booking(
    city: str,
    check_in: date,
    check_out: date,
    save_to_db: bool = True,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Convenience function to search Booking.com and optionally save to database.

    Args:
        city: Destination city
        check_in: Check-in date
        check_out: Check-out date
        save_to_db: Whether to save results to database (default: True)
        **kwargs: Additional arguments passed to BookingClient.search()

    Returns:
        List of property dictionaries

    Example:
        >>> from datetime import date
        >>> properties = await search_booking(
        ...     'Lisbon',
        ...     date(2025, 12, 20),
        ...     date(2025, 12, 27)
        ... )
    """
    async with BookingClient() as client:
        properties = await client.search(city, check_in, check_out, **kwargs)
        family_properties = client.filter_family_friendly(properties)

        if save_to_db and family_properties:
            await client.save_to_database(family_properties)

        return family_properties
