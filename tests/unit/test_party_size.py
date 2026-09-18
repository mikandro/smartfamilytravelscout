"""
Unit tests for party size.

The regression these exist for: the literal ``4`` was hardcoded in 17 places
while ``TripPackage.price_per_person`` used ``4 if family else 2``, so every
one of those sites computed the wrong figure for a parent-escape package.
"""

import pytest

from app.domain.party_size import (
    COUPLE,
    FAMILY,
    PACKAGE_TYPE_FAMILY,
    PACKAGE_TYPE_PARENT_ESCAPE,
    PartySize,
)

pytestmark = pytest.mark.unit


class TestTotals:
    def test_family_is_four(self):
        assert FAMILY.total == 4

    def test_couple_is_two(self):
        assert COUPLE.total == 2

    def test_custom_party(self):
        assert PartySize(adults=2, children=3).total == 5


class TestArithmetic:
    def test_per_person_splits_a_total(self):
        assert FAMILY.per_person(400.0) == 100.0

    def test_total_for_scales_up(self):
        assert FAMILY.total_for(100.0) == 400.0

    def test_couple_does_not_divide_by_four(self):
        """The bug: a parent-escape package priced with the family divisor."""
        assert COUPLE.per_person(800.0) == 400.0
        assert COUPLE.per_person(800.0) != FAMILY.per_person(800.0)

    def test_round_trip_is_stable(self):
        assert FAMILY.total_for(FAMILY.per_person(400.0)) == 400.0

    def test_results_are_rounded_to_cents(self):
        assert PartySize(adults=3, children=0).per_person(100.0) == 33.33


class TestPackageTypeMapping:
    def test_family_package(self):
        assert PartySize.for_package_type(PACKAGE_TYPE_FAMILY) == FAMILY

    def test_parent_escape_package(self):
        assert PartySize.for_package_type(PACKAGE_TYPE_PARENT_ESCAPE) == COUPLE

    def test_unknown_type_is_treated_as_a_couple(self):
        """Matches what TripPackage.price_per_person always did."""
        assert PartySize.for_package_type("something_else") == COUPLE


class TestChildAges:
    def test_two_children_get_two_ages(self):
        assert len(FAMILY.child_ages) == 2

    def test_no_children_gives_no_ages(self):
        assert COUPLE.child_ages == []

    def test_ages_are_capped_at_the_child_count(self):
        assert len(PartySize(adults=2, children=1).child_ages) == 1


class TestValidation:
    def test_needs_at_least_one_adult(self):
        with pytest.raises(ValueError, match="at least one adult"):
            PartySize(adults=0, children=2)

    def test_children_cannot_be_negative(self):
        with pytest.raises(ValueError, match="negative"):
            PartySize(adults=2, children=-1)

    def test_is_immutable(self):
        with pytest.raises(Exception):
            FAMILY.adults = 5
