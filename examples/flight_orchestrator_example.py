"""
Example usage of FlightOrchestrator.

This script demonstrates how to use the FlightOrchestrator to:
1. Scrape flights from all 4 sources in parallel
2. Deduplicate results
3. Save to database

Usage:
    python examples/flight_orchestrator_example.py
"""

import asyncio
import logging
from datetime import date

from rich.console import Console
from rich.logging import RichHandler

from app.orchestration.flight_orchestrator import FlightOrchestrator

# Configure logging with Rich
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_time=False)],
)

logger = logging.getLogger(__name__)
console = Console()


async def main():
    """Run the flight orchestrator example."""
    console.print("\n[bold cyan]═══ Flight Orchestrator Example ═══[/bold cyan]\n")

    # Initialize orchestrator
    orchestrator = FlightOrchestrator()

    # Define search parameters
    origins = ["MUC", "FMM"]  # Munich and Memmingen
    destinations = ["LIS", "BCN", "PRG"]  # Lisbon, Barcelona, Prague

    # Christmas holidays 2025
    date_ranges = [
        (date(2025, 12, 20), date(2025, 12, 27)),  # 1 week
        (date(2025, 12, 22), date(2025, 12, 29)),  # Alternative dates
    ]

    console.print("[bold]Search Parameters:[/bold]")
    console.print(f"  Origins: {', '.join(origins)}")
    console.print(f"  Destinations: {', '.join(destinations)}")
    console.print(f"  Date ranges: {len(date_ranges)} periods")
    console.print(f"  Total searches: {len(origins)} × {len(destinations)} × {len(date_ranges)} × 4 scrapers = {len(origins) * len(destinations) * len(date_ranges) * 4}\n")

    try:
        # Run orchestrator
        console.print("[bold green]Starting parallel scraping...[/bold green]\n")

        unique_flights = await orchestrator.scrape_all(
            origins=origins,
            destinations=destinations,
            date_ranges=date_ranges,
        )

        # Display results
        console.print(f"\n[bold green]✓ Scraping complete![/bold green]")
        console.print(f"Found [bold yellow]{len(unique_flights)}[/bold yellow] unique flights\n")

        # Show sample flights
        if unique_flights:
            console.print("[bold]Sample flights (first 5):[/bold]\n")

            for i, flight in enumerate(unique_flights[:5], 1):
                route = f"{flight.get('origin_airport', 'N/A')} → {flight.get('destination_airport', 'N/A')}"
                airline = flight.get("airline", "Unknown")
                price = flight.get("price_per_person", 0)
                sources = flight.get("sources", [flight.get("source", "unknown")])
                dup_count = flight.get("duplicate_count", 1)

                console.print(
                    f"  {i}. {route} - {airline} - €{price:.2f}/person "
                    f"[dim](from {len(sources)} source{'s' if len(sources) > 1 else ''}, "
                    f"{dup_count} duplicate{'s' if dup_count > 1 else ''})[/dim]"
                )

        # Save to database
        console.print("\n[bold cyan]Saving to database...[/bold cyan]")

        stats = await orchestrator.save_to_database(unique_flights)

        console.print(f"\n[bold green]✓ Database save complete![/bold green]")
        console.print(f"  Inserted: [green]{stats['inserted']}[/green]")
        console.print(f"  Updated: [yellow]{stats['updated']}[/yellow]")
        console.print(f"  Skipped: [red]{stats['skipped']}[/red]")
        console.print(f"  Total processed: {stats['total']}\n")

        # Summary
        console.print("[bold cyan]═══ Summary ═══[/bold cyan]")
        console.print(f"✓ Scraped from 4 sources")
        console.print(f"✓ Found {len(unique_flights)} unique flights")
        console.print(f"✓ Saved {stats['inserted'] + stats['updated']} flights to database")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        logger.exception("Fatal error")
        raise


if __name__ == "__main__":
    asyncio.run(main())
