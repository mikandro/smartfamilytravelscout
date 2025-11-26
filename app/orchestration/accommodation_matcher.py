"""
AccommodationMatcher for pairing flights with accommodations.

This module matches flights with accommodations to create complete trip packages,
calculating total trip costs including flights, accommodation, food, and activities.

Example:
    >>> matcher = AccommodationMatcher()
    >>> async with get_async_session_context() as db:
    ...     packages = await matcher.generate_trip_packages(
    ...         db, max_budget=2000.0, min_nights=3, max_nights=10
    ...     )
    ...     print(f"Generated {len(packages)} trip packages")
"""

import logging
from datetime import date
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.accommodation_scorer import AccommodationScorer
from app.models.accommodation import Accommodation
from app.models.flight import Flight
from app.models.school_holiday import SchoolHoliday
from app.models.trip_package import TripPackage

logger = logging.getLogger(__name__)
console = Console()


class AccommodationMatcher:
    """
    Matches flights with accommodations to generate complete trip packages.

    This class pairs flights (with calculated true costs) with accommodations
    in matching destination cities, calculates total trip costs including
    food and activities, and creates TripPackage database records.

    Features:
        - Smart matching by destination city
        - Trip duration filtering (min/max nights)
        - Budget filtering
        - School holiday filtering
        - Accommodation scoring and ranking
        - Comprehensive cost breakdown
        - Batch database operations

    Cost Components:
        - Flight true cost (includes base price, baggage, parking, fuel, time)
        - Accommodation (price_per_night × num_nights)
        - Food estimate (€100/day for family of 4)
        - Activities budget (€50/day)
    """

    # Cost estimates for family of 4
    DAILY_FOOD_COST = 100.0  # EUR per day
    DAILY_ACTIVITIES_COST = 50.0  # EUR per day

    def __init__(self):
        """Initialize the accommodation matcher with scoring capability."""
        self.scorer = AccommodationScorer()

    async def generate_trip_packages(
        self,
        db: AsyncSession,
        max_budget: float = 2000.0,
        min_nights: int = 3,
        max_nights: int = 10,
        filter_holidays: bool = True,
    ) -> List[TripPackage]:
        """
        Generate all valid trip package combinations.

        Queries flights with calculated true costs, matches them with accommodations
        in the same destination city, filters by budget and trip duration, and
        creates TripPackage objects.

        Args:
            db: Async database session
            max_budget: Maximum total trip budget in EUR (default: 2000.0)
            min_nights: Minimum trip duration in nights (default: 3)
            max_nights: Maximum trip duration in nights (default: 10)
            filter_holidays: Only include trips during school holidays (default: True)

        Returns:
            List of TripPackage objects ready for database insertion

        Example:
            >>> async with get_async_session_context() as db:
            ...     packages = await matcher.generate_trip_packages(
            ...         db, max_budget=2500.0, min_nights=5, max_nights=7
            ...     )
            ...     print(f"Generated {len(packages)} packages")
        """
        logger.info(
            f"Generating trip packages: budget ≤ €{max_budget}, "
            f"nights {min_nights}-{max_nights}, filter_holidays={filter_holidays}"
        )

        packages = []

        # Get all unique destination cities with flights
        stmt = (
            select(Flight.destination_airport_id)
            .where(Flight.true_cost.isnot(None))
            .distinct()
        )
        result = await db.execute(stmt)
        destination_airport_ids = [row[0] for row in result.all()]

        console.print(
            f"\n[bold cyan]Finding trip packages across "
            f"{len(destination_airport_ids)} destinations...[/bold cyan]\n"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task(
                "[cyan]Matching flights with accommodations...",
                total=len(destination_airport_ids),
            )

            for airport_id in destination_airport_ids:
                # Get flights to this destination with relationships loaded
                flight_stmt = (
                    select(Flight)
                    .where(
                        Flight.destination_airport_id == airport_id,
                        Flight.true_cost.isnot(None),
                        Flight.return_date.isnot(None),  # Only round-trip flights
                    )
                    .options(
                        selectinload(Flight.origin_airport),
                        selectinload(Flight.destination_airport),
                    )
                )
                flight_result = await db.execute(flight_stmt)
                flights = flight_result.scalars().all()

                if not flights:
                    progress.update(task_id, advance=1)
                    continue

                # Get destination city from first flight
                destination_city = flights[0].destination_airport.city

                # Update progress with current city
                progress.update(
                    task_id,
                    description=f"[cyan]Processing {destination_city}... ({len(flights)} flights)",
                )

                # Get accommodations in this city
                accom_stmt = select(Accommodation).where(
                    Accommodation.destination_city == destination_city
                )
                accom_result = await db.execute(accom_stmt)
                accommodations = list(accom_result.scalars().all())

                if not accommodations:
                    logger.debug(f"No accommodations found for {destination_city}")
                    console.print(
                        f"[dim yellow]⚠ {destination_city}: No accommodations available[/dim yellow]"
                    )
                    progress.update(task_id, advance=1)
                    continue

                # Score and rank accommodations
                accommodations = await self._score_and_rank_accommodations(
                    db, accommodations
                )

                # Log start of matching for this city
                logger.info(
                    f"Matching {len(flights)} flights with {len(accommodations)} "
                    f"accommodations in {destination_city}"
                )

                # Create all valid combinations
                packages_for_city = 0
                for flight in flights:
                    num_nights = (flight.return_date - flight.departure_date).days

                    # Skip if outside night range
                    if not (min_nights <= num_nights <= max_nights):
                        continue

                    for accommodation in accommodations:
                        cost = self.calculate_trip_cost(flight, accommodation, num_nights)

                        # Skip if over budget
                        if cost["total"] > max_budget:
                            continue

                        # Create package
                        package = self.create_trip_package(flight, accommodation, cost)
                        packages.append(package)
                        packages_for_city += 1

                # Log completion for this city
                logger.info(f"✓ {destination_city}: Created {packages_for_city} packages")
                console.print(
                    f"[dim green]✓ {destination_city}: {packages_for_city} packages created[/dim green]"
                )

                progress.update(task_id, advance=1)

        console.print(
            f"[bold green]✓ Generated {len(packages)} trip packages[/bold green]\n"
        )

        # Filter by school holidays if requested
        if filter_holidays:
            packages = await self.filter_by_school_holidays(db, packages)
            console.print(
                f"[bold yellow]Filtered to {len(packages)} packages "
                f"during school holidays[/bold yellow]\n"
            )

        return packages

    def match_flights_to_accommodations(
        self, flights: List[Flight], accommodations: List[Accommodation]
    ) -> List[Tuple[Flight, Accommodation]]:
        """
        Find all flight + accommodation pairs for a destination.

        This is a helper method that creates cartesian product of flights
        and accommodations for the same city.

        Args:
            flights: List of Flight objects for a destination
            accommodations: List of Accommodation objects for the same city

        Returns:
            List of (flight, accommodation) tuples

        Example:
            >>> pairs = matcher.match_flights_to_accommodations(flights, accommodations)
            >>> print(f"Found {len(pairs)} combinations")
        """
        if not flights or not accommodations:
            return []

        pairs = []
        for flight in flights:
            for accommodation in accommodations:
                pairs.append((flight, accommodation))

        return pairs

    def calculate_trip_cost(
        self, flight: Flight, accommodation: Accommodation, num_nights: int
    ) -> Dict:
        """
        Calculate total trip cost with detailed breakdown.

        Combines flight true cost (which already includes base price, baggage,
        parking, fuel, and time value) with accommodation, food, and activities.

        Args:
            flight: Flight object with true_cost calculated
            accommodation: Accommodation object
            num_nights: Number of nights for the trip

        Returns:
            Dictionary with cost breakdown:
            {
                'flight_cost': 559.27,          # True cost for 4 people
                'accommodation_cost': 560.00,   # 7 nights × €80/night
                'food_cost': 700.00,            # 7 days × €100/day
                'activities_cost': 350.00,      # 7 days × €50/day
                'total': 2169.27,               # Sum of all costs
                'per_person': 542.32            # Total ÷ 4 people
            }

        Example:
            >>> cost = matcher.calculate_trip_cost(flight, accommodation, 7)
            >>> print(f"Total: €{cost['total']:.2f}, Per person: €{cost['per_person']:.2f}")
        """
        # Flight true cost already includes all flight-related expenses
        flight_cost = float(flight.true_cost) if flight.true_cost else 0.0

        # Accommodation cost
        accommodation_cost = float(accommodation.price_per_night) * num_nights

        # Food estimate (€100/day for family of 4)
        food_cost = self.DAILY_FOOD_COST * num_nights

        # Activities budget (€50/day)
        activities_cost = self.DAILY_ACTIVITIES_COST * num_nights

        # Calculate total
        total = flight_cost + accommodation_cost + food_cost + activities_cost

        return {
            "flight_cost": round(flight_cost, 2),
            "accommodation_cost": round(accommodation_cost, 2),
            "food_cost": round(food_cost, 2),
            "activities_cost": round(activities_cost, 2),
            "total": round(total, 2),
            "per_person": round(total / 4.0, 2),  # Family of 4
        }

    def create_trip_package(
        self, flight: Flight, accommodation: Accommodation, cost_breakdown: Dict
    ) -> TripPackage:
        """
        Create TripPackage database object from flight and accommodation.

        Args:
            flight: Flight object
            accommodation: Accommodation object
            cost_breakdown: Cost breakdown dictionary from calculate_trip_cost()

        Returns:
            TripPackage object ready for database insertion

        Example:
            >>> package = matcher.create_trip_package(flight, accommodation, cost)
            >>> db.add(package)
            >>> await db.commit()
        """
        num_nights = (flight.return_date - flight.departure_date).days

        package = TripPackage(
            package_type="family",
            flights_json=[flight.id],  # Store flight IDs as array
            accommodation_id=accommodation.id,
            events_json=[],  # Will be filled by EventMatcher later
            total_price=cost_breakdown["total"],
            destination_city=flight.destination_airport.city,
            departure_date=flight.departure_date,
            return_date=flight.return_date,
            num_nights=num_nights,
            notified=False,
        )

        return package

    async def filter_by_school_holidays(
        self, db: AsyncSession, packages: List[TripPackage]
    ) -> List[TripPackage]:
        """
        Keep only packages that depart during school holidays.

        Queries school holidays from database and filters packages to only
        include trips where the departure date falls within a holiday period.

        Args:
            db: Async database session
            packages: List of TripPackage objects to filter

        Returns:
            Filtered list of TripPackage objects

        Example:
            >>> filtered = await matcher.filter_by_school_holidays(db, packages)
            >>> print(f"Kept {len(filtered)}/{len(packages)} packages")
        """
        if not packages:
            return []

        # Load school holidays
        stmt = select(SchoolHoliday)
        result = await db.execute(stmt)
        holidays = result.scalars().all()

        if not holidays:
            logger.warning("No school holidays found in database, returning all packages")
            return packages

        logger.info(f"Filtering {len(packages)} packages against {len(holidays)} holidays")

        filtered = []
        for package in packages:
            if self._is_during_holiday(package.departure_date, holidays):
                filtered.append(package)

        logger.info(f"Kept {len(filtered)} packages during school holidays")
        return filtered

    def _is_during_holiday(
        self, departure_date: date, holidays: List[SchoolHoliday]
    ) -> bool:
        """
        Check if a departure date falls within any school holiday period.

        Args:
            departure_date: Date to check
            holidays: List of SchoolHoliday objects

        Returns:
            True if date is during a holiday, False otherwise
        """
        for holiday in holidays:
            if holiday.start_date <= departure_date <= holiday.end_date:
                return True
        return False

    async def save_packages(
        self, db: AsyncSession, packages: List[TripPackage]
    ) -> Dict[str, int]:
        """
        Batch save trip packages to database.

        Inserts packages in batches for efficiency. Skips duplicates based on
        flight + accommodation combination.

        Args:
            db: Async database session
            packages: List of TripPackage objects to save

        Returns:
            Dictionary with statistics:
            {
                'total': 150,      # Total packages processed
                'inserted': 145,   # New packages inserted
                'skipped': 5       # Duplicates skipped
            }

        Example:
            >>> stats = await matcher.save_packages(db, packages)
            >>> print(f"Inserted {stats['inserted']} packages")
        """
        stats = {"total": len(packages), "inserted": 0, "skipped": 0}

        if not packages:
            logger.info("No packages to save")
            return stats

        logger.info(f"Saving {len(packages)} trip packages to database...")

        batch_size = 50
        for i in range(0, len(packages), batch_size):
            batch = packages[i : i + batch_size]

            for package in batch:
                try:
                    # Check for existing package with same flight + accommodation
                    existing_stmt = select(TripPackage).where(
                        TripPackage.departure_date == package.departure_date,
                        TripPackage.return_date == package.return_date,
                        TripPackage.accommodation_id == package.accommodation_id,
                    )
                    existing_result = await db.execute(existing_stmt)
                    existing = existing_result.scalar_one_or_none()

                    if existing:
                        # Check if this flight is already in the package
                        existing_flight_ids = existing.flights_json
                        if package.flights_json[0] in existing_flight_ids:
                            stats["skipped"] += 1
                            continue

                    # Insert new package
                    db.add(package)
                    stats["inserted"] += 1

                except Exception as e:
                    logger.error(f"Error saving package: {e}", exc_info=True)
                    stats["skipped"] += 1
                    continue

            # Commit batch
            await db.commit()

        logger.info(
            f"Database save complete: {stats['inserted']} inserted, "
            f"{stats['skipped']} skipped"
        )

        return stats

    async def _score_and_rank_accommodations(
        self, db: AsyncSession, accommodations: List[Accommodation]
    ) -> List[Accommodation]:
        """
        Score and rank accommodations using the accommodation scorer.

        Updates accommodation objects with scores and details, saves to database,
        and returns sorted list (best scored first).

        Args:
            db: Async database session
            accommodations: List of Accommodation objects to score

        Returns:
            Sorted list of Accommodation objects (highest score first)

        Example:
            >>> ranked = await matcher._score_and_rank_accommodations(db, accommodations)
            >>> print(f"Best: {ranked[0].name} (score: {ranked[0].accommodation_score})")
        """
        if not accommodations:
            return []

        # Score all accommodations
        scored_results = self.scorer.compare_accommodations(accommodations)

        # Update database with scores
        for result in scored_results:
            accommodation = result["accommodation"]
            accommodation.accommodation_score = result["overall_score"]
            accommodation.accommodation_score_details = {
                "price_per_person_per_night": result["price_per_person_per_night"],
                "estimated_capacity": result["estimated_capacity"],
                "price_quality_score": result["price_quality_score"],
                "family_suitability_score": result["family_suitability_score"],
                "quality_score": result["quality_score"],
                "value_category": result["value_category"],
                "family_features": result["family_features"],
                "comparison_notes": result["comparison_notes"],
            }
            db.add(accommodation)

        # Commit scores to database
        await db.commit()

        # Return sorted list (best first)
        sorted_accommodations = [r["accommodation"] for r in scored_results]

        logger.info(
            f"Scored {len(sorted_accommodations)} accommodations, "
            f"best score: {sorted_accommodations[0].accommodation_score:.1f}"
            if sorted_accommodations
            else "No accommodations to score"
        )

        return sorted_accommodations

    async def print_package_summary(
        self, db: AsyncSession, packages: List[TripPackage]
    ) -> None:
        """
        Print a summary table of trip packages.

        Args:
            db: Async database session (needed to load relationships)
            packages: List of TripPackage objects to summarize

        Example:
            >>> await matcher.print_package_summary(db, packages)
        """
        if not packages:
            console.print("[yellow]No packages to display[/yellow]")
            return

        table = Table(title=f"Trip Packages ({len(packages)} total)")

        table.add_column("Destination", style="cyan", no_wrap=True)
        table.add_column("Dates", style="green")
        table.add_column("Nights", style="yellow", justify="right")
        table.add_column("Total Price", style="magenta", justify="right")
        table.add_column("Per Person", style="blue", justify="right")

        # Show up to 20 packages
        for package in packages[:20]:
            table.add_row(
                package.destination_city,
                f"{package.departure_date} to {package.return_date}",
                str(package.num_nights),
                f"€{package.total_price:,.2f}",
                f"€{package.price_per_person:,.2f}",
            )

        if len(packages) > 20:
            table.add_row(
                "[dim]...[/dim]",
                "[dim]...[/dim]",
                "[dim]...[/dim]",
                "[dim]...[/dim]",
                "[dim]...[/dim]",
            )

        console.print(table)

        # Print statistics
        console.print(f"\n[bold]Statistics:[/bold]")
        console.print(f"Total packages: {len(packages)}")
        console.print(
            f"Average price: €{sum(p.total_price for p in packages) / len(packages):,.2f}"
        )
        console.print(
            f"Price range: €{min(p.total_price for p in packages):,.2f} - "
            f"€{max(p.total_price for p in packages):,.2f}"
        )
        console.print(
            f"Destinations: {len(set(p.destination_city for p in packages))}"
        )
