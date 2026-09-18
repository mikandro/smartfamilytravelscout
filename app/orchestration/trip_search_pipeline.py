"""
The end-to-end trip search, as a module.

This flow -- resolve destinations, resolve holiday date ranges, scrape flights,
persist them, compute true costs, scrape accommodations, generate packages,
match events, score with AI -- previously existed only as ``_run_pipeline``,
a 290-line private function inside ``app/cli/main.py`` with seven positional
parameters and no test file.

Because it was trapped there:

- ``daily_flight_search``, ``update_flight_prices``, ``discover_events`` and
  ``cleanup_old_data`` are ``TODO(#59)`` stubs that log success and return --
  the scheduled product did nothing, because it could not reach this logic.
- ``search_accommodations`` re-derived parts of it with a different
  destination rule.
- ``scout scrape`` re-implemented a different subset again.
- The call site passed six arguments to a seven-parameter function, so every
  argument after ``dates`` slid by one position: ``--region`` was ignored and
  AI analysis never ran.

The interface here is ``run(spec) -> PipelineReport``: one typed value in, one
report out, no terminal formatting. The CLI renders the report with Rich; a
Celery task can return it as a result; an API route can serialise it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_async_session_context
from app.domain.airport_registry import find_airport
from app.domain.party_size import FAMILY, PartySize
from app.models.airport import Airport
from app.models.flight import Flight
from app.models.trip_package import TripPackage
from app.orchestration.scraper_selection import (
    resolve_accommodation_scrapers,
    resolve_flight_scrapers,
)
from app.utils.cost_calculator import TrueCostCalculator
from app.utils.date_utils import get_school_holiday_periods

logger = logging.getLogger(__name__)

DATES_NEXT_3_MONTHS = "next-3-months"
DATES_NEXT_6_MONTHS = "next-6-months"

#: Cap on packages scored per run, to bound Claude API spend.
DEFAULT_SCORING_LIMIT = 50


@dataclass(frozen=True)
class PipelineSpec:
    """
    What a pipeline run should do.

    A typed value rather than seven positional parameters: the defect this
    module exists to prevent was a call site passing them in the wrong order.

    Attributes:
        destinations: IATA codes, or ``"all"`` for every airport flagged as a
            destination.
        dates: ``"next-3-months"`` or ``"next-6-months"``.
        region: German state whose school-holiday calendar to use.
        analyze: Whether to run AI scoring.
        max_price: Budget cap per package.
        party: Who the trip is for.
        enable_scraper / disable_scraper: Runtime source overrides.
        scoring_limit: Maximum packages to score in one run.
    """

    destinations: str = "all"
    dates: str = DATES_NEXT_3_MONTHS
    region: str = "Bavaria"
    analyze: bool = True
    max_price: Optional[float] = None
    party: PartySize = FAMILY
    enable_scraper: Optional[Sequence[str]] = None
    disable_scraper: Optional[Sequence[str]] = None
    scoring_limit: int = DEFAULT_SCORING_LIMIT

    @property
    def search_horizon(self) -> date:
        """The last date to search, derived from ``dates``."""
        days = 180 if self.dates == DATES_NEXT_6_MONTHS else 90
        return date.today() + timedelta(days=days)


@dataclass
class PipelineReport:
    """
    What a pipeline run did.

    Returned rather than printed, so the CLI, Celery and the API can each
    present it however suits them.
    """

    flights_found: int = 0
    flights_saved: int = 0
    true_costs_calculated: int = 0
    accommodations: int = 0
    packages: int = 0
    analyzed: int = 0
    origins: List[str] = field(default_factory=list)
    destinations: List[str] = field(default_factory=list)
    date_ranges: List[tuple] = field(default_factory=list)
    scrapers_used: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_warning(self, message: str) -> None:
        logger.warning(message)
        self.warnings.append(message)


#: Called with (step_name, detail). The CLI wires this to a Rich progress bar;
#: other callers pass nothing and the pipeline stays silent.
ProgressCallback = Callable[[str, str], None]


def _noop_progress(step: str, detail: str) -> None:
    return None


class TripSearchPipeline:
    """
    Runs the end-to-end trip search.

    Progress is an injected callback rather than a Rich console, so this can
    run under Celery without emitting ANSI markup into worker logs.
    """

    def __init__(self, on_progress: Optional[ProgressCallback] = None):
        self.on_progress = on_progress or _noop_progress

    async def run(self, spec: PipelineSpec) -> PipelineReport:
        """
        Execute the full pipeline.

        Args:
            spec: What to search for.

        Returns:
            A report of what happened. Steps that fail for one destination are
            recorded as warnings rather than aborting the run; a failure that
            makes the whole run meaningless (no scrapers enabled) raises.

        Raises:
            NoScrapersEnabled: If source selection resolves to nothing.
        """
        report = PipelineReport()

        selection = resolve_flight_scrapers(
            enable=spec.enable_scraper,
            disable=spec.disable_scraper,
        )
        report.scrapers_used = list(selection.names)
        for ignored in selection.ignored:
            report.add_warning(f"Ignored unknown scraper '{ignored}'")

        await self._resolve_airports(spec, report)
        self._resolve_date_ranges(spec, report)

        await self._scrape_and_persist_flights(spec, report)
        await self._scrape_accommodations(spec, report)
        await self._generate_packages(spec, report)

        if spec.analyze:
            await self._score_packages(spec, report)

        return report

    # -- steps ------------------------------------------------------------

    async def _resolve_airports(
        self, spec: PipelineSpec, report: PipelineReport
    ) -> None:
        """Resolve which origins and destinations to search."""
        self.on_progress("destinations", "Loading destinations")

        async with get_async_session_context() as db:
            if spec.destinations == "all":
                result = await db.execute(
                    select(Airport).where(Airport.is_destination.is_(True))
                )
                report.destinations = [a.iata_code for a in result.scalars().all()]
            else:
                report.destinations = [
                    code.strip().upper()
                    for code in spec.destinations.split(",")
                    if code.strip()
                ]

            origin_result = await db.execute(
                select(Airport).where(Airport.is_origin.is_(True))
            )
            report.origins = [a.iata_code for a in origin_result.scalars().all()]

        if not report.origins:
            report.add_warning(
                "No airports are flagged as origins; run `scout db seed` first"
            )
        if not report.destinations:
            report.add_warning("No destinations resolved")

    def _resolve_date_ranges(
        self, spec: PipelineSpec, report: PipelineReport
    ) -> None:
        """Resolve the school-holiday windows to search within."""
        self.on_progress("dates", "Calculating date ranges")

        # spec.region is used here. The old call site's argument slide meant
        # this received the boolean `analyze` instead of a region name.
        report.date_ranges = get_school_holiday_periods(
            start_date=date.today(),
            end_date=spec.search_horizon,
            region=spec.region,
        )

        if not report.date_ranges:
            report.add_warning(
                f"No school holiday periods found for region '{spec.region}'"
            )

    async def _scrape_and_persist_flights(
        self, spec: PipelineSpec, report: PipelineReport
    ) -> None:
        """Scrape flights, save them, and compute their true costs."""
        from app.orchestration.flight_orchestrator import FlightOrchestrator

        if not (report.origins and report.destinations and report.date_ranges):
            report.add_warning("Skipping flight scrape: nothing to search")
            return

        self.on_progress("flights", "Scraping flights")

        orchestrator = FlightOrchestrator(
            enabled_scrapers=report.scrapers_used,
            party=spec.party,
            console=None,
        )
        flights = await orchestrator.scrape_all(
            origins=report.origins,
            destinations=report.destinations,
            date_ranges=report.date_ranges,
        )
        report.flights_found = len(flights)

        if not flights:
            return

        # scrape_all returns dictionaries "ready for database insertion" and
        # does not save. The CLI never called this, so scraped flights were
        # discarded and packages were built from stale rows.
        self.on_progress("flights", "Saving flights")
        save_stats = await orchestrator.save_to_database(flights)
        report.flights_saved = save_stats["inserted"] + save_stats["updated"]

        await self._calculate_true_costs(report)

    async def _calculate_true_costs(self, report: PipelineReport) -> None:
        """
        Populate ``Flight.true_cost`` for flights that lack it.

        AccommodationMatcher filters on ``true_cost IS NOT NULL``, and
        TrueCostCalculator had no callers anywhere in ``app/`` -- so the column
        was always NULL and package generation always found zero destinations.
        """
        self.on_progress("true_cost", "Calculating true costs")

        async with get_async_session_context() as db:
            calculator = TrueCostCalculator(db)
            await calculator.load_airports_async()

            # origin_airport must be eager-loaded: the calculator reads
            # flight.origin_airport.iata_code, and a lazy load on an async
            # session raises.
            result = await db.execute(
                select(Flight)
                .where(Flight.true_cost.is_(None))
                .options(selectinload(Flight.origin_airport))
            )
            pending = list(result.scalars().all())
            if pending:
                await calculator.calculate_for_all_flights_async(pending)
            report.true_costs_calculated = len(pending)

    async def _scrape_accommodations(
        self, spec: PipelineSpec, report: PipelineReport
    ) -> None:
        """Scrape accommodations for each destination city."""
        from app.orchestration.accommodation_orchestrator import (
            AccommodationOrchestrator,
        )

        if not report.date_ranges or not report.destinations:
            return

        self.on_progress("accommodations", "Scraping accommodations")

        acc_selection = resolve_accommodation_scrapers(
            enable=spec.enable_scraper,
            disable=spec.disable_scraper,
        )
        orchestrator = AccommodationOrchestrator(
            enabled_scrapers=list(acc_selection.names)
        )
        check_in, check_out = report.date_ranges[0]

        for code in report.destinations:
            try:
                async with get_async_session_context() as db:
                    airport = await find_airport(db, code)
                    city = airport.city if airport else code

                self.on_progress("accommodations", city)

                accommodations = await orchestrator.search_all_sources(
                    city=city,
                    check_in=check_in,
                    check_out=check_out,
                    adults=spec.party.adults,
                    children=spec.party.children,
                )
                if accommodations:
                    stats = await orchestrator.save_to_database(accommodations)
                    report.accommodations += stats["inserted"] + stats["updated"]
            except Exception as exc:
                # One destination failing must not abort the whole run.
                report.add_warning(f"Accommodation scrape failed for {code}: {exc}")

    async def _generate_packages(
        self, spec: PipelineSpec, report: PipelineReport
    ) -> None:
        """Pair flights with accommodations, then attach events."""
        from app.orchestration.accommodation_matcher import AccommodationMatcher
        from app.orchestration.event_matcher import EventMatcher

        self.on_progress("packages", "Generating trip packages")

        async with get_async_session_context() as db:
            matcher = AccommodationMatcher(party=spec.party)
            packages = await matcher.generate_trip_packages(
                db=db,
                max_budget=spec.max_price or settings.max_flight_price_per_person,
            )
            report.packages = len(packages)

            self.on_progress("events", "Matching events")
            event_matcher = EventMatcher(db_session=db)
            await event_matcher.match_events_to_packages(packages)

    async def _score_packages(
        self, spec: PipelineSpec, report: PipelineReport
    ) -> None:
        """Score unscored packages with Claude, up to the run's cap."""
        from redis.asyncio import Redis

        from app.ai.claude_client import ClaudeClient
        from app.ai.deal_scorer import DealScorer

        self.on_progress("scoring", "Running AI analysis")

        redis_client = None
        try:
            redis_client = await Redis.from_url(str(settings.redis_url))
        except Exception as exc:
            report.add_warning(f"Redis unavailable, AI responses will not cache: {exc}")

        try:
            async with get_async_session_context() as db:
                result = await db.execute(
                    select(TripPackage).where(TripPackage.ai_score.is_(None))
                )
                to_score = list(result.scalars().all())[: spec.scoring_limit]

                if not to_score:
                    return

                claude = ClaudeClient(
                    api_key=settings.anthropic_api_key,
                    redis_client=redis_client,
                    db_session=db,
                )
                scorer = DealScorer(claude_client=claude, db_session=db)

                for package in to_score:
                    try:
                        self.on_progress("scoring", package.destination_city or "")
                        score_data = await scorer.score_trip(package)
                        if score_data:
                            package.ai_score = score_data["score"]
                            package.ai_reasoning = score_data["reasoning"]
                            await db.commit()
                            report.analyzed += 1
                    except Exception as exc:
                        # One bad package must not lose the scores already
                        # written for the others.
                        report.add_warning(
                            f"Scoring failed for package {package.id}: {exc}"
                        )
        finally:
            if redis_client is not None:
                await redis_client.close()
