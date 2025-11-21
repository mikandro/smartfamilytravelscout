"""
Airbnb scraper using Apify (primary) or Playwright (fallback).

This module provides functionality to search for family-friendly Airbnb listings
using Apify's pre-built Airbnb Scraper actor or direct scraping with Playwright.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session_context
from app.models.accommodation import Accommodation

logger = logging.getLogger(__name__)


class AirbnbClient:
    """
    Client for scraping Airbnb listings using Apify or Playwright.

    Apify free tier: 5,000 results/month, $5 free credit.
    Actor: https://apify.com/dtrungtin/airbnb-scraper
    """

    # Apify actor ID for Airbnb scraper
    AIRBNB_ACTOR_ID = "dtrungtin/airbnb-scraper"

    # Family-friendly criteria
    MIN_BEDROOMS = 2
    MAX_PRICE_PER_NIGHT = 150.0  # EUR
    REQUIRED_AMENITIES = ["Kitchen"]
    PROPERTY_TYPE = "Entire place"

    def __init__(self, apify_api_key: Optional[str] = None):
        """
        Initialize Airbnb client.

        Args:
            apify_api_key: Apify API key. If not provided, uses settings.
        """
        self.apify_api_key = apify_api_key or settings.apify_api_key
        self.apify_client = None
        self.credits_used = 0.0

        # Initialize Apify client if API key is available
        if self.apify_api_key:
            try:
                from apify_client import ApifyClient
                self.apify_client = ApifyClient(self.apify_api_key)
                logger.info("Apify client initialized successfully")
            except ImportError:
                logger.warning(
                    "apify-client not installed. Install with: pip install apify-client"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Apify client: {e}")

    async def search(
        self,
        city: str,
        check_in: date,
        check_out: date,
        adults: int = 2,
        children: int = 2,
        max_listings: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search for Airbnb listings.

        Tries Apify first, falls back to Playwright if unavailable.

        Args:
            city: Destination city (e.g., "Lisbon, Portugal")
            check_in: Check-in date
            check_out: Check-out date
            adults: Number of adults
            children: Number of children
            max_listings: Maximum number of listings to return

        Returns:
            List of accommodation dictionaries
        """
        logger.info(f"Searching Airbnb for {city}: {check_in} to {check_out}")

        # Try Apify first
        if self.apify_client:
            try:
                return await self._search_with_apify(
                    city, check_in, check_out, adults, children, max_listings
                )
            except Exception as e:
                logger.error(f"Apify search failed: {e}. Falling back to Playwright.")

        # Fallback to Playwright
        logger.info("Using Playwright fallback for scraping")
        return await self._scrape_airbnb_direct(
            city, check_in, check_out, adults, children, max_listings
        )

    async def _search_with_apify(
        self,
        city: str,
        check_in: date,
        check_out: date,
        adults: int,
        children: int,
        max_listings: int,
    ) -> List[Dict[str, Any]]:
        """
        Search Airbnb using Apify actor.

        Args:
            city: Destination city
            check_in: Check-in date
            check_out: Check-out date
            adults: Number of adults
            children: Number of children
            max_listings: Maximum listings

        Returns:
            List of parsed accommodation dictionaries
        """
        # Build Apify input
        actor_input = self.build_apify_input(
            city, check_in, check_out, adults, children, max_listings
        )

        logger.info(f"Running Apify actor with input: {actor_input}")

        # Run the actor and wait for it to finish
        run = self.apify_client.actor(self.AIRBNB_ACTOR_ID).call(run_input=actor_input)

        # Track credits used
        if run.get("stats", {}).get("computeUnits"):
            credits = run["stats"]["computeUnits"]
            self.credits_used += credits
            logger.info(f"Apify credits used: {credits:.4f} (total: {self.credits_used:.4f})")

        # Fetch results from dataset
        dataset_items = []
        for item in self.apify_client.dataset(run["defaultDatasetId"]).iterate_items():
            dataset_items.append(item)

        logger.info(f"Retrieved {len(dataset_items)} listings from Apify")

        # Parse and return results
        return self.parse_apify_results(dataset_items)

    def build_apify_input(
        self,
        city: str,
        check_in: date,
        check_out: date,
        adults: int = 2,
        children: int = 2,
        max_listings: int = 20,
    ) -> Dict[str, Any]:
        """
        Build input configuration for Apify Airbnb Scraper actor.

        Args:
            city: Destination city
            check_in: Check-in date
            check_out: Check-out date
            adults: Number of adults
            children: Number of children
            max_listings: Maximum listings

        Returns:
            Dictionary with actor input configuration
        """
        return {
            "locationQuery": city,
            "checkIn": check_in.strftime("%Y-%m-%d"),
            "checkOut": check_out.strftime("%Y-%m-%d"),
            "currency": "EUR",
            "adults": adults,
            "children": children,
            "propertyType": [self.PROPERTY_TYPE],
            "minBedrooms": self.MIN_BEDROOMS,
            "amenities": self.REQUIRED_AMENITIES,
            "maxListings": max_listings,
            "includeReviews": False,  # Speed up scraping
        }

    def parse_apify_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert Apify output to standardized Accommodation format.

        Apify returns fields like:
        - name, url
        - pricing (price per night)
        - bedrooms, beds, bathrooms
        - amenities (array)
        - rating, reviewsCount
        - host info
        - images (array)

        Args:
            results: Raw results from Apify

        Returns:
            List of standardized accommodation dictionaries
        """
        accommodations = []

        for item in results:
            try:
                # Extract price (handle different price formats)
                price_str = item.get("price", {}).get("rate", 0)
                if isinstance(price_str, str):
                    # Remove currency symbols and parse
                    price_str = price_str.replace("€", "").replace(",", "").strip()
                    price = float(price_str)
                else:
                    price = float(price_str)

                # Get amenities list
                amenities = item.get("amenities", [])
                if isinstance(amenities, list):
                    amenities_list = amenities
                else:
                    amenities_list = []

                # Check for family-friendly indicators
                family_friendly = any(
                    keyword in str(amenities).lower() or keyword in str(item.get("description", "")).lower()
                    for keyword in ["family", "child", "kid", "children"]
                )

                # Check for kitchen
                has_kitchen = any(
                    "kitchen" in str(amenity).lower()
                    for amenity in amenities_list
                )

                # Get images
                images = item.get("images", [])
                image_url = images[0] if images else None

                # Build standardized accommodation dict
                accommodation = {
                    "name": item.get("name", "Airbnb Listing"),
                    "type": "apartment",  # Airbnb listings are typically apartments
                    "destination_city": item.get("location", {}).get("city", "Unknown"),
                    "bedrooms": item.get("bedrooms", 0),
                    "price_per_night": price,
                    "family_friendly": family_friendly,
                    "has_kitchen": has_kitchen,
                    "has_kids_club": False,  # Airbnb doesn't have kids clubs
                    "rating": float(item.get("rating", 0)) if item.get("rating") else None,
                    "review_count": item.get("reviewsCount", 0),
                    "source": "airbnb",
                    "url": item.get("url"),
                    "image_url": image_url,
                    "scraped_at": datetime.utcnow(),
                }

                accommodations.append(accommodation)

            except Exception as e:
                logger.warning(f"Failed to parse Apify result: {e}. Item: {item}")
                continue

        logger.info(f"Parsed {len(accommodations)} accommodations from Apify results")
        return accommodations

    def filter_family_suitable(
        self, listings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter listings for family-friendly criteria.

        Criteria:
        - Type: "Entire place" only (handled in search)
        - Bedrooms >= 2
        - Has kitchen
        - Price <= MAX_PRICE_PER_NIGHT
        - Optionally: family-friendly indicators

        Args:
            listings: List of accommodation dictionaries

        Returns:
            Filtered list of family-suitable accommodations
        """
        filtered = []

        for listing in listings:
            # Check bedrooms
            if listing.get("bedrooms", 0) < self.MIN_BEDROOMS:
                continue

            # Check kitchen
            if not listing.get("has_kitchen", False):
                continue

            # Check price
            if listing.get("price_per_night", 999) > self.MAX_PRICE_PER_NIGHT:
                continue

            filtered.append(listing)

        logger.info(
            f"Filtered {len(filtered)} family-suitable listings from {len(listings)} total"
        )
        return filtered

    async def _scrape_airbnb_direct(
        self,
        city: str,
        check_in: date,
        check_out: date,
        adults: int,
        children: int,
        max_listings: int,
    ) -> List[Dict[str, Any]]:
        """
        Fallback: Direct scraping with Playwright.

        This is used when Apify is unavailable.

        Args:
            city: Destination city
            check_in: Check-in date
            check_out: Check-out date
            adults: Number of adults
            children: Number of children
            max_listings: Maximum listings

        Returns:
            List of accommodation dictionaries
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Cannot perform direct scraping.")
            return []

        logger.info(f"Starting Playwright scraping for {city}")

        # Build Airbnb search URL
        url = self._build_airbnb_url(city, check_in, check_out, adults, children)
        logger.info(f"Scraping URL: {url}")

        accommodations = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=settings.scraper_user_agent,
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            try:
                # Navigate to Airbnb search
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)  # Wait for dynamic content

                # Extract listing cards
                listings = await page.query_selector_all('[data-testid="card-container"]')

                logger.info(f"Found {len(listings)} listing cards")

                for i, listing in enumerate(listings[:max_listings]):
                    try:
                        accommodation = await self._parse_listing_card(listing, city)
                        if accommodation:
                            accommodations.append(accommodation)
                    except Exception as e:
                        logger.warning(f"Failed to parse listing {i}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Playwright scraping failed: {e}")

            finally:
                await browser.close()

        logger.info(f"Playwright scraping completed: {len(accommodations)} listings")
        return accommodations

    def _build_airbnb_url(
        self,
        city: str,
        check_in: date,
        check_out: date,
        adults: int,
        children: int,
    ) -> str:
        """
        Build Airbnb search URL with parameters.

        Args:
            city: Destination city
            check_in: Check-in date
            check_out: Check-out date
            adults: Number of adults
            children: Number of children

        Returns:
            Formatted Airbnb search URL
        """
        base_url = "https://www.airbnb.com/s/{city}/homes"

        # Format dates
        checkin_str = check_in.strftime("%Y-%m-%d")
        checkout_str = check_out.strftime("%Y-%m-%d")

        # Build query parameters
        params = [
            f"checkin={checkin_str}",
            f"checkout={checkout_str}",
            f"adults={adults}",
            f"children={children}",
            "room_types[]=Entire%20home/apt",
            f"min_bedrooms={self.MIN_BEDROOMS}",
            "amenities[]=8",  # Kitchen amenity ID
        ]

        url = base_url.format(city=city.replace(" ", "-")) + "?" + "&".join(params)
        return url

    async def _parse_listing_card(
        self, listing_element, city: str
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single Airbnb listing card element.

        Args:
            listing_element: Playwright element for listing card
            city: Destination city

        Returns:
            Accommodation dictionary or None if parsing fails
        """
        try:
            # Extract title
            title_el = await listing_element.query_selector('[data-testid="listing-card-title"]')
            name = await title_el.inner_text() if title_el else "Airbnb Listing"

            # Extract price
            price_el = await listing_element.query_selector('[data-testid="price-availability-row"]')
            price_text = await price_el.inner_text() if price_el else "€0"
            price = self._extract_price_from_text(price_text)

            # Extract rating
            rating_el = await listing_element.query_selector('[data-testid="listing-card-subtitle"]')
            rating_text = await rating_el.inner_text() if rating_el else ""
            rating = self._extract_rating_from_text(rating_text)

            # Extract URL
            link_el = await listing_element.query_selector('a')
            url = await link_el.get_attribute("href") if link_el else None
            if url and not url.startswith("http"):
                url = f"https://www.airbnb.com{url}"

            # Extract image
            img_el = await listing_element.query_selector('img')
            image_url = await img_el.get_attribute("src") if img_el else None

            return {
                "name": name,
                "type": "apartment",
                "destination_city": city,
                "bedrooms": self.MIN_BEDROOMS,  # Filtered in search
                "price_per_night": price,
                "family_friendly": True,  # Assumed from search filters
                "has_kitchen": True,  # Filtered in search
                "has_kids_club": False,
                "rating": rating,
                "review_count": 0,  # Not easily extractable
                "source": "airbnb",
                "url": url,
                "image_url": image_url,
                "scraped_at": datetime.utcnow(),
            }

        except Exception as e:
            logger.warning(f"Failed to parse listing card: {e}")
            return None

    def _extract_price_from_text(self, text: str) -> float:
        """Extract numeric price from text like '€123 per night'."""
        try:
            # Remove non-numeric characters except decimal point
            price_str = "".join(c for c in text if c.isdigit() or c == ".")
            return float(price_str) if price_str else 0.0
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to extract price from text '{text}': {e}")
            return 0.0

    def _extract_rating_from_text(self, text: str) -> Optional[float]:
        """Extract rating from text like '4.8 (123 reviews)'."""
        try:
            # Look for pattern like "4.8"
            import re
            match = re.search(r"(\d+\.?\d*)", text)
            if match:
                rating = float(match.group(1))
                return rating if 0 <= rating <= 5 else None
            return None
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to extract rating from text '{text}': {e}")
            return None

    async def save_to_database(
        self,
        listings: List[Dict[str, Any]],
        session: Optional[AsyncSession] = None,
    ) -> int:
        """
        Save accommodations to database.

        Args:
            listings: List of accommodation dictionaries
            session: Optional database session (creates new one if not provided)

        Returns:
            Number of accommodations saved
        """
        if not listings:
            logger.warning("No listings to save to database")
            return 0

        # Use provided session or create new one
        if session:
            return await self._save_listings(listings, session)
        else:
            async with get_async_session_context() as db:
                return await self._save_listings(listings, db)

    async def _save_listings(
        self, listings: List[Dict[str, Any]], session: AsyncSession
    ) -> int:
        """Helper method to save listings with a database session."""
        saved_count = 0

        for listing_data in listings:
            try:
                # Check if listing already exists (by URL)
                if listing_data.get("url"):
                    result = await session.execute(
                        select(Accommodation).where(
                            Accommodation.url == listing_data["url"]
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        # Update existing
                        for key, value in listing_data.items():
                            setattr(existing, key, value)
                        logger.debug(f"Updated existing accommodation: {listing_data['name']}")
                    else:
                        # Create new
                        accommodation = Accommodation(**listing_data)
                        session.add(accommodation)
                        saved_count += 1
                        logger.debug(f"Added new accommodation: {listing_data['name']}")
                else:
                    # No URL, just create new
                    accommodation = Accommodation(**listing_data)
                    session.add(accommodation)
                    saved_count += 1

            except Exception as e:
                logger.error(f"Failed to save accommodation: {e}. Data: {listing_data}")
                continue

        await session.commit()
        logger.info(f"Saved {saved_count} new accommodations to database")
        return saved_count

    def get_credits_used(self) -> float:
        """
        Get total Apify credits used in this session.

        Returns:
            Total credits used
        """
        return self.credits_used
