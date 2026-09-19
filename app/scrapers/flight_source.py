"""
One interface for every flight source.

Before this module, there was no flight-source interface. Five dispatch sites
(``FlightOrchestrator.scrape_source``, ``cli scrape``, ``cli test-scraper``,
``cli kiwi-search``, and the accommodation equivalent) each had to know, per
scraper:

- the method name        -- ``search_flights`` vs ``scrape_route``
- the keyword names      -- ``adults/children`` vs ``adult_count/child_count``
- the lifecycle          -- ``async with scraper`` for Skyscanner and Ryanair,
                            plain calls for Kiwi and WizzAir
- the output dict shape  -- ~40 lines of field renames and date/time coercion,
                            duplicated near-verbatim per scraper

An adapter now owns all four. The orchestrator gets a list of sources and never
names one. Adding a scraper means adding an adapter, not editing the dispatch.

The tourism scrapers already worked this way via ``BaseTourismScraper``; this
gives the flight family the same treatment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Protocol, Sequence, runtime_checkable

from app.domain.party_size import FAMILY, PartySize
from app.utils.price_utils import normalize_currency
from app.scrapers.source_errors import (
    SourceBlocked,
    SourceCredentialsInvalid,
    SourceError,
    SourceParseFailed,
    SourceRateLimited,
    SourceUnavailable,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FlightQuery:
    """
    Everything a flight source needs to run one search.

    Replacing loose positional arguments with one value means a source cannot
    be called with the wrong keyword names, which is what the per-scraper
    branches in the old dispatch existed to paper over.
    """

    origin: str
    destination: str
    departure_date: date
    return_date: Optional[date] = None
    party: PartySize = FAMILY

    @property
    def route(self) -> str:
        return f"{self.origin}-{self.destination}"


@runtime_checkable
class FlightSource(Protocol):
    """
    The interface every flight source satisfies.

    Implementations must:

    - return a list of normalised flight dicts (see ``normalise_offer``)
    - raise a ``SourceError`` subclass on failure, never a bare ``Exception``
    - manage their own lifecycle inside ``search`` -- callers never use
      ``async with`` on a source
    - never touch the database; persistence is the repository's job
    """

    #: Stable identifier, also written to ``Flight.source``.
    name: str

    async def search(self, query: FlightQuery) -> List[Dict[str, Any]]:
        """Run one search and return normalised offers."""
        ...


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _as_date_string(value: Any) -> Optional[str]:
    """Render a date-ish value as YYYY-MM-DD."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _as_time_string(value: Any) -> Optional[str]:
    """Render a time-ish value as HH:MM."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    if isinstance(value, time):
        return value.strftime("%H:%M")
    return str(value)


def normalise_offer(
    raw: Dict[str, Any],
    *,
    source: str,
    query: FlightQuery,
    airline: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Bring one scraper's raw dict into the shared shape.

    This is the ~40 lines that used to be duplicated per scraper inside the
    orchestrator's dispatch, with the per-scraper differences now expressed as
    arguments rather than as separate code paths.

    Args:
        raw: The scraper's own dict.
        source: Source name, written to the ``source`` field.
        query: The query this offer answers, used to fill in fields the
            scraper omits (Skyscanner does not echo origin/destination).
        airline: Fixed airline name for single-airline sources.

    Returns:
        A normalised flight dict.
    """
    offer = dict(raw)

    # Airports: prefer what the scraper returned, fall back to the query.
    origin = offer.pop("origin", None) or offer.get("origin_airport") or query.origin
    destination = (
        offer.pop("destination", None)
        or offer.get("destination_airport")
        or query.destination
    )
    offer["origin_airport"] = origin
    offer["destination_airport"] = destination
    offer.setdefault("origin_city", origin)
    offer.setdefault("destination_city", destination)

    # Dates and times: scrapers return str, date, or datetime.
    offer["departure_date"] = (
        _as_date_string(offer.get("departure_date")) or query.departure_date.isoformat()
    )
    offer["return_date"] = _as_date_string(offer.get("return_date")) or (
        query.return_date.isoformat() if query.return_date else None
    )
    if "departure_time" in offer:
        offer["departure_time"] = _as_time_string(offer.get("departure_time"))
    if "return_time" in offer:
        offer["return_time"] = _as_time_string(offer.get("return_time"))

    if airline:
        offer["airline"] = airline

    # Prices. Party size comes from the query, replacing the hardcoded `* 4`
    # that appeared twice in the old dispatch and was wrong for a couple.
    if "price_per_person" not in offer and "price" in offer:
        offer["price_per_person"] = offer["price"]

    # Scrapers return prices as floats or as strings like "€123,45". Route
    # string prices through normalize_currency rather than hand-rolling
    # .replace("€","").replace(",","") per scraper, which is what airbnb:219,
    # booking:358, skyscanner:706, ryanair:701 and wizzair:302 each did.
    per_person = offer.get("price_per_person")
    if isinstance(per_person, str):
        per_person = normalize_currency(per_person)
        offer["price_per_person"] = per_person
    if isinstance(offer.get("total_price"), str):
        offer["total_price"] = normalize_currency(offer["total_price"])

    if per_person is not None and offer.get("total_price") is None:
        offer["total_price"] = query.party.total_for(float(per_person))

    offer["source"] = source
    offer.setdefault("scraped_at", datetime.now().isoformat())
    return offer


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

class _BaseAdapter:
    """Shared error translation for the concrete adapters."""

    name: str = "unknown"

    def _translate(self, exc: Exception) -> SourceError:
        """
        Map a scraper's own exception onto a declared source error mode.

        Each scraper raises its own unrelated types; this is where they become
        one vocabulary. Matching on class name keeps this module from importing
        every scraper just for its exception classes.
        """
        if isinstance(exc, SourceError):
            return exc

        type_name = type(exc).__name__
        message = str(exc) or type_name

        # Credentials first: an auth failure is not retryable, and must not
        # fall through to SourceUnavailable (which is), or a bad API key gets
        # retried forever.
        if any(
            token in type_name
            for token in ("Auth", "APIKeyMissing", "Credential", "Unauthorized", "Forbidden")
        ):
            return SourceCredentialsInvalid(message, source=self.name)

        if "RateLimit" in type_name:
            return SourceRateLimited(message, source=self.name)
        if "Captcha" in type_name or "Blocked" in type_name:
            return SourceBlocked(message, source=self.name)
        if "Timeout" in type_name or "Connection" in type_name:
            return SourceUnavailable(message, source=self.name)
        if isinstance(exc, (KeyError, ValueError, TypeError, AttributeError, IndexError)):
            return SourceParseFailed(message, source=self.name)
        if "APIError" in type_name or "HTTP" in type_name:
            return SourceUnavailable(message, source=self.name)
        return SourceUnavailable(message, source=self.name)


class KiwiSource(_BaseAdapter):
    """Adapter for the Kiwi.com API client (requires KIWI_API_KEY)."""

    name = "kiwi"

    def __init__(self, client=None):
        if client is None:
            from app.scrapers.kiwi_scraper import KiwiClient

            client = KiwiClient()
        self._client = client

    async def search(self, query: FlightQuery) -> List[Dict[str, Any]]:
        try:
            raw = await self._client.search_flights(
                origin=query.origin,
                destination=query.destination,
                departure_date=query.departure_date,
                return_date=query.return_date,
                adults=query.party.adults,
                children=query.party.children,
            )
        except Exception as exc:  # translated to a declared error mode
            raise self._translate(exc) from exc

        return [
            normalise_offer(offer, source=self.name, query=query)
            for offer in (raw or [])
        ]


class SkyscannerSource(_BaseAdapter):
    """
    Adapter for the Skyscanner Playwright scraper.

    Owns the async-context-manager lifecycle the old dispatch branched on, and
    fills in origin/destination, which Skyscanner does not echo back.
    """

    name = "skyscanner"

    def __init__(self, scraper=None, headless: bool = True):
        self._scraper = scraper
        self._headless = headless

    def _build(self):
        if self._scraper is not None:
            return self._scraper
        from app.scrapers.skyscanner_scraper import SkyscannerScraper

        return SkyscannerScraper(headless=self._headless)

    async def search(self, query: FlightQuery) -> List[Dict[str, Any]]:
        scraper = self._build()
        try:
            async with scraper:
                raw = await scraper.scrape_route(
                    origin=query.origin,
                    destination=query.destination,
                    departure_date=query.departure_date,
                    return_date=query.return_date,
                )
        except Exception as exc:
            raise self._translate(exc) from exc

        return [
            normalise_offer(offer, source=self.name, query=query)
            for offer in (raw or [])
        ]


class RyanairSource(_BaseAdapter):
    """Adapter for the Ryanair Playwright scraper (single airline)."""

    name = "ryanair"
    airline = "Ryanair"

    def __init__(self, scraper=None):
        self._scraper = scraper

    def _build(self):
        if self._scraper is not None:
            return self._scraper
        from app.scrapers.ryanair_scraper import RyanairScraper

        return RyanairScraper()

    async def search(self, query: FlightQuery) -> List[Dict[str, Any]]:
        scraper = self._build()
        try:
            async with scraper:
                raw = await scraper.scrape_route(
                    origin=query.origin,
                    destination=query.destination,
                    departure_date=query.departure_date,
                    return_date=query.return_date,
                )
        except Exception as exc:
            raise self._translate(exc) from exc

        return [
            normalise_offer(
                offer, source=self.name, query=query, airline=self.airline
            )
            for offer in (raw or [])
        ]


class WizzAirSource(_BaseAdapter):
    """Adapter for the WizzAir unofficial API scraper (single airline)."""

    name = "wizzair"
    airline = "WizzAir"

    def __init__(self, scraper=None):
        self._scraper = scraper

    def _build(self):
        if self._scraper is not None:
            return self._scraper
        from app.scrapers.wizzair_scraper import WizzAirScraper

        return WizzAirScraper()

    async def search(self, query: FlightQuery) -> List[Dict[str, Any]]:
        scraper = self._build()
        try:
            raw = await scraper.search_flights(
                origin=query.origin,
                destination=query.destination,
                departure_date=query.departure_date,
                return_date=query.return_date,
                adult_count=query.party.adults,
                child_count=query.party.children,
            )
        except Exception as exc:
            raise self._translate(exc) from exc

        return [
            normalise_offer(
                offer, source=self.name, query=query, airline=self.airline
            )
            for offer in (raw or [])
        ]


@dataclass
class InMemoryFlightSource:
    """
    A fake source for tests.

    This is the second adapter that makes the seam real rather than
    hypothetical. Tests previously patched four module globals by name,
    assigned three different method names onto the mocks, and hand-wired
    ``__aenter__``/``__aexit__`` on exactly the two scrapers that happened to
    be context managers -- a 9-line ritual repeated across four tests.

    Attributes:
        name: Source name to report.
        offers: Offers to return from every search.
        error: If set, raised instead of returning offers.
        calls: Queries this fake received, for assertions.
    """

    name: str = "fake"
    offers: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[Exception] = None
    calls: List[FlightQuery] = field(default_factory=list)

    async def search(self, query: FlightQuery) -> List[Dict[str, Any]]:
        self.calls.append(query)
        if self.error is not None:
            raise self.error
        return [
            normalise_offer(dict(offer), source=self.name, query=query)
            for offer in self.offers
        ]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Maps a scraper name to its adapter. Adding a source means adding a row
#: here, not editing a dispatch.
FLIGHT_SOURCE_ADAPTERS = {
    KiwiSource.name: KiwiSource,
    SkyscannerSource.name: SkyscannerSource,
    RyanairSource.name: RyanairSource,
    WizzAirSource.name: WizzAirSource,
}


def build_flight_sources(names: Sequence[str]) -> List[FlightSource]:
    """
    Build adapters for the named sources.

    Args:
        names: Resolved source names, as
            ``app.orchestration.scraper_selection`` produces.

    Returns:
        One adapter per known name, in the order given. Unknown names are
        logged and skipped rather than raising, so one bad config entry cannot
        take down a whole run.
    """
    sources: List[FlightSource] = []
    for name in names:
        adapter = FLIGHT_SOURCE_ADAPTERS.get(name)
        if adapter is None:
            logger.warning("Unknown flight source '%s'; skipping", name)
            continue
        sources.append(adapter())
    return sources
