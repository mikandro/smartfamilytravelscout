"""
Date utility functions for SmartFamilyTravelScout.

Provides functions for working with school holidays, long weekends,
and date ranges for trip planning.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterator, List, Tuple


@dataclass
class Holiday:
    """Represents a holiday period."""

    name: str
    start_date: date
    end_date: date
    holiday_type: str = "major"  # 'major' or 'long_weekend'
    region: str = "Bavaria"

    @property
    def duration_days(self) -> int:
        """Calculate holiday duration in days."""
        return (self.end_date - self.start_date).days + 1

    def contains_date(self, check_date: date) -> bool:
        """Check if a given date falls within this holiday period."""
        return self.start_date <= check_date <= self.end_date


# Bavaria Public Holidays 2025-2026
BAVARIA_HOLIDAYS_2025_2026: List[Holiday] = [
    # 2025 School Holidays
    Holiday(
        name="Winter Break 2025",
        start_date=date(2025, 2, 24),
        end_date=date(2025, 3, 7),
        holiday_type="major",
    ),
    Holiday(
        name="Easter Break 2025",
        start_date=date(2025, 4, 14),
        end_date=date(2025, 4, 25),
        holiday_type="major",
    ),
    Holiday(
        name="Whitsun Break 2025",
        start_date=date(2025, 6, 10),
        end_date=date(2025, 6, 20),
        holiday_type="major",
    ),
    Holiday(
        name="Summer Holidays 2025",
        start_date=date(2025, 8, 1),
        end_date=date(2025, 9, 15),
        holiday_type="major",
    ),
    Holiday(
        name="Autumn Break 2025",
        start_date=date(2025, 10, 27),
        end_date=date(2025, 11, 7),
        holiday_type="major",
    ),
    Holiday(
        name="Christmas Break 2025",
        start_date=date(2025, 12, 22),
        end_date=date(2026, 1, 5),
        holiday_type="major",
    ),
    # 2026 School Holidays
    Holiday(
        name="Winter Break 2026",
        start_date=date(2026, 2, 16),
        end_date=date(2026, 2, 27),
        holiday_type="major",
    ),
    Holiday(
        name="Easter Break 2026",
        start_date=date(2026, 3, 30),
        end_date=date(2026, 4, 10),
        holiday_type="major",
    ),
    Holiday(
        name="Whitsun Break 2026",
        start_date=date(2026, 5, 26),
        end_date=date(2026, 6, 5),
        holiday_type="major",
    ),
    Holiday(
        name="Summer Holidays 2026",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 9, 14),
        holiday_type="major",
    ),
    Holiday(
        name="Autumn Break 2026",
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 6),
        holiday_type="major",
    ),
    Holiday(
        name="Christmas Break 2026",
        start_date=date(2026, 12, 24),
        end_date=date(2027, 1, 8),
        holiday_type="major",
    ),
]

# Bavaria Public Holidays (bank holidays) 2025-2026
BAVARIA_PUBLIC_HOLIDAYS_2025_2026: List[date] = [
    # 2025
    date(2025, 1, 1),  # New Year's Day
    date(2025, 1, 6),  # Epiphany
    date(2025, 4, 18),  # Good Friday
    date(2025, 4, 21),  # Easter Monday
    date(2025, 5, 1),  # Labour Day
    date(2025, 5, 29),  # Ascension Day
    date(2025, 6, 9),  # Whit Monday
    date(2025, 6, 19),  # Corpus Christi
    date(2025, 8, 15),  # Assumption of Mary
    date(2025, 10, 3),  # German Unity Day
    date(2025, 11, 1),  # All Saints' Day
    date(2025, 12, 25),  # Christmas Day
    date(2025, 12, 26),  # Second Day of Christmas
    # 2026
    date(2026, 1, 1),  # New Year's Day
    date(2026, 1, 6),  # Epiphany
    date(2026, 4, 3),  # Good Friday
    date(2026, 4, 6),  # Easter Monday
    date(2026, 5, 1),  # Labour Day
    date(2026, 5, 14),  # Ascension Day
    date(2026, 5, 25),  # Whit Monday
    date(2026, 6, 4),  # Corpus Christi
    date(2026, 8, 15),  # Assumption of Mary
    date(2026, 10, 3),  # German Unity Day
    date(2026, 11, 1),  # All Saints' Day
    date(2026, 12, 25),  # Christmas Day
    date(2026, 12, 26),  # Second Day of Christmas
]


def is_school_holiday(
    check_date: date,
    holidays: List[Holiday] | None = None,
    region: str = "Bavaria"
) -> bool:
    """
    Check if a date falls within school holidays.

    Args:
        check_date: The date to check
        holidays: List of Holiday objects. If None, loads holidays for specified region.
        region: German state name (e.g., "Bavaria", "Berlin"). Default: "Bavaria"

    Returns:
        True if the date is within a school holiday period, False otherwise

    Examples:
        >>> is_school_holiday(date(2025, 8, 15))  # Summer holidays
        True
        >>> is_school_holiday(date(2025, 9, 20))  # Regular school day
        False
        >>> is_school_holiday(date(2025, 12, 25))  # Christmas break
        True
        >>> is_school_holiday(date(2025, 8, 15), region="Berlin")
        True
    """
    if check_date is None:
        return False

    if holidays is None:
        from app.utils.german_school_holidays import get_holidays_for_region
        holidays = get_holidays_for_region(region)

    return any(holiday.contains_date(check_date) for holiday in holidays)


def get_upcoming_holidays(
    months: int = 3,
    from_date: date | None = None,
    region: str = "Bavaria"
) -> List[Holiday]:
    """
    Get school holidays in the next N months.

    Args:
        months: Number of months to look ahead (default: 3)
        from_date: Starting date for the search. If None, uses today.
        region: German state name (e.g., "Bavaria", "Berlin"). Default: "Bavaria"

    Returns:
        List of Holiday objects within the specified period

    Examples:
        >>> holidays = get_upcoming_holidays(months=6)
        >>> len(holidays) >= 1
        True
        >>> holidays = get_upcoming_holidays(months=1, from_date=date(2025, 7, 1))
        >>> any('Summer' in h.name for h in holidays)
        True
        >>> holidays = get_upcoming_holidays(months=6, region="Berlin")
        >>> len(holidays) >= 1
        True
    """
    if from_date is None:
        from_date = date.today()

    if months < 0:
        return []

    end_date = from_date + timedelta(days=months * 30)  # Approximate

    from app.utils.german_school_holidays import get_holidays_for_region
    all_holidays = get_holidays_for_region(region)

    upcoming = [
        holiday
        for holiday in all_holidays
        if holiday.start_date >= from_date and holiday.start_date <= end_date
    ]

    return sorted(upcoming, key=lambda h: h.start_date)


def get_date_ranges_for_holidays(holidays: List[Holiday] | None = None) -> List[Tuple[date, date]]:
    """
    Convert holidays to (start, end) date ranges for searching.

    Args:
        holidays: List of Holiday objects. If None, returns empty list.

    Returns:
        List of tuples (start_date, end_date)

    Examples:
        >>> holidays = [Holiday("Test", date(2025, 8, 1), date(2025, 8, 15))]
        >>> ranges = get_date_ranges_for_holidays(holidays)
        >>> ranges[0]
        (datetime.date(2025, 8, 1), datetime.date(2025, 8, 15))
    """
    if holidays is None or not holidays:
        return []

    return [(holiday.start_date, holiday.end_date) for holiday in holidays]


def find_long_weekends(year: int) -> List[Tuple[date, date]]:
    """
    Find 3-4 day weekends (Fri-Mon or Thu-Mon with public holiday).

    A long weekend is defined as:
    - A public holiday on Friday or Monday (creating a 3-day weekend)
    - A public holiday on Thursday or Tuesday adjacent to a weekend (creating a 4-day weekend)

    Args:
        year: The year to search for long weekends

    Returns:
        List of tuples (start_date, end_date) representing long weekends

    Examples:
        >>> long_weekends = find_long_weekends(2025)
        >>> len(long_weekends) > 0
        True
        >>> # May 1st 2025 is Thursday, creates Thu-Sun long weekend
        >>> (date(2025, 5, 1), date(2025, 5, 4)) in long_weekends
        True
    """
    if year < 2025 or year > 2026:
        return []

    public_holidays = [d for d in BAVARIA_PUBLIC_HOLIDAYS_2025_2026 if d.year == year]
    long_weekends = []

    for holiday in public_holidays:
        weekday = holiday.weekday()  # Monday=0, Sunday=6

        # Skip if holiday falls on weekend (Sat/Sun)
        if weekday in [5, 6]:
            continue

        # Friday holiday: Fri-Sun
        if weekday == 4:
            long_weekends.append((holiday, holiday + timedelta(days=2)))

        # Monday holiday: Sat-Mon
        elif weekday == 0:
            long_weekends.append((holiday - timedelta(days=2), holiday))

        # Thursday holiday: Thu-Sun
        elif weekday == 3:
            long_weekends.append((holiday, holiday + timedelta(days=3)))

        # Tuesday holiday: Sat-Tue
        elif weekday == 1:
            long_weekends.append((holiday - timedelta(days=3), holiday))

    # Remove duplicates and sort
    long_weekends = list(set(long_weekends))
    return sorted(long_weekends, key=lambda x: x[0])


def calculate_nights(departure: date, return_date: date) -> int:
    """
    Calculate the number of nights between departure and return dates.

    Args:
        departure: Departure date
        return_date: Return date

    Returns:
        Number of nights (0 if return is same day or before departure)

    Examples:
        >>> calculate_nights(date(2025, 8, 1), date(2025, 8, 8))
        7
        >>> calculate_nights(date(2025, 8, 1), date(2025, 8, 1))
        0
        >>> calculate_nights(date(2025, 8, 5), date(2025, 8, 1))
        0
    """
    if departure is None or return_date is None:
        return 0

    if return_date <= departure:
        return 0

    return (return_date - departure).days


def date_range(start: date, end: date) -> Iterator[date]:
    """
    Generate all dates between start and end (inclusive).

    Args:
        start: Start date
        end: End date

    Yields:
        Each date from start to end (inclusive)

    Examples:
        >>> dates = list(date_range(date(2025, 1, 1), date(2025, 1, 3)))
        >>> len(dates)
        3
        >>> dates[0]
        datetime.date(2025, 1, 1)
        >>> dates[-1]
        datetime.date(2025, 1, 3)
    """
    if start is None or end is None:
        return

    if start > end:
        return

    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def is_weekend(check_date: date) -> bool:
    """
    Check if a date falls on a weekend (Saturday or Sunday).

    Args:
        check_date: The date to check

    Returns:
        True if the date is Saturday or Sunday, False otherwise

    Examples:
        >>> is_weekend(date(2025, 1, 4))  # Saturday
        True
        >>> is_weekend(date(2025, 1, 5))  # Sunday
        True
        >>> is_weekend(date(2025, 1, 6))  # Monday
        False
    """
    if check_date is None:
        return False

    return check_date.weekday() in [5, 6]  # Saturday=5, Sunday=6


def get_weekday_name(check_date: date) -> str:
    """
    Get the name of the weekday for a given date.

    Args:
        check_date: The date to check

    Returns:
        Weekday name (e.g., 'Monday', 'Tuesday', etc.)

    Examples:
        >>> get_weekday_name(date(2025, 1, 6))
        'Monday'
        >>> get_weekday_name(date(2025, 1, 11))
        'Saturday'
    """
    if check_date is None:
        return ""

    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return weekdays[check_date.weekday()]


def parse_date(date_str: str) -> date | None:
    """
    Parse a date string in common formats.

    Supports formats:
    - YYYY-MM-DD
    - DD.MM.YYYY
    - DD/MM/YYYY

    Args:
        date_str: Date string to parse

    Returns:
        Parsed date object or None if parsing fails

    Examples:
        >>> parse_date("2025-08-15")
        datetime.date(2025, 8, 15)
        >>> parse_date("15.08.2025")
        datetime.date(2025, 8, 15)
        >>> parse_date("15/08/2025")
        datetime.date(2025, 8, 15)
        >>> parse_date("invalid") is None
        True
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()

    formats = [
        "%Y-%m-%d",  # 2025-08-15
        "%d.%m.%Y",  # 15.08.2025
        "%d/%m/%Y",  # 15/08/2025
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return None


def get_school_holiday_periods(
    start_date: date | None = None,
    end_date: date | None = None,
    holidays: List[Holiday] | None = None,
    region: str = "Bavaria",
) -> List[Tuple[date, date]]:
    """
    Get school holiday periods within a date range.

    Args:
        start_date: Start of the search range. If None, uses today.
        end_date: End of the search range. If None, uses 6 months from start.
        holidays: List of Holiday objects. If None, loads holidays for specified region.
        region: German state name (e.g., "Bavaria", "Berlin"). Default: "Bavaria"

    Returns:
        List of tuples (start_date, end_date) for holidays in the range

    Examples:
        >>> periods = get_school_holiday_periods(date(2025, 7, 1), date(2025, 9, 1))
        >>> len(periods) >= 1  # Should include summer holidays
        True
        >>> periods = get_school_holiday_periods(date(2025, 7, 1), date(2025, 9, 1), region="Berlin")
        >>> len(periods) >= 1
        True
    """
    if start_date is None:
        start_date = date.today()

    if end_date is None:
        end_date = start_date + timedelta(days=180)  # 6 months

    if holidays is None:
        from app.utils.german_school_holidays import get_holidays_for_region
        holidays = get_holidays_for_region(region)

    # Filter holidays that overlap with the date range
    matching_holidays = [
        holiday
        for holiday in holidays
        if (
            holiday.start_date <= end_date
            and holiday.end_date >= start_date
        )
    ]

    # Convert to date range tuples
    return [(h.start_date, h.end_date) for h in matching_holidays]
