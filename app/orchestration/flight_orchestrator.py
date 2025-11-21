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

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session_context
from app.models.airport import Airport
from app.models.flight import Flight
from app.models.scraping_job import ScrapingJob
from app.monitoring.decorators import track_scraper_metrics
from app.monitoring.metrics import (
    scraper_requests_total,
    scraper_duration_seconds,
    scraping_errors_total,
    active_scraping_jobs,
    flights_discovered_total,
)
from app.scrapers.kiwi_scraper import KiwiClient
from app.scrapers.ryanair_scraper import RyanairScraper
from app.scrapers.skyscanner_scraper import SkyscannerScraper
from app.scrapers.wizzair_scraper import WizzAirScraper

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

    def __init__(self):
        """Initialize enabled flight scrapers based on configuration."""
        self.enabled_scrapers = settings.get_available_scrapers()

        # Initialize only enabled scrapers
        self.kiwi = KiwiClient() if "kiwi" in self.enabled_scrapers else None
        self.skyscanner = (
            SkyscannerScraper(headless=True) if "skyscanner" in self.enabled_scrapers else None
        )
        self.ryanair = RyanairScraper() if "ryanair" in self.enabled_scrapers else None
        self.wizzair = WizzAirScraper() if "wizzair" in self.enabled_scrapers else None

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

        # Run all tasks concurrently with progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("[cyan]Scraping flights...", total=len(tasks))

            # Gather results with return_exceptions=True to handle failures gracefully
            results = await asyncio.gather(*tasks, return_exceptions=True)

            progress.update(task_id, completed=len(tasks))

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

        # Print statistics table
        self._print_stats_table(scraper_stats, elapsed_time)

        # Deduplicate flights
        console.print(f"\n[bold yellow]Deduplicating {len(all_flights)} flights...[/bold yellow]")
        unique_flights = self.deduplicate(all_flights)

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
        import time

        departure_date, return_date = dates

        logger.info(
            f"[{scraper_name}] Scraping {origin} → {destination}, "
            f"{departure_date} to {return_date}"
        )

        # Track active jobs
        active_scraping_jobs.labels(scraper=scraper_name).inc()
        start_time = time.time()
        status = "success"

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

            logger.info(f"[{scraper_name}] Found {len(flights)} flights")

            # Track discovered flights
            if flights:
                flights_discovered_total.labels(
                    scraper=scraper_name, origin=origin, destination=destination
                ).inc(len(flights))

            return flights

        except Exception as e:
            status = "failure"
            error_type = type(e).__name__
            scraping_errors_total.labels(scraper=scraper_name, error_type=error_type).inc()

            logger.error(
                f"[{scraper_name}] Scraping failed for {origin}→{destination}: {e}",
                exc_info=True,
            )
            return []

        finally:
            # Track metrics
            duration = time.time() - start_time
            scraper_duration_seconds.labels(scraper=scraper_name).observe(duration)
            scraper_requests_total.labels(scraper=scraper_name, status=status).inc()
            active_scraping_jobs.labels(scraper=scraper_name).dec()

    def deduplicate(self, flights: List[Dict]) -> List[Dict]:
        """
        Remove duplicate flights across sources.

        Flights are considered duplicates if they have:
        - Same origin + destination
        - Same airline
        - Departure date/time within 2 hours
        - Return date/time within 2 hours (if applicable)

        When duplicates are found:
        - Keep the one with the lowest price
        - Merge booking_url fields (keep all sources for user choice)

        Args:
            flights: List of flight dictionaries from all sources

        Returns:
            List of unique flight dictionaries with merged booking URLs

        Example:
            >>> all_flights = [...]  # Flights from multiple sources
            >>> unique = orchestrator.deduplicate(all_flights)
            >>> print(f"Reduced from {len(all_flights)} to {len(unique)} flights")
        """
        if not flights:
            return []

        logger.info(f"Deduplicating {len(flights)} flights...")

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

                # Parse time (handle None or empty string)
                if dep_time_str and dep_time_str != "None":
                    try:
                        dep_time = datetime.strptime(dep_time_str, "%H:%M").time()
                        dep_datetime = datetime.combine(dep_date, dep_time)
                    except (ValueError, TypeError):
                        dep_datetime = datetime.combine(dep_date, time(12, 0))  # Default noon
                else:
                    dep_datetime = datetime.combine(dep_date, time(12, 0))  # Default noon

                # Round departure time to 2-hour blocks for grouping
                hour_block = (dep_datetime.hour // 2) * 2
                rounded_time = dep_datetime.replace(hour=hour_block, minute=0, second=0)

                # Parse return date/time similarly
                ret_date_str = flight.get("return_date", "")
                ret_time_str = flight.get("return_time", "00:00")

                if ret_date_str and ret_date_str != "None":
                    try:
                        ret_date = datetime.strptime(ret_date_str, "%Y-%m-%d").date()

                        if ret_time_str and ret_time_str != "None":
                            try:
                                ret_time = datetime.strptime(ret_time_str, "%H:%M").time()
                                ret_datetime = datetime.combine(ret_date, ret_time)
                            except (ValueError, TypeError):
                                ret_datetime = datetime.combine(ret_date, time(12, 0))
                        else:
                            ret_datetime = datetime.combine(ret_date, time(12, 0))

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

        duplicates_removed = len(flights) - len(unique_flights)
        logger.info(
            f"Deduplication complete: {len(unique_flights)} unique flights "
            f"({duplicates_removed} duplicates removed)"
        )

        return unique_flights

    async def save_to_database(
        self, flights: List[Dict], create_job: bool = True
    ) -> Dict[str, int]:
        """
        Batch save flights to database with duplicate checking.

        Uses SQLAlchemy bulk operations for efficiency. Updates existing flights
        if price is cheaper, otherwise skips duplicates.

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

                    for flight_data in batch:
                        try:
                            # Get or create airports
                            origin_airport = await self._get_or_create_airport(
                                db,
                                flight_data.get("origin_airport", ""),
                                flight_data.get("origin_city", ""),
                            )
                            destination_airport = await self._get_or_create_airport(
                                db,
                                flight_data.get("destination_airport", ""),
                                flight_data.get("destination_city", ""),
                            )

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

                            # Parse departure time
                            if dep_time_str and dep_time_str != "None":
                                try:
                                    departure_time_obj = datetime.strptime(dep_time_str, "%H:%M").time()
                                except (ValueError, TypeError):
                                    departure_time_obj = None
                            else:
                                departure_time_obj = None

                            # Parse return date and time
                            ret_date_str = flight_data.get("return_date")
                            ret_time_str = flight_data.get("return_time")

                            if ret_date_str and ret_date_str != "None":
                                try:
                                    return_date_obj = datetime.strptime(ret_date_str, "%Y-%m-%d").date()
                                except (ValueError, TypeError):
                                    return_date_obj = None
                            else:
                                return_date_obj = None

                            if ret_time_str and ret_time_str != "None":
                                try:
                                    return_time_obj = datetime.strptime(ret_time_str, "%H:%M").time()
                                except (ValueError, TypeError):
                                    return_time_obj = None
                            else:
                                return_time_obj = None

                            # Check for existing flight (within 2-hour window)
                            existing_flight = await self._check_duplicate_flight(
                                db,
                                origin_airport.id,
                                destination_airport.id,
                                flight_data.get("airline", "Unknown"),
                                departure_date_obj,
                                departure_time_obj,
                            )

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
                                    airline=flight_data.get("airline", "Unknown"),
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
