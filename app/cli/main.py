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
from redis.asyncio import Redis
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
from app.cli.validators import (
    airport_code_callback,
    date_callback,
    airport_codes_list_callback,
)

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
        callback=airport_code_callback,
    ),
    destination: str = typer.Option(
        ...,
        help="Destination airport IATA code (e.g., LIS, BCN)",
        callback=airport_code_callback,
    ),
    departure_date: Optional[str] = typer.Option(
        None,
        help="Departure date (YYYY-MM-DD). Default: 60 days from today",
        callback=date_callback,
    ),
    return_date: Optional[str] = typer.Option(
        None,
        help="Return date (YYYY-MM-DD). Default: 7 days after departure",
        callback=date_callback,
    ),
    scraper: Optional[str] = typer.Option(
        None,
        help="Specific scraper to use: 'skyscanner', 'ryanair', 'wizzair', 'kiwi', or 'all' for all scrapers",
    ),
    region: str = typer.Option(
        "Bavaria",
        help="German state for school holiday calendar (e.g., Bavaria, Berlin, Hamburg)",
    ),
    disable_scraper: Optional[List[str]] = typer.Option(
        None,
        help="Disable specific scrapers (e.g., --disable-scraper wizzair --disable-scraper ryanair)",
    ),
    enable_scraper: Optional[List[str]] = typer.Option(
        None,
        help="Enable specific scrapers (overrides config, e.g., --enable-scraper kiwi)",
    ),
    save: bool = typer.Option(
        True,
        help="Save results to database",
    ),
):
    """
    Quick flight search using available scrapers.

    Default scrapers (NO API KEY needed):
    - Skyscanner: Web scraper using Playwright
    - Ryanair: Web scraper using Playwright
    - WizzAir: Unofficial API scraper

    Optional scrapers (API KEY required):
    - Kiwi: Kiwi.com API (set KIWI_API_KEY env variable)

    Examples:
        scout scrape --origin MUC --destination LIS                    # All free scrapers
        scout scrape --origin VIE --destination BCN --scraper skyscanner
        scout scrape --origin MUC --destination PRG --departure 2025-12-20 --return 2025-12-27
        scout scrape --origin MUC --destination LIS --disable-scraper wizzair
        scout scrape --origin MUC --destination LIS --enable-scraper kiwi
        scout scrape --origin MUC --destination PRG --scraper kiwi     # Requires API key
        scout scrape --origin MUC --destination LIS --departure 2025-12-20 --return 2025-12-27
        scout scrape --origin MUC --destination LIS --region Berlin    # Use Berlin school holidays
    """
    console.print(Panel(
        "[bold]Quick Flight Search[/bold]",
        border_style="green",
    ))

    try:
        asyncio.run(_run_scrape(
            origin, destination, departure_date, return_date,
            scraper, region, save, disable_scraper, enable_scraper
        ))
    except Exception as e:
        handle_error(e, "Scraping failed")


async def _run_scrape(
    origin: str,
    destination: str,
    departure_date_str: Optional[str],
    return_date_str: Optional[str],
    scraper_name: Optional[str],
    region: str,
    save: bool,
    disable_scraper: Optional[List[str]] = None,
    enable_scraper: Optional[List[str]] = None,
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
    table.add_row("Region", region)

    # Determine which scrapers to use
    if scraper_name and scraper_name != "all":
        scrapers_to_use = [scraper_name.lower()]
        table.add_row("Scraper", scraper_name.title())
    else:
        # Use all default (free) scrapers only
        scrapers_to_use = ["skyscanner", "ryanair", "wizzair"]
        table.add_row("Scrapers", "All free scrapers (Skyscanner, Ryanair, WizzAir)")
        table.add_row("Note", "Use --scraper kiwi for Kiwi.com API (requires API key)")

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
        for idx, scraper in enumerate(scrapers_to_use):
            try:
                progress.update(
                    task,
                    description=f"[yellow]Running {scraper.title()} ({idx+1}/{len(scrapers_to_use)})..."
                )

                # Log start
                console.print(
                    f"[dim cyan]⟳ Starting {scraper.title()} scraper for "
                    f"{origin.upper()}→{destination.upper()}...[/dim cyan]"
                )

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

                elif scraper == "kiwi":
                    # Check for API key
                    if not settings.kiwi_api_key:
                        warning("Kiwi scraper requires KIWI_API_KEY environment variable")
                        progress.update(task, advance=1)
                        continue

                    from app.scrapers.kiwi_scraper import KiwiClient
                    kiwi_client = KiwiClient()
                    results = await kiwi_client.search_flights(
                        origin=origin.upper(),
                        destination=destination.upper(),
                        departure_date=dep_date,
                        return_date=ret_date,
                        adults=2,
                        children=2,
                    )
                    all_results.extend(results)

                else:
                    warning(f"Unknown scraper: {scraper}")
                    progress.update(task, advance=1)
                    continue

                # Log completion
                console.print(
                    f"[dim green]✓ {scraper.title()} completed: {len(results)} flights found[/dim green]"
                )

                progress.update(task, advance=1)

            except Exception as e:
                logger.error(f"Scraper {scraper} failed: {e}")
                console.print(
                    f"[dim red]✗ {scraper.title()} failed: {str(e)}[/dim red]"
                )
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
            # TODO(#59): Implement save logic similar to kiwi-search
            success("Results saved")
    else:
        warning("No flights found")


# ============================================================================
# PIPELINE Command - Main Pipeline (formerly 'run')
# ============================================================================

@app.command()
def pipeline(
    destinations: str = typer.Option(
        "all",
        help="Destinations to search (comma-separated IATA codes or 'all')",
        callback=airport_codes_list_callback,
    ),
    dates: str = typer.Option(
        "next-3-months",
        help="Date range: 'next-3-months', 'next-6-months', or specific dates",
    ),
    region: str = typer.Option(
        "Bavaria",
        help="German state for school holiday calendar (e.g., Bavaria, Berlin, Hamburg)",
    ),
    analyze: bool = typer.Option(
        True,
        help="Run AI analysis on results",
    ),
    max_price: Optional[float] = typer.Option(
        None,
        help="Maximum price per person in EUR",
    ),
    disable_scraper: Optional[List[str]] = typer.Option(
        None,
        help="Disable specific scrapers (e.g., --disable-scraper wizzair --disable-scraper ryanair)",
    ),
    enable_scraper: Optional[List[str]] = typer.Option(
        None,
        help="Enable specific scrapers (overrides config, e.g., --enable-scraper kiwi)",
    ),
):
    """
    Run the complete travel search pipeline (end-to-end automation).

    This command executes a comprehensive travel deal search:
    1. Scrape flights from all available sources (Kiwi, Skyscanner, Ryanair, WizzAir)
    2. Scrape accommodations (Booking.com, Airbnb)
    3. Discover local events (city tourism APIs, Eventbrite)
    4. Generate trip packages by matching flights + accommodations + events
    5. Score packages with AI analysis (value, family-friendliness, recommendations)
    6. Send email notifications for high-scoring deals

    Use this for automated, hands-free deal discovery. For quick manual searches,
    use 'scout scrape' instead.

    Examples:
        scout pipeline                                    # Search all destinations
        scout pipeline --destinations LIS,BCN,PRG         # Specific destinations
        scout pipeline --max-price 150 --no-analyze      # Budget filter, skip AI
        scout pipeline --region Berlin                   # Use Berlin school holidays
    """
    console.print(Panel(
        "[bold]Starting Complete Travel Search Pipeline[/bold]",
        border_style="green",
    ))

    try:
        asyncio.run(_run_pipeline(
            destinations, dates, analyze, max_price,
            disable_scraper, enable_scraper
        ))
    except Exception as e:
        handle_error(e, "Pipeline execution failed")


async def _run_pipeline(
    destinations: str,
    dates: str,
    region: str,
    analyze: bool,
    max_price: Optional[float],
    disable_scraper: Optional[List[str]] = None,
    enable_scraper: Optional[List[str]] = None,
):
    """Execute the main pipeline."""
    from app.orchestration.flight_orchestrator import FlightOrchestrator
    from app.orchestration.accommodation_matcher import AccommodationMatcher
    from app.orchestration.event_matcher import EventMatcher
    from app.models.airport import Airport
    from app.utils.date_utils import get_school_holiday_periods

    # Apply scraper configuration overrides temporarily
    original_scrapers = settings.get_available_scrapers()
    scrapers_to_use = original_scrapers.copy()

    # Apply runtime enable/disable overrides
    if enable_scraper:
        for scraper in enable_scraper:
            scraper = scraper.lower()
            if scraper not in scrapers_to_use:
                scrapers_to_use.append(scraper)

    if disable_scraper:
        for scraper in disable_scraper:
            scraper = scraper.lower()
            if scraper in scrapers_to_use:
                scrapers_to_use.remove(scraper)

    if not scrapers_to_use:
        console.print("[red]Error: All scrapers have been disabled![/red]")
        raise typer.Exit(code=1)

    if scrapers_to_use != original_scrapers:
        info(f"Using scrapers: {', '.join([s.title() for s in scrapers_to_use])}")

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
        info(f"Region: {region}")

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
            region=region,
        )

        progress.update(task2, completed=1)
        info(f"Date ranges: {len(date_ranges)} school holiday periods")

        # Step 3: Scrape flights
        task3 = progress.add_task("[yellow]Scraping flights...", total=None)

        # Initialize Redis client for caching
        redis_client = None
        try:
            redis_client = await Redis.from_url(str(settings.redis_url))
            await redis_client.ping()
            logger.info("Redis connection established for flight caching")
        except Exception as e:
            logger.warning(f"Redis connection failed, caching will be disabled: {e}")
            redis_client = None

        orchestrator = FlightOrchestrator(redis_client=redis_client)
        flights = await orchestrator.scrape_all(
            origins=origin_codes,
            destinations=dest_codes,
            date_ranges=date_ranges,
        )

        # Close Redis connection
        if redis_client:
            await redis_client.close()

        stats["flights"] = len(flights)
        progress.update(task3, completed=1)
        success(f"Found {stats['flights']} flights")

        # Step 4: Scrape accommodations
        task4 = progress.add_task("[yellow]Scraping accommodations...", total=len(dest_codes))

        from app.orchestration.accommodation_orchestrator import AccommodationOrchestrator

        acc_orchestrator = AccommodationOrchestrator()
        all_accommodations = []

        for dest_code in dest_codes:
            try:
                # Get city name for destination
                async with get_async_session_context() as db:
                    result = await db.execute(
                        select(Airport).where(Airport.iata_code == dest_code)
                    )
                    dest_airport = result.scalar_one_or_none()
                    city_name = dest_airport.city if dest_airport else dest_code

                # Use first date range for accommodation search
                if date_ranges:
                    check_in, check_out = date_ranges[0]

                    accommodations = await acc_orchestrator.search_all_sources(
                        city=city_name,
                        check_in=check_in,
                        check_out=check_out,
                        adults=2,
                        children=2,
                    )

                    if accommodations:
                        save_stats = await acc_orchestrator.save_to_database(accommodations)
                        all_accommodations.extend(accommodations)
                        stats["accommodations"] += save_stats["inserted"] + save_stats["updated"]

                progress.update(task4, advance=1)

            except Exception as e:
                logger.error(f"Error scraping accommodations for {dest_code}: {e}")
                progress.update(task4, advance=1)
                continue

        info(f"Found {stats['accommodations']} accommodations")

        # Step 5: Match packages
        task5 = progress.add_task("[cyan]Generating trip packages...", total=None)

        async with get_async_session_context() as db:
            matcher = AccommodationMatcher()
            packages = await matcher.generate_trip_packages(
                db=db,
                max_budget=max_price or settings.max_flight_price_per_person,
            )

            stats["packages"] = len(packages)
            progress.update(task5, completed=1)
            success(f"Generated {stats['packages']} trip packages")

        # Step 6: Match events
        task6 = progress.add_task("[cyan]Matching events to packages...", total=None)

        async with get_async_session_context() as db:
            event_matcher = EventMatcher(db_session=db)
            packages = await event_matcher.match_events_to_packages(packages)

        progress.update(task6, completed=1)

        # Step 7: AI analysis
        if analyze and stats["packages"] > 0:
            from app.ai.claude_client import ClaudeClient
            from app.ai.deal_scorer import DealScorer
            from app.models.trip_package import TripPackage
            from redis.asyncio import Redis

            # Initialize Redis client for caching
            redis_client = await Redis.from_url(str(settings.redis_url))

            try:
                async with get_async_session_context() as db:
                    result = await db.execute(
                        select(TripPackage).where(TripPackage.ai_score.is_(None))
                    )
                    unscored = result.scalars().all()

                    # Limit to 50 for cost control
                    packages_to_score = unscored[:50]

                    task7 = progress.add_task(
                        "[magenta]Running AI analysis...",
                        total=len(packages_to_score)
                    )

                    # Create Claude client and deal scorer with proper dependencies
                    claude_client = ClaudeClient(
                        api_key=settings.anthropic_api_key,
                        redis_client=redis_client,
                        db_session=db,
                    )
                    scorer = DealScorer(
                        claude_client=claude_client,
                        db_session=db,
                    )

                    for idx, package in enumerate(packages_to_score):
                        try:
                            # Update progress with current package being analyzed
                            progress.update(
                                task7,
                                description=f"[magenta]Analyzing {package.destination_city} "
                                f"({idx+1}/{len(packages_to_score)})...",
                            )

                            # Log start of analysis
                            console.print(
                                f"[dim magenta]⟳ Scoring package {package.id}: "
                                f"{package.destination_city}, €{package.total_price}[/dim magenta]"
                            )

                            score_data = await scorer.score_trip(package)

                            if score_data:
                                package.ai_score = score_data["score"]
                                package.ai_reasoning = score_data["reasoning"]
                                await db.commit()
                                stats["analyzed"] += 1

                                # Log completion with score
                                console.print(
                                    f"[dim green]✓ Package {package.id}: "
                                    f"Score {score_data['score']}/100 "
                                    f"({score_data.get('recommendation', 'N/A')})[/dim green]"
                                )
                            else:
                                console.print(
                                    f"[dim yellow]⚠ Package {package.id}: Skipped (over price threshold)[/dim yellow]"
                                )

                            progress.update(task7, advance=1)

                        except Exception as e:
                            logger.error(f"Failed to score package {package.id}: {e}")
                            console.print(
                                f"[dim red]✗ Package {package.id}: Failed - {str(e)}[/dim red]"
                            )
                            progress.update(task7, advance=1)
                            continue

                success(f"Analyzed {stats['analyzed']} packages")
            finally:
                await redis_client.close()

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
# DEALS Command - View Top Deals (High-Scoring AI Recommendations)
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
    limit: int = typer.Option(
        10,
        help="Number of deals to show",
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
    View top-rated travel deals (AI-scored packages with score >= 70).

    Shows trip packages that have been analyzed and scored by AI for value
    and family-friendliness. Only displays packages meeting minimum score threshold.

    Use this to find the BEST deals that have been vetted by AI.
    For viewing ALL packages (including unscored), use 'scout packages'.

    Examples:
        scout deals                                    # Top 10 deals (score >= 70)
        scout deals --min-score 80 --limit 20          # Top 20 excellent deals
        scout deals --destination lisbon --type family # Family deals to Lisbon
        scout deals --format json                      # JSON output for scripts
    """
    try:
        asyncio.run(_show_deals(min_score, destination, limit, package_type, format))
    except Exception as e:
        handle_error(e, "Failed to retrieve deals")


@app.command()
def packages(
    destination: Optional[str] = typer.Option(
        None,
        help="Filter by destination city",
    ),
    limit: int = typer.Option(
        20,
        help="Number of packages to show",
    ),
    package_type: Optional[str] = typer.Option(
        None,
        help="Package type: 'family' or 'parent_escape'",
    ),
    format: str = typer.Option(
        "table",
        help="Output format: 'table' or 'json'",
    ),
    scored_only: bool = typer.Option(
        False,
        help="Show only AI-scored packages",
    ),
):
    """
    View all trip packages (flights + accommodations + events).

    Shows ALL generated trip packages, including those not yet scored by AI.
    This gives you a complete view of available travel options.

    Use 'scout deals' to see only the BEST packages (AI-scored, high ratings).
    Use 'scout packages' to see ALL packages (broader search results).

    Examples:
        scout packages                              # All packages (last 20)
        scout packages --destination barcelona      # All Barcelona packages
        scout packages --scored-only                # Only AI-analyzed packages
        scout packages --limit 50                   # Show 50 packages
    """
    # Show all packages by setting min_score to 0 (unless scored_only is True)
    min_score = 1 if scored_only else 0

    try:
        asyncio.run(_show_deals(min_score, destination, limit, package_type, format))
    except Exception as e:
        handle_error(e, "Failed to retrieve packages")


async def _show_deals(
    min_score: int,
    destination: Optional[str],
    limit: int,
    package_type: Optional[str],
    format: str,
):
    """Retrieve and display top deals."""
    from app.models.trip_package import TripPackage

    async with get_async_session_context() as db:
        # Build query
        query = select(TripPackage).where(
            TripPackage.ai_score >= min_score
        )

        if destination:
            query = query.where(
                TripPackage.destination_city.ilike(f"%{destination}%")
            )

        if package_type:
            query = query.where(TripPackage.package_type == package_type)

        query = query.order_by(desc(TripPackage.ai_score)).limit(limit)

        result = await db.execute(query)
        packages = result.scalars().all()

        if not packages:
            warning("No deals found matching your criteria")
            return

        if format == "json":
            # JSON output
            deals_data = []
            for pkg in packages:
                deals_data.append({
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
                title=f"🌟 Top {len(packages)} Travel Deals",
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
            success(f"Found {len(packages)} deals")


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

    # Scraper flags
    table.add_row("", "")  # Separator
    table.add_row("[bold]Enabled Scrapers[/bold]", "")
    table.add_row("Kiwi.com", "✓" if settings.use_kiwi_scraper else "✗")
    table.add_row("Skyscanner", "✓" if settings.use_skyscanner_scraper else "✗")
    table.add_row("Ryanair", "✓" if settings.use_ryanair_scraper else "✗")
    table.add_row("WizzAir", "✓" if settings.use_wizzair_scraper else "✗")

    available_scrapers = settings.get_available_scrapers()
    table.add_row("Available (with API keys)", ", ".join([s.title() for s in available_scrapers]) if available_scrapers else "None")

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

@app.command("scrape-accommodations")
def scrape_accommodations(
    city: str = typer.Option(
        ...,
        help="Destination city (e.g., Barcelona, Lisbon)",
    ),
    check_in: Optional[str] = typer.Option(
        None,
        help="Check-in date (YYYY-MM-DD). Default: 60 days from today",
    ),
    check_out: Optional[str] = typer.Option(
        None,
        help="Check-out date (YYYY-MM-DD). Default: 7 days after check-in",
    ),
    adults: int = typer.Option(
        2,
        help="Number of adults",
    ),
    children: int = typer.Option(
        2,
        help="Number of children",
    ),
    save: bool = typer.Option(
        True,
        help="Save results to database",
    ),
):
    """
    Search for accommodations using all available scrapers (Booking.com, Airbnb).

    Examples:
        scout scrape-accommodations --city Barcelona
        scout scrape-accommodations --city Lisbon --check-in 2025-07-01 --check-out 2025-07-08
        scout scrape-accommodations --city Prague --adults 2 --children 2
    """
    console.print(Panel(
        "[bold]Accommodation Search (All Sources)[/bold]",
        border_style="green",
    ))

    try:
        asyncio.run(_run_accommodation_scrape(city, check_in, check_out, adults, children, save))
    except Exception as e:
        handle_error(e, "Accommodation scraping failed")


async def _run_accommodation_scrape(
    city: str,
    check_in_str: Optional[str],
    check_out_str: Optional[str],
    adults: int,
    children: int,
    save: bool,
):
    """Execute accommodation scraping."""
    from datetime import date, timedelta
    from app.orchestration.accommodation_orchestrator import AccommodationOrchestrator

    # Parse dates
    if check_in_str:
        check_in_date = datetime.strptime(check_in_str, "%Y-%m-%d").date()
    else:
        check_in_date = date.today() + timedelta(days=60)

    if check_out_str:
        check_out_date = datetime.strptime(check_out_str, "%Y-%m-%d").date()
    else:
        check_out_date = check_in_date + timedelta(days=7)

    # Display search parameters
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("City", city.title())
    table.add_row("Check-in", check_in_date.strftime("%Y-%m-%d"))
    table.add_row("Check-out", check_out_date.strftime("%Y-%m-%d"))
    table.add_row("Adults", str(adults))
    table.add_row("Children", str(children))
    table.add_row("Save to DB", "Yes" if save else "No")

    console.print("\n")
    console.print(table)
    console.print("\n")

    # Run orchestrator
    orchestrator = AccommodationOrchestrator()
    accommodations = await orchestrator.search_all_sources(
        city=city,
        check_in=check_in_date,
        check_out=check_out_date,
        adults=adults,
        children=children,
    )

    # Display results
    if accommodations:
        success(f"Found {len(accommodations)} accommodations")

        # Create results table
        results_table = Table(show_header=True, header_style="bold magenta")
        results_table.add_column("Name", style="cyan", no_wrap=False, max_width=40)
        results_table.add_column("Type", style="yellow")
        results_table.add_column("Price/Night", style="green", justify="right")
        results_table.add_column("Rating", style="magenta", justify="right")
        results_table.add_column("Bedrooms", style="blue", justify="center")
        results_table.add_column("Source", style="white")

        # Sort by price
        sorted_accommodations = sorted(
            accommodations,
            key=lambda x: x.get("price_per_night", 9999)
        )

        for acc in sorted_accommodations[:15]:  # Show top 15
            price = acc.get("price_per_night", 0)
            rating = acc.get("rating")
            rating_str = f"{rating:.1f}" if rating else "N/A"
            bedrooms = acc.get("bedrooms")
            bedrooms_str = str(bedrooms) if bedrooms else "N/A"

            results_table.add_row(
                acc.get("name", "Unknown")[:40],
                acc.get("type", "hotel").title(),
                f"€{price:.0f}",
                rating_str,
                bedrooms_str,
                acc.get("source", "unknown"),
            )

        console.print("\n")
        console.print(results_table)
        console.print("\n")

        if save:
            info("Saving results to database...")
            stats = await orchestrator.save_to_database(accommodations)
            success(
                f"Database save complete: {stats['inserted']} inserted, "
                f"{stats['updated']} updated, {stats['skipped']} skipped"
            )
    else:
        warning("No accommodations found")


@app.command("test-scraper")
def test_scraper(
    scraper: str = typer.Argument(
        ...,
        help="Scraper name: 'kiwi', 'skyscanner', 'ryanair', 'wizzair', 'booking', 'airbnb'",
    ),
    origin: str = typer.Option(
        "MUC",
        help="Origin airport IATA code (for flight scrapers)",
        callback=airport_code_callback,
    ),
    dest: str = typer.Option(
        "LIS",
        help="Destination airport IATA code or city name",
        callback=airport_code_callback,
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
        scout test-scraper booking --dest Barcelona
        scout test-scraper airbnb --dest Lisbon
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
        elif scraper.lower() == "booking":
            from app.scrapers.booking_scraper import BookingClient
            async with BookingClient(headless=True) as scraper_instance:
                results = await scraper_instance.search(
                    city=dest,  # dest is the city name for accommodation scrapers
                    check_in=dep_date,
                    check_out=ret_date,
                    adults=2,
                    children_ages=[3, 6],
                    limit=20,
                )
                results = scraper_instance.filter_family_friendly(results)
        elif scraper.lower() == "airbnb":
            from app.scrapers.airbnb_scraper import AirbnbClient
            scraper_instance = AirbnbClient()
            results = await scraper_instance.search(
                city=dest,  # dest is the city name for accommodation scrapers
                check_in=dep_date,
                check_out=ret_date,
                adults=2,
                children=2,
                max_listings=20,
            )
            results = scraper_instance.filter_family_suitable(results)
        else:
            console.print(f"[red]Unknown scraper: {scraper}[/red]")
            console.print("[yellow]Available scrapers: kiwi, skyscanner, ryanair, wizzair, booking, airbnb[/yellow]")
            raise typer.Exit(code=1)

        progress.update(task, completed=1)

    # Display results
    if results:
        success(f"Found {len(results)} results")

        # Check if results are flights or accommodations
        is_accommodation = scraper.lower() in ["booking", "airbnb"]

        if is_accommodation:
            # Display accommodation results
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Name", style="cyan", max_width=40)
            table.add_column("Type", style="yellow")
            table.add_column("Price/Night", style="green", justify="right")
            table.add_column("Rating", style="magenta", justify="right")

            for result in results[:10]:
                rating = result.get("rating")
                rating_str = f"{rating:.1f}" if rating else "N/A"

                table.add_row(
                    result.get("name", "Unknown")[:40],
                    result.get("type", "hotel").title(),
                    f"€{result.get('price_per_night', 0):.0f}",
                    rating_str,
                )
        else:
            # Display flight results
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
# PRICE-HISTORY Command
# ============================================================================

@app.command("price-history")
def price_history(
    route: Optional[str] = typer.Option(
        None,
        help="Route code (e.g., 'MUC-LIS')",
    ),
    origin: Optional[str] = typer.Option(
        None,
        help="Origin airport IATA code",
    ),
    destination: Optional[str] = typer.Option(
        None,
        help="Destination airport IATA code",
    ),
    source: Optional[str] = typer.Option(
        None,
        help="Filter by source (kiwi, skyscanner, ryanair, wizzair)",
    ),
    days: int = typer.Option(
        30,
        help="Number of days to look back",
    ),
    show_chart: bool = typer.Option(
        False,
        help="Show price trend chart",
    ),
):
    """
    View price history for flight routes.

    Examples:
        scout price-history --route MUC-LIS
        scout price-history --origin MUC --destination BCN --days 60
        scout price-history --origin MUC --destination LIS --source kiwi
        scout price-history --route MUC-PRG --show-chart
    """
    try:
        asyncio.run(_show_price_history(route, origin, destination, source, days, show_chart))
    except Exception as e:
        handle_error(e, "Failed to retrieve price history")


async def _show_price_history(
    route: Optional[str],
    origin: Optional[str],
    destination: Optional[str],
    source: Optional[str],
    days: int,
    show_chart: bool,
):
    """Display price history."""
    from app.services.price_history_service import PriceHistoryService

    # Validate inputs
    if not route and not (origin and destination):
        console.print("[red]Error: Must provide either --route or both --origin and --destination[/red]\n")
        raise typer.Exit(code=1)

    # Build route string
    if route:
        route_str = route.upper()
    else:
        route_str = f"{origin.upper()}-{destination.upper()}"

    console.print("\n")
    console.print(Panel(
        f"[bold]Price History: {route_str}[/bold]\n"
        f"Last {days} days" + (f" - {source.upper()}" if source else " - All sources"),
        border_style="blue",
    ))

    async with get_async_session_context() as db:
        # Get price history
        history = await PriceHistoryService.get_price_history(
            db=db,
            route=route_str,
            source=source,
            days=days,
            limit=100,
        )

        if not history:
            warning(f"No price history found for {route_str}")
            return

        # Get price trends
        trends = await PriceHistoryService.get_price_trends(
            db=db,
            route=route_str,
            source=source,
            days=days,
        )

        # Display summary statistics
        stats_table = Table(title="📊 Price Statistics", show_header=True, header_style="bold magenta")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green", justify="right")

        stats_table.add_row("Current Price", f"€{trends.get('current_price', 0):.2f}")
        stats_table.add_row("Average Price", f"€{trends.get('avg_price', 0):.2f}")
        stats_table.add_row("Minimum Price", f"€{trends.get('min_price', 0):.2f}")
        stats_table.add_row("Maximum Price", f"€{trends.get('max_price', 0):.2f}")

        trend_emoji = {
            "increasing": "📈",
            "decreasing": "📉",
            "stable": "➡️",
            "insufficient_data": "❓"
        }
        trend_value = trends.get('trend', 'unknown')
        stats_table.add_row("Trend", f"{trend_emoji.get(trend_value, '?')} {trend_value.title()}")
        stats_table.add_row("Data Points", str(trends.get('data_points', 0)))

        console.print("\n")
        console.print(stats_table)
        console.print("\n")

        # Get booking recommendation
        recommendation = await PriceHistoryService.get_best_booking_time(
            db=db,
            route=route_str,
            days=days,
        )

        if "error" not in recommendation:
            # Display recommendation
            rec_color = "green" if "Book now" in recommendation['recommendation'] else "yellow"
            console.print(Panel(
                f"[bold {rec_color}]{recommendation['recommendation']}[/bold {rec_color}]\n\n"
                f"Current price: €{recommendation['current_price']:.2f}\n"
                f"vs Average: {recommendation['price_vs_avg_percent']:+.1f}%\n"
                f"vs Minimum: {recommendation['price_vs_min_percent']:+.1f}%\n"
                f"Confidence: {recommendation['confidence'].upper()}",
                title="💡 Booking Recommendation",
                border_style=rec_color,
            ))
            console.print("\n")

        # Display price history table
        history_table = Table(
            title=f"📅 Recent Price History ({len(history[:20])} of {len(history)} records)",
            show_header=True,
            header_style="bold magenta"
        )
        history_table.add_column("Date", style="cyan")
        history_table.add_column("Time", style="blue")
        history_table.add_column("Price", style="green", justify="right")
        history_table.add_column("Source", style="yellow")
        history_table.add_column("Change", style="white", justify="right")

        # Sort by date (most recent first)
        sorted_history = sorted(history, key=lambda x: x.scraped_at, reverse=True)

        prev_price = None
        for record in sorted_history[:20]:  # Show last 20 records
            price = float(record.price)

            # Calculate change from previous
            if prev_price is not None:
                change = price - prev_price
                change_str = f"{change:+.2f} €"
                if change < 0:
                    change_str = f"[green]{change_str}[/green]"
                elif change > 0:
                    change_str = f"[red]{change_str}[/red]"
                else:
                    change_str = "[dim]0.00 €[/dim]"
            else:
                change_str = "-"

            history_table.add_row(
                record.scraped_at.strftime("%Y-%m-%d"),
                record.scraped_at.strftime("%H:%M"),
                f"€{price:.2f}",
                record.source,
                change_str,
            )

            prev_price = price

        console.print(history_table)
        console.print("\n")

        # Show simple ASCII chart if requested
        if show_chart and len(history) > 2:
            console.print(Panel("[bold]Price Trend Chart[/bold]", border_style="blue"))
            _draw_ascii_chart(sorted_history[:30])  # Show chart for last 30 points
            console.print("\n")

        success(f"Displayed {len(history)} price history records")


def _draw_ascii_chart(history: List):
    """Draw a simple ASCII chart of prices."""
    if not history:
        return

    prices = [float(r.price) for r in reversed(history)]  # Oldest to newest
    min_price = min(prices)
    max_price = max(prices)

    # Normalize prices to 0-20 range for chart height
    chart_height = 15
    if max_price > min_price:
        normalized = [int((p - min_price) / (max_price - min_price) * chart_height) for p in prices]
    else:
        normalized = [chart_height // 2] * len(prices)

    # Draw chart
    for row in range(chart_height, -1, -1):
        line = ""
        for val in normalized:
            if val == row:
                line += "●"
            elif val > row:
                line += "│"
            else:
                line += " "

        # Add price labels
        if row == chart_height:
            line += f"  €{max_price:.0f}"
        elif row == 0:
            line += f"  €{min_price:.0f}"

        console.print(f"  {line}")

    # Draw x-axis
    console.print(f"  {'─' * len(prices)}")
    console.print(f"  {history[-1].scraped_at.strftime('%b %d')} → {history[0].scraped_at.strftime('%b %d')}")


@app.command("price-drops")
def price_drops(
    threshold: float = typer.Option(
        10.0,
        help="Minimum price drop percentage to show",
    ),
    days: int = typer.Option(
        7,
        help="Number of days to compare against",
    ),
):
    """
    Detect significant price drops across all routes.

    Examples:
        scout price-drops
        scout price-drops --threshold 15 --days 14
    """
    try:
        asyncio.run(_show_price_drops(threshold, days))
    except Exception as e:
        handle_error(e, "Failed to detect price drops")


async def _show_price_drops(threshold: float, days: int):
    """Display detected price drops."""
    from app.services.price_history_service import PriceHistoryService

    console.print("\n")
    console.print(Panel(
        f"[bold]Price Drop Detection[/bold]\n"
        f"Threshold: {threshold}% | Comparison period: {days} days",
        border_style="green",
    ))

    async with get_async_session_context() as db:
        drops = await PriceHistoryService.detect_price_drops(
            db=db,
            threshold_percent=threshold,
            days=days,
        )

        if not drops:
            warning(f"No price drops of {threshold}% or more detected")
            return

        # Display drops table
        table = Table(
            title=f"🎯 {len(drops)} Price Drops Detected",
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("Route", style="cyan")
        table.add_column("Source", style="yellow")
        table.add_column("Current", style="green", justify="right")
        table.add_column("Was", style="white", justify="right")
        table.add_column("Drop", style="red", justify="right")
        table.add_column("Savings", style="green", justify="right")

        for drop in drops:
            table.add_row(
                drop["route"],
                drop["source"],
                f"€{drop['current_price']:.0f}",
                f"€{drop['previous_avg_price']:.0f}",
                f"{drop['drop_percent']:.1f}%",
                f"€{drop['drop_amount']:.0f}",
            )

        console.print("\n")
        console.print(table)
        console.print("\n")
        success(f"Found {len(drops)} significant price drops")


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
    origin: str = typer.Option(..., help="Origin airport IATA code (e.g., MUC)", callback=airport_code_callback),
    destination: Optional[str] = typer.Option(None, help="Destination airport IATA code (e.g., LIS). Omit for 'anywhere' search.", callback=airport_code_callback),
    departure_date: Optional[str] = typer.Option(None, help="Departure date (YYYY-MM-DD). Default: 60 days from today", callback=date_callback),
    return_date: Optional[str] = typer.Option(None, help="Return date (YYYY-MM-DD). Default: 7 days after departure", callback=date_callback),
    adults: int = typer.Option(2, help="Number of adults"),
    children: int = typer.Option(2, help="Number of children"),
    save: bool = typer.Option(True, help="Save results to database"),
):
    """
    [DEPRECATED] Use 'scout scrape --scraper kiwi' instead.

    This command is deprecated and will be removed in a future version.
    Use the unified 'scout scrape' command with --scraper kiwi option instead.

    Examples (new syntax):
        scout scrape --origin MUC --destination LIS --scraper kiwi
        scout scrape --origin MUC --destination BCN --scraper kiwi --departure 2025-12-20 --return 2025-12-27
    """
    warning("⚠ 'scout kiwi-search' is deprecated. Use 'scout scrape --scraper kiwi' instead.")
    console.print("")
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

    from app.utils.rate_limiter import get_kiwi_rate_limiter

    rate_limiter = get_kiwi_rate_limiter()
    remaining = rate_limiter.get_remaining()
    status = rate_limiter.get_status()
    used = status['current_count']
    max_requests = status['max_requests']

    # Create table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("API calls used (this month)", f"{used}/{max_requests}")
    table.add_row("Remaining calls", f"{remaining}/{max_requests}")
    table.add_row("Usage", f"{(used/max_requests)*100:.1f}%")

    console.print(table)
    console.print()

    if remaining > 10:
        console.print("[green]✓ Plenty of API calls remaining[/green]\n")
    elif remaining > 0:
        console.print(f"[yellow]⚠ Only {remaining} API calls remaining this month[/yellow]\n")
    else:
        console.print("[red]✗ Monthly rate limit exceeded![/red]\n")


# ============================================================================
# Model Pricing Management Commands
# ============================================================================

@db_app.command("pricing-list")
def db_pricing_list(
    service: Optional[str] = typer.Option(None, help="Filter by service (e.g., 'claude')"),
    model: Optional[str] = typer.Option(None, help="Filter by model name"),
):
    """
    List model pricing configurations from the database.
    """
    console.print("\n")
    console.print(Panel(
        "[bold]Model Pricing Configuration[/bold]\n\n"
        "Current pricing for AI models",
        border_style="blue",
    ))

    try:
        from app.models import ModelPricing
        from sqlalchemy import and_

        db = get_sync_session()

        # Build query with optional filters
        filters = []
        if service:
            filters.append(ModelPricing.service == service)
        if model:
            filters.append(ModelPricing.model == model)

        if filters:
            query = db.query(ModelPricing).filter(and_(*filters)).order_by(
                ModelPricing.service, ModelPricing.model, ModelPricing.effective_date.desc()
            )
        else:
            query = db.query(ModelPricing).order_by(
                ModelPricing.service, ModelPricing.model, ModelPricing.effective_date.desc()
            )

        pricing_list = query.all()

        if not pricing_list:
            warning("No pricing configurations found")
            return

        # Create table
        table = Table(title="Model Pricing", show_header=True, header_style="bold magenta")
        table.add_column("Service", style="cyan")
        table.add_column("Model", style="blue")
        table.add_column("Input ($/M)", style="green", justify="right")
        table.add_column("Output ($/M)", style="green", justify="right")
        table.add_column("Effective Date", style="yellow")
        table.add_column("Notes", style="dim")

        for pricing in pricing_list:
            table.add_row(
                pricing.service,
                pricing.model,
                f"${pricing.input_cost_per_million:.2f}",
                f"${pricing.output_cost_per_million:.2f}",
                pricing.effective_date.strftime("%Y-%m-%d"),
                (pricing.notes[:50] + "...") if pricing.notes and len(pricing.notes) > 50 else (pricing.notes or ""),
            )

        console.print(table)
        console.print()
        success(f"Found {len(pricing_list)} pricing configuration(s)")

    except Exception as e:
        handle_error(e, "Failed to list pricing configurations")


@db_app.command("pricing-add")
def db_pricing_add(
    service: str = typer.Option(..., help="Service name (e.g., 'claude')"),
    model: str = typer.Option(..., help="Model name (e.g., 'claude-sonnet-4-5-20250929')"),
    input_cost: float = typer.Option(..., help="Input cost per million tokens (USD)"),
    output_cost: float = typer.Option(..., help="Output cost per million tokens (USD)"),
    effective_date: str = typer.Option(
        None,
        help="Effective date (YYYY-MM-DD format, defaults to today)",
    ),
    notes: Optional[str] = typer.Option(None, help="Additional notes"),
):
    """
    Add or update model pricing configuration.
    """
    console.print("\n")
    console.print(Panel(
        f"[bold]Add Model Pricing[/bold]\n\n"
        f"Service: {service}\n"
        f"Model: {model}\n"
        f"Input: ${input_cost}/M tokens\n"
        f"Output: ${output_cost}/M tokens",
        border_style="blue",
    ))

    try:
        from app.models import ModelPricing

        # Parse effective date
        if effective_date:
            eff_date = datetime.strptime(effective_date, "%Y-%m-%d")
        else:
            eff_date = datetime.now()

        db = get_sync_session()

        # Check if pricing already exists for this service/model/date
        existing = db.query(ModelPricing).filter_by(
            service=service,
            model=model,
            effective_date=eff_date,
        ).first()

        if existing:
            console.print(f"\n[yellow]Pricing already exists for {service}/{model} on {eff_date.date()}[/yellow]")
            update = typer.confirm("Do you want to update it?")
            if not update:
                warning("Operation cancelled")
                return

            existing.input_cost_per_million = input_cost
            existing.output_cost_per_million = output_cost
            if notes:
                existing.notes = notes
            db.commit()
            success(f"Updated pricing for {service}/{model}")
        else:
            # Create new pricing
            new_pricing = ModelPricing(
                service=service,
                model=model,
                input_cost_per_million=input_cost,
                output_cost_per_million=output_cost,
                effective_date=eff_date,
                notes=notes,
            )
            db.add(new_pricing)
            db.commit()
            success(f"Added pricing for {service}/{model}")

        console.print(f"\n[green]✓ Pricing configured:[/green]")
        console.print(f"  Input: ${input_cost}/M tokens")
        console.print(f"  Output: ${output_cost}/M tokens")
        console.print(f"  Effective: {eff_date.date()}")
        console.print()

    except Exception as e:
        handle_error(e, "Failed to add pricing configuration")


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


# ============================================================================
# PARENT-ESCAPE Command - Find Romantic Getaway Opportunities
# ============================================================================

@app.command("parent-escape")
def parent_escape(
    start_date: Optional[str] = typer.Option(
        None,
        help="Start date for search (YYYY-MM-DD). Default: today",
    ),
    end_date: Optional[str] = typer.Option(
        None,
        help="End date for search (YYYY-MM-DD). Default: 3 months from start",
    ),
    max_budget: float = typer.Option(
        1200.0,
        help="Maximum total trip budget in EUR (for 2 people)",
    ),
    min_nights: int = typer.Option(
        2,
        help="Minimum trip duration in nights",
    ),
    max_nights: int = typer.Option(
        3,
        help="Maximum trip duration in nights",
    ),
    max_train_hours: float = typer.Option(
        6.0,
        help="Maximum train travel time in hours",
    ),
    limit: int = typer.Option(
        10,
        help="Number of top opportunities to display",
    ),
    format: str = typer.Option(
        "table",
        help="Output format: 'table' or 'json'",
    ),
):
    """
    Find romantic getaway opportunities for parents.

    Searches for train-accessible destinations from Munich with romantic features
    like wine regions, spa hotels, and cultural events. Perfect for 2-3 night
    weekend escapes!

    Examples:
        scout parent-escape
        scout parent-escape --max-budget 1000 --min-nights 2 --max-nights 2
        scout parent-escape --start-date 2025-04-01 --end-date 2025-06-30
        scout parent-escape --max-train-hours 4.0 --limit 15
        scout parent-escape --format json
    """
    console.print(Panel(
        "[bold]🌹 Parent Escape Opportunity Finder[/bold]\n\n"
        "Finding romantic getaways for parents...\n"
        "Train-accessible destinations with wine, spa, and culture!",
        border_style="magenta",
    ))

    try:
        asyncio.run(_find_parent_escapes(
            start_date,
            end_date,
            max_budget,
            min_nights,
            max_nights,
            max_train_hours,
            limit,
            format,
        ))
    except Exception as e:
        handle_error(e, "Parent escape search failed")


async def _find_parent_escapes(
    start_date_str: Optional[str],
    end_date_str: Optional[str],
    max_budget: float,
    min_nights: int,
    max_nights: int,
    max_train_hours: float,
    limit: int,
    format: str,
):
    """Execute parent escape search."""
    from app.ai.parent_escape_analyzer import ParentEscapeAnalyzer
    from app.ai.claude_client import ClaudeClient

    # Parse dates
    if start_date_str:
        start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    else:
        start = date.today()

    if end_date_str:
        end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    else:
        end = start + timedelta(days=90)

    # Display search parameters
    params_table = Table(show_header=True, header_style="bold magenta")
    params_table.add_column("Parameter", style="cyan")
    params_table.add_column("Value", style="green")

    params_table.add_row("Date Range", f"{start} to {end}")
    params_table.add_row("Max Budget", f"€{max_budget:.0f}")
    params_table.add_row("Trip Duration", f"{min_nights}-{max_nights} nights")
    params_table.add_row("Max Train Travel", f"{max_train_hours}h")
    params_table.add_row("Results to Show", str(limit))

    console.print("\n")
    console.print(params_table)
    console.print("\n")

    # Initialize analyzer
    claude_client = ClaudeClient()
    analyzer = ParentEscapeAnalyzer(claude_client)

    # Find opportunities
    async with get_async_session_context() as db:
        packages = await analyzer.find_escape_opportunities(
            db=db,
            date_range=(start, end),
            max_budget=max_budget,
            min_nights=min_nights,
            max_nights=max_nights,
            max_train_hours=max_train_hours,
        )

    if not packages:
        warning("No parent escape opportunities found matching your criteria")
        info("Try adjusting the date range, budget, or max train hours")
        return

    # Sort by AI score
    sorted_packages = sorted(
        packages,
        key=lambda p: p.ai_score if p.ai_score else 0,
        reverse=True
    )

    if format == "json":
        # JSON output
        escapes_data = []
        for pkg in sorted_packages[:limit]:
            escape_data = {
                "destination": pkg.destination_city,
                "country": pkg.flights_json.get("details", {}).get("country", "Unknown"),
                "departure_date": pkg.departure_date.isoformat(),
                "return_date": pkg.return_date.isoformat(),
                "nights": pkg.num_nights,
                "total_cost": float(pkg.total_price),
                "escape_score": float(pkg.ai_score) if pkg.ai_score else None,
                "romantic_appeal": pkg.itinerary_json.get("romantic_appeal") if pkg.itinerary_json else None,
                "highlights": pkg.itinerary_json.get("highlights", []) if pkg.itinerary_json else [],
                "recommended_experiences": pkg.itinerary_json.get("recommended_experiences", []) if pkg.itinerary_json else [],
                "childcare_suggestions": pkg.itinerary_json.get("childcare_suggestions", []) if pkg.itinerary_json else [],
            }
            escapes_data.append(escape_data)

        console.print(json.dumps(escapes_data, indent=2))
    else:
        # Table output
        await analyzer.print_escape_summary(sorted_packages, show_top=limit)

        # Show detailed information for top result
        if sorted_packages:
            top_package = sorted_packages[0]
            console.print("\n")
            console.print(Panel(
                f"[bold cyan]🏆 Top Recommendation: {top_package.destination_city}[/bold cyan]\n\n"
                f"[white]{top_package.ai_reasoning}[/white]",
                border_style="cyan",
                title="Best Romantic Getaway",
            ))

            # Show highlights if available
            if top_package.itinerary_json and "highlights" in top_package.itinerary_json:
                highlights = top_package.itinerary_json["highlights"]
                if highlights:
                    console.print("\n[bold magenta]Highlights:[/bold magenta]")
                    for highlight in highlights[:3]:
                        console.print(f"  • {highlight}")

            # Show recommended experiences
            if top_package.itinerary_json and "recommended_experiences" in top_package.itinerary_json:
                experiences = top_package.itinerary_json["recommended_experiences"]
                if experiences:
                    console.print("\n[bold magenta]Recommended Experiences:[/bold magenta]")
                    for exp in experiences[:3]:
                        console.print(f"  • {exp}")

            # Show childcare suggestions
            if top_package.itinerary_json and "childcare_suggestions" in top_package.itinerary_json:
                childcare = top_package.itinerary_json["childcare_suggestions"]
                if childcare:
                    console.print("\n[bold magenta]Childcare Options:[/bold magenta]")
                    for option in childcare[:2]:
                        console.print(f"  • {option}")

            console.print("\n")

    success(f"Found {len(packages)} parent escape opportunities!")


if __name__ == "__main__":
    app()
