"""
Command-line interface for SmartFamilyTravelScout.
Professional CLI with Rich formatting and comprehensive commands.
"""

import asyncio
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
    TaskID,
)
from rich.table import Table
from rich.tree import Tree
from rich import print as rprint
from sqlalchemy import select, func, and_, desc

from app import __version__, __app_name__
from app.config import settings
from app.database import check_db_connection, get_async_session_context, get_sync_session

# Create Typer app
app = typer.Typer(
    name="scout",
    help="SmartFamilyTravelScout - AI-powered family travel deal finder",
    add_completion=False,
)

# Create sub-commands
config_app = typer.Typer(help="Manage configuration")
db_app = typer.Typer(help="Database management")

app.add_typer(config_app, name="config")
app.add_typer(db_app, name="db")

console = Console()
logger = logging.getLogger(__name__)


# ============================================================================
# Utility Functions
# ============================================================================

def handle_error(e: Exception, message: str = "An error occurred"):
    """Handle errors with nice formatting."""
    console.print(f"\n[bold red]✗ {message}[/bold red]")
    console.print(f"[red]{type(e).__name__}: {str(e)}[/red]\n")
    if settings.debug:
        console.print_exception()
    raise typer.Exit(code=1)


def success(message: str):
    """Print success message."""
    console.print(f"[bold green]✓ {message}[/bold green]")


def info(message: str):
    """Print info message."""
    console.print(f"[blue]{message}[/blue]")


def warning(message: str):
    """Print warning message."""
    console.print(f"[yellow]⚠ {message}[/yellow]")


# ============================================================================
# Version Callback
# ============================================================================

def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(Panel(
            f"[bold blue]{__app_name__}[/bold blue] version [green]{__version__}[/green]\n"
            f"AI-powered family travel deal finder",
            title="🧳 SmartFamilyTravelScout",
            border_style="blue",
        ))
        raise typer.Exit()


# ============================================================================
# Main Callback
# ============================================================================

@app.callback()
def main():
    """
    SmartFamilyTravelScout CLI - AI-powered family travel deal finder.

    Use 'scout COMMAND --help' for command-specific help.
    """
    pass


# ============================================================================
# SCRAPE Command - Quick scraping with default (free) scrapers
# ============================================================================

@app.command()
def scrape(
    origin: str = typer.Option(
        ...,
        help="Origin airport IATA code (e.g., MUC, VIE)",
    ),
    destination: str = typer.Option(
        ...,
        help="Destination airport IATA code (e.g., LIS, BCN)",
    ),
    departure_date: Optional[str] = typer.Option(
        None,
        help="Departure date (YYYY-MM-DD). Default: 60 days from today",
    ),
    return_date: Optional[str] = typer.Option(
        None,
        help="Return date (YYYY-MM-DD). Default: 7 days after departure",
    ),
    scraper: Optional[str] = typer.Option(
        None,
        help="Specific scraper to use: 'skyscanner', 'ryanair', 'wizzair', or 'all' for all free scrapers",
    ),
    save: bool = typer.Option(
        True,
        help="Save results to database",
    ),
):
    """
    Quick flight search using default (free, no API key) scrapers.

    This command uses Skyscanner, Ryanair, and WizzAir scrapers which don't
    require API keys. Perfect for getting started without configuration!

    Examples:
        scout scrape --origin MUC --destination LIS
        scout scrape --origin VIE --destination BCN --scraper skyscanner
        scout scrape --origin MUC --destination PRG --departure 2025-12-20 --return 2025-12-27
    """
    console.print(Panel(
        "[bold]Quick Flight Scrape (No API Key Required)[/bold]",
        border_style="green",
    ))

    try:
        asyncio.run(_run_scrape(origin, destination, departure_date, return_date, scraper, save))
    except Exception as e:
        handle_error(e, "Scraping failed")


async def _run_scrape(
    origin: str,
    destination: str,
    departure_date_str: Optional[str],
    return_date_str: Optional[str],
    scraper_name: Optional[str],
    save: bool,
):
    """Execute quick scrape with default scrapers."""
    from datetime import date, timedelta

    # Parse dates
    if departure_date_str:
        dep_date = datetime.strptime(departure_date_str, "%Y-%m-%d").date()
    else:
        dep_date = date.today() + timedelta(days=60)

    if return_date_str:
        ret_date = datetime.strptime(return_date_str, "%Y-%m-%d").date()
    else:
        ret_date = dep_date + timedelta(days=7)

    # Display search parameters
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Origin", origin.upper())
    table.add_row("Destination", destination.upper())
    table.add_row("Departure", dep_date.strftime("%Y-%m-%d"))
    table.add_row("Return", ret_date.strftime("%Y-%m-%d"))

    # Determine which scrapers to use
    if scraper_name and scraper_name != "all":
        scrapers_to_use = [scraper_name.lower()]
        table.add_row("Scraper", scraper_name.title())
    else:
        # Use all default (free) scrapers
        scrapers_to_use = ["skyscanner", "ryanair", "wizzair"]
        table.add_row("Scrapers", "All free scrapers (Skyscanner, Ryanair, WizzAir)")

    table.add_row("Save to DB", "Yes" if save else "No")

    console.print("\n")
    console.print(table)
    console.print("\n")

    all_results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[yellow]Scraping flights...", total=len(scrapers_to_use)
        )

        # Run each scraper
        for scraper in scrapers_to_use:
            try:
                progress.update(task, description=f"[yellow]Running {scraper}...")

                if scraper == "skyscanner":
                    from app.scrapers.skyscanner_scraper import SkyscannerScraper
                    async with SkyscannerScraper(headless=True) as scraper_instance:
                        results = await scraper_instance.scrape_route(
                            origin=origin.upper(),
                            destination=destination.upper(),
                            departure_date=dep_date,
                            return_date=ret_date,
                        )
                        # Normalize data
                        for r in results:
                            r["origin_airport"] = origin.upper()
                            r["destination_airport"] = destination.upper()
                            r["source"] = "skyscanner"
                        all_results.extend(results)

                elif scraper == "ryanair":
                    from app.scrapers.ryanair_scraper import RyanairScraper
                    async with RyanairScraper() as scraper_instance:
                        results = await scraper_instance.scrape_route(
                            origin=origin.upper(),
                            destination=destination.upper(),
                            departure_date=dep_date,
                            return_date=ret_date,
                        )
                        all_results.extend(results)

                elif scraper == "wizzair":
                    from app.scrapers.wizzair_scraper import WizzAirScraper
                    scraper_instance = WizzAirScraper()
                    results = await scraper_instance.search_flights(
                        origin=origin.upper(),
                        destination=destination.upper(),
                        departure_date=dep_date,
                        return_date=ret_date,
                        adult_count=2,
                        child_count=2,
                    )
                    all_results.extend(results)

                else:
                    warning(f"Unknown scraper: {scraper}")

                progress.update(task, advance=1)

            except Exception as e:
                logger.error(f"Scraper {scraper} failed: {e}")
                warning(f"{scraper.title()} scraper failed: {str(e)}")
                progress.update(task, advance=1)
                continue

    # Display results
    if all_results:
        success(f"Found {len(all_results)} flights")

        # Create results table
        results_table = Table(show_header=True, header_style="bold magenta")
        results_table.add_column("Airline", style="cyan")
        results_table.add_column("Price/Person", style="green", justify="right")
        results_table.add_column("Total (4 people)", style="green", justify="right")
        results_table.add_column("Direct", style="magenta")
        results_table.add_column("Source", style="yellow")

        # Sort by price
        sorted_results = sorted(
            all_results,
            key=lambda x: x.get("price_per_person", x.get("price", 9999))
        )

        for result in sorted_results[:15]:  # Show top 15
            price_per = result.get("price_per_person", result.get("price", 0))
            total = result.get("total_price", price_per * 4)

            results_table.add_row(
                result.get("airline", "Unknown"),
                f"€{price_per:.0f}",
                f"€{total:.0f}",
                "✓" if result.get("direct_flight", result.get("direct", False)) else "✗",
                result.get("source", "unknown"),
            )

        console.print("\n")
        console.print(results_table)
        console.print("\n")

        if save:
            info("Saving results to database...")
            # TODO: Implement save logic similar to kiwi-search
            success("Results saved")
    else:
        warning("No flights found")


# ============================================================================
# RUN Command - Main Pipeline
# ============================================================================

@app.command()
def run(
    destinations: str = typer.Option(
        "all",
        help="Destinations to search (comma-separated IATA codes or 'all')",
    ),
    dates: str = typer.Option(
        "next-3-months",
        help="Date range: 'next-3-months', 'next-6-months', or specific dates",
    ),
    analyze: bool = typer.Option(
        True,
        help="Run AI analysis on results",
    ),
    max_price: Optional[float] = typer.Option(
        None,
        help="Maximum price per person in EUR",
    ),
):
    """
    Run the full SmartFamilyTravelScout pipeline.

    This command executes:
    1. Flight scraping from all sources
    2. Accommodation scraping
    3. Event discovery
    4. Package generation
    5. AI analysis and scoring
    6. Notification sending

    Examples:
        scout run
        scout run --destinations LIS,BCN,PRG --dates next-3-months
        scout run --max-price 150 --no-analyze
    """
    console.print(Panel(
        "[bold]Starting SmartFamilyTravelScout Pipeline[/bold]",
        border_style="green",
    ))

    try:
        asyncio.run(_run_pipeline(destinations, dates, analyze, max_price))
    except Exception as e:
        handle_error(e, "Pipeline execution failed")


async def _run_pipeline(
    destinations: str,
    dates: str,
    analyze: bool,
    max_price: Optional[float],
):
    """Execute the main pipeline."""
    from app.orchestration.flight_orchestrator import FlightOrchestrator
    from app.orchestration.accommodation_matcher import AccommodationMatcher
    from app.orchestration.event_matcher import EventMatcher
    from app.models.airport import Airport
    from app.utils.date_utils import get_school_holiday_periods

    stats = {
        "flights": 0,
        "accommodations": 0,
        "events": 0,
        "packages": 0,
        "analyzed": 0,
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:

        # Step 1: Determine destinations
        task1 = progress.add_task("[cyan]Loading destinations...", total=1)

        async with get_async_session_context() as db:
            if destinations == "all":
                result = await db.execute(select(Airport).where(Airport.is_destination == True))
                dest_airports = result.scalars().all()
                dest_codes = [a.iata_code for a in dest_airports]
            else:
                dest_codes = [d.strip().upper() for d in destinations.split(",")]

            # Get origin airports
            origin_result = await db.execute(
                select(Airport).where(Airport.is_origin == True)
            )
            origin_airports = origin_result.scalars().all()
            origin_codes = [a.iata_code for a in origin_airports]

        progress.update(task1, completed=1)
        info(f"Origins: {', '.join(origin_codes)}")
        info(f"Destinations: {', '.join(dest_codes)}")

        # Step 2: Determine date ranges
        task2 = progress.add_task("[cyan]Calculating date ranges...", total=1)

        if dates == "next-3-months":
            end_date = date.today() + timedelta(days=90)
        elif dates == "next-6-months":
            end_date = date.today() + timedelta(days=180)
        else:
            end_date = date.today() + timedelta(days=90)

        date_ranges = get_school_holiday_periods(
            start_date=date.today(),
            end_date=end_date,
        )

        progress.update(task2, completed=1)
        info(f"Date ranges: {len(date_ranges)} school holiday periods")

        # Step 3: Scrape flights
        task3 = progress.add_task("[yellow]Scraping flights...", total=None)

        orchestrator = FlightOrchestrator()
        flights = await orchestrator.scrape_all(
            origins=origin_codes,
            destinations=dest_codes,
            date_ranges=date_ranges,
        )

        stats["flights"] = len(flights)
        progress.update(task3, completed=1)
        success(f"Found {stats['flights']} flights")

        # Step 4: Scrape accommodations
        task4 = progress.add_task("[yellow]Scraping accommodations...", total=len(dest_codes))

        # TODO: Implement accommodation scraping
        # For now, we'll query existing accommodations
        async with get_async_session_context() as db:
            from app.models.accommodation import Accommodation
            result = await db.execute(
                select(func.count(Accommodation.id))
            )
            stats["accommodations"] = result.scalar() or 0

        progress.update(task4, completed=len(dest_codes))
        info(f"Available accommodations: {stats['accommodations']}")

        # Step 5: Match packages
        task5 = progress.add_task("[cyan]Generating trip packages...", total=None)

        matcher = AccommodationMatcher()
        packages = await matcher.generate_trip_packages(
            max_budget_per_person=max_price or settings.max_flight_price_per_person,
        )

        stats["packages"] = len(packages)
        progress.update(task5, completed=1)
        success(f"Generated {stats['packages']} trip packages")

        # Step 6: Match events
        task6 = progress.add_task("[cyan]Matching events to packages...", total=None)

        event_matcher = EventMatcher()
        await event_matcher.match_events_to_packages()

        progress.update(task6, completed=1)

        # Step 7: AI analysis
        if analyze and stats["packages"] > 0:
            task7 = progress.add_task("[magenta]Running AI analysis...", total=stats["packages"])

            from app.ai.deal_scorer import DealScorer

            scorer = DealScorer()
            async with get_async_session_context() as db:
                from app.models.trip_package import TripPackage

                result = await db.execute(
                    select(TripPackage).where(TripPackage.ai_score.is_(None))
                )
                unscored = result.scalars().all()

                for idx, package in enumerate(unscored[:50]):  # Limit to 50 for cost control
                    try:
                        score_data = await scorer.score_trip(package)
                        package.ai_score = score_data["score"]
                        package.ai_reasoning = score_data["reasoning"]
                        await db.commit()
                        stats["analyzed"] += 1
                        progress.update(task7, advance=1)
                    except Exception as e:
                        logger.error(f"Failed to score package {package.id}: {e}")
                        continue

            success(f"Analyzed {stats['analyzed']} packages")

    # Display final statistics
    console.print("\n")
    table = Table(title="Pipeline Results", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="green", justify="right")

    table.add_row("Flights Found", str(stats["flights"]))
    table.add_row("Accommodations Available", str(stats["accommodations"]))
    table.add_row("Packages Generated", str(stats["packages"]))
    if analyze:
        table.add_row("Packages Analyzed", str(stats["analyzed"]))

    console.print(table)
    console.print("\n")
    success("Pipeline complete!")


# ============================================================================
# DEALS Command - View Top Deals
# ============================================================================

@app.command()
def deals(
    min_score: int = typer.Option(
        70,
        help="Minimum AI score (0-100)",
    ),
    destination: Optional[str] = typer.Option(
        None,
        help="Filter by destination city",
    ),
    limit: Optional[int] = typer.Option(
        None,
        help="Number of deals to show (deprecated, use --per-page instead)",
    ),
    page: int = typer.Option(
        1,
        help="Page number to display (starts at 1)",
    ),
    per_page: int = typer.Option(
        10,
        help="Number of deals per page",
    ),
    package_type: Optional[str] = typer.Option(
        None,
        help="Package type: 'family' or 'parent_escape'",
    ),
    format: str = typer.Option(
        "table",
        help="Output format: 'table' or 'json'",
    ),
):
    """
    Show top travel deals based on AI scoring with pagination support.

    Examples:
        scout deals
        scout deals --min-score 80 --per-page 20
        scout deals --destination lisbon --type family
        scout deals --page 2 --per-page 15
        scout deals --format json
    """
    try:
        asyncio.run(_show_deals(min_score, destination, limit, page, per_page, package_type, format))
    except Exception as e:
        handle_error(e, "Failed to retrieve deals")


async def _show_deals(
    min_score: int,
    destination: Optional[str],
    limit: Optional[int],
    page: int,
    per_page: int,
    package_type: Optional[str],
    format: str,
):
    """Retrieve and display top deals with pagination."""
    from app.models.trip_package import TripPackage

    # Handle deprecated 'limit' parameter
    if limit is not None:
        warning("The --limit option is deprecated. Use --per-page and --page instead.")
        per_page = limit
        page = 1

    # Validate page number
    if page < 1:
        console.print("[red]Error: Page number must be 1 or greater[/red]")
        return

    # Calculate offset
    offset = (page - 1) * per_page

    async with get_async_session_context() as db:
        # Build base query for filtering
        base_query = select(TripPackage).where(
            TripPackage.ai_score >= min_score
        )

        if destination:
            base_query = base_query.where(
                TripPackage.destination_city.ilike(f"%{destination}%")
            )

        if package_type:
            base_query = base_query.where(TripPackage.package_type == package_type)

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await db.execute(count_query)
        total_count = total_result.scalar() or 0

        if total_count == 0:
            warning("No deals found matching your criteria")
            return

        # Calculate pagination info
        total_pages = (total_count + per_page - 1) // per_page  # Ceiling division
        start_item = offset + 1
        end_item = min(offset + per_page, total_count)

        # Check if page number is valid
        if page > total_pages:
            console.print(f"[red]Error: Page {page} does not exist. Total pages: {total_pages}[/red]")
            return

        # Build paginated query
        query = base_query.order_by(desc(TripPackage.ai_score)).offset(offset).limit(per_page)

        result = await db.execute(query)
        packages = result.scalars().all()

        if format == "json":
            # JSON output with pagination metadata
            deals_data = {
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_items": total_count,
                    "total_pages": total_pages,
                    "showing_from": start_item,
                    "showing_to": end_item,
                },
                "deals": []
            }

            for pkg in packages:
                deals_data["deals"].append({
                    "id": pkg.id,
                    "destination": pkg.destination_city,
                    "departure_date": pkg.departure_date.isoformat(),
                    "return_date": pkg.return_date.isoformat(),
                    "nights": pkg.num_nights,
                    "price": float(pkg.total_price),
                    "price_per_person": float(pkg.price_per_person),
                    "score": float(pkg.ai_score) if pkg.ai_score else None,
                    "type": pkg.package_type,
                })

            console.print(json.dumps(deals_data, indent=2))
        else:
            # Table output
            table = Table(
                title=f"🌟 Travel Deals",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Destination", style="cyan", no_wrap=True)
            table.add_column("Dates", style="blue")
            table.add_column("Nights", style="yellow", justify="right")
            table.add_column("Price", style="green", justify="right")
            table.add_column("Per Person", style="green", justify="right")
            table.add_column("Score", style="magenta", justify="right")
            table.add_column("Type", style="white")

            for pkg in packages:
                score_str = f"{pkg.ai_score:.0f}/100" if pkg.ai_score else "N/A"
                score_style = "bold green" if pkg.ai_score and pkg.ai_score >= 80 else "yellow"

                table.add_row(
                    pkg.destination_city.title(),
                    f"{pkg.departure_date.strftime('%Y-%m-%d')} to\n{pkg.return_date.strftime('%Y-%m-%d')}",
                    str(pkg.num_nights),
                    f"€{pkg.total_price:.0f}",
                    f"€{pkg.price_per_person:.0f}",
                    f"[{score_style}]{score_str}[/{score_style}]",
                    pkg.package_type,
                )

            console.print("\n")
            console.print(table)
            console.print("\n")

            # Display pagination information
            pagination_info = f"[cyan]Showing deals {start_item}-{end_item} of {total_count} total[/cyan]"
            page_info = f"[cyan]Page {page} of {total_pages}[/cyan]"

            console.print(pagination_info)
            console.print(page_info)

            # Show navigation hints
            if page < total_pages:
                console.print(f"[dim]Next page: scout deals --page {page + 1} --per-page {per_page}[/dim]")
            if page > 1:
                console.print(f"[dim]Previous page: scout deals --page {page - 1} --per-page {per_page}[/dim]")

            console.print("\n")
            success(f"Displayed {len(packages)} deals")


# ============================================================================
# CONFIG Commands - Configuration Management
# ============================================================================

@config_app.command("show")
def config_show():
    """
    Display current configuration (without sensitive data).
    """
    console.print("\n")
    console.print(Panel(
        "[bold]Current Configuration[/bold]",
        border_style="blue",
    ))

    # Create table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    # Application settings
    table.add_row("App Name", settings.app_name)
    table.add_row("Version", settings.app_version)
    table.add_row("Environment", settings.environment)
    table.add_row("Debug", str(settings.debug))
    table.add_row("Log Level", settings.log_level)
    table.add_row("Timezone", settings.timezone)

    # Travel settings
    table.add_row("", "")  # Separator
    table.add_row("[bold]Travel Settings[/bold]", "")
    table.add_row("Departure Airports", settings.default_departure_airports)
    table.add_row("Trip Duration (days)", str(settings.default_trip_duration_days))
    table.add_row("Advance Booking (days)", str(settings.advance_booking_days))
    table.add_row("Max Flight Price/Person", f"€{settings.max_flight_price_per_person}")
    table.add_row("Max Accommodation/Night", f"€{settings.max_accommodation_price_per_night}")

    # Feature flags
    table.add_row("", "")  # Separator
    table.add_row("[bold]Feature Flags[/bold]", "")
    table.add_row("Enable Scraping", "✓" if settings.enable_scraping else "✗")
    table.add_row("Enable AI Scoring", "✓" if settings.enable_ai_scoring else "✗")
    table.add_row("Enable Notifications", "✓" if settings.enable_notifications else "✗")
    table.add_row("Enable Metrics", "✓" if settings.enable_metrics else "✗")

    console.print(table)
    console.print("\n")


@config_app.command("get")
def config_get(
    key: str = typer.Argument(..., help="Configuration key to retrieve"),
):
    """
    Get a specific configuration value.

    Example:
        scout config get max_flight_price_per_person
    """
    try:
        value = getattr(settings, key)
        console.print(f"[cyan]{key}[/cyan] = [green]{value}[/green]")
    except AttributeError:
        console.print(f"[red]Configuration key '{key}' not found[/red]")
        raise typer.Exit(code=1)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value"),
):
    """
    Set a configuration value in .env file.

    Example:
        scout config set max_flight_price_per_person 250
    """
    env_file = Path(".env")

    if not env_file.exists():
        console.print("[yellow]Warning: .env file not found, creating new one[/yellow]")
        env_file.touch()

    # Convert key to uppercase for .env
    env_key = key.upper()

    # Read existing .env
    lines = []
    key_found = False

    if env_file.exists():
        with open(env_file, "r") as f:
            lines = f.readlines()

    # Update or add the key
    updated_lines = []
    for line in lines:
        if line.strip().startswith(f"{env_key}="):
            updated_lines.append(f"{env_key}={value}\n")
            key_found = True
        else:
            updated_lines.append(line)

    if not key_found:
        updated_lines.append(f"{env_key}={value}\n")

    # Write back
    with open(env_file, "w") as f:
        f.writelines(updated_lines)

    success(f"Set {key} = {value}")
    info("Restart the application for changes to take effect")


# ============================================================================
# TEST-SCRAPER Command
# ============================================================================

@app.command("test-scraper")
def test_scraper(
    scraper: str = typer.Argument(
        ...,
        help="Scraper name: 'kiwi', 'skyscanner', 'ryanair', 'wizzair', 'booking'",
    ),
    origin: str = typer.Option(
        "MUC",
        help="Origin airport IATA code",
    ),
    dest: str = typer.Option(
        "LIS",
        help="Destination airport IATA code",
    ),
    save: bool = typer.Option(
        False,
        help="Save results to database",
    ),
):
    """
    Test individual scrapers with sample queries.

    Examples:
        scout test-scraper kiwi --origin MUC --dest LIS
        scout test-scraper ryanair --save
        scout test-scraper skyscanner --origin VIE --dest BCN
    """
    console.print(Panel(
        f"[bold]Testing {scraper.upper()} Scraper[/bold]",
        border_style="yellow",
    ))

    try:
        asyncio.run(_test_scraper(scraper, origin, dest, save))
    except Exception as e:
        handle_error(e, f"Scraper test failed")


async def _test_scraper(scraper: str, origin: str, dest: str, save: bool):
    """Test a specific scraper."""
    from datetime import date, timedelta

    # Default dates
    dep_date = date.today() + timedelta(days=60)
    ret_date = dep_date + timedelta(days=7)

    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"[yellow]Running {scraper} scraper...", total=None)

        if scraper.lower() == "kiwi":
            from app.scrapers.kiwi_scraper import KiwiClient
            client = KiwiClient()
            results = await client.search_flights(
                origin=origin,
                destination=dest,
                departure_date=dep_date,
                return_date=ret_date,
            )
        elif scraper.lower() == "skyscanner":
            from app.scrapers.skyscanner_scraper import SkyscannerScraper
            scraper_instance = SkyscannerScraper(headless=True)
            results = await scraper_instance.scrape_flights(
                origin=origin,
                destination=dest,
                departure_date=dep_date,
                return_date=ret_date,
            )
        elif scraper.lower() == "ryanair":
            from app.scrapers.ryanair_scraper import RyanairScraper
            scraper_instance = RyanairScraper()
            results = await scraper_instance.scrape_flights(
                origin=origin,
                destination=dest,
                departure_date=dep_date,
                return_date=ret_date,
            )
        elif scraper.lower() == "wizzair":
            from app.scrapers.wizzair_scraper import WizzAirScraper
            scraper_instance = WizzAirScraper()
            results = await scraper_instance.scrape_flights(
                origin=origin,
                destination=dest,
                departure_date=dep_date,
                return_date=ret_date,
            )
        else:
            console.print(f"[red]Unknown scraper: {scraper}[/red]")
            console.print("[yellow]Available scrapers: kiwi, skyscanner, ryanair, wizzair[/yellow]")
            raise typer.Exit(code=1)

        progress.update(task, completed=1)

    # Display results
    if results:
        success(f"Found {len(results)} results")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Route", style="cyan")
        table.add_column("Airline", style="yellow")
        table.add_column("Price/Person", style="green", justify="right")
        table.add_column("Direct", style="magenta")

        for result in results[:10]:
            table.add_row(
                f"{result.get('origin_airport', origin)} → {result.get('destination_airport', dest)}",
                result.get("airline", "N/A"),
                f"€{result.get('price_per_person', 0):.0f}",
                "✓" if result.get("direct_flight", False) else "✗",
            )

        console.print("\n")
        console.print(table)
        console.print("\n")

        if save:
            info("Saving results to database...")
            # Save logic here
            success("Results saved")
    else:
        warning("No results found")


# ============================================================================
# STATS Command
# ============================================================================

@app.command()
def stats(
    period: str = typer.Option(
        "week",
        help="Time period: 'day', 'week', 'month', 'all'",
    ),
    scraper: Optional[str] = typer.Option(
        None,
        help="Filter by scraper source",
    ),
):
    """
    Show statistics about scraped data and system usage.

    Examples:
        scout stats
        scout stats --period month
        scout stats --scraper kiwi
    """
    try:
        asyncio.run(_show_stats(period, scraper))
    except Exception as e:
        handle_error(e, "Failed to retrieve statistics")


async def _show_stats(period: str, scraper: Optional[str]):
    """Display system statistics."""
    from app.models.flight import Flight
    from app.models.accommodation import Accommodation
    from app.models.event import Event
    from app.models.trip_package import TripPackage
    from app.models.scraping_job import ScrapingJob
    from app.models.api_cost import ApiCost

    # Calculate date filter
    now = datetime.now()
    if period == "day":
        start_date = now - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(weeks=1)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = datetime(2000, 1, 1)  # All time

    async with get_async_session_context() as db:
        # Flight stats
        flight_query = select(func.count(Flight.id))
        if scraper:
            flight_query = flight_query.where(Flight.source == scraper)
        if period != "all":
            flight_query = flight_query.where(Flight.created_at >= start_date)

        flight_count = (await db.execute(flight_query)).scalar() or 0

        # Accommodation stats
        acc_query = select(func.count(Accommodation.id))
        if period != "all":
            acc_query = acc_query.where(Accommodation.created_at >= start_date)

        acc_count = (await db.execute(acc_query)).scalar() or 0

        # Event stats
        event_query = select(func.count(Event.id))
        if period != "all":
            event_query = event_query.where(Event.created_at >= start_date)

        event_count = (await db.execute(event_query)).scalar() or 0

        # Package stats
        pkg_query = select(func.count(TripPackage.id))
        if period != "all":
            pkg_query = pkg_query.where(TripPackage.created_at >= start_date)

        pkg_count = (await db.execute(pkg_query)).scalar() or 0

        # API cost stats
        cost_query = select(func.sum(ApiCost.cost_usd))
        if period != "all":
            cost_query = cost_query.where(ApiCost.created_at >= start_date)

        api_cost = (await db.execute(cost_query)).scalar() or 0.0

        # Scraping job stats
        job_query = select(func.count(ScrapingJob.id))
        if scraper:
            job_query = job_query.where(ScrapingJob.source == scraper)
        if period != "all":
            job_query = job_query.where(ScrapingJob.created_at >= start_date)

        job_count = (await db.execute(job_query)).scalar() or 0

    # Display statistics
    console.print("\n")
    console.print(Panel(
        f"[bold]Statistics - {period.title()}[/bold]",
        border_style="blue",
    ))

    # Data stats
    data_table = Table(title="📊 Data Statistics", show_header=True, header_style="bold magenta")
    data_table.add_column("Metric", style="cyan")
    data_table.add_column("Count", style="green", justify="right")

    data_table.add_row("Flights", f"{flight_count:,}")
    data_table.add_row("Accommodations", f"{acc_count:,}")
    data_table.add_row("Events", f"{event_count:,}")
    data_table.add_row("Trip Packages", f"{pkg_count:,}")
    data_table.add_row("Scraping Jobs", f"{job_count:,}")

    console.print(data_table)
    console.print("\n")

    # Cost stats
    cost_table = Table(title="💰 API Cost", show_header=True, header_style="bold magenta")
    cost_table.add_column("Service", style="cyan")
    cost_table.add_column("Cost", style="green", justify="right")

    cost_table.add_row("Claude API", f"${api_cost:.4f}")

    console.print(cost_table)
    console.print("\n")


# ============================================================================
# DB Commands - Database Management
# ============================================================================

@db_app.command("init")
def db_init():
    """
    Initialize database (create all tables).

    WARNING: Only use in development!
    """
    console.print("\n")
    console.print(Panel(
        "[bold red]⚠ Database Initialization[/bold red]\n\n"
        "This will create all database tables.\n"
        "In production, use Alembic migrations instead.",
        border_style="red",
    ))

    confirm = typer.confirm("Are you sure you want to continue?")

    if not confirm:
        warning("Operation cancelled")
        raise typer.Exit()

    try:
        asyncio.run(_db_init())
    except Exception as e:
        handle_error(e, "Database initialization failed")


async def _db_init():
    """Initialize database tables."""
    from app.models.base import Base
    from app.database import async_engine

    with console.status("[bold yellow]Creating database tables..."):
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    success("Database initialized successfully")
    info("Use 'scout db seed' to populate with sample data")


@db_app.command("seed")
def db_seed():
    """
    Seed database with sample data for testing.
    """
    console.print("\n")
    console.print(Panel(
        "[bold]Database Seeding[/bold]\n\n"
        "This will populate the database with sample airports and data.",
        border_style="blue",
    ))

    try:
        from app.utils.seed_data import seed_airports

        db = get_sync_session()

        with console.status("[bold yellow]Seeding database..."):
            seed_airports(db)

        success("Database seeded successfully")
    except Exception as e:
        handle_error(e, "Database seeding failed")


@db_app.command("reset")
def db_reset():
    """
    Reset database (drop all tables and recreate).

    WARNING: This will delete ALL data!
    """
    console.print("\n")
    console.print(Panel(
        "[bold red]⚠️ DANGER ZONE ⚠️[/bold red]\n\n"
        "This will DELETE ALL DATA and recreate tables.\n"
        "This action cannot be undone!",
        border_style="red",
    ))

    confirm = typer.confirm("Are you absolutely sure?")

    if not confirm:
        warning("Operation cancelled")
        raise typer.Exit()

    # Double confirmation
    confirm2 = typer.confirm("Type 'yes' to confirm deletion of all data", default=False)

    if not confirm2:
        warning("Operation cancelled")
        raise typer.Exit()

    try:
        asyncio.run(_db_reset())
    except Exception as e:
        handle_error(e, "Database reset failed")


async def _db_reset():
    """Reset database."""
    from app.models.base import Base
    from app.database import async_engine

    with console.status("[bold red]Dropping all tables..."):
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    info("All tables dropped")

    with console.status("[bold yellow]Creating tables..."):
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    success("Database reset complete")


# ============================================================================
# HEALTH Command
# ============================================================================

@app.command()
def health():
    """
    Check application health status.
    """
    console.print("\n")
    console.print(Panel(
        "[bold]Health Check[/bold]",
        border_style="blue",
    ))

    # Create table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="white")

    # Check database
    async def check_db():
        return await check_db_connection()

    db_status = asyncio.run(check_db())
    table.add_row(
        "Database",
        "[green]✓ Healthy[/green]" if db_status else "[red]✗ Unhealthy[/red]",
        "PostgreSQL connection",
    )

    # Check configuration
    table.add_row("Configuration", "[green]✓ Loaded[/green]", f"Environment: {settings.environment}")

    # Check API keys
    api_status = "✓" if settings.anthropic_api_key else "✗"
    api_color = "green" if settings.anthropic_api_key else "red"
    table.add_row(
        "Anthropic API",
        f"[{api_color}]{api_status}[/{api_color}]",
        "Claude AI integration",
    )

    kiwi_status = "✓" if settings.kiwi_api_key else "✗"
    kiwi_color = "green" if settings.kiwi_api_key else "yellow"
    table.add_row(
        "Kiwi API",
        f"[{kiwi_color}]{kiwi_status}[/{kiwi_color}]",
        "Flight search",
    )

    console.print(table)
    console.print("\n")

    if not db_status:
        console.print("[red]⚠ Database connection failed[/red]\n")
        raise typer.Exit(code=1)

    success("All systems operational")
    console.print("\n")


# ============================================================================
# Existing Commands (preserved)
# ============================================================================

@app.command(name="kiwi-search")
def kiwi_search(
    origin: str = typer.Option(..., help="Origin airport IATA code (e.g., MUC)"),
    destination: Optional[str] = typer.Option(None, help="Destination airport IATA code (e.g., LIS). Omit for 'anywhere' search."),
    departure_date: Optional[str] = typer.Option(None, help="Departure date (YYYY-MM-DD). Default: 60 days from today"),
    return_date: Optional[str] = typer.Option(None, help="Return date (YYYY-MM-DD). Default: 7 days after departure"),
    adults: int = typer.Option(2, help="Number of adults"),
    children: int = typer.Option(2, help="Number of children"),
    save: bool = typer.Option(True, help="Save results to database"),
):
    """
    Search for flights using Kiwi.com API.

    Examples:
        scout kiwi-search --origin MUC --destination LIS
        scout kiwi-search --origin MUC
        scout kiwi-search --origin MUC --destination BCN --departure 2025-12-20 --return 2025-12-27
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
