"""
Command-line interface for SmartFamilyTravelScout.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from app import __version__, __app_name__
from app.config import settings
from app.database import check_db_connection

# Create Typer app
app = typer.Typer(
    name="travelscout",
    help="SmartFamilyTravelScout - AI-powered family travel deal finder",
    add_completion=False,
)

console = Console()
logger = logging.getLogger(__name__)


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        rprint(f"[bold blue]{__app_name__}[/bold blue] version [green]{__version__}[/green]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """
    SmartFamilyTravelScout CLI - AI-powered family travel deal finder.
    """
    pass


@app.command()
def health():
    """
    Check application health status.
    """
    console.print("\n[bold]Health Check[/bold]\n", style="blue")

    # Create table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")

    # Check database
    async def check_db():
        return await check_db_connection()

    db_status = asyncio.run(check_db())
    table.add_row("Database", "✓ Healthy" if db_status else "✗ Unhealthy")

    # Check configuration
    table.add_row("Configuration", "✓ Loaded")
    table.add_row("Environment", settings.environment)
    table.add_row("Log Level", settings.log_level)

    console.print(table)
    console.print()

    if not db_status:
        console.print("[red]Warning: Database connection failed[/red]")
        raise typer.Exit(code=1)

    console.print("[green]All systems operational[/green]\n")


@app.command()
def config():
    """
    Display current configuration (without sensitive data).
    """
    console.print("\n[bold]Current Configuration[/bold]\n", style="blue")

    # Create table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Add non-sensitive configuration
    table.add_row("App Name", settings.app_name)
    table.add_row("Version", settings.app_version)
    table.add_row("Environment", settings.environment)
    table.add_row("Debug", str(settings.debug))
    table.add_row("Log Level", settings.log_level)
    table.add_row("Timezone", settings.timezone)
    table.add_row("Departure Airports", settings.default_departure_airports)
    table.add_row("Trip Duration (days)", str(settings.default_trip_duration_days))
    table.add_row("Advance Booking (days)", str(settings.advance_booking_days))
    table.add_row("Enable Scraping", str(settings.enable_scraping))
    table.add_row("Enable AI Scoring", str(settings.enable_ai_scoring))

    console.print(table)
    console.print()


@app.command()
def search(
    from_airport: str = typer.Option(..., "--from", "-f", help="Departure airport code (e.g., VIE)"),
    departure_date: str = typer.Option(..., "--departure-date", "-d", help="Departure date (YYYY-MM-DD)"),
    return_date: Optional[str] = typer.Option(None, "--return-date", "-r", help="Return date (YYYY-MM-DD)"),
    max_price: Optional[float] = typer.Option(None, "--max-price", "-p", help="Maximum price per person"),
):
    """
    Search for flight deals.
    """
    console.print("\n[bold]Flight Search[/bold]\n", style="blue")

    try:
        # Parse dates
        dep_date = datetime.strptime(departure_date, "%Y-%m-%d")
        ret_date = datetime.strptime(return_date, "%Y-%m-%d") if return_date else None

        # Display search parameters
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Parameter", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("From", from_airport)
        table.add_row("Departure", dep_date.strftime("%Y-%m-%d"))
        if ret_date:
            table.add_row("Return", ret_date.strftime("%Y-%m-%d"))
        if max_price:
            table.add_row("Max Price", f"€{max_price}")

        console.print(table)
        console.print()

        # TODO: Implement actual search logic
        console.print("[yellow]Search functionality coming soon...[/yellow]\n")

    except ValueError as e:
        console.print(f"[red]Error: Invalid date format. Use YYYY-MM-DD[/red]")
        raise typer.Exit(code=1)


@app.command()
def scrape(
    scraper: str = typer.Option(..., "--scraper", "-s", help="Scraper name (e.g., kiwi, ryanair)"),
):
    """
    Run a specific scraper manually.
    """
    console.print(f"\n[bold]Running {scraper} scraper[/bold]\n", style="blue")

    # TODO: Implement scraper execution
    console.print("[yellow]Scraper execution coming soon...[/yellow]\n")


@app.command(name="kiwi-search")
def kiwi_search(
    origin: str = typer.Option(..., "--origin", "-o", help="Origin airport IATA code (e.g., MUC)"),
    destination: Optional[str] = typer.Option(None, "--destination", "-d", help="Destination airport IATA code (e.g., LIS). Omit for 'anywhere' search."),
    departure_date: Optional[str] = typer.Option(None, "--departure", help="Departure date (YYYY-MM-DD). Default: 60 days from today"),
    return_date: Optional[str] = typer.Option(None, "--return", help="Return date (YYYY-MM-DD). Default: 7 days after departure"),
    adults: int = typer.Option(2, "--adults", help="Number of adults"),
    children: int = typer.Option(2, "--children", help="Number of children"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save results to database"),
):
    """
    Search for flights using Kiwi.com API.

    Examples:
        # Search specific route
        travelscout kiwi-search --origin MUC --destination LIS

        # Search anywhere from origin
        travelscout kiwi-search --origin MUC

        # Custom dates
        travelscout kiwi-search --origin MUC --destination BCN --departure 2025-12-20 --return 2025-12-27
    """
    console.print("\n[bold]Kiwi.com Flight Search[/bold]\n", style="blue")

    from datetime import date, timedelta
    import os
    from app.scrapers.kiwi_scraper import KiwiClient

    # Parse dates
    if departure_date:
        dep_date = datetime.strptime(departure_date, "%Y-%m-%d").date()
    else:
        dep_date = date.today() + timedelta(days=60)

    if return_date:
        ret_date = datetime.strptime(return_date, "%Y-%m-%d").date()
    else:
        ret_date = dep_date + timedelta(days=7)

    # Display search parameters
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Origin", origin)
    if destination:
        table.add_row("Destination", destination)
    else:
        table.add_row("Destination", "Anywhere")
    table.add_row("Departure", dep_date.strftime("%Y-%m-%d"))
    table.add_row("Return", ret_date.strftime("%Y-%m-%d"))
    table.add_row("Passengers", f"{adults} adults + {children} children")
    table.add_row("Save to DB", "Yes" if save else "No")

    console.print(table)
    console.print()

    # Check API key
    api_key = os.getenv("KIWI_API_KEY")
    if not api_key:
        console.print("[red]Error: KIWI_API_KEY environment variable not set[/red]\n")
        raise typer.Exit(code=1)

    async def search():
        client = KiwiClient(api_key=api_key)

        # Search flights
        if destination:
            console.print(f"[yellow]Searching flights from {origin} to {destination}...[/yellow]\n")
            flights = await client.search_flights(
                origin=origin,
                destination=destination,
                departure_date=dep_date,
                return_date=ret_date,
                adults=adults,
                children=children,
            )
        else:
            console.print(f"[yellow]Searching flights from {origin} to anywhere...[/yellow]\n")
            flights = await client.search_anywhere(
                origin=origin,
                departure_date=dep_date,
                return_date=ret_date,
                adults=adults,
                children=children,
            )

        # Display results
        if flights:
            console.print(f"[green]✓ Found {len(flights)} flights[/green]\n")

            # Create results table
            results_table = Table(show_header=True, header_style="bold magenta")
            results_table.add_column("Route", style="cyan")
            results_table.add_column("Airline", style="yellow")
            results_table.add_column("Dates", style="blue")
            results_table.add_column("Price/Person", style="green")
            results_table.add_column("Total", style="green")
            results_table.add_column("Direct", style="magenta")

            for flight in flights[:10]:  # Show top 10
                route = f"{flight['origin_airport']} → {flight['destination_airport']}"
                dates = f"{flight['departure_date']} - {flight['return_date']}"
                price_per = f"€{flight['price_per_person']}"
                total = f"€{flight['total_price']}"
                direct = "✓" if flight['direct_flight'] else "✗"

                results_table.add_row(
                    route,
                    flight['airline'],
                    dates,
                    price_per,
                    total,
                    direct,
                )

            console.print(results_table)
            console.print()

            # Save to database
            if save:
                console.print("[yellow]Saving flights to database...[/yellow]")
                stats = await client.save_to_database(flights)
                console.print(
                    f"[green]✓ Saved: {stats['inserted']} inserted, "
                    f"{stats['updated']} updated, {stats['skipped']} skipped[/green]\n"
                )
        else:
            console.print("[yellow]No flights found[/yellow]\n")

    # Run async search
    asyncio.run(search())


@app.command(name="kiwi-status")
def kiwi_status():
    """
    Check Kiwi.com API rate limit status.
    """
    console.print("\n[bold]Kiwi.com API Status[/bold]\n", style="blue")

    from app.scrapers.kiwi_scraper import RateLimiter

    rate_limiter = RateLimiter()
    remaining = rate_limiter.get_remaining_calls()
    used = 100 - remaining

    # Create table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("API calls used (this month)", f"{used}/100")
    table.add_row("Remaining calls", f"{remaining}/100")
    table.add_row("Usage", f"{(used/100)*100:.1f}%")

    console.print(table)
    console.print()

    if remaining > 10:
        console.print("[green]✓ Plenty of API calls remaining[/green]\n")
    elif remaining > 0:
        console.print(f"[yellow]⚠ Only {remaining} API calls remaining this month[/yellow]\n")
    else:
        console.print("[red]✗ Monthly rate limit exceeded![/red]\n")


@app.command()
def db_init():
    """
    Initialize database (create tables).

    WARNING: Only use in development!
    """
    console.print("\n[bold red]WARNING: This will create all database tables[/bold red]\n")
    confirm = typer.confirm("Are you sure you want to continue?")

    if not confirm:
        console.print("[yellow]Operation cancelled[/yellow]\n")
        raise typer.Exit()

    # TODO: Implement database initialization
    console.print("[yellow]Database initialization coming soon...[/yellow]")
    console.print("[green]Use 'alembic upgrade head' for migrations[/green]\n")


@app.command()
def worker():
    """
    Start Celery worker.
    """
    console.print("\n[bold]Starting Celery worker[/bold]\n", style="blue")

    import subprocess
    subprocess.run([
        "celery",
        "-A",
        "app.tasks.celery_app",
        "worker",
        "--loglevel=info",
    ])


@app.command()
def beat():
    """
    Start Celery beat scheduler.
    """
    console.print("\n[bold]Starting Celery beat scheduler[/bold]\n", style="blue")

    import subprocess
    subprocess.run([
        "celery",
        "-A",
        "app.tasks.celery_app",
        "beat",
        "--loglevel=info",
    ])


if __name__ == "__main__":
    app()
