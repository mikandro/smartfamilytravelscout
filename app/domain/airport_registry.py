"""
Resolving airports by IATA code, in one place.

``select(Airport).where(Airport.iata_code == ...)`` appeared in eight modules:

- ``kiwi_scraper:396``, ``wizzair_scraper:476``, ``skyscanner_scraper:931``
- ``ryanair_db_helper:36``, ``flight_orchestrator:1037``
- ``api_flights:55``, ``api_search:48``, ``cli/main:607``

Half of them created a missing airport and half returned ``None``, so whether
an unseen IATA code broke a scrape depended on which code path reached it
first. This module states the rule once.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.airport import Airport

logger = logging.getLogger(__name__)


async def find_airport(db: AsyncSession, iata_code: str) -> Optional[Airport]:
    """
    Look up an airport by IATA code.

    Args:
        db: Session owned by the caller.
        iata_code: Three-letter code; case and surrounding space are ignored.

    Returns:
        The airport, or ``None`` if the code is empty or unknown.
    """
    if not iata_code:
        return None

    result = await db.execute(
        select(Airport).where(Airport.iata_code == iata_code.strip().upper())
    )
    return result.scalar_one_or_none()


async def find_airports(
    db: AsyncSession, iata_codes: Iterable[str]
) -> Dict[str, Airport]:
    """
    Look up many airports at once.

    Batch form exists so save paths do not issue one query per flight, which
    is the N+1 the orchestrator's save had already worked around locally.

    Args:
        db: Session owned by the caller.
        iata_codes: Codes to resolve.

    Returns:
        Mapping of upper-cased IATA code to airport, omitting unknown codes.
    """
    codes = {code.strip().upper() for code in iata_codes if code}
    if not codes:
        return {}

    result = await db.execute(select(Airport).where(Airport.iata_code.in_(codes)))
    return {airport.iata_code: airport for airport in result.scalars().all()}


async def get_or_create_airport(
    db: AsyncSession,
    iata_code: str,
    city: str = "",
) -> Optional[Airport]:
    """
    Look up an airport, creating a placeholder row if it is unknown.

    Scrapers routinely return codes that are not yet seeded. Creating a
    placeholder keeps a scrape from failing wholesale; the row can be enriched
    later by ``scout db seed``.

    The caller owns the transaction: this flushes so the new row gets an id,
    but does not commit.

    Args:
        db: Session owned by the caller.
        iata_code: Three-letter code.
        city: City name, used only when creating.

    Returns:
        The existing or newly created airport, or ``None`` for an empty code.
    """
    if not iata_code:
        return None

    code = iata_code.strip().upper()
    airport = await find_airport(db, code)
    if airport is not None:
        return airport

    logger.info("Creating placeholder airport %s (%s)", code, city or "unknown city")
    airport = Airport(
        iata_code=code,
        name=f"{city} Airport" if city else f"{code} Airport",
        city=city or code,
        # Not nullable, and genuinely unknown until the airport is seeded.
        # Left at zero so true-cost driving components read as "no drive".
        distance_from_home=0,
        driving_time=0,
    )
    db.add(airport)
    await db.flush()  # assign an id without committing; caller owns the txn
    return airport
