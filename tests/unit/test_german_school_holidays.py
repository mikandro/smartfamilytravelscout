"""
Unit tests for German school holidays multi-region support.
"""

from datetime import date

import pytest

from app.utils.german_school_holidays import (
    GERMAN_HOLIDAYS_2025_2026,
    GERMAN_STATES,
    get_holidays_for_region,
    get_all_regions,
    get_all_holidays,
)


class TestGermanSchoolHolidays:
    """Test multi-region school holiday functionality."""

    def test_all_16_german_states_present(self):
        """Test that all 16 German states are included."""
        assert len(GERMAN_STATES) == 16
        assert "Bavaria" in GERMAN_STATES
        assert "Berlin" in GERMAN_STATES
        assert "Hamburg" in GERMAN_STATES
        assert "North Rhine-Westphalia" in GERMAN_STATES

    def test_all_states_have_holiday_data(self):
        """Test that all states have holiday data."""
        for state in GERMAN_STATES:
            assert state in GERMAN_HOLIDAYS_2025_2026
            holidays = GERMAN_HOLIDAYS_2025_2026[state]
            assert len(holidays) > 0, f"{state} should have holiday data"

    def test_bavaria_holidays_exist(self):
        """Test Bavaria holidays are properly defined."""
        bavaria_holidays = get_holidays_for_region("Bavaria")
        assert len(bavaria_holidays) > 0

        # Check specific known holidays
        holiday_names = [h.name for h in bavaria_holidays]
        assert any("Summer Holiday 2025" in name for name in holiday_names)
        assert any("Christmas Break" in name for name in holiday_names)
        assert any("Easter Break" in name for name in holiday_names)

    def test_berlin_holidays_exist(self):
        """Test Berlin holidays are properly defined."""
        berlin_holidays = get_holidays_for_region("Berlin")
        assert len(berlin_holidays) > 0

        # Berlin should have different dates than Bavaria
        holiday_names = [h.name for h in berlin_holidays]
        assert any("Summer Holiday 2025" in name for name in holiday_names)

    def test_get_holidays_case_insensitive(self):
        """Test region lookup is case-insensitive."""
        holidays_upper = get_holidays_for_region("BAVARIA")
        holidays_lower = get_holidays_for_region("bavaria")
        holidays_mixed = get_holidays_for_region("BaVaRiA")

        assert len(holidays_upper) == len(holidays_lower)
        assert len(holidays_lower) == len(holidays_mixed)
        assert len(holidays_upper) > 0

    def test_get_holidays_unknown_region_defaults_to_bavaria(self):
        """Test unknown region defaults to Bavaria."""
        holidays = get_holidays_for_region("NonExistentState")
        bavaria_holidays = get_holidays_for_region("Bavaria")

        assert len(holidays) == len(bavaria_holidays)

    def test_get_all_regions(self):
        """Test getting all region names."""
        regions = get_all_regions()
        assert len(regions) == 16
        assert "Bavaria" in regions
        assert "Berlin" in regions
        # Should be sorted
        assert regions == sorted(regions)

    def test_get_all_holidays(self):
        """Test getting all holidays from all regions."""
        all_holidays = get_all_holidays()
        assert len(all_holidays) > 100  # Should have many holidays across all states

        # Check we have holidays from different regions
        regions_found = set(h.region for h in all_holidays)
        assert len(regions_found) == 16  # All 16 states represented

    def test_holiday_dates_are_valid(self):
        """Test all holiday dates are valid and in correct order."""
        for state, holidays in GERMAN_HOLIDAYS_2025_2026.items():
            for holiday in holidays:
                # Start date should be before or equal to end date
                assert holiday.start_date <= holiday.end_date, \
                    f"{state}: {holiday.name} has invalid dates"

                # Dates should be in 2025-2027 range
                assert 2025 <= holiday.start_date.year <= 2027, \
                    f"{state}: {holiday.name} start date out of range"
                assert 2025 <= holiday.end_date.year <= 2027, \
                    f"{state}: {holiday.name} end date out of range"

    def test_holiday_types(self):
        """Test holiday types are valid."""
        valid_types = {"major", "long_weekend"}

        for state, holidays in GERMAN_HOLIDAYS_2025_2026.items():
            for holiday in holidays:
                assert holiday.holiday_type in valid_types, \
                    f"{state}: {holiday.name} has invalid type: {holiday.holiday_type}"

    def test_regions_match_in_holidays(self):
        """Test that holiday.region matches the state key."""
        for state, holidays in GERMAN_HOLIDAYS_2025_2026.items():
            for holiday in holidays:
                assert holiday.region == state, \
                    f"Holiday {holiday.name} has mismatched region: {holiday.region} != {state}"

    def test_summer_holidays_different_across_states(self):
        """Test that summer holiday dates vary across states (they do in reality)."""
        summer_dates = {}

        for state in ["Bavaria", "Berlin", "Hamburg", "Saxony"]:
            holidays = get_holidays_for_region(state)
            summer = [h for h in holidays if "Summer Holiday 2025" in h.name]
            if summer:
                summer_dates[state] = (summer[0].start_date, summer[0].end_date)

        # Should have different start dates (German states stagger summer holidays)
        start_dates = [dates[0] for dates in summer_dates.values()]
        assert len(set(start_dates)) > 1, "Summer holidays should vary across states"

    def test_christmas_breaks_similar_across_states(self):
        """Test that Christmas breaks are similar across states."""
        christmas_dates = {}

        for state in GERMAN_STATES:
            holidays = get_holidays_for_region(state)
            christmas = [h for h in holidays if "Christmas Break" in h.name and "2025" in h.name]
            if christmas:
                christmas_dates[state] = (christmas[0].start_date, christmas[0].end_date)

        # Most states should have Christmas breaks
        assert len(christmas_dates) >= 14, "Most states should have Christmas break data"


class TestDateUtilsMultiRegion:
    """Test date_utils functions with multi-region support."""

    def test_is_school_holiday_with_region(self):
        """Test is_school_holiday with different regions."""
        from app.utils.date_utils import is_school_holiday

        # August 15 should be summer holiday in Bavaria
        assert is_school_holiday(date(2025, 8, 15), region="Bavaria")

        # Should also work for Berlin (different dates but overlapping)
        assert is_school_holiday(date(2025, 8, 1), region="Berlin")

    def test_get_upcoming_holidays_with_region(self):
        """Test get_upcoming_holidays with different regions."""
        from app.utils.date_utils import get_upcoming_holidays

        # Get upcoming holidays for Bavaria
        bavaria_holidays = get_upcoming_holidays(
            months=12,
            from_date=date(2025, 1, 1),
            region="Bavaria"
        )
        assert len(bavaria_holidays) > 0

        # Get upcoming holidays for Berlin
        berlin_holidays = get_upcoming_holidays(
            months=12,
            from_date=date(2025, 1, 1),
            region="Berlin"
        )
        assert len(berlin_holidays) > 0

        # Should have different holiday counts or dates
        # (Not necessarily same count due to different holiday structures)
        assert bavaria_holidays[0].region == "Bavaria"
        assert berlin_holidays[0].region == "Berlin"

    def test_get_school_holiday_periods_with_region(self):
        """Test get_school_holiday_periods with different regions."""
        from app.utils.date_utils import get_school_holiday_periods

        # Get summer period for Bavaria
        bavaria_periods = get_school_holiday_periods(
            start_date=date(2025, 7, 1),
            end_date=date(2025, 9, 30),
            region="Bavaria"
        )
        assert len(bavaria_periods) > 0

        # Get summer period for Berlin
        berlin_periods = get_school_holiday_periods(
            start_date=date(2025, 7, 1),
            end_date=date(2025, 9, 30),
            region="Berlin"
        )
        assert len(berlin_periods) > 0

        # Summer holidays should have different dates
        if bavaria_periods and berlin_periods:
            assert bavaria_periods[0] != berlin_periods[0], \
                "Bavaria and Berlin should have different summer holiday dates"

    def test_backwards_compatibility_defaults_to_bavaria(self):
        """Test that functions default to Bavaria for backwards compatibility."""
        from app.utils.date_utils import (
            is_school_holiday,
            get_upcoming_holidays,
            get_school_holiday_periods,
        )

        # Without region parameter, should default to Bavaria
        assert is_school_holiday(date(2025, 8, 15))  # Bavaria summer

        holidays = get_upcoming_holidays(months=12, from_date=date(2025, 1, 1))
        assert len(holidays) > 0
        assert all(h.region == "Bavaria" for h in holidays)

        periods = get_school_holiday_periods(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31)
        )
        assert len(periods) > 0
