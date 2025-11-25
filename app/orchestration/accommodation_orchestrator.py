"""
Accommodation Orchestrator for coordinating multiple accommodation data sources.

This module orchestrates scraping from Booking.com and Airbnb,
deduplicates results, and saves unique accommodations to the database.

Example:
    >>> orchestrator = AccommodationOrchestrator()
    >>> accommodations = await orchestrator.search_all_sources(
    ...     city="Barcelona",
    ...     check_in=date(2025, 7, 1),
    ...     check_out=date(2025, 7, 7)
    ... )
    >>> print(f"Found {len(accommodations)} unique accommodations")
"""

import asyncio
import logging
from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session_context
from app.models.accommodation import Accommodation
from app.models.scraping_job import ScrapingJob
from app.scrapers.booking_scraper import BookingClient
from app.scrapers.airbnb_scraper import AirbnbClient

logger = logging.getLogger(__name__)
console = Console()


class AccommodationOrchestrator:
    """
    Orchestrates multiple accommodation scrapers to gather and deduplicate accommodation data.

    This class coordinates two accommodation data sources (Booking.com and Airbnb),
    runs them in parallel for maximum efficiency, deduplicates results based on
    name and location, and saves unique accommodations to the database.

    Features:
        - Parallel execution of all scrapers using asyncio.gather()
        - Graceful error handling - continues if individual scrapers fail
        - Deduplication based on name, city, and price range
        - Batch database operations for efficiency
        - Progress tracking with Rich console output
        - Comprehensive logging and statistics

    Attributes:
        booking: Booking.com scraper client
        airbnb: Airbnb scraper client
    """

    def __init__(self):
        """Initialize enabled accommodation scrapers based on configuration."""
        self.enabled_scrapers = self._get_available_scrapers()

        # Initialize scrapers based on availability
        self.booking = None
        self.airbnb = None

        if "booking" in self.enabled_scrapers:
            self.booking = BookingClient(headless=True)

        if "airbnb" in self.enabled_scrapers:
            self.airbnb = AirbnbClient()

        logger.info(
            f"AccommodationOrchestrator initialized with {len(self.enabled_scrapers)} scrapers: "
            f"{', '.join(self.enabled_scrapers)}"
        )

    def _get_available_scrapers(self) -> List[str]:
        """
        Determine which accommodation scrapers are available.

        Returns:
            List of available scraper names
        """
        available = []

        # Booking.com is always available (uses Playwright)
        available.append("booking")

        # Airbnb is always available (uses Apify or Playwright fallback)
        available.append("airbnb")

        return available

    async def search_all_sources(
        self,
        city: str,
        check_in: date,
        check_out: date,
        adults: int = 2,
        children: int = 2,
    ) -> List[Dict]:
        """
        Run all scrapers in parallel, deduplicate, and return unique accommodations.

        This is the main entry point for accommodation scraping. It creates tasks for all
        enabled scrapers, then runs them concurrently using asyncio.gather().

        Args:
            city: Destination city name (e.g., 'Barcelona', 'Lisbon')
            check_in: Check-in date
            check_out: Check-out date
            adults: Number of adults (default: 2)
            children: Number of children (default: 2)

        Returns:
            List of unique accommodation dictionaries ready for database insertion

        Example:
            >>> accommodations = await orchestrator.search_all_sources(
            ...     city="Barcelona",
            ...     check_in=date(2025, 7, 1),
            ...     check_out=date(2025, 7, 7)
            ... )
            >>> print(f"Found {len(accommodations)} unique accommodations")
        """
        logger.info(
            f"Starting search_all_sources for {city}: "
            f"{check_in} to {check_out}, {adults} adults, {children} children"
        )

        start_time = datetime.now()

        # Create tasks for all enabled scrapers
        tasks = []
        task_metadata = []  # Track which scraper each task represents

        if self.booking:
            tasks.append(
                self._scrape_source(
                    self.booking, "booking", city, check_in, check_out, adults, children
                )
            )
            task_metadata.append(f"Booking.com: {city}")

        if self.airbnb:
            tasks.append(
                self._scrape_source(
                    self.airbnb, "airbnb", city, check_in, check_out, adults, children
                )
            )
            task_metadata.append(f"Airbnb: {city}")

        if not tasks:
            logger.warning("No scrapers available")
            return []

        console.print(
            f"\n[bold cyan]Starting {len(tasks)} accommodation scraping tasks in parallel...[/bold cyan]\n"
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
            task_id = progress.add_task("[cyan]Scraping accommodations...", total=len(tasks))

            # Gather results with return_exceptions=True to handle failures gracefully
            results = await asyncio.gather(*tasks, return_exceptions=True)

            progress.update(task_id, completed=len(tasks))

        # Process results and collect statistics
        all_accommodations = []
        successful_scrapers = 0
        failed_scrapers = 0
        scraper_stats = defaultdict(lambda: {"success": 0, "failed": 0, "accommodations": 0})

        for idx, result in enumerate(results):
            scraper_name = task_metadata[idx].split(":")[0]

            if isinstance(result, Exception):
                logger.error(f"Scraper failed ({task_metadata[idx]}): {result}")
                failed_scrapers += 1
                scraper_stats[scraper_name]["failed"] += 1
            else:
                successful_scrapers += 1
                scraper_stats[scraper_name]["success"] += 1
                scraper_stats[scraper_name]["accommodations"] += len(result)
                all_accommodations.extend(result)

        # Log statistics
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Scraping completed: {successful_scrapers} successful, {failed_scrapers} failed, "
            f"{len(all_accommodations)} total accommodations, {elapsed_time:.2f}s elapsed"
        )

        # Print statistics table
        self._print_stats_table(scraper_stats, elapsed_time)

        # Deduplicate accommodations
        console.print(
            f"\n[bold yellow]Deduplicating {len(all_accommodations)} accommodations...[/bold yellow]"
        )
        unique_accommodations = self.deduplicate(all_accommodations)

        console.print(
            f"[bold green]✓ Found {len(unique_accommodations)} unique accommodations "
            f"(removed {len(all_accommodations) - len(unique_accommodations)} duplicates)[/bold green]\n"
        )

        return unique_accommodations

    def _print_stats_table(self, scraper_stats: Dict, elapsed_time: float):
        """Print a Rich table with scraper statistics."""
        table = Table(title="Scraping Statistics")

        table.add_column("Scraper", style="cyan", no_wrap=True)
        table.add_column("Successful", style="green")
        table.add_column("Failed", style="red")
        table.add_column("Accommodations Found", style="yellow")

        for scraper, stats in scraper_stats.items():
            table.add_row(
                scraper,
                str(stats["success"]),
                str(stats["failed"]),
                str(stats["accommodations"]),
            )

        table.add_section()
        table.add_row(
            "[bold]Total[/bold]",
            "[bold]" + str(sum(s["success"] for s in scraper_stats.values())) + "[/bold]",
            "[bold]" + str(sum(s["failed"] for s in scraper_stats.values())) + "[/bold]",
            "[bold]" + str(sum(s["accommodations"] for s in scraper_stats.values())) + "[/bold]",
        )

        console.print(table)
        console.print(f"\n[dim]Time elapsed: {elapsed_time:.2f}s[/dim]\n")

    async def _scrape_source(
        self,
        scraper,
        scraper_name: str,
        city: str,
        check_in: date,
        check_out: date,
        adults: int,
        children: int,
    ) -> List[Dict]:
        """
        Scrape a single source with error handling and normalization.

        This method wraps individual scraper calls with error handling, logging,
        and data normalization to ensure consistent output format.

        Args:
            scraper: Scraper instance (BookingClient or AirbnbClient)
            scraper_name: Name of the scraper for logging ('booking', 'airbnb')
            city: Destination city name
            check_in: Check-in date
            check_out: Check-out date
            adults: Number of adults
            children: Number of children

        Returns:
            List of normalized accommodation dictionaries, or empty list if scraping fails
        """
        logger.info(
            f"[{scraper_name}] Scraping {city}, "
            f"{check_in} to {check_out}, {adults} adults, {children} children"
        )

        try:
            if scraper_name == "booking":
                # Booking.com scraper
                async with scraper:
                    accommodations = await scraper.search(
                        city=city,
                        check_in=check_in,
                        check_out=check_out,
                        adults=adults,
                        children_ages=[3, 6] if children >= 2 else [3],
                        limit=20,
                    )
                    # Apply family-friendly filter
                    accommodations = scraper.filter_family_friendly(
                        accommodations,
                        min_bedrooms=2,
                        max_price=settings.max_accommodation_price_per_night,
                        min_rating=7.5,
                    )

                # Normalize Booking.com data
                for acc in accommodations:
                    acc["destination_city"] = city
                    acc["source"] = "booking"
                    acc["scraped_at"] = datetime.now().isoformat()

            elif scraper_name == "airbnb":
                # Airbnb scraper
                accommodations = await scraper.search(
                    city=city,
                    check_in=check_in,
                    check_out=check_out,
                    adults=adults,
                    children=children,
                    max_listings=20,
                )

                # Apply family-friendly filter
                accommodations = scraper.filter_family_suitable(accommodations)

                # Normalize Airbnb data
                for acc in accommodations:
                    acc["destination_city"] = city
                    acc["source"] = "airbnb"
                    if isinstance(acc.get("scraped_at"), datetime):
                        acc["scraped_at"] = acc["scraped_at"].isoformat()
                    else:
                        acc["scraped_at"] = datetime.now().isoformat()

            else:
                logger.error(f"Unknown scraper: {scraper_name}")
                return []

            logger.info(f"[{scraper_name}] Found {len(accommodations)} accommodations")
            return accommodations

        except Exception as e:
            logger.error(
                f"[{scraper_name}] Scraping failed for {city}: {e}",
                exc_info=True,
            )
            return []

    def deduplicate(self, accommodations: List[Dict]) -> List[Dict]:
        """
        Remove duplicate accommodations across sources.

        Accommodations are considered duplicates if they have:
        - Similar name (fuzzy match)
        - Same city
        - Similar price (within 10%)

        When duplicates are found:
        - Keep the one with the highest rating
        - Merge booking URLs (keep all sources for user choice)

        Args:
            accommodations: List of accommodation dictionaries from all sources

        Returns:
            List of unique accommodation dictionaries with merged URLs

        Example:
            >>> all_accommodations = [...]  # Accommodations from multiple sources
            >>> unique = orchestrator.deduplicate(all_accommodations)
            >>> print(f"Reduced from {len(all_accommodations)} to {len(unique)} accommodations")
        """
        if not accommodations:
            return []

        logger.info(f"Deduplicating {len(accommodations)} accommodations...")

        # Simple deduplication based on name similarity and price
        # Group by city and approximate name
        grouped = defaultdict(list)

        for acc in accommodations:
            try:
                # Create grouping key based on normalized name and city
                name = acc.get("name", "").lower().strip()
                city = acc.get("destination_city", "").lower().strip()
                price = acc.get("price_per_night", 0)

                # Normalize name (remove common words for better matching)
                name_normalized = name.replace("apartment", "").replace("hotel", "").strip()

                # Group by first 20 characters of normalized name + city
                # This allows for minor variations in naming
                key = (
                    name_normalized[:20] if len(name_normalized) >= 20 else name_normalized,
                    city,
                    int(price / 10) * 10,  # Group by price in 10 EUR buckets
                )

                grouped[key].append(acc)

            except Exception as e:
                logger.warning(f"Error processing accommodation for deduplication: {e}")
                continue

        # Keep best from each group
        unique_accommodations = []

        for key, acc_group in grouped.items():
            try:
                # Find accommodation with highest rating
                best = max(
                    acc_group,
                    key=lambda a: (
                        a.get("rating") or 0,
                        -(a.get("price_per_night") or 999),  # Prefer lower price as tiebreaker
                    ),
                )

                # Merge URLs from all sources
                urls = []
                sources = []

                for acc in acc_group:
                    url = acc.get("url")
                    if url and url not in urls:
                        urls.append(url)

                    source = acc.get("source")
                    if source and source not in sources:
                        sources.append(source)

                # Update best accommodation with merged data
                best["booking_urls"] = urls
                best["sources"] = sources
                best["duplicate_count"] = len(acc_group)

                unique_accommodations.append(best)

            except Exception as e:
                logger.warning(f"Error selecting best accommodation from group: {e}")
                continue

        duplicates_removed = len(accommodations) - len(unique_accommodations)
        logger.info(
            f"Deduplication complete: {len(unique_accommodations)} unique accommodations "
            f"({duplicates_removed} duplicates removed)"
        )

        return unique_accommodations

    async def save_to_database(
        self, accommodations: List[Dict], create_job: bool = True
    ) -> Dict[str, int]:
        """
        Batch save accommodations to database with duplicate checking.

        Uses SQLAlchemy bulk operations for efficiency. Updates existing accommodations
        if price is cheaper, otherwise skips duplicates.

        Args:
            accommodations: List of accommodation dictionaries to save
            create_job: Whether to create a ScrapingJob record (default: True)

        Returns:
            Dict with statistics:
                {
                    'total': Total accommodations processed,
                    'inserted': New accommodations inserted,
                    'updated': Accommodations updated with cheaper prices,
                    'skipped': Accommodations skipped (duplicates)
                }

        Example:
            >>> stats = await orchestrator.save_to_database(unique_accommodations)
            >>> print(f"Inserted {stats['inserted']}, Updated {stats['updated']}")
        """
        stats = {
            "total": len(accommodations),
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
        }

        if not accommodations:
            logger.info("No accommodations to save")
            return stats

        logger.info(f"Saving {len(accommodations)} accommodations to database...")

        # Create scraping job if requested
        job = None
        job_start_time = datetime.now()

        async with get_async_session_context() as db:
            try:
                if create_job:
                    job = ScrapingJob(
                        job_type="accommodations",
                        source="orchestrator",
                        status="running",
                        items_scraped=0,
                        started_at=job_start_time,
                    )
                    db.add(job)
                    await db.flush()

                # Process accommodations in batches for efficiency
                batch_size = 50

                for i in range(0, len(accommodations), batch_size):
                    batch = accommodations[i : i + batch_size]

                    for acc_data in batch:
                        try:
                            # Convert scraped_at to datetime if it's a string
                            if isinstance(acc_data.get("scraped_at"), str):
                                acc_data["scraped_at"] = datetime.fromisoformat(
                                    acc_data["scraped_at"].replace("Z", "+00:00")
                                )

                            # Check for existing accommodation (by name and city)
                            existing_acc = await self._check_duplicate_accommodation(
                                db,
                                acc_data.get("name", ""),
                                acc_data.get("destination_city", ""),
                            )

                            price_per_night = acc_data.get("price_per_night", 0.0)

                            if existing_acc:
                                # Update if new price is cheaper
                                if price_per_night < existing_acc.price_per_night:
                                    logger.info(
                                        f"Updating accommodation {existing_acc.id}: "
                                        f"€{existing_acc.price_per_night} → €{price_per_night}"
                                    )
                                    existing_acc.price_per_night = price_per_night
                                    existing_acc.url = acc_data.get("url", existing_acc.url)
                                    existing_acc.image_url = acc_data.get("image_url", existing_acc.image_url)
                                    existing_acc.rating = acc_data.get("rating", existing_acc.rating)
                                    existing_acc.review_count = acc_data.get("review_count", existing_acc.review_count)
                                    existing_acc.scraped_at = datetime.now()
                                    stats["updated"] += 1
                                else:
                                    stats["skipped"] += 1
                            else:
                                # Insert new accommodation
                                new_accommodation = Accommodation(
                                    destination_city=acc_data.get("destination_city", "Unknown"),
                                    name=acc_data.get("name", "Unknown"),
                                    type=acc_data.get("type", "hotel"),
                                    bedrooms=acc_data.get("bedrooms"),
                                    price_per_night=price_per_night,
                                    family_friendly=acc_data.get("family_friendly", False),
                                    has_kitchen=acc_data.get("has_kitchen", False),
                                    has_kids_club=acc_data.get("has_kids_club", False),
                                    rating=acc_data.get("rating"),
                                    review_count=acc_data.get("review_count"),
                                    source=acc_data.get("source", "unknown"),
                                    url=acc_data.get("url"),
                                    image_url=acc_data.get("image_url"),
                                    scraped_at=acc_data.get("scraped_at", datetime.now()),
                                )
                                db.add(new_accommodation)
                                stats["inserted"] += 1

                        except Exception as e:
                            logger.error(f"Error saving accommodation: {e}", exc_info=True)
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

    async def _check_duplicate_accommodation(
        self, db: AsyncSession, name: str, city: str
    ) -> Optional[Accommodation]:
        """
        Check if a similar accommodation already exists in the database.

        A duplicate is defined as:
        - Same name (case-insensitive)
        - Same destination city

        Args:
            db: Database session
            name: Accommodation name
            city: Destination city

        Returns:
            Existing accommodation if found, None otherwise
        """
        if not name or not city:
            return None

        result = await db.execute(
            select(Accommodation).where(
                Accommodation.name.ilike(name),
                Accommodation.destination_city.ilike(city),
            )
        )
        return result.scalar_one_or_none()
