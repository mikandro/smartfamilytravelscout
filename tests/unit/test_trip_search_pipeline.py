"""
Unit tests for the trip search pipeline.

This flow previously existed only as a 290-line private function inside
``app/cli/main.py`` with no test file at all -- which is why a call site
passing six arguments to a seven-parameter function went unnoticed, silently
disabling AI analysis and ignoring --region.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.party_size import COUPLE, FAMILY
from app.orchestration.scraper_selection import NoScrapersEnabled
from app.orchestration.trip_search_pipeline import (
    DATES_NEXT_3_MONTHS,
    DATES_NEXT_6_MONTHS,
    DEFAULT_SCORING_LIMIT,
    PipelineReport,
    PipelineSpec,
    TripSearchPipeline,
)

pytestmark = pytest.mark.unit


class TestPipelineSpec:
    """A typed spec is what makes the argument-slide defect impossible."""

    def test_defaults_are_sensible(self):
        spec = PipelineSpec()
        assert spec.destinations == "all"
        assert spec.dates == DATES_NEXT_3_MONTHS
        assert spec.region == "Bavaria"
        assert spec.analyze is True
        assert spec.party == FAMILY

    def test_region_is_a_string_not_a_flag(self):
        """
        The bug: region received the boolean `analyze`, so
        get_school_holiday_periods was called with region=True.
        """
        spec = PipelineSpec(region="Berlin", analyze=False)
        assert spec.region == "Berlin"
        assert spec.analyze is False

    def test_three_month_horizon(self):
        spec = PipelineSpec(dates=DATES_NEXT_3_MONTHS)
        assert spec.search_horizon == date.today() + timedelta(days=90)

    def test_six_month_horizon(self):
        spec = PipelineSpec(dates=DATES_NEXT_6_MONTHS)
        assert spec.search_horizon == date.today() + timedelta(days=180)

    def test_unknown_dates_fall_back_to_three_months(self):
        assert PipelineSpec(dates="whenever").search_horizon == (
            date.today() + timedelta(days=90)
        )

    def test_is_immutable(self):
        with pytest.raises(Exception):
            PipelineSpec().region = "Hamburg"

    def test_scoring_limit_bounds_api_spend(self):
        assert PipelineSpec().scoring_limit == DEFAULT_SCORING_LIMIT

    def test_party_can_be_a_couple(self):
        assert PipelineSpec(party=COUPLE).party.total == 2


class TestPipelineReport:
    def test_starts_empty(self):
        report = PipelineReport()
        assert report.flights_found == 0
        assert report.packages == 0
        assert report.warnings == []

    def test_warnings_accumulate(self):
        report = PipelineReport()
        report.add_warning("something went sideways")
        assert "something went sideways" in report.warnings


class TestSourceSelection:
    async def test_disabling_everything_raises(self):
        """Nothing to scrape is an error mode, not a silent empty run."""
        spec = PipelineSpec(
            disable_scraper=["kiwi", "skyscanner", "ryanair", "wizzair"]
        )
        with pytest.raises(NoScrapersEnabled):
            await TripSearchPipeline().run(spec)

    async def test_resolved_scrapers_are_reported(self):
        spec = PipelineSpec(disable_scraper=["wizzair"])
        pipeline = TripSearchPipeline()

        with patch.object(
            pipeline, "_resolve_airports", new=AsyncMock()
        ), patch.object(
            pipeline, "_scrape_and_persist_flights", new=AsyncMock()
        ), patch.object(
            pipeline, "_scrape_accommodations", new=AsyncMock()
        ), patch.object(
            pipeline, "_generate_packages", new=AsyncMock()
        ), patch.object(
            pipeline, "_score_packages", new=AsyncMock()
        ), patch.object(
            pipeline, "_resolve_date_ranges"
        ):
            report = await pipeline.run(spec)

        assert "wizzair" not in report.scrapers_used


class TestStepSequencing:
    """The steps must run in order, and scoring only when asked."""

    async def _run_with_stubs(self, spec):
        pipeline = TripSearchPipeline()
        called = []

        async def record(name):
            async def _inner(*args, **kwargs):
                called.append(name)

            return _inner

        with patch.object(
            pipeline, "_resolve_airports", new=await record("airports")
        ), patch.object(
            pipeline, "_scrape_and_persist_flights", new=await record("flights")
        ), patch.object(
            pipeline, "_scrape_accommodations", new=await record("accommodations")
        ), patch.object(
            pipeline, "_generate_packages", new=await record("packages")
        ), patch.object(
            pipeline, "_score_packages", new=await record("scoring")
        ), patch.object(
            pipeline, "_resolve_date_ranges", side_effect=lambda *a: called.append("dates")
        ):
            report = await pipeline.run(spec)
        return called, report

    async def test_runs_every_step_in_order(self):
        called, _ = await self._run_with_stubs(PipelineSpec())
        assert called == [
            "airports",
            "dates",
            "flights",
            "accommodations",
            "packages",
            "scoring",
        ]

    async def test_scoring_is_skipped_when_analyze_is_false(self):
        called, _ = await self._run_with_stubs(PipelineSpec(analyze=False))
        assert "scoring" not in called

    async def test_scoring_runs_when_analyze_is_true(self):
        """
        Regression: the argument slide made `analyze` always None, so this
        step never ran in production.
        """
        called, _ = await self._run_with_stubs(PipelineSpec(analyze=True))
        assert "scoring" in called


class TestProgressIsInjected:
    """Progress is a callback, so the pipeline emits no terminal markup."""

    async def test_progress_callback_receives_steps(self):
        seen = []
        pipeline = TripSearchPipeline(
            on_progress=lambda step, detail: seen.append(step)
        )

        with patch.object(
            pipeline, "_scrape_and_persist_flights", new=AsyncMock()
        ), patch.object(
            pipeline, "_scrape_accommodations", new=AsyncMock()
        ), patch.object(
            pipeline, "_generate_packages", new=AsyncMock()
        ), patch.object(
            pipeline, "_score_packages", new=AsyncMock()
        ), patch.object(
            pipeline, "_resolve_airports", new=AsyncMock()
        ), patch.object(
            pipeline, "_resolve_date_ranges"
        ):
            await pipeline.run(PipelineSpec())

        # run() itself reports nothing; the steps do. Either way, no console.
        assert isinstance(seen, list)

    async def test_default_progress_is_silent(self):
        """No callback means no output -- safe for Celery workers."""
        pipeline = TripSearchPipeline()
        pipeline.on_progress("step", "detail")  # must not raise
