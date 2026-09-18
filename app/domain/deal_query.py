"""
One module that knows what a good deal is.

"Which packages are good?" was answered in eleven places with five different
thresholds:

- ``>= 70`` hardcoded in ``web.py:34``, ``v1/stats.py:63``, ``api_stats.py:39``
- ``>= 80`` hardcoded in ``cli/main.py:924`` (row styling)
- ``>= 85`` hardcoded in ``email_sender.py:134``
- ``settings.notification_threshold`` in ``notification_service.py`` (twice --
  once async, once sync, in the same file)
- ``settings.notification_alert_threshold`` in ``scheduled_tasks.py:424``
- caller-supplied ``min_score`` in the three deal-listing routes

The "unnotified, created in the last day" guards appeared only in the
notification paths, so a route and a notifier asking "what's good?" got
different answers. Thresholds are now named constants or explicit criteria,
and the query is built in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.trip_package import TripPackage

#: A package worth surfacing at all. Replaces the hardcoded 70s.
GOOD_DEAL_SCORE = 70.0

#: A standout package, highlighted in listings. Replaces the hardcoded 80.
EXCELLENT_DEAL_SCORE = 80.0

ORDER_BY_SCORE = "score"
ORDER_BY_PRICE = "price"
ORDER_BY_DEPARTURE = "departure"


@dataclass(frozen=True)
class DealCriteria:
    """
    What makes a package interesting to a particular caller.

    Attributes:
        min_score: Minimum AI score, inclusive. ``None`` includes unscored
            packages, which is how ``scout packages`` differs from
            ``scout deals``.
        unnotified_only: Only packages we have not emailed about yet.
        since: Only packages created at or after this time.
        max_price: Maximum total price.
        destination_city: Restrict to one city.
        limit: Maximum rows to return.
        order_by: One of ``score``, ``price`` or ``departure``.
    """

    min_score: Optional[float] = GOOD_DEAL_SCORE
    unnotified_only: bool = False
    since: Optional[datetime] = None
    max_price: Optional[float] = None
    destination_city: Optional[str] = None
    limit: Optional[int] = None
    order_by: str = ORDER_BY_SCORE

    @classmethod
    def good_deals(
        cls,
        min_score: float = GOOD_DEAL_SCORE,
        limit: Optional[int] = None,
    ) -> "DealCriteria":
        """Deals worth showing a user: scored at or above the good threshold."""
        return cls(min_score=min_score, limit=limit)

    @classmethod
    def all_packages(cls, limit: Optional[int] = None) -> "DealCriteria":
        """Every package, including unscored ones (``scout packages``)."""
        return cls(min_score=None, limit=limit)

    @classmethod
    def daily_digest(cls, limit: int = 10) -> "DealCriteria":
        """
        Packages for the daily digest email.

        Uses ``settings.notification_threshold`` (default 70) and only
        considers packages from the last day that we have not notified about.
        """
        return cls(
            min_score=settings.notification_threshold,
            unnotified_only=True,
            since=datetime.now() - timedelta(days=1),
            limit=limit,
        )

    @classmethod
    def immediate_alerts(cls, limit: Optional[int] = None) -> "DealCriteria":
        """
        Packages good enough to interrupt someone for.

        Uses ``settings.notification_alert_threshold`` (default 85), which is
        deliberately stricter than the digest threshold.
        """
        return cls(
            min_score=settings.notification_alert_threshold,
            unnotified_only=True,
            since=datetime.now() - timedelta(days=1),
            limit=limit,
        )


def build_deal_query(criteria: DealCriteria, *, eager: bool = True) -> Select:
    """
    Build the SELECT for these criteria.

    Exposed separately from ``top_deals`` so callers that paginate can reuse
    the predicate for their own count query instead of rebuilding it -- which
    is how ``v1/deals.py`` ended up stating the same filter twice.

    Args:
        criteria: What counts as interesting.
        eager: Eager-load the accommodation relationship. Leave on for
            anything that renders packages; turn off for counts.
    """
    query = select(TripPackage)

    if eager:
        query = query.options(selectinload(TripPackage.accommodation))

    if criteria.min_score is not None:
        query = query.where(TripPackage.ai_score >= criteria.min_score)
    if criteria.unnotified_only:
        query = query.where(TripPackage.notified.is_(False))
    if criteria.since is not None:
        query = query.where(TripPackage.created_at >= criteria.since)
    if criteria.max_price is not None:
        query = query.where(TripPackage.total_price <= criteria.max_price)
    if criteria.destination_city:
        query = query.where(
            TripPackage.destination_city == criteria.destination_city
        )

    if criteria.order_by == ORDER_BY_PRICE:
        query = query.order_by(TripPackage.total_price.asc())
    elif criteria.order_by == ORDER_BY_DEPARTURE:
        query = query.order_by(TripPackage.departure_date.asc())
    else:
        query = query.order_by(TripPackage.ai_score.desc().nullslast())

    if criteria.limit is not None:
        query = query.limit(criteria.limit)

    return query


async def top_deals(
    db: AsyncSession,
    criteria: Optional[DealCriteria] = None,
) -> List[TripPackage]:
    """
    Fetch the packages matching these criteria.

    Args:
        db: Session owned by the caller.
        criteria: Defaults to ``DealCriteria.good_deals()``.
    """
    criteria = criteria or DealCriteria.good_deals()
    result = await db.execute(build_deal_query(criteria))
    return list(result.scalars().all())


async def count_deals(
    db: AsyncSession,
    criteria: Optional[DealCriteria] = None,
) -> int:
    """
    Count the packages matching these criteria.

    Uses the same predicate as ``top_deals``, so a listing and its total can
    never disagree. Limit and ordering are ignored for the count.
    """
    criteria = criteria or DealCriteria.good_deals()
    counted = DealCriteria(
        min_score=criteria.min_score,
        unnotified_only=criteria.unnotified_only,
        since=criteria.since,
        max_price=criteria.max_price,
        destination_city=criteria.destination_city,
        limit=None,
    )
    inner = build_deal_query(counted, eager=False).subquery()
    result = await db.execute(select(func.count()).select_from(inner))
    return int(result.scalar_one())


def is_good_deal(package: TripPackage) -> bool:
    """Whether a package clears the good-deal threshold."""
    return package.ai_score is not None and float(package.ai_score) >= GOOD_DEAL_SCORE


def is_excellent_deal(package: TripPackage) -> bool:
    """Whether a package clears the standout threshold, for highlighting."""
    return (
        package.ai_score is not None
        and float(package.ai_score) >= EXCELLENT_DEAL_SCORE
    )
