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
