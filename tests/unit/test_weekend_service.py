"""
Unit tests for the weekend planner service, Celery tasks and schedule.

The planner itself is covered in test_weekend_planner.py; here it is replaced
by a canned plan so only the send / store / skip decisions are under test.
"""

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from celery.schedules import crontab

from app.models.place import WeekendPlan
from app.weekend import service
from app.weekend.planner import LEAD_INDOOR, LEAD_OUTDOOR, PlaceOption, WeekendPlanResult
from app.weekend.weather import DayForecast

SATURDAY = date(2026, 11, 14)
SUNDAY = date(2026, 11, 15)
THURSDAY = date(2026, 11, 12)


def make_option(slug="park"):
    return PlaceOption(
        slug=slug,
        name=slug.title(),
        category="park",
        setting="outdoor",
        drive_minutes=10,
        transit_minutes=None,
        transit_note=None,
        duration_hours=2.0,
        cost_family_eur=0,
        booking_required=False,
        stroller_friendly=True,
        url=None,
    )


def make_plan(*, wet=False, empty=False):
    rain = 9.0 if wet else 0.0
    forecast = [
        DayForecast(SATURDAY, 10.0, 3.0, rain, 95 if wet else 5, 10.0, 63 if wet else 1),
        DayForecast(SUNDAY, 10.0, 3.0, rain, 95 if wet else 5, 10.0, 63 if wet else 1),
    ]
    return WeekendPlanResult(
        weekend_start=SATURDAY,
        days=[SATURDAY, SUNDAY],
        forecast=forecast,
        lead=LEAD_INDOOR if wet else LEAD_OUTDOOR,
        outdoor=None if empty else make_option("park"),
        indoor=None if empty else make_option("museum"),
    )


@pytest.fixture
def harness(monkeypatch):
    """Patch everything around run_weekend_planner and expose the mocks."""
    db = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield db

    notifier = Mock()
    notifier.send_weekend_plan = AsyncMock(return_value=True)

    mocks = MagicMock()
    mocks.db = db
    mocks.notifier = notifier
    mocks.build = AsyncMock(return_value=make_plan())
    mocks.stored = AsyncMock(return_value=None)
    mocks.save = AsyncMock()
    mocks.recipients = AsyncMock(return_value=["family@example.com"])
    mocks.ensure_events = AsyncMock(return_value=None)

    monkeypatch.setattr(service, "get_async_session_context", fake_session)
    monkeypatch.setattr(service, "build_weekend_plan", mocks.build)
    monkeypatch.setattr(service, "get_stored_plan", mocks.stored)
    monkeypatch.setattr(service, "save_plan", mocks.save)
    monkeypatch.setattr(service, "get_recipients", mocks.recipients)
    monkeypatch.setattr(service, "ensure_local_events", mocks.ensure_events)
    monkeypatch.setattr(
        "app.notifications.email_sender.create_email_notifier", lambda *a, **k: notifier
    )
    return mocks


def stored_plan(plan, sent=True):
    return WeekendPlan(
        weekend_start=plan.weekend_start,
        forecast_json=plan.forecast_dict(),
        plan_json=plan.to_dict(),
        sent_at=datetime.now(timezone.utc) if sent else None,
    )


class TestRunWeekendPlanner:
    async def test_preview_does_not_send_or_store(self, harness):
        run = await service.run_weekend_planner(send=False, use_ai=False, today=THURSDAY)
        assert run.status == service.STATUS_PREVIEW
        harness.notifier.send_weekend_plan.assert_not_called()
        harness.save.assert_not_called()

    async def test_no_ai_passes_no_claude_client(self, harness):
        await service.run_weekend_planner(send=False, use_ai=False, today=THURSDAY)
        assert harness.build.call_args.kwargs["claude"] is None
        assert harness.build.call_args.kwargs["today"] == THURSDAY

    async def test_send_emails_every_recipient_and_stores_plan(self, harness):
        harness.recipients.return_value = ["a@example.com", "b@example.com"]
        run = await service.run_weekend_planner(send=True, use_ai=False, today=THURSDAY)
        assert run.status == service.STATUS_SENT
        assert run.sent_to == ["a@example.com", "b@example.com"]
        assert run.is_update is False
        harness.save.assert_awaited_once()
        assert harness.save.call_args.kwargs["sent"] is True

    async def test_empty_plan_is_not_sent(self, harness):
        harness.build.return_value = make_plan(empty=True)
        run = await service.run_weekend_planner(send=True, use_ai=False, today=THURSDAY)
        assert run.status == service.STATUS_EMPTY
        harness.notifier.send_weekend_plan.assert_not_called()

    async def test_no_recipients_is_reported_and_not_stored(self, harness):
        harness.recipients.return_value = []
        run = await service.run_weekend_planner(send=True, use_ai=False, today=THURSDAY)
        assert run.status == service.STATUS_NO_RECIPIENTS
        harness.save.assert_not_called()

    async def test_failed_send_is_not_recorded_as_sent(self, harness):
        harness.notifier.send_weekend_plan.return_value = False
        run = await service.run_weekend_planner(send=True, use_ai=False, today=THURSDAY)
        assert run.status == service.STATUS_SEND_FAILED
        harness.save.assert_not_called()

    async def test_friday_check_is_silent_when_forecast_holds(self, harness):
        harness.stored.return_value = stored_plan(make_plan())
        run = await service.run_weekend_planner(
            send=True, use_ai=False, only_if_forecast_changed=True, today=THURSDAY
        )
        assert run.status == service.STATUS_UNCHANGED
        harness.notifier.send_weekend_plan.assert_not_called()
        harness.save.assert_not_called()

    async def test_friday_check_sends_update_when_forecast_flips(self, harness):
        harness.stored.return_value = stored_plan(make_plan())
        harness.build.return_value = make_plan(wet=True)
        run = await service.run_weekend_planner(
            send=True, use_ai=False, only_if_forecast_changed=True, today=THURSDAY
        )
        assert run.status == service.STATUS_SENT
        assert run.is_update is True
        assert harness.notifier.send_weekend_plan.call_args.kwargs["is_update"] is True

    async def test_friday_check_sends_full_plan_if_thursday_never_went_out(self, harness):
        harness.stored.return_value = None
        run = await service.run_weekend_planner(
            send=True, use_ai=False, only_if_forecast_changed=True, today=THURSDAY
        )
        assert run.status == service.STATUS_SENT
        assert run.is_update is False

    async def test_friday_check_treats_unsent_stored_plan_as_not_sent(self, harness):
        harness.stored.return_value = stored_plan(make_plan(), sent=False)
        run = await service.run_weekend_planner(
            send=True, use_ai=False, only_if_forecast_changed=True, today=THURSDAY
        )
        assert run.status == service.STATUS_SENT
        assert run.is_update is False


class TestGetRecipients:
    async def test_configured_address_wins(self, monkeypatch):
        monkeypatch.setattr(service.settings, "weekend_plan_email", "me@example.com")
        db = AsyncMock()
        assert await service.get_recipients(db) == ["me@example.com"]
        db.execute.assert_not_called()

    async def test_falls_back_to_users_with_notifications(self, monkeypatch):
        monkeypatch.setattr(service.settings, "weekend_plan_email", None)
        result = MagicMock()
        result.scalars.return_value.all.return_value = ["b@example.com", "a@example.com", None]
        db = AsyncMock()
        db.execute = AsyncMock(return_value=result)
        assert await service.get_recipients(db) == ["a@example.com", "b@example.com"]


class TestWeekendTasks:
    def test_thursday_and_friday_schedules(self):
        from app.tasks.celery_app import celery_app

        plan = celery_app.conf.beat_schedule["weekly-weekend-plan"]
        check = celery_app.conf.beat_schedule["weekly-weekend-forecast-check"]
        assert plan["task"] == "app.tasks.scheduled_tasks.send_weekend_plan"
        assert plan["schedule"] == crontab(hour=18, minute=0, day_of_week=4)  # Thursday
        assert check["task"] == "app.tasks.scheduled_tasks.check_weekend_forecast"
        assert check["schedule"] == crontab(hour=18, minute=0, day_of_week=5)  # Friday

    @pytest.mark.parametrize(
        "task_name,expected_flag",
        [("send_weekend_plan", False), ("check_weekend_forecast", True)],
    )
    def test_tasks_run_the_planner_with_send(self, task_name, expected_flag):
        from app.tasks import scheduled_tasks

        run = service.WeekendRun(
            status=service.STATUS_SENT, plan=make_plan(), sent_to=["family@example.com"]
        )
        planner = AsyncMock(return_value=run)
        with patch("app.weekend.service.run_weekend_planner", planner):
            result = getattr(scheduled_tasks, task_name).apply().get()

        assert result["status"] == "sent"
        assert result["sent"] == 1
        assert result["weekend_start"] == "2026-11-14"
        assert planner.call_args.kwargs == {
            "send": True,
            "only_if_forecast_changed": expected_flag,
            "refresh_events": True,
        }

    def test_task_skips_when_disabled(self, monkeypatch):
        from app.tasks import scheduled_tasks

        monkeypatch.setattr(scheduled_tasks.settings, "enable_weekend_planner", False)
        planner = AsyncMock()
        with patch("app.weekend.service.run_weekend_planner", planner):
            result = scheduled_tasks.send_weekend_plan.apply().get()
        assert result["status"] == "disabled"
        planner.assert_not_called()
