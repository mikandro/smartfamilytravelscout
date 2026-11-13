"""
Unit tests for the weekend planner (weather, filtering, plan building, email).

No network, database or Claude calls: the forecast is injected, the session is
mocked and Claude is an AsyncMock.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.models.place import Place, PlaceVisit
from app.weekend import planner
from app.weekend.planner import (
    LEAD_INDOOR,
    LEAD_OUTDOOR,
    WeekendPlanResult,
    build_weekend_plan,
    choose_lead,
    filter_candidates,
    forecast_changed,
    upcoming_weekend,
)
from app.weekend.seed_places import PLACES
from app.weekend.weather import (
    VERDICT_INDOOR,
    VERDICT_MIXED,
    VERDICT_OUTDOOR,
    DayForecast,
    WeatherUnavailable,
    parse_open_meteo,
)

SATURDAY = date(2026, 11, 14)
SUNDAY = date(2026, 11, 15)
THURSDAY = date(2026, 11, 12)
KIDS = [3, 7]


def make_day(day=SATURDAY, *, tmax=10.0, tmin=3.0, rain=0.0, prob=10, wind=10.0, code=1):
    return DayForecast(
        day=day,
        temp_max_c=tmax,
        temp_min_c=tmin,
        precipitation_mm=rain,
        precipitation_probability=prob,
        wind_max_kmh=wind,
        weather_code=code,
    )


def make_place(id, slug, setting, **overrides):
    values = dict(
        id=id,
        slug=slug,
        name=slug.replace("-", " ").title(),
        category="test",
        setting=setting,
        latitude=48.1,
        longitude=11.5,
        drive_minutes=20,
        transit_minutes=None,
        transit_note=None,
        age_min=0,
        age_max=None,
        stroller_friendly=True,
        duration_hours=2.0,
        cost_family_eur=0,
        booking_required=False,
        months_open=None,
        notes="Seed note.",
        url=None,
        is_active=True,
    )
    values.update(overrides)
    return Place(**values)


def make_visit(place_id, visited_on, rating=None):
    return PlaceVisit(place_id=place_id, visited_on=visited_on, rating=rating)


def filter_kwargs(**overrides):
    values = dict(weekend_start=SATURDAY, kid_ages=KIDS, max_drive_minutes=75, repeat_after_days=49)
    values.update(overrides)
    return values


def mock_db(places, visits=(), events=()):
    """A session whose executes return places, then visits, then events."""

    def result_for(rows):
        result = MagicMock()
        result.scalars.return_value.all.return_value = list(rows)
        return result

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[result_for(places), result_for(visits), result_for(events)])
    return db


def plan_kwargs(**overrides):
    values = dict(
        today=THURSDAY,
        kid_ages=KIDS,
        home_name="Munich",
        home_latitude=48.137,
        home_longitude=11.575,
        max_drive_minutes=75,
        repeat_after_days=49,
    )
    values.update(overrides)
    return values


# --------------------------------------------------------------------------- #
# Weather
# --------------------------------------------------------------------------- #


class TestDayForecast:
    def test_dry_day_is_outdoor(self):
        assert make_day(rain=0.0, prob=10).verdict == VERDICT_OUTDOOR

    def test_cold_but_dry_day_is_still_outdoor(self):
        assert make_day(tmax=1.0, tmin=-4.0, rain=0.0, prob=5).verdict == VERDICT_OUTDOOR

    def test_heavy_rain_is_indoor(self):
        assert make_day(rain=8.0, prob=90, code=63).verdict == VERDICT_INDOOR

    def test_likely_moderate_rain_is_indoor(self):
        assert make_day(rain=2.5, prob=80, code=61).verdict == VERDICT_INDOOR

    def test_thunderstorm_is_indoor_even_if_little_rain(self):
        assert make_day(rain=0.5, prob=30, code=95).verdict == VERDICT_INDOOR

    def test_storm_wind_is_indoor(self):
        assert make_day(wind=70.0).verdict == VERDICT_INDOOR

    def test_hard_frost_is_indoor(self):
        assert make_day(tmax=-6.0, tmin=-12.0).verdict == VERDICT_INDOOR

    def test_showery_day_is_mixed(self):
        assert make_day(rain=1.5, prob=55, code=80).verdict == VERDICT_MIXED

    def test_missing_probability_is_treated_as_zero(self):
        assert make_day(prob=None).verdict == VERDICT_OUTDOOR

    def test_dry_day_outscores_wet_day(self):
        assert make_day(rain=0.0).outdoor_score > make_day(rain=6.0, prob=90).outdoor_score

    def test_summary_mentions_temperatures_and_rain(self):
        text = make_day(tmax=9.4, tmin=3.6, rain=3.2, prob=60, code=61).summary()
        assert "Sat 14 Nov" in text
        assert "4–9°C" in text
        assert "60% rain" in text
        assert "3.2 mm" in text

    def test_to_dict_is_json_safe_and_has_verdict(self):
        data = make_day().to_dict()
        assert data["day"] == "2026-11-14"
        assert data["verdict"] == VERDICT_OUTDOOR


class TestParseOpenMeteo:
    PAYLOAD = {
        "daily": {
            "time": ["2026-11-14", "2026-11-15"],
            "weather_code": [3, 63],
            "temperature_2m_max": [9.1, 6.0],
            "temperature_2m_min": [2.0, 3.5],
            "precipitation_sum": [0.0, 7.4],
            "precipitation_probability_max": [15, 95],
            "wind_speed_10m_max": [12.0, 25.0],
        }
    }

    def test_parses_requested_days_in_order(self):
        days = parse_open_meteo(self.PAYLOAD, [SATURDAY, SUNDAY])
        assert [d.day for d in days] == [SATURDAY, SUNDAY]
        assert days[0].verdict == VERDICT_OUTDOOR
        assert days[1].verdict == VERDICT_INDOOR
        assert days[1].description == "rain"

    def test_missing_day_raises(self):
        with pytest.raises(WeatherUnavailable, match="2026-11-16"):
            parse_open_meteo(self.PAYLOAD, [SUNDAY, date(2026, 11, 16)])

    def test_malformed_payload_raises(self):
        with pytest.raises(WeatherUnavailable):
            parse_open_meteo({"error": True}, [SATURDAY])

    def test_null_precipitation_is_zero(self):
        payload = {"daily": dict(self.PAYLOAD["daily"], precipitation_sum=[None, None])}
        days = parse_open_meteo(payload, [SATURDAY])
        assert days[0].precipitation_mm == 0.0


# --------------------------------------------------------------------------- #
# Dates and lead
# --------------------------------------------------------------------------- #


class TestUpcomingWeekend:
    def test_thursday_plans_coming_saturday_and_sunday(self):
        assert upcoming_weekend(THURSDAY) == (SATURDAY, [SATURDAY, SUNDAY])

    def test_monday_plans_same_week(self):
        assert upcoming_weekend(date(2026, 11, 9)) == (SATURDAY, [SATURDAY, SUNDAY])

    def test_saturday_plans_today_and_tomorrow(self):
        assert upcoming_weekend(SATURDAY) == (SATURDAY, [SATURDAY, SUNDAY])

    def test_sunday_plans_only_sunday(self):
        assert upcoming_weekend(SUNDAY) == (SATURDAY, [SUNDAY])


class TestChooseLead:
    def test_one_dry_day_leads_outdoor(self):
        forecast = [make_day(SATURDAY, rain=9.0, prob=90), make_day(SUNDAY)]
        assert choose_lead(forecast, 11) == LEAD_OUTDOOR

    def test_two_wet_days_lead_indoor(self):
        forecast = [make_day(SATURDAY, rain=9.0, prob=90), make_day(SUNDAY, rain=6.0, prob=80)]
        assert choose_lead(forecast, 7) == LEAD_INDOOR

    def test_mixed_days_lead_indoor(self):
        forecast = [make_day(SATURDAY, rain=1.5, prob=55), make_day(SUNDAY, rain=2.0, prob=50)]
        assert choose_lead(forecast, 7) == LEAD_INDOOR

    @pytest.mark.parametrize(
        "month,expected", [(11, LEAD_INDOOR), (1, LEAD_INDOOR), (6, LEAD_OUTDOOR)]
    )
    def test_without_forecast_the_season_decides(self, month, expected):
        assert choose_lead([], month) == expected


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #


class TestFilterCandidates:
    def test_splits_by_setting_with_mixed_counted_as_outdoor(self):
        places = [
            make_place(1, "park", "outdoor"),
            make_place(2, "museum", "indoor"),
            make_place(3, "zoo", "mixed"),
        ]
        result = filter_candidates(places, [], **filter_kwargs())
        assert {p.slug for p in result.outdoor} == {"park", "zoo"}
        assert [p.slug for p in result.indoor] == ["museum"]

    def test_mixed_fills_indoor_slot_when_nothing_is_indoor(self):
        places = [make_place(1, "park", "outdoor"), make_place(2, "zoo", "mixed")]
        result = filter_candidates(places, [], **filter_kwargs())
        assert [p.slug for p in result.indoor] == ["zoo"]

    def test_place_too_old_for_the_three_year_old_is_dropped(self):
        places = [make_place(1, "studio-tour", "indoor", age_min=6)]
        assert filter_candidates(places, [], **filter_kwargs()).indoor == []

    def test_place_too_young_for_the_seven_year_old_is_dropped(self):
        places = [make_place(1, "toddler-gym", "indoor", age_max=5)]
        assert filter_candidates(places, [], **filter_kwargs()).indoor == []

    def test_age_range_covering_both_kids_is_kept(self):
        places = [make_place(1, "kinderreich", "indoor", age_min=3, age_max=8)]
        assert len(filter_candidates(places, [], **filter_kwargs()).indoor) == 1

    def test_out_of_season_place_is_dropped(self):
        places = [make_place(1, "bathing-lake", "outdoor", months_open=[6, 7, 8])]
        assert filter_candidates(places, [], **filter_kwargs()).outdoor == []

    def test_in_season_place_is_kept(self):
        places = [make_place(1, "bathing-lake", "outdoor", months_open=[6, 7, 8])]
        result = filter_candidates(places, [], **filter_kwargs(weekend_start=date(2026, 7, 4)))
        assert len(result.outdoor) == 1

    def test_place_beyond_drive_limit_is_dropped(self):
        places = [make_place(1, "legoland", "outdoor", drive_minutes=80)]
        assert filter_candidates(places, [], **filter_kwargs()).outdoor == []

    def test_inactive_place_is_dropped(self):
        places = [make_place(1, "closed", "indoor", is_active=False)]
        assert filter_candidates(places, [], **filter_kwargs()).indoor == []

    def test_recently_visited_place_is_dropped(self):
        places = [make_place(1, "zoo", "mixed")]
        visits = [make_visit(1, SATURDAY - timedelta(days=14), rating=5)]
        assert filter_candidates(places, visits, **filter_kwargs()).outdoor == []

    def test_place_visited_long_ago_is_back(self):
        places = [make_place(1, "zoo", "mixed")]
        visits = [make_visit(1, SATURDAY - timedelta(days=60), rating=5)]
        assert len(filter_candidates(places, visits, **filter_kwargs()).outdoor) == 1

    def test_disliked_place_never_returns(self):
        places = [make_place(1, "boring", "indoor")]
        visits = [make_visit(1, SATURDAY - timedelta(days=400), rating=2)]
        assert filter_candidates(places, visits, **filter_kwargs()).indoor == []

    def test_latest_rating_wins_over_an_old_bad_one(self):
        places = [make_place(1, "second-chance", "indoor")]
        visits = [
            make_visit(1, SATURDAY - timedelta(days=400), rating=1),
            make_visit(1, SATURDAY - timedelta(days=100), rating=4),
        ]
        assert len(filter_candidates(places, visits, **filter_kwargs()).indoor) == 1

    def test_closer_place_ranks_first_when_otherwise_equal(self):
        # 60 minutes apart outweighs the per-weekend shuffle (at most 3 points).
        places = [
            make_place(1, "far", "outdoor", drive_minutes=70),
            make_place(2, "near", "outdoor", drive_minutes=10),
        ]
        result = filter_candidates(places, [], **filter_kwargs())
        assert [p.slug for p in result.outdoor] == ["near", "far"]

    def test_recent_visits_are_reported_newest_first(self):
        places = [make_place(1, "a", "indoor"), make_place(2, "b", "indoor")]
        visits = [
            make_visit(1, SATURDAY - timedelta(days=30)),
            make_visit(2, SATURDAY - timedelta(days=7)),
        ]
        result = filter_candidates(places, visits, **filter_kwargs())
        assert [place.slug for place, _ in result.recent] == ["b", "a"]


# --------------------------------------------------------------------------- #
# Plan building
# --------------------------------------------------------------------------- #


class TestBuildWeekendPlan:
    PLACES = [
        make_place(1, "park", "outdoor", drive_minutes=10),
        make_place(2, "lake", "outdoor", drive_minutes=40),
        make_place(3, "museum", "indoor", drive_minutes=10),
        make_place(4, "pool", "indoor", drive_minutes=40),
    ]
    DRY_THEN_WET = [make_day(SATURDAY), make_day(SUNDAY, rain=9.0, prob=95, code=63)]

    async def test_without_claude_uses_ranking_and_assigns_days(self):
        plan = await build_weekend_plan(
            mock_db(self.PLACES), forecast=self.DRY_THEN_WET, **plan_kwargs()
        )
        assert plan.ai_used is False
        assert plan.lead == LEAD_OUTDOOR
        assert plan.outdoor.slug == "park"
        assert plan.indoor.slug == "museum"
        assert plan.outdoor.best_day == SATURDAY.isoformat()
        assert plan.indoor.best_day == SUNDAY.isoformat()
        assert plan.outdoor.why == "Seed note."
        assert {o.slug for o in plan.alternates} == {"lake", "pool"}

    async def test_wet_weekend_leads_with_indoor(self):
        wet = [make_day(SATURDAY, rain=9.0, prob=95), make_day(SUNDAY, rain=7.0, prob=90)]
        plan = await build_weekend_plan(mock_db(self.PLACES), forecast=wet, **plan_kwargs())
        assert plan.lead == LEAD_INDOOR
        assert [kind for kind, _ in plan.ordered_options] == ["indoor", "outdoor"]
        assert plan.outdoor.best_day is None  # no usable outdoor day

    async def test_claude_picks_are_used(self):
        claude = AsyncMock()
        claude.analyze.return_value = {
            "summary": "Dry Saturday, wet Sunday.",
            "outdoor": {
                "slug": "lake",
                "why": "Ducks.",
                "tips": "Go early.",
                "best_day": "2026-11-14",
            },
            "indoor": {"slug": "pool", "why": "Slides.", "tips": "Bring armbands."},
            "alternates": [{"slug": "park", "why": "Close by."}, {"slug": "lake", "why": "dup"}],
        }
        plan = await build_weekend_plan(
            mock_db(self.PLACES), forecast=self.DRY_THEN_WET, claude=claude, **plan_kwargs()
        )
        assert plan.ai_used is True
        assert plan.summary == "Dry Saturday, wet Sunday."
        assert (plan.outdoor.slug, plan.outdoor.why, plan.outdoor.tips) == (
            "lake",
            "Ducks.",
            "Go early.",
        )
        assert plan.indoor.slug == "pool"
        assert plan.indoor.best_day == SUNDAY.isoformat()  # defaulted to the wet day
        assert [o.slug for o in plan.alternates] == ["park"]  # chosen places not repeated

        prompt_data = claude.analyze.call_args.kwargs["data"]
        assert "3 and 7" in prompt_data["kid_ages"]
        assert "park" in prompt_data["outdoor_places"]
        assert claude.analyze.call_args.kwargs["operation"] == "weekend_plan"

    async def test_real_prompt_template_formats_with_the_context(self):
        """ClaudeClient calls prompt.format(**data); a stray brace would raise."""
        claude = AsyncMock()
        claude.analyze.return_value = {"summary": "ok"}
        await build_weekend_plan(
            mock_db(self.PLACES), forecast=self.DRY_THEN_WET, claude=claude, **plan_kwargs()
        )
        kwargs = claude.analyze.call_args.kwargs
        prompt = kwargs["prompt"].format(**kwargs["data"])
        assert "children aged 3 and 7" in prompt
        assert "Saturday 14 November 2026, Sunday 15 November 2026" in prompt
        assert "- park | Park | test | outdoor | drive 10 min | car only" in prompt
        assert "-> outdoor" in prompt and "-> indoor" in prompt
        assert '"best_day": "<one of: 2026-11-14, 2026-11-15>"' in prompt
        assert "(no visits logged yet)" in prompt

    async def test_unknown_slug_from_claude_falls_back_to_ranking(self):
        claude = AsyncMock()
        claude.analyze.return_value = {
            "summary": "ok",
            "outdoor": {"slug": "made-up-place", "why": "x"},
            "indoor": None,
        }
        plan = await build_weekend_plan(
            mock_db(self.PLACES), forecast=self.DRY_THEN_WET, claude=claude, **plan_kwargs()
        )
        assert plan.outdoor.slug == "park"
        assert plan.indoor.slug == "museum"

    async def test_invalid_best_day_from_claude_is_replaced(self):
        claude = AsyncMock()
        claude.analyze.return_value = {
            "summary": "ok",
            "outdoor": {"slug": "park", "why": "x", "best_day": "2026-12-25"},
        }
        plan = await build_weekend_plan(
            mock_db(self.PLACES), forecast=self.DRY_THEN_WET, claude=claude, **plan_kwargs()
        )
        assert plan.outdoor.best_day == SATURDAY.isoformat()

    async def test_claude_failure_still_produces_a_plan(self):
        claude = AsyncMock()
        claude.analyze.side_effect = RuntimeError("API down")
        plan = await build_weekend_plan(
            mock_db(self.PLACES), forecast=self.DRY_THEN_WET, claude=claude, **plan_kwargs()
        )
        assert plan.ai_used is False
        assert plan.outdoor.slug == "park"
        assert any("AI write-up unavailable" in w for w in plan.warnings)

    async def test_malformed_claude_response_still_produces_a_plan(self):
        claude = AsyncMock()
        claude.analyze.return_value = {"unexpected": True}
        plan = await build_weekend_plan(
            mock_db(self.PLACES), forecast=self.DRY_THEN_WET, claude=claude, **plan_kwargs()
        )
        assert plan.ai_used is False
        assert plan.indoor.slug == "museum"

    async def test_same_mixed_place_is_not_used_for_both_slots(self):
        places = [
            make_place(1, "zoo", "mixed"),
            make_place(2, "gardens", "mixed", drive_minutes=60),
        ]
        plan = await build_weekend_plan(
            mock_db(places), forecast=self.DRY_THEN_WET, **plan_kwargs()
        )
        assert plan.outdoor.slug == "zoo"
        assert plan.indoor.slug == "gardens"

    async def test_no_places_gives_empty_plan_and_skips_claude(self):
        claude = AsyncMock()
        plan = await build_weekend_plan(
            mock_db([]), forecast=self.DRY_THEN_WET, claude=claude, **plan_kwargs()
        )
        assert plan.is_empty
        assert any("No places matched" in w for w in plan.warnings)
        claude.analyze.assert_not_called()

    async def test_forecast_failure_is_a_warning_not_an_error(self, monkeypatch):
        monkeypatch.setattr(
            planner, "fetch_forecast", AsyncMock(side_effect=WeatherUnavailable("offline"))
        )
        plan = await build_weekend_plan(mock_db(self.PLACES), **plan_kwargs())
        assert plan.forecast == []
        assert plan.lead == LEAD_INDOOR  # November, no forecast
        assert plan.outdoor is not None and plan.indoor is not None
        assert any("Forecast unavailable" in w for w in plan.warnings)

    async def test_plan_serialises_for_storage(self):
        plan = await build_weekend_plan(
            mock_db(self.PLACES), forecast=self.DRY_THEN_WET, **plan_kwargs()
        )
        data = plan.to_dict()
        assert data["weekend_start"] == "2026-11-14"
        assert data["outdoor"]["slug"] == "park"
        forecast = plan.forecast_dict()
        assert forecast["lead"] == LEAD_OUTDOOR
        assert [d["verdict"] for d in forecast["days"]] == [VERDICT_OUTDOOR, VERDICT_INDOOR]


class TestForecastChanged:
    def _plan(self, forecast):
        return WeekendPlanResult(
            weekend_start=SATURDAY,
            days=[SATURDAY, SUNDAY],
            forecast=forecast,
            lead=choose_lead(forecast, 11),
            outdoor=None,
            indoor=None,
        )

    def test_same_forecast_is_unchanged(self):
        forecast = [make_day(SATURDAY), make_day(SUNDAY, rain=9.0, prob=95)]
        stored = self._plan(forecast).forecast_dict()
        assert forecast_changed(stored, self._plan(forecast)) is False

    def test_small_temperature_shift_is_unchanged(self):
        stored = self._plan([make_day(SATURDAY), make_day(SUNDAY)]).forecast_dict()
        new = self._plan([make_day(SATURDAY, tmax=12.0), make_day(SUNDAY, tmax=8.0)])
        assert forecast_changed(stored, new) is False

    def test_lead_flip_is_a_change(self):
        stored = self._plan([make_day(SATURDAY), make_day(SUNDAY)]).forecast_dict()
        wet = [make_day(SATURDAY, rain=9.0, prob=95), make_day(SUNDAY, rain=8.0, prob=95)]
        assert forecast_changed(stored, self._plan(wet)) is True

    def test_dry_day_moving_to_the_other_day_is_a_change(self):
        stored = self._plan(
            [make_day(SATURDAY), make_day(SUNDAY, rain=9.0, prob=95)]
        ).forecast_dict()
        new = self._plan([make_day(SATURDAY, rain=9.0, prob=95), make_day(SUNDAY)])
        assert forecast_changed(stored, new) is True


# --------------------------------------------------------------------------- #
# Seed data
# --------------------------------------------------------------------------- #


class TestSeedPlaces:
    def test_slugs_are_unique(self):
        slugs = [p["slug"] for p in PLACES]
        assert len(slugs) == len(set(slugs))

    def test_every_entry_builds_a_valid_place(self):
        for data in PLACES:
            place = Place(**data)
            assert place.setting in ("indoor", "outdoor", "mixed"), place.slug
            assert place.drive_minutes > 0, place.slug
            assert place.notes, place.slug
            assert all(1 <= m <= 12 for m in (place.months_open or [])), place.slug
            if place.transit_minutes is None:
                assert place.transit_note is None, place.slug

    def test_november_has_indoor_and_outdoor_choices_for_ages_3_and_7(self):
        places = [Place(id=i, is_active=True, **data) for i, data in enumerate(PLACES, 1)]
        result = filter_candidates(places, [], **filter_kwargs())
        assert len(result.indoor) >= 8
        assert len(result.outdoor) >= 8
        slugs = {p.slug for p in result.indoor + result.outdoor}
        assert "bavaria-filmstadt" not in slugs  # too old for the 3-year-old
        assert "legoland" not in slugs  # closed in November, beyond the drive limit
        assert "woerthsee" not in slugs  # bathing lake, summer only


# --------------------------------------------------------------------------- #
# Email
# --------------------------------------------------------------------------- #


class TestWeekendEmail:
    @pytest.fixture
    def notifier(self):
        from app.config import get_settings
        from app.notifications.email_sender import EmailNotifier

        return EmailNotifier(get_settings(), user_email="family@example.com")

    @pytest.fixture
    async def plan(self):
        places = [
            make_place(
                1,
                "wildpark",
                "outdoor",
                name="Wildpark <Poing>",
                transit_minutes=35,
                transit_note="S2 Poing, 15 min walk",
                cost_family_eur=40,
                url="https://example.com/wildpark",
            ),
            make_place(
                2, "therme", "indoor", name="Therme", booking_required=True, cost_family_eur=130
            ),
        ]
        forecast = [make_day(SATURDAY), make_day(SUNDAY, rain=9.0, prob=95, code=63)]
        return await build_weekend_plan(mock_db(places), forecast=forecast, **plan_kwargs())

    def test_html_contains_both_options_and_practical_details(self, notifier, plan):
        html = notifier.render_weekend_plan(plan)
        assert "Sat 14 – Sun 15 November" in html
        assert "Wildpark &lt;Poing&gt;" in html  # escaped
        assert "https://example.com/wildpark" in html
        assert "S2 Poing, 15 min walk" in html
        assert "about €40 for the family" in html
        assert "book ahead" in html
        assert "best on Saturday" in html
        assert "Forecast changed" not in html
        # Outdoor leads on a dry Saturday, so it comes first.
        assert html.index("Wildpark") < html.index("Therme")

    def test_update_email_is_flagged(self, notifier, plan):
        assert "Forecast changed" in notifier.render_weekend_plan(plan, is_update=True)

    def test_text_version_lists_the_plan(self, notifier, plan):
        text = notifier.render_weekend_plan_text(plan)
        assert "If it's dry (best on Saturday): Wildpark <Poing>" in text
        assert "If it's wet (best on Sunday): Therme" in text
        assert "car only" in text

    async def test_send_uses_recipient_and_subject(self, notifier, plan):
        notifier.send_email = Mock(return_value=True)
        assert await notifier.send_weekend_plan(plan, is_update=True) is True
        kwargs = notifier.send_email.call_args.kwargs
        assert kwargs["to_email"] == "family@example.com"
        assert "Forecast changed" in kwargs["subject"]
        assert kwargs["text_body"]

    async def test_send_without_recipient_fails(self, plan):
        from app.config import get_settings
        from app.notifications.email_sender import EmailNotifier

        assert await EmailNotifier(get_settings()).send_weekend_plan(plan) is False
