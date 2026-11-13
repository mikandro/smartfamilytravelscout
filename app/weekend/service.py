"""
One entry point for producing (and optionally emailing) the weekend plan.

Both the CLI and the Celery tasks call ``run_weekend_planner``, so the Thursday
email and ``scout weekend`` can never drift apart.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_session_context
from app.models.user_preference import UserPreference
from app.weekend.events import load_weekend_events, refresh_local_events
from app.weekend.planner import (
    WeekendPlanResult,
    build_weekend_plan,
    forecast_changed,
    get_stored_plan,
    save_plan,
    upcoming_weekend,
)

logger = logging.getLogger(__name__)

STATUS_SENT = "sent"
STATUS_PREVIEW = "preview"
STATUS_UNCHANGED = "unchanged"
STATUS_NO_RECIPIENTS = "no_recipients"
STATUS_SEND_FAILED = "send_failed"
STATUS_EMPTY = "empty"


@dataclass
class WeekendRun:
    """Outcome of one planner run."""

    status: str
    plan: WeekendPlanResult
    is_update: bool = False
    recipients: List[str] = field(default_factory=list)
    sent_to: List[str] = field(default_factory=list)


async def get_recipients(db: AsyncSession) -> List[str]:
    """
    Who gets the weekend plan.

    ``WEEKEND_PLAN_EMAIL`` wins when set; otherwise every user with an email
    address and notifications switched on.
    """
    if settings.weekend_plan_email:
        return [settings.weekend_plan_email]
    result = await db.execute(
        select(UserPreference.email)
        .where(UserPreference.enable_notifications.is_(True))
        .where(UserPreference.email.isnot(None))
    )
    return sorted({email for email in result.scalars().all() if email})


async def ensure_local_events(
    db: AsyncSession, *, today: date, refresh: Optional[bool]
) -> Optional[str]:
    """
    Make sure dated events for the weekend are in the database.

    Args:
        db: Database session (caller owns lifecycle).
        today: The date the plan is made on.
        refresh: True scrapes now, False never scrapes, None scrapes only when
            nothing is stored yet for the weekend.

    Returns:
        A warning for the plan if the scrape failed, otherwise None. A failed
        scrape never stops the plan: places are still suggested.
    """
    if refresh is False or not settings.weekend_scrape_events:
        return None

    _, days = upcoming_weekend(today)
    city = settings.weekend_home_name
    if refresh is None and await load_weekend_events(db, city=city, days=days):
        return None

    try:
        await refresh_local_events(db, city=city, start_date=days[0], end_date=days[-1])
    except Exception as exc:  # noqa: BLE001 - events are optional
        logger.warning("Could not refresh local events: %s", exc)
        return "Local events could not be refreshed, so this weekend's events may be missing."
    return None


async def run_weekend_planner(
    *,
    send: bool,
    use_ai: bool = True,
    only_if_forecast_changed: bool = False,
    today: Optional[date] = None,
    refresh_events: Optional[bool] = None,
) -> WeekendRun:
    """
    Build the weekend plan and, if asked, email and store it.

    Args:
        send: Email the plan and record it. False builds a preview only and
            leaves the database untouched.
        use_ai: Let Claude pick and write up the plan. Falls back to the
            automatic ranking when False, when AI scoring is disabled, or when
            the Claude call fails.
        only_if_forecast_changed: The Friday check. Sends only when the
            weather has shifted since the stored plan; if no plan was sent for
            this weekend yet, sends the full plan instead.
        today: Override the current date (for tests and ``--date``).
        refresh_events: True scrapes local events first, False never does,
            None (default) scrapes only when none are stored for the weekend.

    Returns:
        A ``WeekendRun`` describing what happened.
    """
    from app.notifications.email_sender import create_email_notifier

    today = today or date.today()
    redis_client = None

    try:
        async with get_async_session_context() as db:
            claude = None
            if use_ai and settings.enable_ai_scoring:
                from redis.asyncio import Redis

                from app.ai.claude_client import ClaudeClient

                try:
                    redis_client = await Redis.from_url(str(settings.redis_url))
                except Exception as exc:  # noqa: BLE001 - caching is optional
                    logger.warning("Redis unavailable, AI responses will not cache: %s", exc)
                claude = ClaudeClient(
                    api_key=settings.anthropic_api_key,
                    redis_client=redis_client,
                    db_session=db,
                )

            events_warning = await ensure_local_events(db, today=today, refresh=refresh_events)

            plan = await build_weekend_plan(
                db,
                today=today,
                kid_ages=settings.get_weekend_kid_ages(),
                home_name=settings.weekend_home_name,
                home_latitude=settings.weekend_home_latitude,
                home_longitude=settings.weekend_home_longitude,
                max_drive_minutes=settings.weekend_max_drive_minutes,
                repeat_after_days=settings.weekend_repeat_after_days,
                claude=claude,
            )
            if events_warning:
                plan.warnings.append(events_warning)

            if not send:
                return WeekendRun(status=STATUS_PREVIEW, plan=plan)

            if plan.is_empty:
                logger.warning("Weekend plan is empty; nothing sent")
                return WeekendRun(status=STATUS_EMPTY, plan=plan)

            is_update = False
            if only_if_forecast_changed:
                stored = await get_stored_plan(db, plan.weekend_start)
                if stored is not None and stored.sent_at is not None:
                    if not forecast_changed(stored.forecast_json, plan):
                        logger.info("Weekend forecast unchanged; no update sent")
                        return WeekendRun(status=STATUS_UNCHANGED, plan=plan)
                    is_update = True

            recipients = await get_recipients(db)
            if not recipients:
                logger.warning("No recipients for the weekend plan")
                return WeekendRun(status=STATUS_NO_RECIPIENTS, plan=plan, is_update=is_update)

            notifier = create_email_notifier()
            sent_to = [
                email
                for email in recipients
                if await notifier.send_weekend_plan(plan, to_email=email, is_update=is_update)
            ]

            if not sent_to:
                return WeekendRun(
                    status=STATUS_SEND_FAILED,
                    plan=plan,
                    is_update=is_update,
                    recipients=recipients,
                )

            await save_plan(db, plan, sent=True)
            return WeekendRun(
                status=STATUS_SENT,
                plan=plan,
                is_update=is_update,
                recipients=recipients,
                sent_to=sent_to,
            )
    finally:
        if redis_client is not None:
            await redis_client.close()
