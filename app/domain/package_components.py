"""
Typed access to the JSONB columns on ``TripPackage``.

``TripPackage.flights_json`` is annotated ``dict[str, Any]`` but three writers
put three incompatible shapes in it:

- ``AccommodationMatcher`` wrote ``[flight.id]``               -> list[int]
- ``ParentEscapeAnalyzer`` wrote ``{"travel_method", "details"}`` -> dict
- ``email_preview`` wrote ``{}``                                -> empty dict

Six readers then guessed. ``DealScorer`` guarded with ``isinstance`` ladders in
three places and still crashed: on a package from the main pipeline it reached
``flights_json[0].get("price_per_person")`` against an ``int``, raising
``AttributeError: 'int' object has no attribute 'get'``.

This module is the seam. Writers build components through it, readers read
through it, and legacy rows in any of the historical shapes are normalised on
read so existing data keeps working.

Canonical stored shape::

    {
        "travel_method": "flight",
        "flight_ids": [4, 7],
        "details": {}
    }
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.flight import Flight

logger = logging.getLogger(__name__)

TRAVEL_METHOD_FLIGHT = "flight"
TRAVEL_METHOD_TRAIN = "train"
TRAVEL_METHOD_CAR = "car"

# Keys that identify a legacy embedded flight snapshot rather than the
# canonical envelope.
_SNAPSHOT_HINTS = frozenset(
    {
        "price_per_person",
        "origin_airport",
        "destination_airport",
        "airline",
        "true_cost",
        "total_price",
        "booking_url",
    }
)


@dataclass(frozen=True)
class PackageFlights:
    """
    The travel component of a trip package, in one shape.

    Attributes:
        travel_method: How the family travels -- "flight", "train" or "car".
        flight_ids: Ids of ``Flight`` rows backing this package. Empty for
            non-flight travel.
        details: Free-form context for non-flight travel (the parent-escape
            path stores city info here).
        snapshot: Flight fields that a legacy row embedded directly in the
            JSON instead of referencing by id. Readers should prefer resolving
            ``flight_ids`` against the database and fall back to this.
    """

    travel_method: str = TRAVEL_METHOD_FLIGHT
    flight_ids: tuple[int, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)
    snapshot: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_flight(self) -> bool:
        return self.travel_method == TRAVEL_METHOD_FLIGHT

    @property
    def has_ids(self) -> bool:
        return bool(self.flight_ids)

    def to_json(self) -> dict[str, Any]:
        """Render back to the canonical stored shape."""
        payload: dict[str, Any] = {
            "travel_method": self.travel_method,
            "flight_ids": list(self.flight_ids),
            "details": dict(self.details),
        }
        if self.snapshot:
            payload["snapshot"] = dict(self.snapshot)
        return payload


def build_flight_components(flights: Sequence[Flight]) -> dict[str, Any]:
    """
    Build the stored shape for a package backed by real ``Flight`` rows.

    Args:
        flights: Persisted flights. Each must already have an ``id``; a flight
            that has not been flushed cannot be referenced.

    Returns:
        The canonical JSON payload to assign to ``TripPackage.flights_json``.

    Raises:
        ValueError: If any flight has no id, which would silently produce a
            package that references nothing.
    """
    ids: list[int] = []
    for flight in flights:
        flight_id = getattr(flight, "id", None)
        if flight_id is None:
            raise ValueError(
                "Cannot build flight components from an unpersisted Flight "
                "(id is None). Flush the session before building the package."
            )
        ids.append(int(flight_id))

    return PackageFlights(
        travel_method=TRAVEL_METHOD_FLIGHT,
        flight_ids=tuple(ids),
    ).to_json()


def build_alternative_travel_components(
    travel_method: str,
    details: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """
    Build the stored shape for travel that is not a scraped flight.

    Used by the parent-escape path, which travels by train and carries city
    context rather than flight ids.

    Args:
        travel_method: "train" or "car".
        details: Context to preserve (country, journey time, and so on).
    """
    return PackageFlights(
        travel_method=travel_method,
        flight_ids=(),
        details=dict(details or {}),
    ).to_json()


def empty_components() -> dict[str, Any]:
    """The stored shape for a package with no travel component yet (previews)."""
    return PackageFlights(travel_method=TRAVEL_METHOD_FLIGHT).to_json()


def read_flight_components(raw: Any) -> PackageFlights:
    """
    Normalise whatever is in ``flights_json`` into one shape.

    Accepts the canonical envelope and every historical shape. Never raises on
    malformed input: an unreadable value yields empty components and a warning,
    because a reporting path should not crash on one bad row.

    Args:
        raw: The value of ``TripPackage.flights_json``.
    """
    if raw is None or raw == {} or raw == []:
        return PackageFlights()

    # Canonical envelope.
    if isinstance(raw, Mapping) and (
        "travel_method" in raw or "flight_ids" in raw
    ):
        return PackageFlights(
            travel_method=str(raw.get("travel_method") or TRAVEL_METHOD_FLIGHT),
            flight_ids=_coerce_ids(raw.get("flight_ids")),
            details=dict(raw.get("details") or {}),
            snapshot=dict(raw.get("snapshot") or {}),
        )

    # Legacy: a single embedded flight snapshot as a bare dict.
    if isinstance(raw, Mapping):
        if _SNAPSHOT_HINTS & set(raw.keys()):
            return PackageFlights(
                travel_method=TRAVEL_METHOD_FLIGHT,
                flight_ids=_coerce_ids(raw.get("id")),
                snapshot=dict(raw),
            )
        # An unrecognised mapping: keep it as details rather than dropping it.
        return PackageFlights(details=dict(raw))

    # Legacy: a list. Either flight ids (the main pipeline) or embedded
    # snapshots (older rows).
    if isinstance(raw, (list, tuple)):
        ids: list[int] = []
        snapshot: dict[str, Any] = {}
        for entry in raw:
            if isinstance(entry, bool):
                continue
            if isinstance(entry, int):
                ids.append(entry)
            elif isinstance(entry, str) and entry.strip().lstrip("-").isdigit():
                ids.append(int(entry))
            elif isinstance(entry, Mapping):
                if not snapshot:
                    snapshot = dict(entry)
                entry_id = entry.get("id")
                if isinstance(entry_id, int) and not isinstance(entry_id, bool):
                    ids.append(entry_id)
        return PackageFlights(
            travel_method=TRAVEL_METHOD_FLIGHT,
            flight_ids=tuple(ids),
            snapshot=snapshot,
        )

    logger.warning(
        "Unreadable flights_json of type %s; treating as empty", type(raw).__name__
    )
    return PackageFlights()


def _coerce_ids(value: Any) -> tuple[int, ...]:
    """Coerce an id or list of ids into a tuple of ints, dropping junk."""
    if value is None:
        return ()
    if isinstance(value, bool):
        return ()
    if isinstance(value, int):
        return (value,)
    if isinstance(value, str):
        stripped = value.strip()
        return (int(stripped),) if stripped.lstrip("-").isdigit() else ()
    if isinstance(value, Iterable):
        ids: list[int] = []
        for entry in value:
            if isinstance(entry, bool):
                continue
            if isinstance(entry, int):
                ids.append(entry)
            elif isinstance(entry, str) and entry.strip().lstrip("-").isdigit():
                ids.append(int(entry.strip()))
        return tuple(ids)
    return ()


async def load_flights(
    components: PackageFlights,
    db: AsyncSession,
) -> list[Flight]:
    """
    Resolve a package's flight ids to ``Flight`` rows.

    Airport relationships are eager-loaded, because every caller formats
    origin and destination and would otherwise trigger lazy loads on an async
    session.

    Args:
        components: Normalised components from ``read_flight_components``.
        db: Session owned by the caller.

    Returns:
        The flights, in the order their ids appear. Ids with no matching row
        are skipped.
    """
    if not components.flight_ids:
        return []

    stmt = (
        select(Flight)
        .where(Flight.id.in_(components.flight_ids))
        .options(
            selectinload(Flight.origin_airport),
            selectinload(Flight.destination_airport),
        )
    )
    result = await db.execute(stmt)
    by_id = {flight.id: flight for flight in result.scalars().all()}

    missing = [fid for fid in components.flight_ids if fid not in by_id]
    if missing:
        logger.warning("flights_json references missing Flight ids: %s", missing)

    return [by_id[fid] for fid in components.flight_ids if fid in by_id]


def describe_flight(flight: Optional[Flight], components: PackageFlights) -> str:
    """
    Render a one-line human description of how the family travels.

    Prefers a resolved ``Flight`` row, falls back to a legacy embedded
    snapshot, and describes non-flight travel from its details.
    """
    if flight is not None:
        origin = getattr(flight.origin_airport, "iata_code", None) or "N/A"
        destination = (
            getattr(flight.destination_airport, "iata_code", None) or "N/A"
        )
        airline = flight.airline or "N/A"
        return f"{origin} → {destination} via {airline}"

    if components.snapshot:
        snap = components.snapshot
        origin = snap.get("origin_airport", "N/A")
        destination = snap.get("destination_airport", "N/A")
        airline = snap.get("airline", "N/A")
        return f"{origin} → {destination} via {airline}"

    if not components.is_flight:
        detail = components.details or {}
        country = detail.get("country")
        suffix = f" ({country})" if country else ""
        return f"Travel by {components.travel_method}{suffix}"

    return "Travel details not available"
