"""
Example usage of AccommodationMatcher.

This script demonstrates how to use the AccommodationMatcher to generate
trip packages by pairing flights with accommodations.

Requirements:
    - Database with flights that have true_cost calculated
    - Accommodations scraped for destination cities
    - School holidays configured in database

Usage:
    python examples/accommodation_matcher_example.py
"""

import asyncio
import logging
from datetime import date

from rich.console import Console

from app.database import get_async_session_context
from app.orchestration.accommodation_matcher import AccommodationMatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

console = Console()


async def example_generate_packages():
    """
    Example: Generate trip packages with default settings.

    This will:
    1. Find all flights with calculated true costs
    2. Match them with accommodations in destination cities
    3. Calculate total trip costs
    4. Filter by budget (€2000 default)
    5. Filter by school holidays
    """
    console.print("\n[bold cyan]Example 1: Generate Trip Packages[/bold cyan]\n")

    matcher = AccommodationMatcher()

    async with get_async_session_context() as db:
        packages = await matcher.generate_trip_packages(
            db,
            max_budget=2000.0,
            min_nights=3,
            max_nights=10,
            filter_holidays=True,
        )

        console.print(f"\n[bold green]Generated {len(packages)} trip packages[/bold green]\n")

        # Print summary
        await matcher.print_package_summary(db, packages)

        # Save to database
        if packages:
            console.print("\n[yellow]Saving packages to database...[/yellow]")
            stats = await matcher.save_packages(db, packages)
            console.print(
                f"[green]Saved {stats['inserted']} new packages "
                f"(skipped {stats['skipped']} duplicates)[/green]\n"
            )


async def example_custom_budget():
    """
    Example: Generate packages with custom budget constraints.

    Use this to find luxury trips or budget trips.
    """
    console.print("\n[bold cyan]Example 2: Custom Budget Constraints[/bold cyan]\n")

    matcher = AccommodationMatcher()

    async with get_async_session_context() as db:
        # Budget trips (max €1500)
        budget_packages = await matcher.generate_trip_packages(
            db,
            max_budget=1500.0,
            min_nights=3,
            max_nights=7,
            filter_holidays=True,
        )

        console.print(
            f"\n[bold green]Found {len(budget_packages)} budget-friendly packages "
            f"(< €1500)[/bold green]\n"
        )

        # Luxury trips (€2000 - €3000)
        all_packages = await matcher.generate_trip_packages(
            db,
            max_budget=3000.0,
            min_nights=5,
            max_nights=10,
            filter_holidays=True,
        )

        luxury_packages = [p for p in all_packages if p.total_price >= 2000]

        console.print(
            f"[bold green]Found {len(luxury_packages)} luxury packages "
            f"(€2000-€3000)[/bold green]\n"
        )


async def example_destination_specific():
    """
    Example: Generate packages for specific destinations.

    Filter packages after generation to focus on specific cities.
    """
    console.print("\n[bold cyan]Example 3: Destination-Specific Packages[/bold cyan]\n")

    matcher = AccommodationMatcher()

    async with get_async_session_context() as db:
        # Generate all packages
        all_packages = await matcher.generate_trip_packages(
            db, max_budget=2000.0, min_nights=3, max_nights=10
        )

        # Filter for specific destinations
        lisbon_packages = [p for p in all_packages if p.destination_city == "Lisbon"]
        prague_packages = [p for p in all_packages if p.destination_city == "Prague"]
        barcelona_packages = [p for p in all_packages if p.destination_city == "Barcelona"]

        console.print(f"[cyan]Lisbon packages: {len(lisbon_packages)}[/cyan]")
        console.print(f"[cyan]Prague packages: {len(prague_packages)}[/cyan]")
        console.print(f"[cyan]Barcelona packages: {len(barcelona_packages)}[/cyan]\n")

        # Show Lisbon packages
        if lisbon_packages:
            console.print("\n[bold]Lisbon Trip Packages:[/bold]")
            await matcher.print_package_summary(db, lisbon_packages[:10])


async def example_cost_breakdown():
    """
    Example: View detailed cost breakdowns for trips.

    This shows how to calculate and display cost components.
    """
    console.print("\n[bold cyan]Example 4: Detailed Cost Breakdown[/bold cyan]\n")

    matcher = AccommodationMatcher()

    async with get_async_session_context() as db:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        from app.models.accommodation import Accommodation
        from app.models.flight import Flight

        # Get a sample flight with true cost
        flight_stmt = (
            select(Flight)
            .where(Flight.true_cost.isnot(None))
            .options(selectinload(Flight.destination_airport))
            .limit(1)
        )
        result = await db.execute(flight_stmt)
        flight = result.scalar_one_or_none()

        if not flight:
            console.print("[red]No flights with true cost found[/red]")
            return

        # Get a sample accommodation for the same destination
        accom_stmt = select(Accommodation).where(
            Accommodation.destination_city == flight.destination_airport.city
        )
        accom_result = await db.execute(accom_stmt)
        accommodation = accom_result.scalar_one_or_none()

        if not accommodation:
            console.print(
                f"[red]No accommodations found for {flight.destination_airport.city}[/red]"
            )
            return

        # Calculate cost breakdown
        num_nights = (flight.return_date - flight.departure_date).days
        cost = matcher.calculate_trip_cost(flight, accommodation, num_nights)

        # Display breakdown
        console.print(f"\n[bold]Trip to {flight.destination_airport.city}[/bold]")
        console.print(f"Duration: {num_nights} nights")
        console.print(f"\n[bold]Cost Breakdown:[/bold]")
        console.print(f"  Flight (true cost):    €{cost['flight_cost']:>8.2f}")
        console.print(f"  Accommodation:         €{cost['accommodation_cost']:>8.2f}")
        console.print(f"  Food (€100/day):       €{cost['food_cost']:>8.2f}")
        console.print(f"  Activities (€50/day):  €{cost['activities_cost']:>8.2f}")
        console.print(f"  " + "─" * 35)
        console.print(f"  [bold]Total:                 €{cost['total']:>8.2f}[/bold]")
        console.print(f"  [bold]Per person:            €{cost['per_person']:>8.2f}[/bold]\n")


async def example_weekend_trips():
    """
    Example: Find short weekend getaway packages.

    Filter for 3-4 night trips only.
    """
    console.print("\n[bold cyan]Example 5: Weekend Getaway Packages[/bold cyan]\n")

    matcher = AccommodationMatcher()

    async with get_async_session_context() as db:
        packages = await matcher.generate_trip_packages(
            db,
            max_budget=1500.0,
            min_nights=3,
            max_nights=4,  # Short trips only
            filter_holidays=True,
        )

        console.print(
            f"\n[bold green]Found {len(packages)} weekend getaway packages "
            f"(3-4 nights)[/bold green]\n"
        )

        if packages:
            # Sort by price
            packages.sort(key=lambda p: p.total_price)

            # Show cheapest 5
            console.print("[bold]Top 5 Cheapest Weekend Trips:[/bold]")
            for i, pkg in enumerate(packages[:5], 1):
                console.print(
                    f"{i}. {pkg.destination_city} - {pkg.num_nights} nights - "
                    f"€{pkg.total_price:.2f} (€{pkg.price_per_person:.2f}/person)"
                )


async def main():
    """Run all examples."""
    console.print("\n" + "=" * 70)
    console.print("[bold magenta]AccommodationMatcher Examples[/bold magenta]")
    console.print("=" * 70)

    # Run examples
    await example_generate_packages()
    await example_custom_budget()
    await example_destination_specific()
    await example_cost_breakdown()
    await example_weekend_trips()

    console.print("\n" + "=" * 70)
    console.print("[bold green]✓ All examples completed[/bold green]")
    console.print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
