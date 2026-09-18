"""
Party size: how many people a trip is priced for.

Party size was hardcoded as the literal ``4`` in 17 places across 8 modules
(flight orchestrator, kiwi, skyscanner, ryanair_db_helper, flight_cache,
accommodation matcher, accommodation scorer, cost calculator, CLI), while
``TripPackage.price_per_person`` knew it actually varies::

    num_people = 4 if self.package_type == "family" else 2

So every ``/ 4`` and ``* 4`` was wrong for the parent-escape packages, which
are for two people. This module gives the concept one interface: the divisor
comes from the request rather than from a literal.
"""

from __future__ import annotations

from dataclasses import dataclass

PACKAGE_TYPE_FAMILY = "family"
PACKAGE_TYPE_PARENT_ESCAPE = "parent_escape"


@dataclass(frozen=True)
class PartySize:
    """
    The people a trip is booked and priced for.

    Attributes:
        adults: Number of adults travelling.
        children: Number of children travelling.
    """

    adults: int = 2
    children: int = 2

    def __post_init__(self) -> None:
        if self.adults < 1:
            raise ValueError("A party needs at least one adult")
        if self.children < 0:
            raise ValueError("children cannot be negative")

    @property
    def total(self) -> int:
        """Total travellers -- the divisor for per-person arithmetic."""
        return self.adults + self.children

    def per_person(self, total_price: float) -> float:
        """
        Split a total price across the party.

        Args:
            total_price: Price for the whole party.

        Returns:
            Price per person, rounded to cents.
        """
        return round(float(total_price) / self.total, 2)

    def total_for(self, price_per_person: float) -> float:
        """
        Scale a per-person price up to the whole party.

        Args:
            price_per_person: Price for one traveller.

        Returns:
            Price for the party, rounded to cents.
        """
        return round(float(price_per_person) * self.total, 2)

    @property
    def child_ages(self) -> list[int]:
        """
        Representative child ages for scrapers that require them.

        Booking.com and some flight APIs want ages rather than a count. This
        replaces ``children_ages=[3, 6] if children >= 2 else [3]``, which sat
        in the accommodation orchestrator's dispatch.
        """
        default_ages = [3, 6, 9, 12]
        return default_ages[: self.children] or []

    @classmethod
    def for_package_type(cls, package_type: str) -> "PartySize":
        """
        The party a package type is priced for.

        Args:
            package_type: ``"family"``, ``"parent_escape"``, or anything else.

        Returns:
            FAMILY for family packages, COUPLE for everything else -- which
            matches what ``TripPackage.price_per_person`` always assumed.
        """
        if package_type == PACKAGE_TYPE_FAMILY:
            return FAMILY
        return COUPLE


#: Two adults and two children -- the default family this project searches for.
FAMILY = PartySize(adults=2, children=2)

#: Two adults, no children -- the parent-escape party.
COUPLE = PartySize(adults=2, children=0)
