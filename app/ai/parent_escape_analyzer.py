"""
Parent Escape Analyzer for finding romantic getaway opportunities.

This module identifies 2-3 night romantic trips for parents, focusing on:
- Train-accessible destinations from Munich (< 6 hours)
- Special events (wine tastings, concerts, cultural events)
- Spa hotels and romantic venues
- Timing uniqueness (special events happening during visit)

Example:
    >>> analyzer = ParentEscapeAnalyzer(claude_client)
    >>> async with get_async_session_context() as db:
    ...     opportunities = await analyzer.find_escape_opportunities(
    ...         db, date_range=(date(2025, 3, 1), date(2025, 6, 1))
    ...     )
    ...     print(f"Found {len(opportunities)} romantic getaway opportunities")
"""

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.claude_client import ClaudeClient
from app.ai.prompt_loader import load_prompt
from app.models.accommodation import Accommodation
from app.models.event import Event
from app.models.flight import Flight
from app.models.trip_package import TripPackage

logger = logging.getLogger(__name__)
console = Console()


# Train destinations from Munich with approximate travel times
TRAIN_DESTINATIONS = {
    # Austria - Close and romantic
    "Vienna": {"travel_time_hours": 4.0, "country": "Austria", "romantic_features": ["wine", "culture", "spa"]},
    "Salzburg": {"travel_time_hours": 1.5, "country": "Austria", "romantic_features": ["culture", "spa", "mountains"]},
    "Innsbruck": {"travel_time_hours": 2.0, "country": "Austria", "romantic_features": ["spa", "mountains"]},

    # Italy - Wine & Romance
    "Venice": {"travel_time_hours": 6.5, "country": "Italy", "romantic_features": ["wine", "culture"]},  # Slightly over, but iconic
    "Verona": {"travel_time_hours": 5.5, "country": "Italy", "romantic_features": ["wine", "culture"]},
    "Bolzano": {"travel_time_hours": 4.5, "country": "Italy", "romantic_features": ["wine", "spa", "mountains"]},
    "Merano": {"travel_time_hours": 5.0, "country": "Italy", "romantic_features": ["spa", "wine"]},

    # Switzerland - Spa & Mountains
    "Zurich": {"travel_time_hours": 4.0, "country": "Switzerland", "romantic_features": ["culture", "spa"]},
    "Lucerne": {"travel_time_hours": 4.5, "country": "Switzerland", "romantic_features": ["mountains", "spa"]},
    "St. Moritz": {"travel_time_hours": 5.5, "country": "Switzerland", "romantic_features": ["spa", "mountains"]},

    # Germany - Wine Regions & Culture
    "Stuttgart": {"travel_time_hours": 2.5, "country": "Germany", "romantic_features": ["wine"]},
    "Heidelberg": {"travel_time_hours": 3.5, "country": "Germany", "romantic_features": ["culture", "wine"]},
    "Baden-Baden": {"travel_time_hours": 4.0, "country": "Germany", "romantic_features": ["spa"]},
    "Freiburg": {"travel_time_hours": 4.5, "country": "Germany", "romantic_features": ["wine"]},

    # Czech Republic - Culture & Spa
    "Prague": {"travel_time_hours": 5.5, "country": "Czech Republic", "romantic_features": ["culture", "spa"]},
}

# Short flight destinations (< 1.5 hours) as alternatives
SHORT_FLIGHT_DESTINATIONS = {
    "Milan": {"flight_time_hours": 1.0, "country": "Italy", "romantic_features": ["culture", "wine", "dining"]},
    "Florence": {"flight_time_hours": 1.2, "country": "Italy", "romantic_features": ["culture", "wine", "dining"]},
    "Lyon": {"flight_time_hours": 1.3, "country": "France", "romantic_features": ["wine", "dining"]},
}


class ParentEscapeAnalyzer:
    """
    Analyzer for finding romantic getaway opportunities for parents.

    Identifies destinations accessible from Munich via train (< 6h) or short flight (< 1.5h),
    scores them based on romantic appeal, events, and timing uniqueness.

    Features:
        - Train destination prioritization
        - Event timing analysis (wine festivals, concerts, etc.)
        - Spa hotel identification
        - AI-powered romantic appeal scoring
        - Kid-care solution suggestions
    """

    # Cost estimates for couples (2 people)
    DAILY_FOOD_COST = 80.0  # EUR per day for romantic dining
    DAILY_ACTIVITIES_COST = 60.0  # EUR per day for experiences

    def __init__(self, claude_client: ClaudeClient):
        """
        Initialize the Parent Escape Analyzer.

        Args:
            claude_client: ClaudeClient instance for AI-powered analysis
        """
        self.claude = claude_client
        logger.info("Initialized ParentEscapeAnalyzer")

    async def find_escape_opportunities(
        self,
        db: AsyncSession,
        date_range: Optional[Tuple[date, date]] = None,
        max_budget: float = 1200.0,
        min_nights: int = 2,
        max_nights: int = 3,
        max_train_hours: float = 6.0,
    ) -> List[TripPackage]:
        """
        Find romantic getaway opportunities for parents.

        Searches for train-accessible destinations with romantic features,
        matches with events and accommodations, and scores based on timing uniqueness.

        Args:
            db: Async database session
            date_range: Optional tuple of (start_date, end_date) to search within
            max_budget: Maximum total trip budget in EUR (default: 1200.0 for 2 people)
            min_nights: Minimum trip duration (default: 2)
            max_nights: Maximum trip duration (default: 3)
            max_train_hours: Maximum train travel time in hours (default: 6.0)

        Returns:
            List of TripPackage objects with type='parent_escape'

        Example:
            >>> opportunities = await analyzer.find_escape_opportunities(
            ...     db,
            ...     date_range=(date(2025, 4, 1), date(2025, 6, 30)),
            ...     max_budget=1000.0
            ... )
        """
        if date_range is None:
            # Default to next 3 months
            start_date = date.today()
            end_date = start_date + timedelta(days=90)
            date_range = (start_date, end_date)

        logger.info(
            f"Finding parent escape opportunities: {date_range[0]} to {date_range[1]}, "
            f"budget ≤ €{max_budget}, {min_nights}-{max_nights} nights"
        )

        packages = []

        # Filter train destinations by max travel time
        eligible_cities = [
            city for city, info in TRAIN_DESTINATIONS.items()
            if info["travel_time_hours"] <= max_train_hours
        ]

        console.print(
            f"\n[bold cyan]Searching for romantic getaways in {len(eligible_cities)} "
            f"train-accessible cities...[/bold cyan]\n"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "[cyan]Analyzing romantic destinations...",
                total=len(eligible_cities)
            )

            for city in eligible_cities:
                city_info = TRAIN_DESTINATIONS[city]

                # Find accommodations in this city (prefer spa, boutique, romantic)
                accommodations = await self._find_romantic_accommodations(db, city)

                if not accommodations:
                    logger.debug(f"No accommodations found for {city}")
                    progress.update(task, advance=1)
                    continue

                # Find relevant events during date range
                events = await self._find_romantic_events(db, city, date_range)

                # Create trip packages for different date combinations
                city_packages = await self._create_city_packages(
                    db=db,
                    city=city,
                    city_info=city_info,
                    accommodations=accommodations,
                    events=events,
                    date_range=date_range,
                    min_nights=min_nights,
                    max_nights=max_nights,
                    max_budget=max_budget,
                )

                packages.extend(city_packages)
                progress.update(task, advance=1)

        console.print(
            f"[bold green]✓ Found {len(packages)} parent escape opportunities[/bold green]\n"
        )

        return packages

    async def score_escape(
        self,
        destination: str,
        destination_info: Dict,
        accommodation: Accommodation,
        events: List[Event],
        duration_nights: int,
        total_cost: float,
    ) -> Dict:
        """
        Score a parent escape opportunity using Claude AI.

        Analyzes romantic appeal, accessibility, event timing, and overall suitability
        for a 2-3 night romantic getaway.

        Args:
            destination: City name (e.g., "Vienna")
            destination_info: Dict with travel_time_hours, romantic_features, etc.
            accommodation: Accommodation object
            events: List of Event objects happening during visit
            duration_nights: Trip duration in nights
            total_cost: Total trip cost in EUR

        Returns:
            Dictionary with AI analysis including:
            - escape_score: Overall score 0-100
            - romantic_appeal: Romance rating 0-10
            - event_timing_score: Timing uniqueness 0-10
            - recommended_experiences: List of activities
            - childcare_suggestions: Kid-care solutions
        """
        # Build destination details
        destination_details = self._build_destination_summary(
            destination, destination_info, accommodation, total_cost
        )

        # Build events list
        events_summary = self._build_events_summary(events)

        # Determine travel method
        if destination in TRAIN_DESTINATIONS:
            travel_method = "Train"
            travel_time = f"{destination_info['travel_time_hours']}h by train"
        else:
            travel_method = "Flight"
            travel_time = f"{destination_info.get('flight_time_hours', 0)}h flight"

        # Load prompt template
        try:
            prompt_template = load_prompt("parent_escape_destination")
        except FileNotFoundError:
            logger.error("Prompt template 'parent_escape_destination' not found")
            # Return a default score structure
            return {
                "escape_score": 50,
                "romantic_appeal": 5,
                "accessibility_score": 5,
                "event_timing_score": 5,
                "weekend_suitability": 5,
                "highlights": ["Romantic destination"],
                "recommended_experiences": [],
                "childcare_suggestions": [
                    "Hire local babysitter service",
                    "Ask grandparents or family to help",
                    "Consider au pair or trusted nanny"
                ],
                "best_time_to_go": "Any weekend works",
                "recommendation": "A charming getaway destination"
            }

        # Call Claude API
        data = {
            "destination_details": destination_details,
            "travel_method": travel_method,
            "travel_time": travel_time,
            "duration_nights": duration_nights,
            "events_list": events_summary,
        }

        try:
            response = await self.claude.analyze(
                prompt=prompt_template,
                data=data,
                response_format="json",
                operation="parent_escape_scoring",
                max_tokens=2048,
            )

            logger.info(
                f"Scored {destination}: {response.get('escape_score', 0)}/100 "
                f"(romantic: {response.get('romantic_appeal', 0)}/10)"
            )

            return response

        except Exception as e:
            logger.error(f"Error scoring escape to {destination}: {e}")
            # Return minimal valid response
            return {
                "escape_score": 0,
                "romantic_appeal": 0,
                "accessibility_score": 0,
                "event_timing_score": 0,
                "weekend_suitability": 0,
                "highlights": [],
                "recommended_experiences": [],
                "childcare_suggestions": [],
                "best_time_to_go": "Unknown",
                "recommendation": "Error during analysis"
            }

    async def _find_romantic_accommodations(
        self, db: AsyncSession, city: str, limit: int = 10
    ) -> List[Accommodation]:
        """
        Find romantic accommodations (spa hotels, boutique hotels) in a city.

        Prefers higher-rated accommodations and filters by type.
        """
        stmt = (
            select(Accommodation)
            .where(Accommodation.destination_city == city)
            .where(Accommodation.rating >= 7.5)  # High-rated only
            .order_by(Accommodation.rating.desc())
            .limit(limit)
        )

        result = await db.execute(stmt)
        accommodations = result.scalars().all()

        logger.debug(f"Found {len(accommodations)} romantic accommodations in {city}")
        return list(accommodations)

    async def _find_romantic_events(
        self, db: AsyncSession, city: str, date_range: Tuple[date, date]
    ) -> List[Event]:
        """
        Find romantic events (wine tastings, concerts, cultural events) in a city.

        Filters by category and date range.
        """
        start_date, end_date = date_range

        stmt = (
            select(Event)
            .where(
                and_(
                    Event.destination_city == city,
                    Event.event_date >= start_date,
                    Event.event_date <= end_date,
                    or_(
                        Event.category == "parent_escape",
                        Event.category == "cultural",
                        Event.category.like("%wine%"),
                        Event.category.like("%concert%"),
                        Event.category.like("%spa%"),
                    )
                )
            )
            .order_by(Event.event_date)
        )

        result = await db.execute(stmt)
        events = result.scalars().all()

        logger.debug(f"Found {len(events)} romantic events in {city}")
        return list(events)

    async def _create_city_packages(
        self,
        db: AsyncSession,
        city: str,
        city_info: Dict,
        accommodations: List[Accommodation],
        events: List[Event],
        date_range: Tuple[date, date],
        min_nights: int,
        max_nights: int,
        max_budget: float,
    ) -> List[TripPackage]:
        """
        Create trip packages for a city with different date combinations.

        Generates packages for event-aligned dates and general weekend getaways.
        """
        packages = []

        # Strategy 1: Create packages around special events
        for event in events[:5]:  # Top 5 events
            for accommodation in accommodations[:3]:  # Top 3 hotels
                # Create 2-3 night packages around event date
                for num_nights in range(min_nights, max_nights + 1):
                    # Option A: Arrive day before event
                    departure_date = event.event_date - timedelta(days=1)
                    return_date = departure_date + timedelta(days=num_nights)

                    if date_range[0] <= departure_date <= date_range[1]:
                        package = await self._build_package(
                            city=city,
                            city_info=city_info,
                            accommodation=accommodation,
                            events=[event],
                            departure_date=departure_date,
                            return_date=return_date,
                            num_nights=num_nights,
                            max_budget=max_budget,
                        )
                        if package:
                            packages.append(package)

        # Strategy 2: Create general weekend packages (Fridays)
        if not events:  # Only if no events found
            current_date = date_range[0]
            while current_date <= date_range[1]:
                # Find next Friday
                days_until_friday = (4 - current_date.weekday()) % 7
                if days_until_friday == 0 and current_date.weekday() != 4:
                    days_until_friday = 7
                friday = current_date + timedelta(days=days_until_friday)

                if friday > date_range[1]:
                    break

                # Create weekend package (Friday to Sunday = 2 nights)
                for accommodation in accommodations[:2]:
                    package = await self._build_package(
                        city=city,
                        city_info=city_info,
                        accommodation=accommodation,
                        events=[],
                        departure_date=friday,
                        return_date=friday + timedelta(days=2),
                        num_nights=2,
                        max_budget=max_budget,
                    )
                    if package:
                        packages.append(package)

                current_date = friday + timedelta(days=7)  # Next week

        return packages

    async def _build_package(
        self,
        city: str,
        city_info: Dict,
        accommodation: Accommodation,
        events: List[Event],
        departure_date: date,
        return_date: date,
        num_nights: int,
        max_budget: float,
    ) -> Optional[TripPackage]:
        """Build a single trip package with cost calculation and AI scoring."""

        # Calculate costs
        # Train cost estimate (round trip for 2 people)
        train_cost_per_hour = 30.0  # Rough estimate
        train_cost = city_info["travel_time_hours"] * train_cost_per_hour * 2  # Round trip

        accommodation_cost = float(accommodation.price_per_night) * num_nights
        food_cost = self.DAILY_FOOD_COST * num_nights
        activities_cost = self.DAILY_ACTIVITIES_COST * num_nights

        total_cost = train_cost + accommodation_cost + food_cost + activities_cost

        # Skip if over budget
        if total_cost > max_budget:
            return None

        # Score the escape
        score_result = await self.score_escape(
            destination=city,
            destination_info=city_info,
            accommodation=accommodation,
            events=events,
            duration_nights=num_nights,
            total_cost=total_cost,
        )

        # Create package
        package = TripPackage(
            package_type="parent_escape",
            flights_json={"travel_method": "train", "details": city_info},
            accommodation_id=accommodation.id,
            events_json=[e.id for e in events] if events else [],
            destination_city=city,
            departure_date=departure_date,
            return_date=return_date,
            num_nights=num_nights,
            total_price=total_cost,
            ai_score=score_result.get("escape_score", 0),
            ai_reasoning=score_result.get("recommendation", ""),
            itinerary_json=score_result,  # Store full analysis
            notified=False,
        )

        return package

    def _build_destination_summary(
        self,
        destination: str,
        destination_info: Dict,
        accommodation: Accommodation,
        total_cost: float,
    ) -> str:
        """Build a text summary of destination for AI analysis."""
        features = ", ".join(destination_info.get("romantic_features", []))

        summary = f"""
Destination: {destination}, {destination_info['country']}
Romantic Features: {features}
Travel Time: {destination_info.get('travel_time_hours', 0)}h by train from Munich

Accommodation: {accommodation.name}
Type: {accommodation.type}
Rating: {accommodation.rating}/10
Price: €{accommodation.price_per_night}/night

Total Trip Cost: €{total_cost:.2f} for 2 people
""".strip()

        return summary

    def _build_events_summary(self, events: List[Event]) -> str:
        """Build a text summary of events for AI analysis."""
        if not events:
            return "No special events during visit (general romantic getaway)"

        event_lines = []
        for event in events:
            event_lines.append(
                f"- {event.title} ({event.category}) on {event.event_date}"
            )

        return "\n".join(event_lines)

    async def print_escape_summary(
        self, packages: List[TripPackage], show_top: int = 10
    ) -> None:
        """
        Print a summary table of parent escape opportunities.

        Args:
            packages: List of TripPackage objects to display
            show_top: Number of top-scored packages to show (default: 10)
        """
        if not packages:
            console.print("[yellow]No parent escape opportunities found[/yellow]")
            return

        # Sort by AI score (highest first)
        sorted_packages = sorted(
            packages,
            key=lambda p: p.ai_score if p.ai_score else 0,
            reverse=True
        )

        table = Table(title=f"🌹 Parent Escape Opportunities (Top {show_top})")

        table.add_column("Destination", style="cyan", no_wrap=True)
        table.add_column("Dates", style="green")
        table.add_column("Nights", style="yellow", justify="right")
        table.add_column("Score", style="magenta", justify="right")
        table.add_column("Cost", style="blue", justify="right")
        table.add_column("Highlights", style="white")

        for package in sorted_packages[:show_top]:
            highlights = ""
            if package.itinerary_json and "highlights" in package.itinerary_json:
                highlights = ", ".join(package.itinerary_json["highlights"][:2])

            table.add_row(
                package.destination_city,
                f"{package.departure_date}",
                str(package.num_nights),
                f"{package.ai_score or 0:.0f}/100",
                f"€{package.total_price:,.0f}",
                highlights[:50],
            )

        console.print(table)

        # Print statistics
        console.print(f"\n[bold]Statistics:[/bold]")
        console.print(f"Total opportunities: {len(packages)}")
        console.print(
            f"Average score: {sum(p.ai_score or 0 for p in packages) / len(packages):.1f}/100"
        )
        console.print(
            f"Average cost: €{sum(p.total_price for p in packages) / len(packages):,.0f}"
        )
        console.print(
            f"Destinations: {len(set(p.destination_city for p in packages))}"
        )
