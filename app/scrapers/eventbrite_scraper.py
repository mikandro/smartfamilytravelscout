"""
EventBrite API client for discovering family-friendly and cultural events.

This module provides integration with EventBrite's public API to search for events
in specific cities and date ranges, categorize them, and save to the database.

API Documentation: https://www.eventbrite.com/platform/api
Rate Limit: 1,000 requests/day (free tier)
"""

import logging
import re
from datetime import date, datetime, timezone
from typing import Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session_context
from app.exceptions import APIKeyMissingError
from app.models.event import Event
from app.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)

# EventBrite API configuration
EVENTBRITE_API_BASE_URL = "https://www.eventbriteapi.com/v3"
EVENTBRITE_EVENTS_ENDPOINT = f"{EVENTBRITE_API_BASE_URL}/events/search/"

# EventBrite category IDs for different event types
# Reference: https://www.eventbrite.com/platform/api#/reference/category
EVENTBRITE_CATEGORIES = {
    "family": [103, 115],  # Family & Education, Kids & Family
    "food_drink": [110],  # Food & Drink
    "music": [103],  # Music
    "arts": [105],  # Performing & Visual Arts
    "nightlife": [118],  # Nightlife
    "sports": [108],  # Sports & Fitness
    "cultural": [105, 113],  # Arts, Community & Culture
}

# Rate limiting tracker
_api_call_count = 0
_api_call_reset_time = None
MAX_DAILY_CALLS = 1000
RATE_LIMIT_WARNING_THRESHOLD = 900


class EventBriteAPIError(Exception):
    """Custom exception for EventBrite API errors."""

    pass


class EventBriteRateLimitError(Exception):
    """Exception raised when rate limit is exceeded."""

    pass


class EventBriteClient:
    """
    Client for interacting with EventBrite API.

    Handles event searching, categorization, and database persistence.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize EventBrite client.

        Args:
            api_key: EventBrite private token. If not provided, uses settings.
        """
        self.api_key = api_key or settings.eventbrite_api_key
        if not self.api_key:
            raise APIKeyMissingError(
                service="EventBrite API",
                env_var="EVENTBRITE_API_KEY",
                optional=True,
                fallback_info=(
                    "Get a free API key (1,000 requests/day) at: https://www.eventbrite.com/platform/api\n\n"
                    "EventBrite integration will be disabled. You can still use:\n"
                    "  - Tourism scrapers (Barcelona, Prague, Lisbon)\n"
                    "  - Other event sources"
                )
            )

        self.session: Optional[httpx.AsyncClient] = None
        self._call_count = 0

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=settings.scraper_timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.aclose()

    def _track_api_call(self):
        """Track API call count and warn if approaching rate limit."""
        global _api_call_count, _api_call_reset_time

        # Reset counter at midnight UTC
        now = datetime.now(timezone.utc)
        if _api_call_reset_time is None or now.date() > _api_call_reset_time.date():
            _api_call_count = 0
            _api_call_reset_time = now

        _api_call_count += 1
        self._call_count += 1

        if _api_call_count >= MAX_DAILY_CALLS:
            raise EventBriteRateLimitError(
                f"EventBrite API daily rate limit reached ({MAX_DAILY_CALLS} calls/day)"
            )

        if _api_call_count >= RATE_LIMIT_WARNING_THRESHOLD:
            logger.warning(
                f"Approaching EventBrite API rate limit: {_api_call_count}/{MAX_DAILY_CALLS} calls used"
            )

    @retry_with_backoff(
        max_attempts=3,
        backoff_seconds=2,
        exceptions=(httpx.HTTPError, TimeoutError),
    )
    async def _make_request(
        self, url: str, params: Optional[Dict] = None
    ) -> Dict:
        """
        Make HTTP request to EventBrite API with retry logic.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            EventBriteAPIError: If API returns an error
            EventBriteRateLimitError: If rate limit is exceeded
        """
        if not self.session:
            raise RuntimeError("Client must be used as async context manager")

        self._track_api_call()

        logger.debug(f"Making EventBrite API request: {url} with params: {params}")

        response = await self.session.get(url, params=params)

        if response.status_code == 429:
            raise EventBriteRateLimitError("EventBrite API rate limit exceeded")

        if response.status_code == 401:
            raise EventBriteAPIError("Invalid EventBrite API key")

        if response.status_code == 404:
            raise EventBriteAPIError("EventBrite API endpoint not found")

        if response.status_code >= 400:
            error_text = response.text
            raise EventBriteAPIError(
                f"EventBrite API error {response.status_code}: {error_text}"
            )

        return response.json()

    async def search_events(
        self,
        city: str,
        start_date: date,
        end_date: date,
        categories: Optional[List[str]] = None,
        max_results: int = 50,
    ) -> List[Dict]:
        """
        Search for events in a city during a date range.

        Args:
            city: City name (e.g., "Prague", "Lisbon")
            start_date: Start date for event search
            end_date: End date for event search
            categories: List of category names to filter (e.g., ["family", "cultural"])
            max_results: Maximum number of results to return (default: 50)

        Returns:
            List of event dictionaries in standardized format

        Example:
            >>> async with EventBriteClient() as client:
            >>>     events = await client.search_events(
            >>>         "Prague",
            >>>         date(2025, 12, 15),
            >>>         date(2025, 12, 25),
            >>>         categories=["family", "cultural"]
            >>>     )
        """
        logger.info(
            f"Searching EventBrite events in {city} from {start_date} to {end_date}"
        )

        # Build category IDs list
        category_ids = []
        if categories:
            for cat in categories:
                if cat in EVENTBRITE_CATEGORIES:
                    category_ids.extend(EVENTBRITE_CATEGORIES[cat])
        else:
            # Default to family and cultural events
            category_ids.extend(EVENTBRITE_CATEGORIES["family"])
            category_ids.extend(EVENTBRITE_CATEGORIES["cultural"])

        # Remove duplicates
        category_ids = list(set(category_ids))

        params = {
            "location.address": city,
            "start_date.range_start": start_date.isoformat() + "T00:00:00Z",
            "start_date.range_end": end_date.isoformat() + "T23:59:59Z",
            "expand": "venue,category,ticket_availability",
            "page_size": min(max_results, 50),  # EventBrite max is 50 per page
        }

        # Add categories if specified
        if category_ids:
            params["categories"] = ",".join(map(str, category_ids))

        all_events = []
        page = 1

        # Handle pagination
        while len(all_events) < max_results:
            params["page"] = page

            try:
                response = await self._make_request(EVENTBRITE_EVENTS_ENDPOINT, params)
            except EventBriteAPIError as e:
                logger.error(f"Failed to fetch events: {e}")
                break

            events = response.get("events", [])
            if not events:
                break

            # Parse and add events
            for event_data in events:
                parsed_event = self.parse_event(event_data, city)
                if parsed_event:
                    all_events.append(parsed_event)

            # Check if there are more pages
            pagination = response.get("pagination", {})
            if not pagination.get("has_more_items", False):
                break

            page += 1

            # Stop if we've reached max results
            if len(all_events) >= max_results:
                break

        logger.info(f"Found {len(all_events)} events in {city}")
        return all_events[:max_results]

    def categorize_event(self, event: Dict) -> str:
        """
        Categorize event based on title, description, and EventBrite category.

        Uses keyword matching to determine if event is:
        - family: Kid-friendly, educational activities
        - parent_escape: Adult-only activities, nightlife
        - cultural: Museums, art, theatre
        - sports: Sports events, fitness activities

        Args:
            event: Raw EventBrite event dictionary

        Returns:
            Category string: "family", "parent_escape", "cultural", or "sports"

        Example:
            >>> category = client.categorize_event(event_data)
            >>> assert category in ["family", "parent_escape", "cultural", "sports"]
        """
        # Get text to analyze
        title = event.get("name", {}).get("text", "").lower()
        description_obj = event.get("description", {})
        description = ""

        if isinstance(description_obj, dict):
            description = description_obj.get("text", "").lower()
        elif isinstance(description_obj, str):
            description = description_obj.lower()

        # Clean HTML tags from description
        description = re.sub(r"<[^>]+>", " ", description)

        combined_text = title + " " + description

        # Family event indicators
        family_keywords = [
            "kids",
            "children",
            "family",
            "toddler",
            "baby",
            "child",
            "families",
            "kid-friendly",
            "all ages",
            "educational",
            "learning",
            "workshop for children",
        ]
        if any(keyword in combined_text for keyword in family_keywords):
            return "family"

        # Parent escape indicators
        parent_escape_keywords = [
            "wine tasting",
            "cocktail",
            "adults only",
            "nightlife",
            "bar",
            "club",
            "18+",
            "21+",
            "wine pairing",
            "beer tasting",
            "mixology",
            "speakeasy",
        ]
        if any(keyword in combined_text for keyword in parent_escape_keywords):
            return "parent_escape"

        # Sports indicators
        sports_keywords = [
            "sport",
            "match",
            "game",
            "race",
            "tournament",
            "competition",
            "fitness",
            "marathon",
            "cycling",
            "football",
            "basketball",
            "tennis",
        ]
        if any(keyword in combined_text for keyword in sports_keywords):
            return "sports"

        # Cultural indicators (default fallback)
        cultural_keywords = [
            "museum",
            "art",
            "exhibition",
            "theatre",
            "theater",
            "gallery",
            "concert",
            "opera",
            "ballet",
            "symphony",
            "cultural",
            "heritage",
            "historic",
        ]
        if any(keyword in combined_text for keyword in cultural_keywords):
            return "cultural"

        # Default to cultural if no specific match
        return "cultural"

    def _extract_price_range(self, event: Dict) -> str:
        """
        Extract price range from EventBrite event data.

        Categorizes based on lowest ticket price:
        - 'free': All tickets are free
        - '<€20': Cheapest ticket under €20
        - '€20-50': Cheapest ticket €20-50
        - '€50+': Cheapest ticket over €50

        Args:
            event: Raw EventBrite event dictionary

        Returns:
            Price range string
        """
        # Check if event is free
        is_free = event.get("is_free", False)
        if is_free:
            return "free"

        # Try to get ticket information
        ticket_availability = event.get("ticket_availability")
        if not ticket_availability:
            return "free"

        min_price = ticket_availability.get("minimum_ticket_price")

        if not min_price:
            # No price info available
            return "free"

        # Extract price and currency
        try:
            currency = min_price.get("currency", "EUR")
            major_value = int(min_price.get("major_value", 0))

            # Convert to EUR if needed (simplified - assumes 1:1 for demo)
            # In production, you'd use a currency conversion API
            if currency != "EUR":
                logger.debug(f"Non-EUR currency detected: {currency}, treating as EUR")

            # Categorize price
            if major_value == 0:
                return "free"
            elif major_value < 20:
                return "<€20"
            elif major_value <= 50:
                return "€20-50"
            else:
                return "€50+"

        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse price: {e}")
            return "free"

    def parse_event(self, event_data: Dict, city: str) -> Optional[Dict]:
        """
        Convert EventBrite event to standardized format.

        Args:
            event_data: Raw EventBrite event dictionary
            city: City name for the event

        Returns:
            Standardized event dictionary or None if parsing fails

        Format:
            {
                'destination_city': str,
                'title': str,
                'event_date': str (ISO date),
                'end_date': str (ISO date) or None,
                'category': str,
                'description': str,
                'price_range': str,
                'source': 'eventbrite',
                'url': str,
                'ai_relevance_score': None,
                'scraped_at': str (ISO datetime),
            }
        """
        try:
            # Extract dates
            start_datetime = event_data.get("start", {}).get("utc")
            end_datetime = event_data.get("end", {}).get("utc")

            if not start_datetime:
                logger.warning(f"Event missing start date: {event_data.get('id')}")
                return None

            # Parse dates
            start_date = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
            end_date = None
            if end_datetime:
                end_date = datetime.fromisoformat(end_datetime.replace("Z", "+00:00"))

            # Extract description
            description_obj = event_data.get("description", {})
            if isinstance(description_obj, dict):
                description = description_obj.get("text", "")
            else:
                description = str(description_obj) if description_obj else ""

            # Clean HTML from description
            description = re.sub(r"<[^>]+>", "", description)
            # Limit description length
            if len(description) > 1000:
                description = description[:997] + "..."

            # Build standardized event
            parsed_event = {
                "destination_city": city,
                "title": event_data.get("name", {}).get("text", "Untitled Event"),
                "event_date": start_date.date().isoformat(),
                "end_date": (
                    end_date.date().isoformat()
                    if end_date and end_date.date() > start_date.date()
                    else None
                ),
                "category": self.categorize_event(event_data),
                "description": description or None,
                "price_range": self._extract_price_range(event_data),
                "source": "eventbrite",
                "url": event_data.get("url", ""),
                "ai_relevance_score": None,  # To be filled by AI later
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }

            return parsed_event

        except Exception as e:
            logger.error(f"Failed to parse event: {e}", exc_info=True)
            return None

    async def save_to_database(
        self, events: List[Dict], db: Optional[AsyncSession] = None
    ) -> int:
        """
        Save events to database.

        Avoids duplicates by checking for existing events with same
        title, city, and date.

        Args:
            events: List of standardized event dictionaries
            db: Optional database session. If not provided, creates new session.

        Returns:
            Number of events saved

        Example:
            >>> async with EventBriteClient() as client:
            >>>     events = await client.search_events("Prague", start, end)
            >>>     saved_count = await client.save_to_database(events)
            >>>     print(f"Saved {saved_count} events")
        """
        if not events:
            logger.info("No events to save")
            return 0

        saved_count = 0

        async def _save_events(session: AsyncSession):
            nonlocal saved_count

            for event_data in events:
                try:
                    # Check for duplicate
                    stmt = select(Event).where(
                        Event.destination_city == event_data["destination_city"],
                        Event.title == event_data["title"],
                        Event.event_date == date.fromisoformat(event_data["event_date"]),
                        Event.source == "eventbrite",
                    )
                    result = await session.execute(stmt)
                    existing_event = result.scalar_one_or_none()

                    if existing_event:
                        logger.debug(
                            f"Event already exists: {event_data['title']} on {event_data['event_date']}"
                        )
                        continue

                    # Create new event
                    event = Event(
                        destination_city=event_data["destination_city"],
                        title=event_data["title"],
                        event_date=date.fromisoformat(event_data["event_date"]),
                        end_date=(
                            date.fromisoformat(event_data["end_date"])
                            if event_data.get("end_date")
                            else None
                        ),
                        category=event_data["category"],
                        description=event_data.get("description"),
                        price_range=event_data.get("price_range"),
                        source=event_data["source"],
                        url=event_data.get("url"),
                        ai_relevance_score=event_data.get("ai_relevance_score"),
                        scraped_at=datetime.now(timezone.utc),
                    )

                    session.add(event)
                    saved_count += 1

                except Exception as e:
                    logger.error(f"Failed to save event {event_data.get('title')}: {e}")
                    continue

            await session.commit()

        # Use provided session or create new one
        if db:
            await _save_events(db)
        else:
            async with get_async_session_context() as session:
                await _save_events(session)

        logger.info(f"Saved {saved_count} new events to database")
        return saved_count

    def get_call_count(self) -> int:
        """Get number of API calls made by this client instance."""
        return self._call_count

    @staticmethod
    def get_global_call_count() -> int:
        """Get total number of API calls made today across all instances."""
        return _api_call_count
