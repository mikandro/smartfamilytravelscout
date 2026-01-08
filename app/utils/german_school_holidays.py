"""
German school holidays data for all 16 federal states (2025-2026).

This module provides comprehensive school holiday data for all German states
to enable multi-region trip planning.

Data source: Official school holiday calendars from German state authorities.
"""

from datetime import date
from typing import Dict, List

from app.utils.date_utils import Holiday


# All 16 German federal states
GERMAN_STATES = [
    "Baden-Württemberg",
    "Bavaria",
    "Berlin",
    "Brandenburg",
    "Bremen",
    "Hamburg",
    "Hesse",
    "Mecklenburg-Vorpommern",
    "Lower Saxony",
    "North Rhine-Westphalia",
    "Rhineland-Palatinate",
    "Saarland",
    "Saxony",
    "Saxony-Anhalt",
    "Schleswig-Holstein",
    "Thuringia",
]

# Comprehensive holiday data for all German states (2025-2026)
GERMAN_HOLIDAYS_2025_2026: Dict[str, List[Holiday]] = {
    # Baden-Württemberg
    "Baden-Württemberg": [
        Holiday("Easter Break 2025", date(2025, 4, 14), date(2025, 4, 26), "major", "Baden-Württemberg"),
        Holiday("Whitsun Break 2025", date(2025, 6, 10), date(2025, 6, 21), "major", "Baden-Württemberg"),
        Holiday("Summer Holiday 2025", date(2025, 7, 31), date(2025, 9, 13), "major", "Baden-Württemberg"),
        Holiday("Autumn Break 2025", date(2025, 10, 27), date(2025, 10, 31), "long_weekend", "Baden-Württemberg"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 5), "major", "Baden-Württemberg"),
        Holiday("Winter Break 2026", date(2026, 2, 9), date(2026, 2, 13), "long_weekend", "Baden-Württemberg"),
        Holiday("Easter Break 2026", date(2026, 3, 30), date(2026, 4, 11), "major", "Baden-Württemberg"),
        Holiday("Whitsun Break 2026", date(2026, 5, 26), date(2026, 6, 6), "major", "Baden-Württemberg"),
        Holiday("Summer Holiday 2026", date(2026, 7, 30), date(2026, 9, 12), "major", "Baden-Württemberg"),
    ],

    # Bavaria (Bayern)
    "Bavaria": [
        Holiday("Winter Break 2025", date(2025, 2, 24), date(2025, 3, 7), "major", "Bavaria"),
        Holiday("Easter Break 2025", date(2025, 4, 14), date(2025, 4, 25), "major", "Bavaria"),
        Holiday("Whitsun Break 2025", date(2025, 6, 10), date(2025, 6, 20), "major", "Bavaria"),
        Holiday("Summer Holiday 2025", date(2025, 8, 1), date(2025, 9, 15), "major", "Bavaria"),
        Holiday("Autumn Break 2025", date(2025, 10, 27), date(2025, 11, 7), "major", "Bavaria"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 10), "major", "Bavaria"),
        Holiday("Winter Break 2026", date(2026, 2, 16), date(2026, 2, 20), "long_weekend", "Bavaria"),
        Holiday("Easter Break 2026", date(2026, 3, 30), date(2026, 4, 10), "major", "Bavaria"),
        Holiday("Whitsun Break 2026", date(2026, 5, 26), date(2026, 6, 5), "major", "Bavaria"),
        Holiday("Summer Holiday 2026", date(2026, 8, 3), date(2026, 9, 14), "major", "Bavaria"),
    ],

    # Berlin
    "Berlin": [
        Holiday("Winter Break 2025", date(2025, 2, 3), date(2025, 2, 8), "long_weekend", "Berlin"),
        Holiday("Easter Break 2025", date(2025, 4, 14), date(2025, 4, 26), "major", "Berlin"),
        Holiday("Summer Holiday 2025", date(2025, 7, 24), date(2025, 9, 6), "major", "Berlin"),
        Holiday("Autumn Break 2025", date(2025, 10, 20), date(2025, 11, 2), "major", "Berlin"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 2), "major", "Berlin"),
        Holiday("Winter Break 2026", date(2026, 2, 2), date(2026, 2, 7), "long_weekend", "Berlin"),
        Holiday("Easter Break 2026", date(2026, 3, 30), date(2026, 4, 11), "major", "Berlin"),
        Holiday("Summer Holiday 2026", date(2026, 7, 23), date(2026, 9, 5), "major", "Berlin"),
        Holiday("Autumn Break 2026", date(2026, 10, 19), date(2026, 10, 31), "major", "Berlin"),
    ],

    # Brandenburg
    "Brandenburg": [
        Holiday("Winter Break 2025", date(2025, 2, 3), date(2025, 2, 8), "long_weekend", "Brandenburg"),
        Holiday("Easter Break 2025", date(2025, 4, 14), date(2025, 4, 26), "major", "Brandenburg"),
        Holiday("Summer Holiday 2025", date(2025, 7, 24), date(2025, 9, 6), "major", "Brandenburg"),
        Holiday("Autumn Break 2025", date(2025, 10, 20), date(2025, 11, 1), "major", "Brandenburg"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 2), "major", "Brandenburg"),
        Holiday("Winter Break 2026", date(2026, 2, 2), date(2026, 2, 6), "long_weekend", "Brandenburg"),
        Holiday("Easter Break 2026", date(2026, 3, 25), date(2026, 4, 11), "major", "Brandenburg"),
        Holiday("Summer Holiday 2026", date(2026, 7, 23), date(2026, 9, 5), "major", "Brandenburg"),
    ],

    # Bremen
    "Bremen": [
        Holiday("Winter Break 2025", date(2025, 2, 3), date(2025, 2, 4), "long_weekend", "Bremen"),
        Holiday("Easter Break 2025", date(2025, 3, 24), date(2025, 4, 9), "major", "Bremen"),
        Holiday("Summer Holiday 2025", date(2025, 7, 24), date(2025, 9, 3), "major", "Bremen"),
        Holiday("Autumn Break 2025", date(2025, 10, 20), date(2025, 11, 1), "major", "Bremen"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 5), "major", "Bremen"),
        Holiday("Winter Break 2026", date(2026, 2, 2), date(2026, 2, 3), "long_weekend", "Bremen"),
        Holiday("Easter Break 2026", date(2026, 3, 25), date(2026, 4, 11), "major", "Bremen"),
        Holiday("Summer Holiday 2026", date(2026, 7, 23), date(2026, 9, 2), "major", "Bremen"),
    ],

    # Hamburg
    "Hamburg": [
        Holiday("Winter Break 2025", date(2025, 2, 3), date(2025, 2, 7), "long_weekend", "Hamburg"),
        Holiday("Easter Break 2025", date(2025, 3, 10), date(2025, 3, 21), "major", "Hamburg"),
        Holiday("Summer Holiday 2025", date(2025, 7, 24), date(2025, 9, 3), "major", "Hamburg"),
        Holiday("Autumn Break 2025", date(2025, 10, 20), date(2025, 10, 31), "major", "Hamburg"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 2), "major", "Hamburg"),
        Holiday("Winter Break 2026", date(2026, 1, 30), date(2026, 1, 30), "long_weekend", "Hamburg"),
        Holiday("Easter Break 2026", date(2026, 3, 2), date(2026, 3, 13), "major", "Hamburg"),
        Holiday("Summer Holiday 2026", date(2026, 7, 23), date(2026, 9, 2), "major", "Hamburg"),
    ],

    # Hesse (Hessen)
    "Hesse": [
        Holiday("Easter Break 2025", date(2025, 4, 7), date(2025, 4, 22), "major", "Hesse"),
        Holiday("Summer Holiday 2025", date(2025, 7, 21), date(2025, 8, 29), "major", "Hesse"),
        Holiday("Autumn Break 2025", date(2025, 10, 20), date(2025, 11, 1), "major", "Hesse"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 10), "major", "Hesse"),
        Holiday("Easter Break 2026", date(2026, 3, 30), date(2026, 4, 11), "major", "Hesse"),
        Holiday("Summer Holiday 2026", date(2026, 7, 20), date(2026, 8, 28), "major", "Hesse"),
        Holiday("Autumn Break 2026", date(2026, 10, 19), date(2026, 10, 31), "major", "Hesse"),
    ],

    # Mecklenburg-Vorpommern
    "Mecklenburg-Vorpommern": [
        Holiday("Winter Break 2025", date(2025, 2, 3), date(2025, 2, 15), "major", "Mecklenburg-Vorpommern"),
        Holiday("Easter Break 2025", date(2025, 4, 14), date(2025, 4, 23), "major", "Mecklenburg-Vorpommern"),
        Holiday("Whitsun Break 2025", date(2025, 5, 30), date(2025, 5, 30), "long_weekend", "Mecklenburg-Vorpommern"),
        Holiday("Summer Holiday 2025", date(2025, 7, 21), date(2025, 8, 30), "major", "Mecklenburg-Vorpommern"),
        Holiday("Autumn Break 2025", date(2025, 10, 20), date(2025, 10, 25), "long_weekend", "Mecklenburg-Vorpommern"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 2), "major", "Mecklenburg-Vorpommern"),
        Holiday("Winter Break 2026", date(2026, 2, 2), date(2026, 2, 11), "major", "Mecklenburg-Vorpommern"),
        Holiday("Easter Break 2026", date(2026, 3, 30), date(2026, 4, 9), "major", "Mecklenburg-Vorpommern"),
    ],

    # Lower Saxony (Niedersachsen)
    "Lower Saxony": [
        Holiday("Winter Break 2025", date(2025, 2, 3), date(2025, 2, 4), "long_weekend", "Lower Saxony"),
        Holiday("Easter Break 2025", date(2025, 3, 24), date(2025, 4, 9), "major", "Lower Saxony"),
        Holiday("Summer Holiday 2025", date(2025, 7, 3), date(2025, 8, 13), "major", "Lower Saxony"),
        Holiday("Autumn Break 2025", date(2025, 10, 13), date(2025, 10, 25), "major", "Lower Saxony"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 5), "major", "Lower Saxony"),
        Holiday("Winter Break 2026", date(2026, 2, 2), date(2026, 2, 3), "long_weekend", "Lower Saxony"),
        Holiday("Easter Break 2026", date(2026, 3, 23), date(2026, 4, 9), "major", "Lower Saxony"),
        Holiday("Summer Holiday 2026", date(2026, 7, 2), date(2026, 8, 12), "major", "Lower Saxony"),
    ],

    # North Rhine-Westphalia (Nordrhein-Westfalen)
    "North Rhine-Westphalia": [
        Holiday("Easter Break 2025", date(2025, 4, 14), date(2025, 4, 26), "major", "North Rhine-Westphalia"),
        Holiday("Whitsun Break 2025", date(2025, 6, 10), date(2025, 6, 10), "long_weekend", "North Rhine-Westphalia"),
        Holiday("Summer Holiday 2025", date(2025, 7, 14), date(2025, 8, 26), "major", "North Rhine-Westphalia"),
        Holiday("Autumn Break 2025", date(2025, 10, 13), date(2025, 10, 25), "major", "North Rhine-Westphalia"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 6), "major", "North Rhine-Westphalia"),
        Holiday("Easter Break 2026", date(2026, 3, 30), date(2026, 4, 11), "major", "North Rhine-Westphalia"),
        Holiday("Summer Holiday 2026", date(2026, 7, 6), date(2026, 8, 18), "major", "North Rhine-Westphalia"),
        Holiday("Autumn Break 2026", date(2026, 10, 12), date(2026, 10, 24), "major", "North Rhine-Westphalia"),
    ],

    # Rhineland-Palatinate (Rheinland-Pfalz)
    "Rhineland-Palatinate": [
        Holiday("Easter Break 2025", date(2025, 3, 24), date(2025, 4, 2), "major", "Rhineland-Palatinate"),
        Holiday("Summer Holiday 2025", date(2025, 7, 21), date(2025, 8, 29), "major", "Rhineland-Palatinate"),
        Holiday("Autumn Break 2025", date(2025, 10, 20), date(2025, 10, 31), "major", "Rhineland-Palatinate"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 7), "major", "Rhineland-Palatinate"),
        Holiday("Easter Break 2026", date(2026, 3, 26), date(2026, 4, 3), "major", "Rhineland-Palatinate"),
        Holiday("Summer Holiday 2026", date(2026, 7, 20), date(2026, 8, 28), "major", "Rhineland-Palatinate"),
        Holiday("Autumn Break 2026", date(2026, 10, 12), date(2026, 10, 23), "major", "Rhineland-Palatinate"),
    ],

    # Saarland
    "Saarland": [
        Holiday("Winter Break 2025", date(2025, 2, 17), date(2025, 2, 22), "long_weekend", "Saarland"),
        Holiday("Easter Break 2025", date(2025, 4, 14), date(2025, 4, 26), "major", "Saarland"),
        Holiday("Summer Holiday 2025", date(2025, 7, 21), date(2025, 8, 29), "major", "Saarland"),
        Holiday("Autumn Break 2025", date(2025, 10, 20), date(2025, 10, 31), "long_weekend", "Saarland"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 2), "major", "Saarland"),
        Holiday("Winter Break 2026", date(2026, 2, 16), date(2026, 2, 21), "long_weekend", "Saarland"),
        Holiday("Easter Break 2026", date(2026, 3, 30), date(2026, 4, 11), "major", "Saarland"),
        Holiday("Summer Holiday 2026", date(2026, 7, 20), date(2026, 8, 28), "major", "Saarland"),
    ],

    # Saxony (Sachsen)
    "Saxony": [
        Holiday("Winter Break 2025", date(2025, 2, 10), date(2025, 2, 22), "major", "Saxony"),
        Holiday("Easter Break 2025", date(2025, 4, 18), date(2025, 4, 26), "major", "Saxony"),
        Holiday("Whitsun Break 2025", date(2025, 5, 30), date(2025, 5, 30), "long_weekend", "Saxony"),
        Holiday("Summer Holiday 2025", date(2025, 6, 28), date(2025, 8, 8), "major", "Saxony"),
        Holiday("Autumn Break 2025", date(2025, 10, 20), date(2025, 11, 1), "major", "Saxony"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 2), "major", "Saxony"),
        Holiday("Winter Break 2026", date(2026, 2, 7), date(2026, 2, 21), "major", "Saxony"),
        Holiday("Easter Break 2026", date(2026, 4, 2), date(2026, 4, 11), "major", "Saxony"),
        Holiday("Summer Holiday 2026", date(2026, 6, 27), date(2026, 8, 7), "major", "Saxony"),
    ],

    # Saxony-Anhalt (Sachsen-Anhalt)
    "Saxony-Anhalt": [
        Holiday("Winter Break 2025", date(2025, 2, 3), date(2025, 2, 12), "major", "Saxony-Anhalt"),
        Holiday("Easter Break 2025", date(2025, 4, 7), date(2025, 4, 12), "long_weekend", "Saxony-Anhalt"),
        Holiday("Whitsun Break 2025", date(2025, 5, 19), date(2025, 5, 19), "long_weekend", "Saxony-Anhalt"),
        Holiday("Summer Holiday 2025", date(2025, 7, 3), date(2025, 8, 13), "major", "Saxony-Anhalt"),
        Holiday("Autumn Break 2025", date(2025, 10, 27), date(2025, 10, 31), "long_weekend", "Saxony-Anhalt"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 19), date(2026, 1, 3), "major", "Saxony-Anhalt"),
        Holiday("Winter Break 2026", date(2026, 2, 2), date(2026, 2, 7), "long_weekend", "Saxony-Anhalt"),
        Holiday("Easter Break 2026", date(2026, 3, 23), date(2026, 3, 28), "long_weekend", "Saxony-Anhalt"),
    ],

    # Schleswig-Holstein
    "Schleswig-Holstein": [
        Holiday("Easter Break 2025", date(2025, 4, 7), date(2025, 4, 19), "major", "Schleswig-Holstein"),
        Holiday("Summer Holiday 2025", date(2025, 7, 21), date(2025, 8, 30), "major", "Schleswig-Holstein"),
        Holiday("Autumn Break 2025", date(2025, 10, 20), date(2025, 11, 1), "major", "Schleswig-Holstein"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 6), "major", "Schleswig-Holstein"),
        Holiday("Easter Break 2026", date(2026, 4, 1), date(2026, 4, 18), "major", "Schleswig-Holstein"),
        Holiday("Summer Holiday 2026", date(2026, 7, 20), date(2026, 8, 29), "major", "Schleswig-Holstein"),
        Holiday("Autumn Break 2026", date(2026, 10, 19), date(2026, 10, 31), "major", "Schleswig-Holstein"),
    ],

    # Thuringia (Thüringen)
    "Thuringia": [
        Holiday("Winter Break 2025", date(2025, 2, 3), date(2025, 2, 8), "long_weekend", "Thuringia"),
        Holiday("Easter Break 2025", date(2025, 4, 7), date(2025, 4, 19), "major", "Thuringia"),
        Holiday("Whitsun Break 2025", date(2025, 5, 30), date(2025, 5, 30), "long_weekend", "Thuringia"),
        Holiday("Summer Holiday 2025", date(2025, 7, 10), date(2025, 8, 20), "major", "Thuringia"),
        Holiday("Autumn Break 2025", date(2025, 10, 6), date(2025, 10, 18), "major", "Thuringia"),
        Holiday("Christmas Break 2025/2026", date(2025, 12, 22), date(2026, 1, 3), "major", "Thuringia"),
        Holiday("Winter Break 2026", date(2026, 2, 2), date(2026, 2, 7), "long_weekend", "Thuringia"),
        Holiday("Easter Break 2026", date(2026, 3, 30), date(2026, 4, 11), "major", "Thuringia"),
        Holiday("Summer Holiday 2026", date(2026, 7, 9), date(2026, 8, 19), "major", "Thuringia"),
    ],
}


def get_holidays_for_region(region: str) -> List[Holiday]:
    """
    Get school holidays for a specific German region/state.

    Args:
        region: Name of the German state (e.g., "Bavaria", "Berlin", etc.)
               Case-insensitive.

    Returns:
        List of Holiday objects for that region. Returns Bavaria holidays if region not found.

    Examples:
        >>> holidays = get_holidays_for_region("Bavaria")
        >>> len(holidays) > 0
        True
        >>> holidays = get_holidays_for_region("berlin")  # Case-insensitive
        >>> len(holidays) > 0
        True
    """
    # Case-insensitive lookup
    for state_name, holidays in GERMAN_HOLIDAYS_2025_2026.items():
        if state_name.lower() == region.lower():
            return holidays

    # Default to Bavaria if region not found
    return GERMAN_HOLIDAYS_2025_2026.get("Bavaria", [])


def get_all_regions() -> List[str]:
    """
    Get list of all available German regions.

    Returns:
        Sorted list of German state names

    Examples:
        >>> regions = get_all_regions()
        >>> "Bavaria" in regions
        True
        >>> "Berlin" in regions
        True
        >>> len(regions)
        16
    """
    return sorted(GERMAN_STATES)


def get_all_holidays() -> List[Holiday]:
    """
    Get all holidays from all German regions.

    Returns:
        Combined list of all Holiday objects from all regions

    Examples:
        >>> all_holidays = get_all_holidays()
        >>> len(all_holidays) > 100
        True
    """
    all_holidays = []
    for holidays in GERMAN_HOLIDAYS_2025_2026.values():
        all_holidays.extend(holidays)
    return all_holidays
