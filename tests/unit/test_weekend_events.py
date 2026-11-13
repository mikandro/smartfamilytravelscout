"""
Unit tests for dated events in the weekend planner: storing scraped events,
offering them to Claude, the unvetted fallback, and the email section.
"""

from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import ScraperException
from app.models.event import Event
from app.models.scraping_job import ScrapingJob
from app.weekend import events as events_module
from app.weekend import service
from app.weekend.events import refresh_local_events, save_local_events
from app.weekend.planner import (
    build_weekend_plan,
    fallback_events,
    group_weekend_events,
)
from tests.unit.test_weekend_planner import (
    SATURDAY,
    SUNDAY,
    make_day,
    make_place,
    mock_db,
    plan_kwargs,
)

PLACES = [make_place(1, "park", "outdoor"), make_place(2, "museum", "indoor")]
FORECAST = [make_day(SATURDAY), make_day(SUNDAY)]


def make_event(title, day=SATURDAY, **overrides):
    values = dict(
        destination_city="Munich",
        title=title,
        venue="Testbühne",
        event_date=day,
        end_date=day,
        category="family",
        description=None,
        price_range="varies",
        source="muenchen.de",
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        showtimes=["15:00-16:00"],
    )
    values.update(overrides)
    return Event(**values)


def event_dict(title="Kasperl", day=SATURDAY, **overrides):
    values = dict(
        destination_city="Munich",
        title=title,
        venue="Testbühne",
        event_date=day,
        end_date=day,
        category="family",
        description=None,
        price_range="varies",
        source="muenchen.de",
        url="https://example.com/kasperl",
        showtimes=["15:00"],
    )
    values.update(overrides)
    return values


def storage_db(existing=None):
    """A session mock for save_local_events: every lookup returns ``existing``."""
    result = MagicMock()
    result.scalars.return_value.first.return_value = existing

    @asynccontextmanager
    async def savepoint():
        yield

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.begin_nested = MagicMock(side_effect=savepoint)
    return db


# --------------------------------------------------------------------------- #
# Grouping and fallback
# --------------------------------------------------------------------------- #


class TestGroupWeekendEvents:
    def test_same_show_on_both_days_becomes_one_option(self):
        events = [
            make_event("Kasperl", SATURDAY, showtimes=["15:00-16:00"]),
            make_event("Kasperl", SUNDAY, showtimes=["11:00-12:00", "15:00-16:00"]),
        ]
        (option,) = group_weekend_events(events, SATURDAY)
        assert option.schedule == {
            "2026-11-14": ["15:00-16:00"],
            "2026-11-15": ["11:00-12:00", "15:00-16:00"],
        }
        assert option.when_text == "Sat 15:00-16:00 · Sun 11:00-12:00, 15:00-16:00"

    def test_same_title_at_another_venue_stays_separate(self):
        events = [make_event("Kasperl"), make_event("Kasperl", venue="Andere Bühne")]
        assert len(group_weekend_events(events, SATURDAY)) == 2

    def test_long_running_event_is_marked_ongoing_and_sorted_last(self):
        events = [
            make_event("Ausstellung", end_date=date(2027, 1, 10), showtimes=["09:00-17:00"]),
            make_event("Einmaliges Fest", showtimes=["16:00"]),
        ]
        options = group_weekend_events(events, SATURDAY)
        assert [(o.title, o.ongoing) for o in options] == [
            ("Einmaliges Fest", False),
            ("Ausstellung", True),
        ]

    def test_family_events_come_before_other_categories(self):
        events = [
            make_event("Wintermarkt", category="christmas_market", showtimes=["10:00"]),
            make_event("Kasperl", showtimes=["15:00"]),
        ]
        assert [o.title for o in group_weekend_events(events, SATURDAY)] == [
            "Kasperl",
            "Wintermarkt",
        ]

    def test_event_without_times_shows_only_the_day(self):
        (option,) = group_weekend_events([make_event("Flohmarkt", showtimes=None)], SATURDAY)
        assert option.when_text == "Sat"

    def test_fallback_takes_only_limited_run_family_events(self):
        events = [
            make_event("Ausstellung", end_date=date(2027, 1, 10)),
            make_event("Wintermarkt", category="christmas_market"),
            make_event("A"),
            make_event("B"),
            make_event("C"),
            make_event("D"),
        ]
        picked = fallback_events(group_weekend_events(events, SATURDAY))
        assert [o.title for o in picked] == ["A", "B", "C"]
        assert all(not o.vetted for o in picked)


# --------------------------------------------------------------------------- #
# Events in the plan
# --------------------------------------------------------------------------- #


class TestPlanWithEvents:
    EVENTS = [
        make_event("Kasperl", description="Puppentheater. Facts: Alter: ab 3 Jahren"),
        make_event("Mozart-Requiem", category="family", showtimes=["19:00"]),
        make_event("Wintermarkt", category="christmas_market", showtimes=["11:00-20:00"]),
    ]

    async def test_events_are_loaded_from_the_database_for_the_home_city(self):
        db = mock_db(PLACES, events=self.EVENTS)
        await build_weekend_plan(db, forecast=FORECAST, **plan_kwargs())
        query = str(
            db.execute.call_args_list[2].args[0].compile(compile_kwargs={"literal_binds": True})
        )
        assert "destination_city = 'Munich'" in query
        assert "'muenchen.de'" in query
        assert "2026-11-14" in query and "2026-11-15" in query

    async def test_without_claude_events_are_shown_unvetted(self):
        plan = await build_weekend_plan(
            mock_db(PLACES, events=self.EVENTS), forecast=FORECAST, **plan_kwargs()
        )
        assert [e.title for e in plan.events] == ["Kasperl", "Mozart-Requiem"]
        assert all(not e.vetted for e in plan.events)

    async def test_claude_sees_the_events_and_its_picks_are_vetted(self):
        claude = AsyncMock()
        claude.analyze.return_value = {
            "summary": "ok",
            "events": [
                {"id": "e1", "why": "Puppet show for small children.", "age_note": "from age 3"},
                {"id": "e99", "why": "not in the list"},
                {"id": "e1", "why": "duplicate"},
            ],
        }
        plan = await build_weekend_plan(
            mock_db(PLACES, events=self.EVENTS), forecast=FORECAST, claude=claude, **plan_kwargs()
        )
        (event,) = plan.events
        assert (event.title, event.why, event.age_note, event.vetted) == (
            "Kasperl",
            "Puppet show for small children.",
            "from age 3",
            True,
        )

        kwargs = claude.analyze.call_args.kwargs
        prompt = kwargs["prompt"].format(**kwargs["data"])
        assert "- e1 | Kasperl | Testbühne | family | Sat 15:00-16:00 | limited run" in prompt
        assert "Alter: ab 3 Jahren" in prompt
        assert "e3 | Wintermarkt" in prompt
        assert "pick up to 3" in prompt

    async def test_claude_choosing_no_events_removes_the_unvetted_ones(self):
        claude = AsyncMock()
        claude.analyze.return_value = {"summary": "ok", "events": []}
        plan = await build_weekend_plan(
            mock_db(PLACES, events=self.EVENTS), forecast=FORECAST, claude=claude, **plan_kwargs()
        )
        assert plan.events == []

    async def test_claude_failure_keeps_the_unvetted_events(self):
        claude = AsyncMock()
        claude.analyze.side_effect = RuntimeError("API down")
        plan = await build_weekend_plan(
            mock_db(PLACES, events=self.EVENTS), forecast=FORECAST, claude=claude, **plan_kwargs()
        )
        assert [e.title for e in plan.events] == ["Kasperl", "Mozart-Requiem"]

    async def test_prompt_says_so_when_there_are_no_events(self):
        claude = AsyncMock()
        claude.analyze.return_value = {"summary": "ok"}
        plan = await build_weekend_plan(
            mock_db(PLACES), forecast=FORECAST, claude=claude, **plan_kwargs()
        )
        assert plan.events == []
        assert claude.analyze.call_args.kwargs["data"]["events"] == "(no dated events found)"

    async def test_events_are_stored_with_the_plan(self):
        plan = await build_weekend_plan(
            mock_db(PLACES, events=self.EVENTS), forecast=FORECAST, **plan_kwargs()
        )
        stored = plan.to_dict()["events"]
        assert stored[0]["title"] == "Kasperl"
        assert stored[0]["schedule"] == {"2026-11-14": ["15:00-16:00"]}


# --------------------------------------------------------------------------- #
# Storing scraped events
# --------------------------------------------------------------------------- #


class TestSaveLocalEvents:
    async def test_new_event_is_inserted_with_showtimes_and_hash(self):
        db = storage_db()
        counts = await save_local_events(db, [event_dict(showtimes=["11:00", "15:00"])])
        assert counts == {"created": 1, "updated": 0}
        saved = db.add.call_args.args[0]
        assert isinstance(saved, Event)
        assert saved.showtimes == ["11:00", "15:00"]
        assert saved.destination_city == "Munich"
        assert len(saved.deduplication_hash) == 64

    async def test_same_event_twice_in_one_batch_is_stored_once(self):
        db = storage_db()
        counts = await save_local_events(db, [event_dict(), event_dict()])
        assert counts == {"created": 1, "updated": 0}

    async def test_existing_event_is_refreshed_not_duplicated(self):
        existing = make_event("Kasperl", showtimes=["15:00"], description="Short", url=None)
        db = storage_db(existing)
        counts = await save_local_events(
            db,
            [
                event_dict(
                    showtimes=["11:00", "15:00"],
                    description="A much longer description",
                    price_range="free",
                    end_date=SUNDAY,
                )
            ],
        )
        assert counts == {"created": 0, "updated": 1}
        db.add.assert_not_called()
        assert existing.showtimes == ["11:00", "15:00"]
        assert existing.description == "A much longer description"
        assert existing.price_range == "free"
        assert existing.end_date == SUNDAY
        assert existing.url == "https://example.com/kasperl"

    async def test_refresh_does_not_replace_a_longer_description_or_known_price(self):
        existing = make_event("Kasperl", description="A long existing text", price_range="free")
        db = storage_db(existing)
        await save_local_events(db, [event_dict(description="Short", price_range="varies")])
        assert existing.description == "A long existing text"
        assert existing.price_range == "free"


class TestRefreshLocalEvents:
    def scraper(self, result=None, error=None):
        scraper = MagicMock()
        scraper.SOURCE_NAME = "muenchen.de"
        scraper.scrape_events = AsyncMock(return_value=result, side_effect=error)
        scraper.close = AsyncMock()
        return scraper

    def job(self, db):
        return next(c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], ScrapingJob))

    async def test_scrapes_stores_and_records_a_completed_job(self):
        db = storage_db()
        scraper = self.scraper([event_dict("A"), event_dict("B")])
        result = await refresh_local_events(
            db, city="Munich", start_date=SATURDAY, end_date=SUNDAY, scraper=scraper
        )
        assert (result.scraped, result.created, result.updated) == (2, 2, 0)
        scraper.scrape_events.assert_awaited_once_with(SATURDAY, SUNDAY)
        scraper.close.assert_awaited_once()
        job = self.job(db)
        assert (job.job_type, job.source, job.status, job.items_scraped) == (
            "local_events",
            "muenchen.de",
            "completed",
            2,
        )
        assert job.completed_at is not None

    async def test_scraper_failure_marks_the_job_failed_and_reraises(self):
        db = storage_db()
        scraper = self.scraper(error=ScraperException("layout changed"))
        with pytest.raises(ScraperException):
            await refresh_local_events(
                db, city="Munich", start_date=SATURDAY, end_date=SUNDAY, scraper=scraper
            )
        job = self.job(db)
        assert job.status == "failed"
        assert "layout changed" in job.error_message
        scraper.close.assert_awaited_once()


# --------------------------------------------------------------------------- #
# Service: when to scrape
# --------------------------------------------------------------------------- #


class TestEnsureLocalEvents:
    @pytest.fixture
    def mocks(self, monkeypatch):
        mocks = MagicMock()
        mocks.load = AsyncMock(return_value=[])
        mocks.refresh = AsyncMock()
        monkeypatch.setattr(service, "load_weekend_events", mocks.load)
        monkeypatch.setattr(service, "refresh_local_events", mocks.refresh)
        monkeypatch.setattr(service.settings, "weekend_scrape_events", True)
        return mocks

    async def test_auto_scrapes_when_nothing_is_stored(self, mocks):
        warning = await service.ensure_local_events(AsyncMock(), today=SATURDAY, refresh=None)
        assert warning is None
        kwargs = mocks.refresh.call_args.kwargs
        assert (kwargs["start_date"], kwargs["end_date"]) == (SATURDAY, SUNDAY)

    async def test_auto_reuses_stored_events(self, mocks):
        mocks.load.return_value = [make_event("Kasperl")]
        await service.ensure_local_events(AsyncMock(), today=SATURDAY, refresh=None)
        mocks.refresh.assert_not_called()

    async def test_forced_refresh_scrapes_even_with_stored_events(self, mocks):
        mocks.load.return_value = [make_event("Kasperl")]
        await service.ensure_local_events(AsyncMock(), today=SATURDAY, refresh=True)
        mocks.refresh.assert_awaited_once()

    async def test_refresh_false_never_scrapes(self, mocks):
        await service.ensure_local_events(AsyncMock(), today=SATURDAY, refresh=False)
        mocks.refresh.assert_not_called()

    async def test_setting_switches_scraping_off(self, mocks, monkeypatch):
        monkeypatch.setattr(service.settings, "weekend_scrape_events", False)
        await service.ensure_local_events(AsyncMock(), today=SATURDAY, refresh=True)
        mocks.refresh.assert_not_called()

    async def test_scrape_failure_becomes_a_warning_not_an_error(self, mocks):
        mocks.refresh.side_effect = ScraperException("site down")
        warning = await service.ensure_local_events(AsyncMock(), today=SATURDAY, refresh=True)
        assert "could not be refreshed" in warning

    def test_module_reads_only_local_sources(self):
        assert events_module.LOCAL_SOURCES == ("muenchen.de",)


# --------------------------------------------------------------------------- #
# Email
# --------------------------------------------------------------------------- #


class TestEventsInEmail:
    @pytest.fixture
    def notifier(self):
        from app.config import get_settings
        from app.notifications.email_sender import EmailNotifier

        return EmailNotifier(get_settings(), user_email="family@example.com")

    async def plan(self, claude=None):
        events = [
            make_event("Kasperl & <Seppl>", SATURDAY, price_range="free"),
            make_event("Kasperl & <Seppl>", SUNDAY, price_range="free", showtimes=["11:00"]),
        ]
        return await build_weekend_plan(
            mock_db(PLACES, events=events), forecast=FORECAST, claude=claude, **plan_kwargs()
        )

    async def test_unvetted_event_is_shown_with_a_caution(self, notifier):
        html = notifier.render_weekend_plan(await self.plan())
        assert "Only this weekend" in html
        assert "Kasperl &amp; &lt;Seppl&gt;" in html
        assert "Sat 15:00-16:00 · Sun 11:00" in html
        assert "Testbühne" in html
        assert "💶 free" in html
        assert "Not checked for age fit" in html
        assert "Events from muenchen.de" in html

    async def test_vetted_event_shows_reason_and_age_note_without_caution(self, notifier):
        claude = AsyncMock()
        claude.analyze.return_value = {
            "summary": "ok",
            "events": [{"id": "e1", "why": "Classic puppet show.", "age_note": "from age 3"}],
        }
        html = notifier.render_weekend_plan(await self.plan(claude))
        assert "Classic puppet show." in html
        assert "Ages: from age 3" in html
        assert "Not checked for age fit" not in html

    async def test_no_events_means_no_section(self, notifier):
        plan = await build_weekend_plan(mock_db(PLACES), forecast=FORECAST, **plan_kwargs())
        html = notifier.render_weekend_plan(plan)
        assert "Only this weekend" not in html
        assert "Only this weekend" not in notifier.render_weekend_plan_text(plan)

    async def test_text_version_lists_events(self, notifier):
        text = notifier.render_weekend_plan_text(await self.plan())
        assert "Only this weekend" in text
        assert "- Kasperl & <Seppl> at Testbühne: Sat 15:00-16:00 · Sun 11:00" in text
        assert "Not checked for age fit." in text
