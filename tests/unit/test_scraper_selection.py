"""
Unit tests for scraper selection.

These test the interface: given configuration and runtime overrides, which
scrapers run, and what happens when nothing is left. Before this module
existed, the same question was answered in four places and two of them
ignored the override flags entirely.
"""

import pytest

from app.orchestration.scraper_selection import (
    ALL_ACCOMMODATION_SCRAPERS,
    ALL_FLIGHT_SCRAPERS,
    FREE_FLIGHT_SCRAPERS,
    NoScrapersEnabled,
    ScraperSelection,
    resolve_accommodation_scrapers,
    resolve_flight_scrapers,
)

pytestmark = pytest.mark.unit


class TestQuickSearchDefaults:
    """`scout scrape` must work with no API keys configured."""

    def test_defaults_to_free_scrapers(self):
        selection = resolve_flight_scrapers(base=FREE_FLIGHT_SCRAPERS)
        assert selection.names == ("skyscanner", "ryanair", "wizzair")

    def test_free_defaults_exclude_api_key_scrapers(self):
        selection = resolve_flight_scrapers(base=FREE_FLIGHT_SCRAPERS)
        assert "kiwi" not in selection


class TestRuntimeOverrides:
    """The regression these tests exist for: overrides used to be ignored."""

    def test_disable_removes_a_scraper(self):
        selection = resolve_flight_scrapers(
            disable=["wizzair"], base=FREE_FLIGHT_SCRAPERS
        )
        assert "wizzair" not in selection
        assert selection.names == ("skyscanner", "ryanair")

    def test_disable_accepts_several(self):
        selection = resolve_flight_scrapers(
            disable=["wizzair", "ryanair"], base=FREE_FLIGHT_SCRAPERS
        )
        assert selection.names == ("skyscanner",)

    def test_enable_adds_a_scraper_configuration_excluded(self):
        selection = resolve_flight_scrapers(
            enable=["kiwi"], base=FREE_FLIGHT_SCRAPERS
        )
        assert "kiwi" in selection

    def test_enable_and_disable_combine(self):
        selection = resolve_flight_scrapers(
            enable=["kiwi"], disable=["skyscanner"], base=FREE_FLIGHT_SCRAPERS
        )
        assert "kiwi" in selection
        assert "skyscanner" not in selection

    def test_overrides_are_case_insensitive(self):
        selection = resolve_flight_scrapers(
            disable=["WizzAir"], base=FREE_FLIGHT_SCRAPERS
        )
        assert "wizzair" not in selection

    def test_whitespace_is_tolerated(self):
        selection = resolve_flight_scrapers(
            disable=["  wizzair  "], base=FREE_FLIGHT_SCRAPERS
        )
        assert "wizzair" not in selection

    def test_disabling_an_absent_scraper_is_harmless(self):
        selection = resolve_flight_scrapers(
            disable=["kiwi"], base=FREE_FLIGHT_SCRAPERS
        )
        assert selection.names == FREE_FLIGHT_SCRAPERS


class TestSingleScraperSelection:
    """`scout scrape --scraper X` runs exactly one source."""

    def test_only_selects_one(self):
        selection = resolve_flight_scrapers(only="ryanair")
        assert selection.names == ("ryanair",)

    def test_only_all_falls_back_to_base(self):
        selection = resolve_flight_scrapers(
            only="all", base=FREE_FLIGHT_SCRAPERS
        )
        assert selection.names == FREE_FLIGHT_SCRAPERS

    def test_only_is_case_insensitive(self):
        assert resolve_flight_scrapers(only="Ryanair").names == ("ryanair",)

    def test_unknown_only_raises(self):
        with pytest.raises(ValueError, match="Unknown scraper"):
            resolve_flight_scrapers(only="notascraper")


class TestUnknownNames:
    """A typo should be reported, not silently ignored."""

    def test_unknown_disable_is_reported(self):
        selection = resolve_flight_scrapers(
            disable=["ryanir"], base=FREE_FLIGHT_SCRAPERS
        )
        assert "ryanir" in selection.ignored
        assert selection.names == FREE_FLIGHT_SCRAPERS

    def test_unknown_enable_is_reported(self):
        selection = resolve_flight_scrapers(
            enable=["skyscnner"], base=FREE_FLIGHT_SCRAPERS
        )
        assert "skyscnner" in selection.ignored


class TestEmptySelectionIsAnErrorMode:
    """"Nothing left to run" is part of the interface, not a silent empty list."""

    def test_disabling_everything_raises(self):
        with pytest.raises(NoScrapersEnabled):
            resolve_flight_scrapers(
                disable=list(FREE_FLIGHT_SCRAPERS), base=FREE_FLIGHT_SCRAPERS
            )

    def test_error_names_what_was_disabled(self):
        with pytest.raises(NoScrapersEnabled) as exc:
            resolve_flight_scrapers(
                disable=list(FREE_FLIGHT_SCRAPERS), base=FREE_FLIGHT_SCRAPERS
            )
        assert "wizzair" in exc.value.disabled

    def test_empty_base_raises(self):
        with pytest.raises(NoScrapersEnabled):
            resolve_flight_scrapers(base=[])


class TestOrderIsStable:
    """Order must not depend on how the overrides arrived."""

    def test_enable_order_does_not_change_result(self):
        a = resolve_flight_scrapers(
            enable=["kiwi", "skyscanner"], base=["ryanair"]
        )
        b = resolve_flight_scrapers(
            enable=["skyscanner", "kiwi"], base=["ryanair"]
        )
        assert a.names == b.names

    def test_order_follows_the_canonical_list(self):
        selection = resolve_flight_scrapers(enable=["kiwi"], base=["wizzair"])
        assert selection.names == ("wizzair", "kiwi")


class TestAccommodationSelection:
    """Accommodations resolve through the same rule as flights."""

    def test_defaults_to_all(self):
        assert resolve_accommodation_scrapers().names == ALL_ACCOMMODATION_SCRAPERS

    def test_disable_is_honoured(self):
        selection = resolve_accommodation_scrapers(disable=["booking"])
        assert selection.names == ("airbnb",)

    def test_disabling_everything_raises(self):
        with pytest.raises(NoScrapersEnabled):
            resolve_accommodation_scrapers(
                disable=list(ALL_ACCOMMODATION_SCRAPERS)
            )

    def test_flight_scraper_name_is_not_accepted(self):
        selection = resolve_accommodation_scrapers(disable=["ryanair"])
        assert "ryanair" in selection.ignored
        assert selection.names == ALL_ACCOMMODATION_SCRAPERS


class TestSelectionValueType:
    def test_is_iterable_and_sized(self):
        selection = ScraperSelection(names=("a", "b"))
        assert list(selection) == ["a", "b"]
        assert len(selection) == 2
        assert "a" in selection

    def test_free_scrapers_are_a_subset_of_all(self):
        assert set(FREE_FLIGHT_SCRAPERS).issubset(set(ALL_FLIGHT_SCRAPERS))
