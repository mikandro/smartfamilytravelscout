"""
EventMatcher - Associates events with trip packages.

This module provides functionality to match events from EventBrite and tourism boards
with trip packages based on destination, dates, and package type (family vs parent_escape).
"""

from datetime import date
from typing import List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.trip_package import TripPackage


class EventMatcher:
    """
    Matches events to trip packages based on destination, dates, and package type.

    Features:
    - Find events during trip dates at destination
    - Filter by age appropriateness for family trips
    - Categorize events by package type (family vs parent_escape)
    - Rank events by relevance score
    - Update packages with matching event IDs
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize EventMatcher with database session.

        Args:
            db_session: Async SQLAlchemy database session
        """
        self.db = db_session

    async def match_events_to_packages(
        self,
        packages: List[TripPackage],
    ) -> List[TripPackage]:
        """
        Add matching events to each package.

        For each package:
        1. Find events in destination during trip dates
        2. Filter by package type (family/parent_escape)
        3. Apply age appropriateness filters if needed
        4. Rank by relevance
        5. Store event IDs in package

        Args:
            packages: List of TripPackage objects to enrich with events

        Returns:
            List of TripPackage objects with events_json populated
        """
        for package in packages:
            # Find events in destination during trip dates
            events = await self.find_events_for_trip(
                package.destination_city,
                package.departure_date,
                package.return_date,
            )

            # Filter by package type
            if package.package_type == "family":
                # Apply age appropriateness filter for families with young kids
                events = self.filter_by_age_appropriateness(events)
                # Keep only family and cultural events
                events = self.categorize_for_package_type(events, "family")
            else:  # parent_escape
                # Keep only parent escape and cultural events
                events = self.categorize_for_package_type(events, "parent_escape")

            # Rank events by relevance and keep top 10
            events = self.rank_events_by_relevance(events, package)

            # Store event IDs in package
            if events:
                package.events_json = [event.id for event in events]
            else:
                package.events_json = []

        return packages

    async def find_events_for_trip(
        self,
        destination: str,
        start_date: date,
        end_date: date,
    ) -> List[Event]:
        """
        Find events during trip dates at destination.

        Matches events that:
        - Are in the same city as the destination
        - Occur during the trip dates (event_date between start and end)
        - OR are multi-day events that overlap with the trip

        Args:
            destination: City name (e.g., 'Lisbon', 'Barcelona')
            start_date: Trip start date
            end_date: Trip end date (inclusive)

        Returns:
            List of Event objects matching the criteria
        """
        # Build query for events in destination during trip dates
        stmt = select(Event).where(
            and_(
                Event.destination_city == destination,
                or_(
                    # Single-day events during trip
                    and_(
                        Event.event_date >= start_date,
                        Event.event_date <= end_date,
                        Event.end_date.is_(None),
                    ),
                    # Multi-day events that overlap with trip
                    and_(
                        Event.event_date <= end_date,
                        Event.end_date >= start_date,
                    ),
                ),
            )
        )

        result = await self.db.execute(stmt)
        events = list(result.scalars().all())

        return events

    def filter_by_age_appropriateness(
        self,
        events: List[Event],
        kids_ages: Optional[List[int]] = None,
    ) -> List[Event]:
        """
        Filter events suitable for young children.

        Excludes adult-only events (18+, nightclub, etc.)
        Prefers family-friendly events for young kids (3-6 years)

        Args:
            events: List of events to filter
            kids_ages: Ages of children (default: [3, 6])

        Returns:
            List of age-appropriate events
        """
        if kids_ages is None:
            kids_ages = [3, 6]

        appropriate = []

        # Keywords indicating adult-only content
        adult_keywords = [
            "18+",
            "21+",
            "adults only",
            "nightclub",
            "night club",
            "bar crawl",
            "pub crawl",
            "wine tasting",
            "beer tasting",
            "cocktail",
        ]

        # Keywords indicating family-friendly content
        family_keywords = [
            "kids",
            "children",
            "family",
            "playground",
            "child",
            "toddler",
            "baby",
            "puppet",
            "animation",
            "storytelling",
            "story time",
        ]

        for event in events:
            title_lower = event.title.lower()
            desc_lower = event.description.lower() if event.description else ""
            combined_text = title_lower + " " + desc_lower

            # Exclude adult-only events
            if any(word in combined_text for word in adult_keywords):
                continue

            # For young kids (3-6), prefer specific types
            is_family_friendly = any(
                word in combined_text for word in family_keywords
            )
            is_appropriate_category = event.category in ["family", "cultural"]

            if is_family_friendly or is_appropriate_category:
                appropriate.append(event)

        return appropriate

    def categorize_for_package_type(
        self,
        events: List[Event],
        package_type: str,
    ) -> List[Event]:
        """
        Keep only relevant events for package type.

        Family packages: family + cultural events
        Parent escape packages: parent_escape + cultural events

        Args:
            events: List of events to categorize
            package_type: 'family' or 'parent_escape'

        Returns:
            List of events matching the package type
        """
        if package_type == "family":
            # Keep family and cultural events
            return [e for e in events if e.category in ["family", "cultural"]]
        elif package_type == "parent_escape":
            # Keep parent escape and cultural events
            return [e for e in events if e.category in ["parent_escape", "cultural"]]
        else:
            # Unknown package type, return all events
            return events

    def rank_events_by_relevance(
        self,
        events: List[Event],
        package: TripPackage,
    ) -> List[Event]:
        """
        Sort events by relevance to trip and return top 10.

        Ranking criteria:
        1. Events with high AI relevance scores first
        2. Free events ranked higher (good for budget-conscious families)
        3. Multi-day events ranked lower (less flexible)

        Args:
            events: List of events to rank
            package: The trip package for context

        Returns:
            List of top 10 most relevant events, sorted by score
        """
        if not events:
            return []

        def score_event(event: Event) -> float:
            """Calculate relevance score for an event."""
            score = 0.0

            # AI relevance score (0-10) - primary ranking factor
            if event.ai_relevance_score is not None:
                score += float(event.ai_relevance_score) * 10  # Weight: 0-100
            else:
                score += 50  # Default middle score if no AI score

            # Free events get bonus points
            if event.price_range and "free" in event.price_range.lower():
                score += 20

            # Weekend events get bonus if trip includes weekend
            if hasattr(package, "departure_date") and hasattr(package, "return_date"):
                # Check if event is on weekend (Saturday=5, Sunday=6)
                event_weekday = event.event_date.weekday()
                if event_weekday in [5, 6]:
                    # Check if trip includes this weekend
                    trip_weekdays = [
                        (package.departure_date.toordinal() + i) % 7
                        for i in range((package.return_date - package.departure_date).days + 1)
                    ]
                    if event_weekday in trip_weekdays:
                        score += 10

            # Multi-day events get slight penalty (less flexible scheduling)
            if event.end_date and event.end_date > event.event_date:
                score -= 5

            return score

        # Sort events by score (highest first) and return top 10
        scored_events = sorted(events, key=score_event, reverse=True)
        return scored_events[:10]
