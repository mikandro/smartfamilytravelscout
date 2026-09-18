"""
Scraper selection: resolve which scrapers should run for a given search.

This module owns the single answer to "which scrapers run?". Before it existed,
that question was answered in four places which disagreed with each other:

- ``settings.get_available_scrapers()`` read the env flags
- ``_run_pipeline`` read the env flags and then applied CLI overrides inline
- ``_run_scrape`` hardcoded a list and ignored both the flags and the overrides
- ``AccommodationOrchestrator._get_available_scrapers`` hardcoded a list and
  ignored configuration entirely

Callers now pass their overrides here and receive the resolved list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from app.config import settings

# Flight scrapers that never require an API key. These are the "quick search"
# default: `scout scrape` uses them unless the caller asks for something else.
FREE_FLIGHT_SCRAPERS: tuple[str, ...] = ("skyscanner", "ryanair", "wizzair")

# Flight scrapers that require credentials to be configured.
API_KEY_FLIGHT_SCRAPERS: tuple[str, ...] = ("kiwi",)

ALL_FLIGHT_SCRAPERS: tuple[str, ...] = FREE_FLIGHT_SCRAPERS + API_KEY_FLIGHT_SCRAPERS

ALL_ACCOMMODATION_SCRAPERS: tuple[str, ...] = ("booking", "airbnb")


class NoScrapersEnabled(ValueError):
    """
    Raised when selection resolves to an empty list.

    This is part of the interface: callers must expect it rather than checking
    for an empty list themselves. It carries enough context to tell the user
    *why* nothing is left to run.
    """

    def __init__(self, requested: Sequence[str], disabled: Sequence[str]) -> None:
        self.requested = list(requested)
        self.disabled = list(disabled)
        detail = ""
        if self.disabled:
            detail = f" after disabling {', '.join(self.disabled)}"
        super().__init__(
            f"No scrapers are enabled{detail}. "
            f"Enable one in configuration (USE_<NAME>_SCRAPER=true) "
            f"or pass --enable-scraper."
        )


@dataclass(frozen=True)
class ScraperSelection:
    """
    The resolved outcome of a selection.

    ``names`` is what should run. ``ignored`` records override entries that
    named something unknown, so a caller can warn about a typo instead of
    silently doing nothing -- which is how the original inline logic behaved.
    """

    names: tuple[str, ...]
    ignored: tuple[str, ...] = ()

    def __iter__(self):
        return iter(self.names)

    def __len__(self) -> int:
        return len(self.names)

    def __contains__(self, item: object) -> bool:
        return item in self.names


def _normalise(values: Optional[Iterable[str]]) -> List[str]:
    if not values:
        return []
    return [value.strip().lower() for value in values if value and value.strip()]


def resolve_flight_scrapers(
    *,
    enable: Optional[Iterable[str]] = None,
    disable: Optional[Iterable[str]] = None,
    only: Optional[str] = None,
    base: Optional[Iterable[str]] = None,
) -> ScraperSelection:
    """
    Resolve which flight scrapers should run.

    Args:
        enable: Scraper names to add even if configuration disables them. Used
            for ``--enable-scraper``; lets you reach a premium scraper without
            editing ``.env``.
        disable: Scraper names to remove. Used for ``--disable-scraper``.
        only: A single scraper name to run in isolation, or ``"all"``. Used for
            ``scout scrape --scraper X``. When set, it replaces the base set,
            but ``enable``/``disable`` still apply on top.
        base: The starting set. Defaults to the scrapers that configuration
            reports as available. Pass ``FREE_FLIGHT_SCRAPERS`` for the quick
            search path that should not require API keys.

    Returns:
        A ``ScraperSelection``. Iterate it, or read ``.names``.

    Raises:
        NoScrapersEnabled: If the resolved list is empty.
    """
    enable_list = _normalise(enable)
    disable_list = _normalise(disable)
    ignored: List[str] = []

    if only and only.strip().lower() != "all":
        requested = only.strip().lower()
        if requested not in ALL_FLIGHT_SCRAPERS:
            raise ValueError(
                f"Unknown scraper '{only}'. "
                f"Available: {', '.join(ALL_FLIGHT_SCRAPERS)}"
            )
        selected = [requested]
    elif base is not None:
        selected = [name for name in _normalise(base)]
    else:
        selected = list(settings.get_available_scrapers())

    for name in enable_list:
        if name not in ALL_FLIGHT_SCRAPERS:
            ignored.append(name)
            continue
        if name not in selected:
            selected.append(name)

    for name in disable_list:
        if name not in ALL_FLIGHT_SCRAPERS:
            ignored.append(name)
            continue
        if name in selected:
            selected.remove(name)

    if not selected:
        raise NoScrapersEnabled(requested=enable_list, disabled=disable_list)

    # Keep a stable, predictable order regardless of how overrides arrived.
    ordered = tuple(name for name in ALL_FLIGHT_SCRAPERS if name in selected)
    return ScraperSelection(names=ordered, ignored=tuple(ignored))


def resolve_accommodation_scrapers(
    *,
    enable: Optional[Iterable[str]] = None,
    disable: Optional[Iterable[str]] = None,
) -> ScraperSelection:
    """
    Resolve which accommodation scrapers should run.

    Both Booking.com and Airbnb are available without an API key, so the base
    set is all of them. Overrides behave as they do for flights, which is the
    point: one resolution rule for every source family.

    Raises:
        NoScrapersEnabled: If the resolved list is empty.
    """
    enable_list = _normalise(enable)
    disable_list = _normalise(disable)
    ignored: List[str] = []

    selected = list(ALL_ACCOMMODATION_SCRAPERS)

    for name in enable_list:
        if name not in ALL_ACCOMMODATION_SCRAPERS:
            ignored.append(name)
            continue
        if name not in selected:
            selected.append(name)

    for name in disable_list:
        if name not in ALL_ACCOMMODATION_SCRAPERS:
            ignored.append(name)
            continue
        if name in selected:
            selected.remove(name)

    if not selected:
        raise NoScrapersEnabled(requested=enable_list, disabled=disable_list)

    ordered = tuple(
        name for name in ALL_ACCOMMODATION_SCRAPERS if name in selected
    )
    return ScraperSelection(names=ordered, ignored=tuple(ignored))
