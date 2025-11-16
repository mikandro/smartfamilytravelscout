"""
Unit tests for date_utils module.
"""

import pytest
from datetime import date, timedelta

from app.utils.date_utils import (
    Holiday,
    BAVARIA_HOLIDAYS_2025_2026,
    BAVARIA_PUBLIC_HOLIDAYS_2025_2026,
    is_school_holiday,
    get_upcoming_holidays,
    get_date_ranges_for_holidays,
    find_long_weekends,
    calculate_nights,
    date_range,
    is_weekend,
    get_weekday_name,
    parse_date,
)


class TestHoliday:
    """Tests for Holiday dataclass."""

    def test_holiday_creation(self):
        """Test creating a Holiday object."""
        holiday = Holiday(
            name="Test Holiday",
            start_date=date(2025, 8, 1),
            end_date=date(2025, 8, 15),
            holiday_type="major",
        )
        assert holiday.name == "Test Holiday"
        assert holiday.start_date == date(2025, 8, 1)
        assert holiday.end_date == date(2025, 8, 15)
        assert holiday.holiday_type == "major"

    def test_duration_days(self):
        """Test holiday duration calculation."""
        holiday = Holiday(
            name="Test", start_date=date(2025, 8, 1), end_date=date(2025, 8, 15)
        )
        assert holiday.duration_days == 15

    def test_contains_date(self):
        """Test if date falls within holiday."""
        holiday = Holiday(
            name="Test", start_date=date(2025, 8, 1), end_date=date(2025, 8, 15)
        )
        assert holiday.contains_date(date(2025, 8, 1))  # Start date
        assert holiday.contains_date(date(2025, 8, 8))  # Middle
        assert holiday.contains_date(date(2025, 8, 15))  # End date
        assert not holiday.contains_date(date(2025, 7, 31))  # Before
        assert not holiday.contains_date(date(2025, 8, 16))  # After


class TestIsSchoolHoliday:
    """Tests for is_school_holiday function."""

    def test_is_school_holiday_summer(self):
        """Test checking if date is in summer holidays."""
        # Summer holidays 2025: Aug 1 - Sep 15
        assert is_school_holiday(date(2025, 8, 15))
        assert is_school_holiday(date(2025, 9, 1))

    def test_is_not_school_holiday(self):
        """Test checking if date is not in school holidays."""
        assert not is_school_holiday(date(2025, 9, 20))
        assert not is_school_holiday(date(2025, 10, 15))

    def test_is_school_holiday_christmas(self):
        """Test checking if date is in Christmas holidays."""
        assert is_school_holiday(date(2025, 12, 25))
        assert is_school_holiday(date(2026, 1, 2))

    def test_is_school_holiday_none_date(self):
        """Test with None date."""
        assert not is_school_holiday(None)

    def test_is_school_holiday_custom_list(self):
        """Test with custom holiday list."""
        custom_holidays = [
            Holiday(
                name="Custom",
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 10),
            )
        ]
        assert is_school_holiday(date(2025, 1, 5), holidays=custom_holidays)
        assert not is_school_holiday(date(2025, 1, 15), holidays=custom_holidays)


class TestGetUpcomingHolidays:
    """Tests for get_upcoming_holidays function."""

    def test_get_upcoming_holidays_3_months(self):
        """Test getting holidays in next 3 months."""
        holidays = get_upcoming_holidays(months=3, from_date=date(2025, 7, 1))
        assert len(holidays) >= 1
        # Should include summer holidays starting Aug 1
        assert any("Summer" in h.name for h in holidays)

    def test_get_upcoming_holidays_6_months(self):
        """Test getting holidays in next 6 months."""
        holidays = get_upcoming_holidays(months=6, from_date=date(2025, 7, 1))
        assert len(holidays) >= 2

    def test_get_upcoming_holidays_sorted(self):
        """Test that holidays are sorted by start date."""
        holidays = get_upcoming_holidays(months=12, from_date=date(2025, 1, 1))
        for i in range(len(holidays) - 1):
            assert holidays[i].start_date <= holidays[i + 1].start_date

    def test_get_upcoming_holidays_negative_months(self):
        """Test with negative months."""
        holidays = get_upcoming_holidays(months=-1)
        assert holidays == []

    def test_get_upcoming_holidays_no_from_date(self):
        """Test without specifying from_date (uses today)."""
        holidays = get_upcoming_holidays(months=12)
        assert isinstance(holidays, list)


class TestGetDateRangesForHolidays:
    """Tests for get_date_ranges_for_holidays function."""

    def test_get_date_ranges(self):
        """Test converting holidays to date ranges."""
        holidays = [
            Holiday(
                name="Test1", start_date=date(2025, 8, 1), end_date=date(2025, 8, 15)
            ),
            Holiday(
                name="Test2", start_date=date(2025, 9, 1), end_date=date(2025, 9, 10)
            ),
        ]
        ranges = get_date_ranges_for_holidays(holidays)
        assert len(ranges) == 2
        assert ranges[0] == (date(2025, 8, 1), date(2025, 8, 15))
        assert ranges[1] == (date(2025, 9, 1), date(2025, 9, 10))

    def test_get_date_ranges_none(self):
        """Test with None."""
        ranges = get_date_ranges_for_holidays(None)
        assert ranges == []

    def test_get_date_ranges_empty(self):
        """Test with empty list."""
        ranges = get_date_ranges_for_holidays([])
        assert ranges == []


class TestFindLongWeekends:
    """Tests for find_long_weekends function."""

    def test_find_long_weekends_2025(self):
        """Test finding long weekends in 2025."""
        long_weekends = find_long_weekends(2025)
        assert len(long_weekends) > 0
        # May 1st 2025 is Thursday, should create a long weekend
        assert (date(2025, 5, 1), date(2025, 5, 4)) in long_weekends

    def test_find_long_weekends_2026(self):
        """Test finding long weekends in 2026."""
        long_weekends = find_long_weekends(2026)
        assert len(long_weekends) > 0

    def test_find_long_weekends_invalid_year(self):
        """Test with year outside range."""
        long_weekends = find_long_weekends(2024)
        assert long_weekends == []
        long_weekends = find_long_weekends(2027)
        assert long_weekends == []

    def test_find_long_weekends_sorted(self):
        """Test that long weekends are sorted."""
        long_weekends = find_long_weekends(2025)
        for i in range(len(long_weekends) - 1):
            assert long_weekends[i][0] <= long_weekends[i + 1][0]


class TestCalculateNights:
    """Tests for calculate_nights function."""

    def test_calculate_nights_week(self):
        """Test calculating nights for a week."""
        nights = calculate_nights(date(2025, 8, 1), date(2025, 8, 8))
        assert nights == 7

    def test_calculate_nights_same_day(self):
        """Test with same day departure and return."""
        nights = calculate_nights(date(2025, 8, 1), date(2025, 8, 1))
        assert nights == 0

    def test_calculate_nights_return_before_departure(self):
        """Test with return before departure."""
        nights = calculate_nights(date(2025, 8, 8), date(2025, 8, 1))
        assert nights == 0

    def test_calculate_nights_none_values(self):
        """Test with None values."""
        assert calculate_nights(None, date(2025, 8, 1)) == 0
        assert calculate_nights(date(2025, 8, 1), None) == 0
        assert calculate_nights(None, None) == 0


class TestDateRange:
    """Tests for date_range function."""

    def test_date_range_week(self):
        """Test generating date range for a week."""
        dates = list(date_range(date(2025, 8, 1), date(2025, 8, 7)))
        assert len(dates) == 7
        assert dates[0] == date(2025, 8, 1)
        assert dates[-1] == date(2025, 8, 7)

    def test_date_range_single_day(self):
        """Test with same start and end date."""
        dates = list(date_range(date(2025, 8, 1), date(2025, 8, 1)))
        assert len(dates) == 1
        assert dates[0] == date(2025, 8, 1)

    def test_date_range_reverse(self):
        """Test with end before start."""
        dates = list(date_range(date(2025, 8, 7), date(2025, 8, 1)))
        assert len(dates) == 0

    def test_date_range_none_values(self):
        """Test with None values."""
        dates = list(date_range(None, date(2025, 8, 1)))
        assert len(dates) == 0
        dates = list(date_range(date(2025, 8, 1), None))
        assert len(dates) == 0


class TestIsWeekend:
    """Tests for is_weekend function."""

    def test_is_weekend_saturday(self):
        """Test Saturday."""
        assert is_weekend(date(2025, 1, 4))  # Saturday

    def test_is_weekend_sunday(self):
        """Test Sunday."""
        assert is_weekend(date(2025, 1, 5))  # Sunday

    def test_is_not_weekend_weekday(self):
        """Test weekday."""
        assert not is_weekend(date(2025, 1, 6))  # Monday
        assert not is_weekend(date(2025, 1, 10))  # Friday

    def test_is_weekend_none(self):
        """Test with None."""
        assert not is_weekend(None)


class TestGetWeekdayName:
    """Tests for get_weekday_name function."""

    def test_get_weekday_name_monday(self):
        """Test Monday."""
        assert get_weekday_name(date(2025, 1, 6)) == "Monday"

    def test_get_weekday_name_friday(self):
        """Test Friday."""
        assert get_weekday_name(date(2025, 1, 10)) == "Friday"

    def test_get_weekday_name_saturday(self):
        """Test Saturday."""
        assert get_weekday_name(date(2025, 1, 4)) == "Saturday"

    def test_get_weekday_name_sunday(self):
        """Test Sunday."""
        assert get_weekday_name(date(2025, 1, 5)) == "Sunday"

    def test_get_weekday_name_none(self):
        """Test with None."""
        assert get_weekday_name(None) == ""


class TestParseDate:
    """Tests for parse_date function."""

    def test_parse_date_iso_format(self):
        """Test parsing ISO format (YYYY-MM-DD)."""
        assert parse_date("2025-08-15") == date(2025, 8, 15)

    def test_parse_date_german_format(self):
        """Test parsing German format (DD.MM.YYYY)."""
        assert parse_date("15.08.2025") == date(2025, 8, 15)

    def test_parse_date_slash_format(self):
        """Test parsing slash format (DD/MM/YYYY)."""
        assert parse_date("15/08/2025") == date(2025, 8, 15)

    def test_parse_date_with_spaces(self):
        """Test parsing date with leading/trailing spaces."""
        assert parse_date("  2025-08-15  ") == date(2025, 8, 15)

    def test_parse_date_invalid(self):
        """Test parsing invalid date."""
        assert parse_date("invalid") is None
        assert parse_date("32.13.2025") is None

    def test_parse_date_none(self):
        """Test with None."""
        assert parse_date(None) is None

    def test_parse_date_empty(self):
        """Test with empty string."""
        assert parse_date("") is None


class TestBavariaHolidaysData:
    """Tests for Bavaria holidays data."""

    def test_bavaria_holidays_exist(self):
        """Test that Bavaria holidays are defined."""
        assert len(BAVARIA_HOLIDAYS_2025_2026) > 0

    def test_bavaria_holidays_have_required_fields(self):
        """Test that all holidays have required fields."""
        for holiday in BAVARIA_HOLIDAYS_2025_2026:
            assert holiday.name
            assert holiday.start_date
            assert holiday.end_date
            assert holiday.start_date <= holiday.end_date

    def test_bavaria_public_holidays_exist(self):
        """Test that Bavaria public holidays are defined."""
        assert len(BAVARIA_PUBLIC_HOLIDAYS_2025_2026) > 0

    def test_bavaria_public_holidays_2025(self):
        """Test that 2025 public holidays include expected dates."""
        # New Year's Day
        assert date(2025, 1, 1) in BAVARIA_PUBLIC_HOLIDAYS_2025_2026
        # Christmas
        assert date(2025, 12, 25) in BAVARIA_PUBLIC_HOLIDAYS_2025_2026
        assert date(2025, 12, 26) in BAVARIA_PUBLIC_HOLIDAYS_2025_2026
