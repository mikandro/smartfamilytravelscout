"""
Flight Orchestrator for coordinating multiple flight data sources.

This module orchestrates scraping from Kiwi, Skyscanner, Ryanair, and WizzAir,
deduplicates results, and saves unique flights to the database.

Example:
    >>> orchestrator = FlightOrchestrator()
    >>> flights = await orchestrator.scrape_all(
    ...     origins=['MUC', 'FMM'],
    ...     destinations=['LIS', 'BCN', 'PRG'],
    ...     date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))]
    ... )
    >>> print(f"Found {len(flights)} unique flights")
"""

import asyncio
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

from redis.asyncio import Redis
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_async_session_context
from app.exceptions import ScraperFailureThresholdExceeded
from app.models.airport import Airport
from app.models.flight import Flight
from app.models.scraping_job import ScrapingJob
from app.scrapers.kiwi_scraper import KiwiClient
from app.scrapers.ryanair_scraper import RyanairScraper
from app.scrapers.skyscanner_scraper import SkyscannerScraper
from app.scrapers.wizzair_scraper import WizzAirScraper
from app.utils.date_utils import parse_time
from app.utils.flight_cache import FlightDeduplicationCache

logger = logging.getLogger(__name__)
console = Console()


class FlightOrchestrator:
    """
    Orchestrates multiple flight scrapers to gather and deduplicate flight data.

    This class coordinates four flight data sources (Kiwi, Skyscanner, Ryanair, WizzAir),
    runs them in parallel for maximum efficiency, deduplicates results based on route,
    airline, and timing, and saves unique flights to the database.

    Features:
        - Parallel execution of all scrapers using asyncio.gather()
        - Graceful error handling - continues if individual scrapers fail
        - Deduplication based on route + airline + time window
        - Batch database operations for efficiency
        - Progress tracking with Rich console output
        - Comprehensive logging and statistics

    Attributes:
        kiwi: Kiwi.com API client
        skyscanner: Skyscanner web scraper
        ryanair: Ryanair web scraper
        wizzair: WizzAir API scraper
    """

    def __init__(self, redis_client: Optional[Redis] = None):
        """
        Initialize enabled flight scrapers based on configuration.

        Args:
            redis_client: Optional Redis client for caching. If not provided,
                         caching will be disabled and all flights will be deduplicated.
        """
        self.enabled_scrapers = settings.get_available_scrapers()

        # Initialize only enabled scrapers
        self.kiwi = KiwiClient() if "kiwi" in self.enabled_scrapers else None
        self.skyscanner = (
            SkyscannerScraper(headless=True) if "skyscanner" in self.enabled_scrapers else None
        )
        self.ryanair = RyanairScraper() if "ryanair" in self.enabled_scrapers else None
        self.wizzair = WizzAirScraper() if "wizzair" in self.enabled_scrapers else None

        # Initialize flight cache if Redis is available
        self.cache = None
        if redis_client:
            self.cache = FlightDeduplicationCache(
                redis_client=redis_client,
                ttl=settings.cache_ttl_flights,  # Use configured TTL (default: 3600s)
            )
            logger.info(
                f"FlightOrchestrator initialized with Redis cache (TTL: {settings.cache_ttl_flights}s)"
            )
        else:
            logger.warning(
                "FlightOrchestrator initialized without Redis cache - deduplication will be slower"
            )

        logger.info(
            f"FlightOrchestrator initialized with {len(self.enabled_scrapers)} scrapers: "
            f"{', '.join(self.enabled_scrapers)}"
        )

    async def scrape_all(
        self,
        origins: List[str],
        destinations: List[str],
        date_ranges: List[Tuple[date, date]],
    ) -> List[Dict]:
        """
        Run all scrapers in parallel, deduplicate, and return unique flights.

        This is the main entry point for flight scraping. It creates tasks for all
        combinations of origins, destinations, date ranges, and scrapers, then runs
        them concurrently using asyncio.gather().

        Args:
            origins: List of origin airport IATA codes (e.g., ['MUC', 'FMM', 'NUE', 'SZG'])
            destinations: List of destination airport IATA codes (e.g., ['LIS', 'BCN', 'PRG'])
            date_ranges: List of (departure_date, return_date) tuples for school holidays

        Returns:
            List of unique flight dictionaries ready for database insertion

        Example:
            >>> flights = await orchestrator.scrape_all(
            ...     origins=['MUC', 'FMM'],
            ...     destinations=['LIS', 'BCN'],
            ...     date_ranges=[(date(2025, 12, 20), date(2025, 12, 27))]
            ... )
            >>> print(f"Found {len(flights)} unique flights")
        """
        logger.info(
            f"Starting scrape_all: {len(origins)} origins × {len(destinations)} destinations "
            f"× {len(date_ranges)} date ranges × 4 scrapers"
        )

        start_time = datetime.now()

        # Create tasks for all combinations
        tasks = []
        task_metadata = []  # Track which scraper/route each task represents

        for origin in origins:
            for destination in destinations:
                for departure_date, return_date in date_ranges:
                    # Create task for each ENABLED scraper
                    if self.kiwi:
                        tasks.append(
                            self.scrape_source(
                                self.kiwi, "kiwi", origin, destination, (departure_date, return_date)
                            )
                        )
                        task_metadata.append(f"Kiwi: {origin}→{destination}")

                    if self.skyscanner:
                        tasks.append(
                            self.scrape_source(
                                self.skyscanner,
                                "skyscanner",
                                origin,
                                destination,
                                (departure_date, return_date),
                            )
                        )
                        task_metadata.append(f"Skyscanner: {origin}→{destination}")

                    if self.ryanair:
                        tasks.append(
                            self.scrape_source(
                                self.ryanair, "ryanair", origin, destination, (departure_date, return_date)
                            )
                        )
                        task_metadata.append(f"Ryanair: {origin}→{destination}")

                    if self.wizzair:
                        tasks.append(
                            self.scrape_source(
                                self.wizzair, "wizzair", origin, destination, (departure_date, return_date)
                            )
                        )
                        task_metadata.append(f"WizzAir: {origin}→{destination}")

        console.print(
            f"\n[bold cyan]Starting {len(tasks)} scraping tasks in parallel...[/bold cyan]\n"
        )

        # Run all tasks concurrently with real-time progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Create individual progress tasks for each scraper type
            scraper_tasks = {}
            for scraper in ["Kiwi", "Skyscanner", "Ryanair", "WizzAir"]:
                scraper_count = sum(1 for t in task_metadata if t.startswith(scraper))
                if scraper_count > 0:
                    scraper_tasks[scraper] = progress.add_task(
                        f"[yellow]{scraper}: Starting...", total=scraper_count
                    )

            # Gather results with return_exceptions=True to handle failures gracefully
            # We'll track completion in real-time using task callbacks
            results = await self._gather_with_progress(
                tasks, task_metadata, progress, scraper_tasks
            )

        # Process results and collect statistics
        all_flights = []
        successful_scrapers = 0
        failed_scrapers = 0
        scraper_stats = defaultdict(lambda: {"success": 0, "failed": 0, "flights": 0})

        for idx, result in enumerate(results):
            scraper_name = task_metadata[idx].split(":")[0]

            if isinstance(result, Exception):
                logger.error(f"Scraper failed ({task_metadata[idx]}): {result}")
                failed_scrapers += 1
                scraper_stats[scraper_name]["failed"] += 1
            else:
                successful_scrapers += 1
                scraper_stats[scraper_name]["success"] += 1
                scraper_stats[scraper_name]["flights"] += len(result)
                all_flights.extend(result)

        # Log statistics
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Scraping completed: {successful_scrapers} successful, {failed_scrapers} failed, "
            f"{len(all_flights)} total flights, {elapsed_time:.2f}s elapsed"
        )

        # Check failure threshold
        total_scrapers = successful_scrapers + failed_scrapers
        if total_scrapers > 0:
            failure_rate = failed_scrapers / total_scrapers
            threshold = settings.scraper_failure_threshold

            if failure_rate > threshold:
                logger.critical(
                    f"CRITICAL: Scraper failure threshold exceeded! "
                    f"{failed_scrapers}/{total_scrapers} scrapers failed "
                    f"({failure_rate:.1%} failure rate, threshold: {threshold:.1%})"
                )
                raise ScraperFailureThresholdExceeded(
                    total_scrapers=total_scrapers,
                    failed_scrapers=failed_scrapers,
                    failure_rate=failure_rate,
                    threshold=threshold,
                )

        # Print statistics table
        self._print_stats_table(scraper_stats, elapsed_time)

        # Deduplicate flights (with caching if available)
        console.print(f"\n[bold yellow]Deduplicating {len(all_flights)} flights...[/bold yellow]")
        unique_flights = await self.deduplicate(all_flights)

        console.print(
            f"[bold green]✓ Found {len(unique_flights)} unique flights "
            f"(removed {len(all_flights) - len(unique_flights)} duplicates)[/bold green]\n"
        )

        return unique_flights

    def _print_stats_table(self, scraper_stats: Dict, elapsed_time: float):
        """Print a Rich table with scraper statistics."""
        table = Table(title="Scraping Statistics")

        table.add_column("Scraper", style="cyan", no_wrap=True)
        table.add_column("Successful", style="green")
        table.add_column("Failed", style="red")
        table.add_column("Flights Found", style="yellow")

        for scraper, stats in scraper_stats.items():
            table.add_row(
                scraper,
                str(stats["success"]),
                str(stats["failed"]),
                str(stats["flights"]),
            )

        table.add_section()
        table.add_row(
            "[bold]Total[/bold]",
            "[bold]" + str(sum(s["success"] for s in scraper_stats.values())) + "[/bold]",
            "[bold]" + str(sum(s["failed"] for s in scraper_stats.values())) + "[/bold]",
            "[bold]" + str(sum(s["flights"] for s in scraper_stats.values())) + "[/bold]",
        )

        console.print(table)
        console.print(f"\n[dim]Time elapsed: {elapsed_time:.2f}s[/dim]\n")

    async def _gather_with_progress(
        self,
        tasks: List,
        task_metadata: List[str],
        progress: Progress,
        scraper_tasks: Dict,
    ) -> List:
        """
        Execute tasks with real-time progress updates.

        This method wraps asyncio.gather to provide real-time feedback as each
        scraper completes, updating the progress bars and showing immediate results.

        Args:
            tasks: List of coroutines to execute
            task_metadata: List of task descriptions matching tasks
            progress: Rich Progress instance
            scraper_tasks: Dict mapping scraper names to progress task IDs

        Returns:
            List of results from all tasks (with exceptions for failures)
        """
        results = [None] * len(tasks)
        pending_tasks = {
            asyncio.create_task(task): (idx, task_metadata[idx])
            for idx, task in enumerate(tasks)
        }

        # Process tasks as they complete
        while pending_tasks:
            done, pending = await asyncio.wait(
                pending_tasks.keys(), return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                idx, metadata = pending_tasks.pop(task)
                scraper_name = metadata.split(":")[0].strip()
                route = metadata.split(":")[1].strip() if ":" in metadata else ""

                try:
                    result = task.result()
                    results[idx] = result
                    flight_count = len(result) if isinstance(result, list) else 0

                    # Update progress for this scraper
                    if scraper_name in scraper_tasks:
                        progress.update(
                            scraper_tasks[scraper_name],
                            advance=1,
                            description=f"[green]{scraper_name}: {route} ({flight_count} flights)",
                        )

                    # Log completion
                    logger.info(f"✓ {scraper_name} completed {route}: {flight_count} flights found")

                except Exception as e:
                    results[idx] = e

                    # Update progress to show failure
                    if scraper_name in scraper_tasks:
                        progress.update(
                            scraper_tasks[scraper_name],
                            advance=1,
                            description=f"[red]{scraper_name}: {route} (failed)",
                        )

                    # Log error
                    logger.error(f"✗ {scraper_name} failed {route}: {str(e)}")

        return results

    async def scrape_source(
        self,
        scraper,
        scraper_name: str,
        origin: str,
        destination: str,
        dates: Tuple[date, date],
    ) -> List[Dict]:
        """
        Scrape a single source with error handling and normalization.

        This method wraps individual scraper calls with error handling, logging,
        and data normalization to ensure consistent output format.

        Args:
            scraper: Scraper instance (KiwiClient, SkyscannerScraper, etc.)
            scraper_name: Name of the scraper for logging ('kiwi', 'skyscanner', etc.)
            origin: Origin airport IATA code
            destination: Destination airport IATA code
            dates: Tuple of (departure_date, return_date)

        Returns:
            List of normalized flight dictionaries, or empty list if scraping fails
        """
        departure_date, return_date = dates

        # Log start of scraping with console output for immediate feedback
        log_msg = (
            f"[{scraper_name}] Starting scrape: {origin} → {destination}, "
            f"{departure_date} to {return_date}"
        )
        logger.info(log_msg)
        console.print(f"[dim cyan]⟳ {log_msg}[/dim cyan]")

        try:
            # Call appropriate scraper method based on type
            if scraper_name == "kiwi":
                flights = await scraper.search_flights(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    adults=2,
                    children=2,
                )

            elif scraper_name == "skyscanner":
                # Skyscanner uses context manager
                async with scraper:
                    flights = await scraper.scrape_route(
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        return_date=return_date,
                    )
                # Normalize Skyscanner data (it doesn't include origin/destination in results)
                for flight in flights:
                    flight["origin_airport"] = origin
                    flight["destination_airport"] = destination
                    flight["origin_city"] = origin  # Will be enriched from DB
                    flight["destination_city"] = destination
                    flight["departure_date"] = departure_date.strftime("%Y-%m-%d")
                    flight["return_date"] = return_date.strftime("%Y-%m-%d") if return_date else None
                    flight["source"] = "skyscanner"
                    flight["scraped_at"] = datetime.now().isoformat()

            elif scraper_name == "ryanair":
                # Ryanair uses context manager
                async with scraper:
                    flights = await scraper.scrape_route(
                        origin=origin,
                        destination=destination,
                        departure_date=departure_date,
                        return_date=return_date,
                    )
                # Normalize Ryanair data
                for flight in flights:
                    # Ryanair returns different format, normalize it
                    flight["origin_airport"] = flight.pop("origin", origin)
                    flight["destination_airport"] = flight.pop("destination", destination)
                    flight["origin_city"] = flight.get("origin_airport", origin)
                    flight["destination_city"] = flight.get("destination_airport", destination)
                    flight["airline"] = "Ryanair"
                    # Convert dates if they're date objects
                    if isinstance(flight.get("departure_date"), date):
                        flight["departure_date"] = flight["departure_date"].strftime("%Y-%m-%d")
                    if isinstance(flight.get("return_date"), date):
                        flight["return_date"] = flight["return_date"].strftime("%Y-%m-%d")
                    # Convert times if they're time objects or strings
                    if isinstance(flight.get("departure_time"), time):
                        flight["departure_time"] = flight["departure_time"].strftime("%H:%M")
                    if isinstance(flight.get("return_time"), time):
                        flight["return_time"] = flight["return_time"].strftime("%H:%M")
                    # Extract price from potentially nested structure
                    if "price" in flight and "price_per_person" not in flight:
                        flight["price_per_person"] = flight["price"]
                        flight["total_price"] = flight["price"] * 4

            elif scraper_name == "wizzair":
                flights = await scraper.search_flights(
                    origin=origin,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    adult_count=2,
                    child_count=2,
                )
                # Normalize WizzAir data
                for flight in flights:
                    flight["origin_airport"] = flight.pop("origin", origin)
                    flight["destination_airport"] = flight.pop("destination", destination)
                    flight["origin_city"] = flight.get("origin_airport", origin)
                    flight["destination_city"] = flight.get("destination_airport", destination)
                    flight["airline"] = "WizzAir"
                    # Convert dates if they're date objects
                    if isinstance(flight.get("departure_date"), date):
                        flight["departure_date"] = flight["departure_date"].strftime("%Y-%m-%d")
                    if isinstance(flight.get("return_date"), date):
                        flight["return_date"] = flight["return_date"].strftime("%Y-%m-%d")
                    # Convert times if they're time objects
                    if isinstance(flight.get("departure_time"), time):
                        flight["departure_time"] = flight["departure_time"].strftime("%H:%M")
                    if isinstance(flight.get("return_time"), time):
                        flight["return_time"] = flight["return_time"].strftime("%H:%M")
                    # Extract price
                    if "price" in flight and "price_per_person" not in flight:
                        flight["price_per_person"] = flight["price"]
                        flight["total_price"] = flight["price"] * 4
                    flight["source"] = "wizzair"
                    flight["scraped_at"] = datetime.now().isoformat()

            else:
                logger.error(f"Unknown scraper: {scraper_name}")
                return []

            # Log completion with console output for immediate feedback
            success_msg = f"[{scraper_name}] Completed: {len(flights)} flights found"
            logger.info(success_msg)
            console.print(f"[dim green]✓ {success_msg}[/dim green]")
            return flights

        except Exception as e:
            # Log error with console output for immediate user feedback
            error_msg = f"[{scraper_name}] Scraping failed for {origin}→{destination}: {e}"
            logger.error(error_msg, exc_info=True)
            console.print(f"[dim red]✗ {error_msg}[/dim red]")

            # Re-raise exception to let scrape_all handle it via return_exceptions=True
            # This allows proper failure tracking and threshold checking
            raise

    async def deduplicate(self, flights: List[Dict]) -> List[Dict]:
        """
        Remove duplicate flights across sources with Redis caching.

        Flights are considered duplicates if they have:
        - Same origin + destination
        - Same airline
        - Departure date/time within 2 hours
        - Return date/time within 2 hours (if applicable)

        When duplicates are found:
        - Keep the one with the lowest price
        - Merge booking_url fields (keep all sources for user choice)

        Redis Caching:
        - Before deduplication, filters out flights already in cache
        - After deduplication, caches unique flights
        - Dramatically reduces CPU usage for repeated queries

        Args:
            flights: List of flight dictionaries from all sources

        Returns:
            List of unique flight dictionaries with merged booking URLs

        Example:
            >>> all_flights = [...]  # Flights from multiple sources
            >>> unique = await orchestrator.deduplicate(all_flights)
            >>> print(f"Reduced from {len(all_flights)} to {len(unique)} flights")
        """
        if not flights:
            return []

        logger.info(f"Deduplicating {len(flights)} flights...")

        # Filter out cached flights if cache is available
        flights_to_process = flights
        cached_count = 0

        if self.cache:
            logger.info("Checking flight cache to skip already-processed flights...")
            flights_to_process = await self.cache.filter_uncached_flights(flights)
            cached_count = len(flights) - len(flights_to_process)

            if cached_count > 0:
                logger.info(
                    f"Cache hit: {cached_count} flights already processed, "
                    f"{len(flights_to_process)} need deduplication"
                )
                console.print(
                    f"[dim]  → Cache hit: {cached_count} flights already seen, "
                    f"processing {len(flights_to_process)} new flights[/dim]"
                )

        # If all flights are cached, return empty list (they've all been processed before)
        if not flights_to_process:
            logger.info("All flights found in cache - no deduplication needed")
            return []

        # Group flights by route + airline + approximate time
        grouped = defaultdict(list)

        for flight in flights:
            try:
                # Parse departure date and time
                dep_date_str = flight.get("departure_date", "")
                dep_time_str = flight.get("departure_time", "00:00")

                if not dep_date_str:
                    logger.warning(f"Skipping flight with no departure_date: {flight}")
                    continue

                # Parse date
                try:
                    dep_date = datetime.strptime(dep_date_str, "%Y-%m-%d").date()
                except ValueError:
                    logger.warning(f"Invalid departure_date format: {dep_date_str}")
                    continue

                # Parse time using robust parser
                dep_time = parse_time(
                    dep_time_str,
                    context=f"departure_time for {flight.get('origin_airport')}->{flight.get('destination_airport')}"
                )

                # Use parsed time or default to noon if parsing failed
                if dep_time is not None:
                    dep_datetime = datetime.combine(dep_date, dep_time)
                else:
                    # Default to noon for grouping purposes when time is unavailable
                    dep_datetime = datetime.combine(dep_date, time(12, 0))
                    if dep_time_str:  # Only log if there was a value that failed to parse
                        logger.debug(
                            f"Using default noon for grouping (departure time unavailable): "
                            f"{flight.get('origin_airport')}->{flight.get('destination_airport')} on {dep_date}"
                        )

                # Round departure time to 2-hour blocks for grouping
                hour_block = (dep_datetime.hour // 2) * 2
                rounded_time = dep_datetime.replace(hour=hour_block, minute=0, second=0)

                # Parse return date/time similarly
                ret_date_str = flight.get("return_date", "")
                ret_time_str = flight.get("return_time", "00:00")

                if ret_date_str and ret_date_str != "None":
                    try:
                        ret_date = datetime.strptime(ret_date_str, "%Y-%m-%d").date()

                        # Parse return time using robust parser
                        ret_time = parse_time(
                            ret_time_str,
                            context=f"return_time for {flight.get('origin_airport')}->{flight.get('destination_airport')}"
                        )

                        # Use parsed time or default to noon if parsing failed
                        if ret_time is not None:
                            ret_datetime = datetime.combine(ret_date, ret_time)
                        else:
                            # Default to noon for grouping purposes when time is unavailable
                            ret_datetime = datetime.combine(ret_date, time(12, 0))
                            if ret_time_str:  # Only log if there was a value that failed to parse
                                logger.debug(
                                    f"Using default noon for grouping (return time unavailable): "
                                    f"{flight.get('origin_airport')}->{flight.get('destination_airport')} on {ret_date}"
                                )

                        ret_hour_block = (ret_datetime.hour // 2) * 2
                        rounded_ret_time = ret_datetime.replace(
                            hour=ret_hour_block, minute=0, second=0
                        )
                    except ValueError:
                        rounded_ret_time = None
                else:
                    rounded_ret_time = None

                # Create grouping key
                key = (
                    flight.get("origin_airport", "").upper(),
                    flight.get("destination_airport", "").upper(),
                    flight.get("airline", "Unknown").upper(),
                    rounded_time,
                    rounded_ret_time,
                )

                grouped[key].append(flight)

            except Exception as e:
                logger.warning(f"Error processing flight for deduplication: {e}", exc_info=True)
                continue

        # Keep cheapest from each group and merge URLs
        unique_flights = []

        for key, flight_group in grouped.items():
            try:
                # Find cheapest flight
                best = min(
                    flight_group,
                    key=lambda f: f.get("price_per_person") or f.get("total_price", float("inf")),
                )

                # Merge booking URLs from all sources
                booking_urls = []
                sources = []

                for f in flight_group:
                    url = f.get("booking_url")
                    if url and url not in booking_urls:
                        booking_urls.append(url)

                    source = f.get("source")
                    if source and source not in sources:
                        sources.append(source)

                # Update best flight with merged data
                best["booking_urls"] = booking_urls
                best["sources"] = sources
                best["duplicate_count"] = len(flight_group)  # Track how many were merged

                unique_flights.append(best)

            except Exception as e:
                logger.warning(f"Error selecting best flight from group: {e}", exc_info=True)
                continue

        duplicates_removed = len(flights_to_process) - len(unique_flights)
        logger.info(
            f"Deduplication complete: {len(unique_flights)} unique flights "
            f"({duplicates_removed} duplicates removed from {len(flights_to_process)} processed)"
        )

        # Cache the unique flights for future queries
        if self.cache and unique_flights:
            logger.info(f"Caching {len(unique_flights)} unique flights...")
            cached_count = await self.cache.cache_multiple_flights(unique_flights)
            logger.info(f"Successfully cached {cached_count} flights (TTL: {self.cache.ttl}s)")

        return unique_flights

    async def save_to_database(
        self, flights: List[Dict], create_job: bool = True
    ) -> Dict[str, int]:
        """
        Batch save flights to database with duplicate checking.

        Uses SQLAlchemy bulk operations for efficiency. Updates existing flights
        if price is cheaper, otherwise skips duplicates.

        Optimized to avoid N+1 queries by:
        - Batch loading all required airports upfront
        - Batch loading potential duplicate flights upfront

        Args:
            flights: List of flight dictionaries to save
            create_job: Whether to create a ScrapingJob record (default: True)

        Returns:
            Dict with statistics:
                {
                    'total': Total flights processed,
                    'inserted': New flights inserted,
                    'updated': Flights updated with cheaper prices,
                    'skipped': Flights skipped (duplicates)
                }

        Example:
            >>> stats = await orchestrator.save_to_database(unique_flights)
            >>> print(f"Inserted {stats['inserted']}, Updated {stats['updated']}")
        """
        stats = {
            "total": len(flights),
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
        }

        if not flights:
            logger.info("No flights to save")
            return stats

        logger.info(f"Saving {len(flights)} flights to database...")

        # Create scraping job if requested
        job = None
        job_start_time = datetime.now()

        async with get_async_session_context() as db:
            try:
                if create_job:
                    job = ScrapingJob(
                        job_type="flights",
                        source="orchestrator",
                        status="running",
                        items_scraped=0,
                        started_at=job_start_time,
                    )
                    db.add(job)
                    await db.flush()

                # Process flights in batches for efficiency
                batch_size = 50

                for i in range(0, len(flights), batch_size):
                    batch = flights[i : i + batch_size]

                    # FIX N+1: Collect all unique airport IATA codes in this batch
                    airport_codes = set()
                    for flight_data in batch:
                        origin = flight_data.get("origin_airport", "")
                        destination = flight_data.get("destination_airport", "")
                        if origin:
                            airport_codes.add(origin.upper())
                        if destination:
                            airport_codes.add(destination.upper())

                    # FIX N+1: Batch load all airports at once
                    airport_stmt = select(Airport).where(Airport.iata_code.in_(airport_codes))
                    airport_result = await db.execute(airport_stmt)
                    airports_list = airport_result.scalars().all()

                    # Build airport cache by IATA code
                    airport_cache: Dict[str, Airport] = {
                        airport.iata_code: airport for airport in airports_list
                    }

                    # FIX N+1: Create missing airports in batch
                    missing_codes = airport_codes - set(airport_cache.keys())
                    for iata_code in missing_codes:
                        # Find the city name from flight data
                        city = ""
                        for flight_data in batch:
                            if flight_data.get("origin_airport", "").upper() == iata_code:
                                city = flight_data.get("origin_city", "")
                                break
                            elif flight_data.get("destination_airport", "").upper() == iata_code:
                                city = flight_data.get("destination_city", "")
                                break

                        logger.info(f"Creating new airport: {iata_code} ({city})")
                        new_airport = Airport(
                            iata_code=iata_code,
                            name=f"{city} Airport" if city else f"{iata_code} Airport",
                            city=city or iata_code,
                            distance_from_home=0,
                            driving_time=0,
                        )
                        db.add(new_airport)
                        airport_cache[iata_code] = new_airport

                    # Flush to get IDs for new airports
                    await db.flush()

                    # FIX N+1: Collect all flight parameters for duplicate checking
                    flight_params = []
                    for flight_data in batch:
                        dep_date_str = flight_data.get("departure_date", "")
                        if not dep_date_str:
                            continue

                        try:
                            departure_date_obj = datetime.strptime(dep_date_str, "%Y-%m-%d").date()
                            origin_code = flight_data.get("origin_airport", "").upper()
                            dest_code = flight_data.get("destination_airport", "").upper()

                            if origin_code in airport_cache and dest_code in airport_cache:
                                flight_params.append({
                                    "origin_airport_id": airport_cache[origin_code].id,
                                    "destination_airport_id": airport_cache[dest_code].id,
                                    "airline": flight_data.get("airline", "Unknown"),
                                    "departure_date": departure_date_obj,
                                })
                        except (ValueError, TypeError):
                            continue

                    # FIX N+1: Batch load all potential duplicate flights
                    existing_flights_map = {}
                    if flight_params:
                        # Build query to find all potential duplicates
                        duplicate_conditions = []
                        for params in flight_params:
                            duplicate_conditions.append(
                                and_(
                                    Flight.origin_airport_id == params["origin_airport_id"],
                                    Flight.destination_airport_id == params["destination_airport_id"],
                                    Flight.airline == params["airline"],
                                    Flight.departure_date == params["departure_date"],
                                )
                            )

                        if duplicate_conditions:
                            from sqlalchemy import or_
                            existing_stmt = select(Flight).where(or_(*duplicate_conditions))
                            existing_result = await db.execute(existing_stmt)
                            existing_flights = existing_result.scalars().all()

                            # Build index for O(1) lookup
                            for flight in existing_flights:
                                key = (
                                    flight.origin_airport_id,
                                    flight.destination_airport_id,
                                    flight.airline,
                                    flight.departure_date,
                                )
                                if key not in existing_flights_map:
                                    existing_flights_map[key] = []
                                existing_flights_map[key].append(flight)

                    # Now process each flight with cached data
                    for flight_data in batch:
                        try:
                            # Get airports from cache
                            origin_code = flight_data.get("origin_airport", "").upper()
                            dest_code = flight_data.get("destination_airport", "").upper()

                            origin_airport = airport_cache.get(origin_code)
                            destination_airport = airport_cache.get(dest_code)

                            if not origin_airport or not destination_airport:
                                logger.warning(
                                    f"Skipping flight: airports not found "
                                    f"({flight_data.get('origin_airport')} or "
                                    f"{flight_data.get('destination_airport')})"
                                )
                                stats["skipped"] += 1
                                continue

                            # Parse dates and times
                            dep_date_str = flight_data.get("departure_date", "")
                            dep_time_str = flight_data.get("departure_time")

                            try:
                                departure_date_obj = datetime.strptime(dep_date_str, "%Y-%m-%d").date()
                            except (ValueError, TypeError):
                                logger.warning(f"Invalid departure_date: {dep_date_str}")
                                stats["skipped"] += 1
                                continue

                            # Parse departure time using robust parser
                            departure_time_obj = parse_time(
                                dep_time_str,
                                context=f"departure_time for DB save {origin_airport.iata_code}->{destination_airport.iata_code}"
                            )

                            # Parse return date and time
                            ret_date_str = flight_data.get("return_date")
                            ret_time_str = flight_data.get("return_time")

                            # Parse return date
                            if ret_date_str and ret_date_str != "None":
                                try:
                                    return_date_obj = datetime.strptime(ret_date_str, "%Y-%m-%d").date()
                                except (ValueError, TypeError):
                                    return_date_obj = None
                            else:
                                return_date_obj = None

                            # Parse return time using robust parser
                            return_time_obj = parse_time(
                                ret_time_str,
                                context=f"return_time for DB save {origin_airport.iata_code}->{destination_airport.iata_code}"
                            )

                            # Check for existing flight using cached data
                            airline = flight_data.get("airline", "Unknown")
                            lookup_key = (
                                origin_airport.id,
                                destination_airport.id,
                                airline,
                                departure_date_obj,
                            )

                            existing_flight = None
                            candidates = existing_flights_map.get(lookup_key, [])

                            # Check time window for candidates
                            if departure_time_obj:
                                time_lower = (
                                    datetime.combine(departure_date_obj, departure_time_obj) - timedelta(hours=2)
                                ).time()
                                time_upper = (
                                    datetime.combine(departure_date_obj, departure_time_obj) + timedelta(hours=2)
                                ).time()

                                for candidate in candidates:
                                    if candidate.departure_time:
                                        if time_lower <= candidate.departure_time <= time_upper:
                                            existing_flight = candidate
                                            break
                            elif candidates:
                                # No time specified, take first candidate
                                existing_flight = candidates[0]

                            # Get price (handle both price_per_person and total_price)
                            price_per_person = flight_data.get("price_per_person")
                            if price_per_person is None:
                                # Fallback to total_price / 4
                                total_price = flight_data.get("total_price", 0)
                                price_per_person = total_price / 4 if total_price else 0

                            total_price = flight_data.get("total_price")
                            if total_price is None:
                                total_price = price_per_person * 4

                            if existing_flight:
                                # Update if new price is cheaper
                                if price_per_person < existing_flight.price_per_person:
                                    logger.info(
                                        f"Updating flight {existing_flight.id}: "
                                        f"€{existing_flight.price_per_person} → €{price_per_person}"
                                    )
                                    existing_flight.price_per_person = price_per_person
                                    existing_flight.total_price = total_price
                                    existing_flight.booking_url = flight_data.get(
                                        "booking_url", existing_flight.booking_url
                                    )
                                    existing_flight.scraped_at = datetime.now()
                                    stats["updated"] += 1
                                else:
                                    stats["skipped"] += 1
                            else:
                                # Insert new flight
                                new_flight = Flight(
                                    origin_airport_id=origin_airport.id,
                                    destination_airport_id=destination_airport.id,
                                    airline=airline,
                                    departure_date=departure_date_obj,
                                    departure_time=departure_time_obj,
                                    return_date=return_date_obj,
                                    return_time=return_time_obj,
                                    price_per_person=price_per_person,
                                    total_price=total_price,
                                    booking_class=flight_data.get("booking_class", "Economy"),
                                    direct_flight=flight_data.get("direct_flight", True),
                                    source=flight_data.get("source", "unknown"),
                                    booking_url=flight_data.get("booking_url"),
                                    scraped_at=datetime.now(),
                                )
                                db.add(new_flight)
                                stats["inserted"] += 1

                        except Exception as e:
                            logger.error(f"Error saving flight: {e}", exc_info=True)
                            stats["skipped"] += 1
                            continue

                    # Commit batch
                    await db.commit()

                # Update job status
                if job:
                    job.status = "completed"
                    job.items_scraped = stats["inserted"] + stats["updated"]
                    job.completed_at = datetime.now()
                    await db.commit()

                logger.info(
                    f"Database save complete: {stats['inserted']} inserted, "
                    f"{stats['updated']} updated, {stats['skipped']} skipped"
                )

            except Exception as e:
                logger.error(f"Error saving to database: {e}", exc_info=True)
                await db.rollback()

                # Mark job as failed
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.completed_at = datetime.now()
                    await db.commit()

                raise

        return stats

    async def _get_or_create_airport(
        self, db: AsyncSession, iata_code: str, city: str = ""
    ) -> Optional[Airport]:
        """
        Get airport from database by IATA code, or create if doesn't exist.

        Args:
            db: Database session
            iata_code: Airport IATA code (e.g., 'MUC')
            city: City name (optional, for creation)

        Returns:
            Airport model instance or None if code is empty
        """
        if not iata_code:
            return None

        iata_code = iata_code.upper()

        # Try to find existing airport
        result = await db.execute(select(Airport).where(Airport.iata_code == iata_code))
        airport = result.scalar_one_or_none()

        if airport:
            return airport

        # Create new airport with minimal info
        logger.info(f"Creating new airport: {iata_code} ({city})")
        airport = Airport(
            iata_code=iata_code,
            name=f"{city} Airport" if city else f"{iata_code} Airport",
            city=city or iata_code,
            distance_from_home=0,  # Unknown, will be updated later
            driving_time=0,  # Unknown, will be updated later
        )
        db.add(airport)
        await db.flush()  # Get the ID without committing
        return airport

    async def _check_duplicate_flight(
        self,
        db: AsyncSession,
        origin_airport_id: int,
        destination_airport_id: int,
        airline: str,
        departure_date: date,
        departure_time: Optional[time],
    ) -> Optional[Flight]:
        """
        Check if a similar flight already exists in the database.

        A duplicate is defined as:
        - Same route (origin + destination)
        - Same airline
        - Same date
        - Similar time (±2 hours, or any time if None)

        Args:
            db: Database session
            origin_airport_id: Origin airport ID
            destination_airport_id: Destination airport ID
            airline: Airline name
            departure_date: Departure date
            departure_time: Departure time (can be None)

        Returns:
            Existing flight if found, None otherwise
        """
        # Build base query
        from sqlalchemy import and_

        conditions = [
            Flight.origin_airport_id == origin_airport_id,
            Flight.destination_airport_id == destination_airport_id,
            Flight.airline == airline,
            Flight.departure_date == departure_date,
        ]

        # Add time window condition if time is provided
        if departure_time:
            # Calculate time window (±2 hours)
            time_lower = (
                datetime.combine(departure_date, departure_time) - timedelta(hours=2)
            ).time()
            time_upper = (
                datetime.combine(departure_date, departure_time) + timedelta(hours=2)
            ).time()

            conditions.extend(
                [
                    Flight.departure_time >= time_lower,
                    Flight.departure_time <= time_upper,
                ]
            )

        result = await db.execute(select(Flight).where(and_(*conditions)))
        return result.scalar_one_or_none()
