"""
Weekend planner: pick an outdoor and an indoor outing for the coming weekend.

The flow is: work out which days are left this weekend, filter the known
places down to ones that suit the children, the season and the drive limit and
that the family has not just been to, then let Claude pick and explain. If
Claude is unavailable the deterministic ranking is used as-is, so a plan always
goes out.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.judgement import JudgementSchema, judge
from app.models.event import Event
from app.models.place import (
    SETTING_INDOOR,
    SETTING_MIXED,
    SETTING_OUTDOOR,
    Place,
    PlaceVisit,
    WeekendPlan,
)
from app.weekend.events import is_ongoing, load_weekend_events
from app.weekend.weather import (
    VERDICT_INDOOR,
    VERDICT_OUTDOOR,
    DayForecast,
    WeatherUnavailable,
    fetch_forecast,
)

logger = logging.getLogger(__name__)

LEAD_OUTDOOR = "outdoor"
LEAD_INDOOR = "indoor"

#: How many candidates per slot are shown to Claude.
SHORTLIST_SIZE = 15

#: How many dated events are shown to Claude, and how many end up in the plan.
EVENT_SHORTLIST_SIZE = 40
MAX_PLAN_EVENTS = 3

#: A place last rated this low (1-5) or lower is never suggested again.
DISLIKED_RATING = 2

WEEKEND_SCHEMA = JudgementSchema(
    required=("summary",),
    optional=("outdoor", "indoor", "alternates", "events"),
    defaults={"outdoor": None, "indoor": None, "alternates": [], "events": []},
)


class PlaceNotFound(LookupError):
    """No place matched the name or slug given."""


@dataclass
class PlaceOption:
    """One suggested outing, ready for display."""

    slug: str
    name: str
    category: str
    setting: str
    drive_minutes: int
    transit_minutes: Optional[int]
    transit_note: Optional[str]
    duration_hours: float
    cost_family_eur: Optional[int]
    booking_required: bool
    stroller_friendly: bool
    url: Optional[str]
    why: str = ""
    tips: str = ""
    best_day: Optional[str] = None  # ISO date

    @classmethod
    def from_place(cls, place: Place, **extra: Any) -> "PlaceOption":
        """Build an option from a ``Place`` row."""
        return cls(
            slug=place.slug,
            name=place.name,
            category=place.category,
            setting=place.setting,
            drive_minutes=place.drive_minutes,
            transit_minutes=place.transit_minutes,
            transit_note=place.transit_note,
            duration_hours=place.duration_hours,
            cost_family_eur=place.cost_family_eur,
            booking_required=bool(place.booking_required),
            stroller_friendly=bool(place.stroller_friendly),
            url=place.url,
            why=extra.pop("why", None) or place.notes or "",
            **extra,
        )

    @property
    def travel_text(self) -> str:
        """e.g. ``🚗 25 min · 🚆 35 min (S2 to Poing, 15 min walk)``."""
        text = f"🚗 {self.drive_minutes} min"
        if self.transit_minutes is not None:
            text += f" · 🚆 {self.transit_minutes} min"
            if self.transit_note:
                text += f" ({self.transit_note})"
        else:
            text += " · car only"
        return text

    @property
    def cost_text(self) -> str:
        """e.g. ``free`` or ``about €40 for the family``."""
        if self.cost_family_eur is None:
            return "cost varies"
        if self.cost_family_eur == 0:
            return "free"
        return f"about €{self.cost_family_eur} for the family"

    @property
    def best_day_text(self) -> str:
        """Weekday name of ``best_day``, or an empty string."""
        if not self.best_day:
            return ""
        return date.fromisoformat(self.best_day).strftime("%A")


@dataclass
class EventOption:
    """A dated event happening this weekend (one title at one venue)."""

    title: str
    venue: Optional[str]
    category: str
    #: ISO day -> showtimes on that day, e.g. {"2026-11-14": ["15:00-17:00"]}
    schedule: Dict[str, List[str]]
    url: Optional[str]
    price_range: Optional[str]
    ongoing: bool
    description: Optional[str] = None
    why: str = ""
    age_note: str = ""
    #: False when nobody (Claude) checked that it suits the children.
    vetted: bool = False

    @property
    def when_text(self) -> str:
        """e.g. ``Sat 15:00-17:00 · Sun 11:00, 15:00`` (or ``Sat · Sun``)."""
        parts = []
        for iso_day in sorted(self.schedule):
            label = date.fromisoformat(iso_day).strftime("%a")
            times = ", ".join(self.schedule[iso_day])
            parts.append(f"{label} {times}".strip())
        return " · ".join(parts)

    @property
    def price_text(self) -> str:
        """``free`` when known to be free, otherwise an empty string."""
        return "free" if self.price_range == "free" else ""


@dataclass
class WeekendPlanResult:
    """The plan for one weekend."""

    weekend_start: date
    days: List[date]
    forecast: List[DayForecast]
    lead: str
    outdoor: Optional[PlaceOption]
    indoor: Optional[PlaceOption]
    alternates: List[PlaceOption] = field(default_factory=list)
    events: List[EventOption] = field(default_factory=list)
    summary: str = ""
    ai_used: bool = False
    warnings: List[str] = field(default_factory=list)

    @property
    def ordered_options(self) -> List[Tuple[str, PlaceOption]]:
        """The outdoor and indoor options, lead first, skipping empty slots."""
        slots = [(LEAD_OUTDOOR, self.outdoor), (LEAD_INDOOR, self.indoor)]
        if self.lead == LEAD_INDOOR:
            slots.reverse()
        return [(kind, option) for kind, option in slots if option is not None]

    @property
    def is_empty(self) -> bool:
        """True when there is nothing to suggest at all."""
        return self.outdoor is None and self.indoor is None

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe representation (stored in ``weekend_plans.plan_json``)."""
        return {
            "weekend_start": self.weekend_start.isoformat(),
            "days": [day.isoformat() for day in self.days],
            "lead": self.lead,
            "outdoor": asdict(self.outdoor) if self.outdoor else None,
            "indoor": asdict(self.indoor) if self.indoor else None,
            "alternates": [asdict(option) for option in self.alternates],
            "events": [asdict(event) for event in self.events],
            "summary": self.summary,
            "ai_used": self.ai_used,
            "warnings": list(self.warnings),
        }

    def forecast_dict(self) -> Dict[str, Any]:
        """JSON-safe forecast (stored in ``weekend_plans.forecast_json``)."""
        return {"lead": self.lead, "days": [day.to_dict() for day in self.forecast]}


@dataclass
class Candidates:
    """Places that passed the filters, best first, split by slot."""

    outdoor: List[Place]
    indoor: List[Place]
    recent: List[Tuple[Place, PlaceVisit]]


# --------------------------------------------------------------------------- #
# Pure logic
# --------------------------------------------------------------------------- #


def upcoming_weekend(today: date) -> Tuple[date, List[date]]:
    """
    Return the Saturday of the relevant weekend and the days still to plan.

    Monday to Saturday this is the coming (or current) Saturday and Sunday. On
    a Sunday it is that Sunday alone, since Saturday is already over.
    """
    weekday = today.weekday()  # Monday = 0 ... Sunday = 6
    if weekday == 6:
        return today - timedelta(days=1), [today]
    saturday = today + timedelta(days=5 - weekday)
    return saturday, [saturday, saturday + timedelta(days=1)]


def choose_lead(forecast: Sequence[DayForecast], month: int) -> str:
    """
    Decide whether the outdoor or the indoor plan goes first.

    Outdoor leads when at least one day is properly dry. Without a forecast the
    season decides: indoor from November to March, outdoor otherwise.
    """
    if not forecast:
        return LEAD_INDOOR if month in (11, 12, 1, 2, 3) else LEAD_OUTDOOR
    if any(day.verdict == VERDICT_OUTDOOR for day in forecast):
        return LEAD_OUTDOOR
    return LEAD_INDOOR


def best_outdoor_day(forecast: Sequence[DayForecast]) -> Optional[DayForecast]:
    """The day with the best weather for being outside, if any is usable."""
    usable = [day for day in forecast if day.verdict != VERDICT_INDOOR]
    if not usable:
        return None
    return max(usable, key=lambda day: day.outdoor_score)


def best_indoor_day(forecast: Sequence[DayForecast]) -> Optional[DayForecast]:
    """The day with the worst weather: the one to spend inside."""
    if not forecast:
        return None
    return min(forecast, key=lambda day: day.outdoor_score)


def _latest_visits(visits: Iterable[PlaceVisit]) -> Dict[int, PlaceVisit]:
    latest: Dict[int, PlaceVisit] = {}
    for visit in visits:
        current = latest.get(visit.place_id)
        if current is None or visit.visited_on > current.visited_on:
            latest[visit.place_id] = visit
    return latest


def _average_ratings(visits: Iterable[PlaceVisit]) -> Dict[int, float]:
    ratings: Dict[int, List[int]] = {}
    for visit in visits:
        if visit.rating is not None:
            ratings.setdefault(visit.place_id, []).append(visit.rating)
    return {place_id: sum(values) / len(values) for place_id, values in ratings.items()}


def rank_score(
    place: Place,
    kid_ages: Sequence[int],
    weekend_start: date,
    average_rating: Optional[float],
) -> float:
    """
    Deterministic score used for the shortlist and the no-AI fallback.

    Rewards a comfortable age fit, a short drive and good past ratings, and
    adds a small per-weekend shuffle so the fallback does not repeat itself.
    """
    age_fit = 0.0
    for age in kid_ages:
        below = age - place.age_min
        above = (place.age_max - age) if place.age_max is not None else 5
        age_fit += min(below, above, 3)

    drive_penalty = place.drive_minutes / 15.0
    rating_bonus = (average_rating - 3) * 2 if average_rating is not None else 1.0

    digest = hashlib.sha256(f"{place.slug}:{weekend_start.isoformat()}".encode()).digest()
    shuffle = digest[0] / 255.0 * 3

    return age_fit - drive_penalty + rating_bonus + shuffle


def filter_candidates(
    places: Sequence[Place],
    visits: Sequence[PlaceVisit],
    *,
    weekend_start: date,
    kid_ages: Sequence[int],
    max_drive_minutes: int,
    repeat_after_days: int,
) -> Candidates:
    """
    Reduce all known places to the ones worth suggesting this weekend.

    A place is dropped when it is inactive, out of season, outside any child's
    age range, further than the drive limit, visited within
    ``repeat_after_days``, or last rated ``DISLIKED_RATING`` or lower.
    """
    latest = _latest_visits(visits)
    averages = _average_ratings(visits)
    not_before = weekend_start - timedelta(days=repeat_after_days)
    by_id = {place.id: place for place in places}

    eligible: List[Place] = []
    for place in places:
        if not place.is_active:
            continue
        if not place.is_open_in(weekend_start.month):
            continue
        if not place.suits_ages(list(kid_ages)):
            continue
        if place.drive_minutes > max_drive_minutes:
            continue
        last = latest.get(place.id)
        if last is not None:
            if last.rating is not None and last.rating <= DISLIKED_RATING:
                continue
            if last.visited_on > not_before:
                continue
        eligible.append(place)

    eligible.sort(
        key=lambda place: rank_score(place, kid_ages, weekend_start, averages.get(place.id)),
        reverse=True,
    )

    outdoor = [p for p in eligible if p.setting in (SETTING_OUTDOOR, SETTING_MIXED)]
    indoor = [p for p in eligible if p.setting == SETTING_INDOOR]
    if not indoor:
        # Better a half-covered place than no rainy-day suggestion at all.
        indoor = [p for p in eligible if p.setting == SETTING_MIXED]

    recent = sorted(
        ((by_id[pid], visit) for pid, visit in latest.items() if pid in by_id),
        key=lambda pair: pair[1].visited_on,
        reverse=True,
    )[:10]

    return Candidates(outdoor=outdoor, indoor=indoor, recent=recent)


def forecast_changed(stored_forecast: Mapping[str, Any], plan: WeekendPlanResult) -> bool:
    """
    Whether the weather has shifted enough since the stored plan to re-send.

    True when the indoor/outdoor lead flipped, or when the best day to be
    outside moved to the other day.
    """
    if stored_forecast.get("lead") != plan.lead:
        return True

    stored_days = stored_forecast.get("days") or []
    if not stored_days or not plan.forecast:
        return False

    def best_day_iso(days: Sequence[Mapping[str, Any]]) -> Optional[str]:
        # Only meaningful when exactly one day is the dry one.
        outdoor_days = [d for d in days if d.get("verdict") == VERDICT_OUTDOOR]
        if len(outdoor_days) == 1:
            return str(outdoor_days[0].get("day"))
        return None

    new_days = [day.to_dict() for day in plan.forecast]
    return best_day_iso(stored_days) != best_day_iso(new_days)


def group_weekend_events(events: Sequence[Event], weekend_start: date) -> List[EventOption]:
    """
    Merge per-day event rows into one option per (title, venue).

    One-off events come before long-running ones (exhibitions, markets open for
    weeks), family events before other categories, then by first showtime.
    """
    grouped: Dict[Tuple[str, str], EventOption] = {}
    for event in events:
        key = (event.title.lower(), (event.venue or "").lower())
        option = grouped.get(key)
        if option is None:
            option = EventOption(
                title=event.title,
                venue=event.venue,
                category=event.category,
                schedule={},
                url=event.url,
                price_range=event.price_range,
                ongoing=is_ongoing(event, weekend_start),
                description=event.description,
            )
            grouped[key] = option
        option.schedule[event.event_date.isoformat()] = list(event.showtimes or [])
        if not option.description and event.description:
            option.description = event.description

    def sort_key(option: EventOption) -> Tuple[int, int, str, str]:
        first_day = min(option.schedule)
        first_time = (option.schedule[first_day] or ["99:99"])[0]
        return (option.ongoing, option.category != "family", first_day + first_time, option.title)

    return sorted(grouped.values(), key=sort_key)


def fallback_events(options: Sequence[EventOption]) -> List[EventOption]:
    """
    Events to show when Claude has not vetted them.

    Only one-off family-category events qualify, since nothing has checked
    their age fit; they stay flagged as ``vetted=False``.
    """
    return [o for o in options if o.category == "family" and not o.ongoing][:MAX_PLAN_EVENTS]


def _event_line(index: int, option: EventOption) -> str:
    parts = [
        f"e{index}",
        option.title,
        option.venue or "venue not stated",
        option.category,
        option.when_text,
        "runs for several more weeks" if option.ongoing else "limited run",
    ]
    if option.price_text:
        parts.append(option.price_text)
    line = "- " + " | ".join(parts)
    if option.description:
        line += f" | {option.description}"
    return line


def _format_events(options: Sequence[EventOption]) -> str:
    return (
        "\n".join(_event_line(i, option) for i, option in enumerate(options, 1))
        or "(no dated events found)"
    )


def _pick_events(raw: Any, options: Sequence[EventOption]) -> List[EventOption]:
    """Turn Claude's ``[{id, why, age_note}]`` into vetted event options."""
    by_id = {f"e{i}": option for i, option in enumerate(options, 1)}
    picked: List[EventOption] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, Mapping):
            continue
        option = by_id.get(str(item.get("id", "")))
        if option is None or option in picked:
            continue
        option.why = str(item.get("why") or "")
        option.age_note = str(item.get("age_note") or "")
        option.vetted = True
        picked.append(option)
    return picked[:MAX_PLAN_EVENTS]


# --------------------------------------------------------------------------- #
# Claude
# --------------------------------------------------------------------------- #


def _place_line(place: Place) -> str:
    transit = (
        f"transit {place.transit_minutes} min ({place.transit_note or 'S-Bahn/U-Bahn'})"
        if place.transit_minutes is not None
        else "car only"
    )
    cost = "cost unknown" if place.cost_family_eur is None else f"€{place.cost_family_eur}"
    ages = (
        f"ages {place.age_min}+"
        if place.age_max is None
        else (f"ages {place.age_min}-{place.age_max}")
    )
    parts = [
        place.slug,
        place.name,
        place.category,
        place.setting,
        f"drive {place.drive_minutes} min",
        transit,
        f"~{place.duration_hours:g}h",
        cost,
        ages,
        "stroller ok" if place.stroller_friendly else "no stroller",
        "booking needed" if place.booking_required else "no booking",
    ]
    line = "- " + " | ".join(parts)
    if place.notes:
        line += f" | {place.notes}"
    return line


def _format_places(places: Sequence[Place]) -> str:
    return "\n".join(_place_line(place) for place in places) or "(none available)"


def _format_recent(recent: Sequence[Tuple[Place, PlaceVisit]]) -> str:
    if not recent:
        return "(no visits logged yet)"
    lines = []
    for place, visit in recent:
        rating = f", rated {visit.rating}/5" if visit.rating is not None else ""
        lines.append(f"- {place.name} on {visit.visited_on.isoformat()}{rating}")
    return "\n".join(lines)


def _format_forecast(forecast: Sequence[DayForecast]) -> str:
    if not forecast:
        return "(forecast unavailable - assume typical weather for the season)"
    return "\n".join(f"- {day.summary()} -> {day.verdict}" for day in forecast)


def _pick(
    raw: Any,
    pool: Mapping[str, Place],
    valid_days: Sequence[str],
    default_day: Optional[str],
) -> Optional[PlaceOption]:
    """Turn Claude's ``{slug, why, tips, best_day}`` into an option, or None."""
    if not isinstance(raw, Mapping):
        return None
    place = pool.get(str(raw.get("slug", "")))
    if place is None:
        return None
    best_day = raw.get("best_day")
    if best_day not in valid_days:
        best_day = default_day
    return PlaceOption.from_place(
        place,
        why=str(raw.get("why") or ""),
        tips=str(raw.get("tips") or ""),
        best_day=best_day,
    )


async def _ask_claude(
    claude: Any,
    *,
    candidates: Candidates,
    forecast: Sequence[DayForecast],
    days: Sequence[date],
    kid_ages: Sequence[int],
    home_name: str,
    lead: str,
    events: Sequence[EventOption] = (),
) -> Dict[str, Any]:
    outdoor = candidates.outdoor[:SHORTLIST_SIZE]
    indoor = candidates.indoor[:SHORTLIST_SIZE]
    return await judge(
        claude,
        prompt_name="weekend_plan",
        context={
            "home_name": home_name,
            "kid_ages": " and ".join(str(age) for age in kid_ages),
            "youngest_age": min(kid_ages) if kid_ages else 0,
            "oldest_age": max(kid_ages) if kid_ages else 0,
            "days": ", ".join(day.strftime("%A %d %B %Y") for day in days),
            "valid_days": ", ".join(day.isoformat() for day in days),
            "forecast": _format_forecast(forecast),
            "lead": lead,
            "outdoor_places": _format_places(outdoor),
            "indoor_places": _format_places(indoor),
            "recent_visits": _format_recent(candidates.recent),
            "events": _format_events(events),
            "max_events": MAX_PLAN_EVENTS,
        },
        schema=WEEKEND_SCHEMA,
        operation="weekend_plan",
        max_tokens=2000,
    )


# --------------------------------------------------------------------------- #
# Database-backed entry points (caller owns the session)
# --------------------------------------------------------------------------- #


async def load_candidates(
    db: AsyncSession,
    *,
    weekend_start: date,
    kid_ages: Sequence[int],
    max_drive_minutes: int,
    repeat_after_days: int,
) -> Candidates:
    """Load places and visits and apply ``filter_candidates``."""
    places = list((await db.execute(select(Place))).scalars().all())
    visits = list((await db.execute(select(PlaceVisit))).scalars().all())
    return filter_candidates(
        places,
        visits,
        weekend_start=weekend_start,
        kid_ages=kid_ages,
        max_drive_minutes=max_drive_minutes,
        repeat_after_days=repeat_after_days,
    )


async def build_weekend_plan(
    db: AsyncSession,
    *,
    today: date,
    kid_ages: Sequence[int],
    home_name: str,
    home_latitude: float,
    home_longitude: float,
    max_drive_minutes: int,
    repeat_after_days: int,
    claude: Any = None,
    forecast: Optional[Sequence[DayForecast]] = None,
    events: Optional[Sequence[Event]] = None,
) -> WeekendPlanResult:
    """
    Build the plan for the weekend that ``today`` belongs to.

    Args:
        db: Database session (caller owns lifecycle).
        today: The date the plan is made on.
        kid_ages: Children's ages; every suggestion must suit all of them.
        home_name: Home city name, used in the prompt.
        home_latitude: Home latitude for the forecast.
        home_longitude: Home longitude for the forecast.
        max_drive_minutes: Longest one-way drive to suggest.
        repeat_after_days: Minimum gap before a place is suggested again.
        claude: Optional ``ClaudeClient``. Without it the ranking alone decides.
        forecast: Optional pre-fetched forecast (skips the Open-Meteo call).
        events: Optional dated events for the weekend. Loaded from the
            database (home city, local sources) when not given.

    Returns:
        The plan. ``is_empty`` is True when no place passed the filters.
    """
    weekend_start, days = upcoming_weekend(today)
    warnings: List[str] = []

    if forecast is None:
        try:
            forecast = await fetch_forecast(home_latitude, home_longitude, days)
        except WeatherUnavailable as exc:
            logger.warning("Weekend forecast unavailable: %s", exc)
            warnings.append("Forecast unavailable, so both plans are shown without a weather pick.")
            forecast = []
    forecast = list(forecast)

    candidates = await load_candidates(
        db,
        weekend_start=weekend_start,
        kid_ages=kid_ages,
        max_drive_minutes=max_drive_minutes,
        repeat_after_days=repeat_after_days,
    )

    if events is None:
        events = await load_weekend_events(db, city=home_name, days=days)
    event_options = group_weekend_events(events, weekend_start)[:EVENT_SHORTLIST_SIZE]

    lead = choose_lead(forecast, weekend_start.month)
    outdoor_day = best_outdoor_day(forecast)
    indoor_day = best_indoor_day(forecast)
    outdoor_day_iso = outdoor_day.day.isoformat() if outdoor_day else None
    indoor_day_iso = indoor_day.day.isoformat() if indoor_day else None
    valid_days = [day.isoformat() for day in days]

    # Deterministic picks: used directly without Claude, and as the fallback
    # for any slot Claude leaves empty or fills with an unknown slug.
    fallback_outdoor = (
        PlaceOption.from_place(candidates.outdoor[0], best_day=outdoor_day_iso)
        if candidates.outdoor
        else None
    )
    indoor_pool = [
        p for p in candidates.indoor if not (fallback_outdoor and p.slug == fallback_outdoor.slug)
    ]
    fallback_indoor = (
        PlaceOption.from_place(indoor_pool[0], best_day=indoor_day_iso) if indoor_pool else None
    )

    plan = WeekendPlanResult(
        weekend_start=weekend_start,
        days=list(days),
        forecast=forecast,
        lead=lead,
        outdoor=fallback_outdoor,
        indoor=fallback_indoor,
        events=fallback_events(event_options),
        warnings=warnings,
    )

    if not candidates.outdoor and not candidates.indoor:
        plan.warnings.append(
            "No places matched. Run 'scout weekend seed' or relax the drive limit."
        )
        return plan

    if claude is not None:
        try:
            response = await _ask_claude(
                claude,
                candidates=candidates,
                forecast=forecast,
                days=days,
                kid_ages=kid_ages,
                home_name=home_name,
                lead=lead,
                events=event_options,
            )
            outdoor_by_slug = {p.slug: p for p in candidates.outdoor[:SHORTLIST_SIZE]}
            indoor_by_slug = {p.slug: p for p in candidates.indoor[:SHORTLIST_SIZE]}

            picked_outdoor = _pick(
                response.get("outdoor"), outdoor_by_slug, valid_days, outdoor_day_iso
            )
            picked_indoor = _pick(
                response.get("indoor"), indoor_by_slug, valid_days, indoor_day_iso
            )

            if picked_outdoor:
                plan.outdoor = picked_outdoor
            if picked_indoor and not (plan.outdoor and picked_indoor.slug == plan.outdoor.slug):
                plan.indoor = picked_indoor
            if plan.outdoor and plan.indoor and plan.outdoor.slug == plan.indoor.slug:
                # The same place ended up in both slots; refill the indoor one.
                plan.indoor = next(
                    (
                        PlaceOption.from_place(p, best_day=indoor_day_iso)
                        for p in candidates.indoor
                        if p.slug != plan.outdoor.slug
                    ),
                    None,
                )
            plan.summary = str(response.get("summary") or "")
            plan.ai_used = True
            # Claude's list replaces the unvetted fallback, even when empty:
            # "nothing suits these children" is a valid answer.
            plan.events = _pick_events(response.get("events"), event_options)

            chosen = {o.slug for _, o in plan.ordered_options}
            all_by_slug = {**outdoor_by_slug, **indoor_by_slug}
            for raw in response.get("alternates") or []:
                option = _pick(raw, all_by_slug, valid_days, None)
                if option and option.slug not in chosen:
                    plan.alternates.append(option)
                    chosen.add(option.slug)
        except Exception as exc:  # noqa: BLE001 - a plan must still go out
            logger.error("Claude weekend planning failed, using ranking: %s", exc, exc_info=True)
            plan.warnings.append("AI write-up unavailable, so this is the automatic ranking.")

    if not plan.alternates:
        chosen = {o.slug for _, o in plan.ordered_options}
        for place in candidates.outdoor[:3] + candidates.indoor[:3]:
            if place.slug not in chosen:
                chosen.add(place.slug)
                plan.alternates.append(PlaceOption.from_place(place))
    plan.alternates = plan.alternates[:3]

    return plan


async def get_stored_plan(db: AsyncSession, weekend_start: date) -> Optional[WeekendPlan]:
    """Return the stored plan for a weekend, if one was saved."""
    result = await db.execute(select(WeekendPlan).where(WeekendPlan.weekend_start == weekend_start))
    return result.scalars().first()


async def save_plan(db: AsyncSession, plan: WeekendPlanResult, *, sent: bool) -> WeekendPlan:
    """
    Insert or update the stored plan for ``plan.weekend_start``.

    Args:
        db: Database session (caller owns lifecycle and commit).
        plan: The plan to store.
        sent: Whether the plan was emailed; stamps ``sent_at`` when True.
    """
    stored = await get_stored_plan(db, plan.weekend_start)
    if stored is None:
        stored = WeekendPlan(weekend_start=plan.weekend_start)
        db.add(stored)
    stored.forecast_json = plan.forecast_dict()
    stored.plan_json = plan.to_dict()
    if sent:
        stored.sent_at = datetime.now(timezone.utc)
    await db.flush()
    return stored


async def find_place(db: AsyncSession, name_or_slug: str) -> Place:
    """
    Find one place by slug, exact name or unambiguous partial name.

    Raises:
        PlaceNotFound: If nothing matches, or the text matches several places.
    """
    text = name_or_slug.strip()
    result = await db.execute(select(Place).where(Place.slug == text.lower()))
    place = result.scalars().first()
    if place is not None:
        return place

    result = await db.execute(select(Place).where(Place.name.ilike(f"%{text}%")))
    matches = list(result.scalars().all())
    exact = [p for p in matches if p.name.lower() == text.lower()]
    if len(exact) == 1:
        return exact[0]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise PlaceNotFound(f"No place matches '{name_or_slug}'")
    names = ", ".join(sorted(p.name for p in matches))
    raise PlaceNotFound(f"'{name_or_slug}' matches several places: {names}")


async def log_visit(
    db: AsyncSession,
    name_or_slug: str,
    *,
    visited_on: date,
    rating: Optional[int] = None,
    comment: Optional[str] = None,
) -> PlaceVisit:
    """
    Record a visit so the place is not suggested again too soon.

    Raises:
        PlaceNotFound: If the place cannot be identified.
        ValueError: If ``rating`` is outside 1-5.
    """
    if rating is not None and not 1 <= rating <= 5:
        raise ValueError("rating must be between 1 and 5")
    place = await find_place(db, name_or_slug)
    visit = PlaceVisit(place_id=place.id, visited_on=visited_on, rating=rating, comment=comment)
    visit.place = place
    db.add(visit)
    await db.flush()
    return visit
