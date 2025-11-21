"""
Utility functions for airport operations.

This module provides shared utilities for working with airports,
including database operations like get-or-create patterns.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.airport import Airport

logger = logging.getLogger(__name__)


async def get_or_create_airport(
    db: AsyncSession,
    iata_code: str,
    city: str = "",
) -> Optional[Airport]:
    """
    Get airport from database by IATA code, or create if doesn't exist.

    This function provides a consolidated get-or-create pattern for airports,
    ensuring consistent behavior across all scrapers and orchestrators.

    Args:
        db: Database session
        iata_code: Airport IATA code (e.g., 'MUC', 'LIS')
        city: City name (optional, used for creating new airports)

    Returns:
        Airport model instance, or None if iata_code is empty

    Example:
        >>> async with get_async_session_context() as db:
        ...     airport = await get_or_create_airport(db, 'MUC', 'Munich')
        ...     print(f"Airport: {airport.name}")
    """
    if not iata_code:
        return None

    # Normalize IATA code to uppercase
    iata_code = iata_code.upper()

    # Try to find existing airport
    result = await db.execute(
        select(Airport).where(Airport.iata_code == iata_code)
    )
    airport = result.scalar_one_or_none()

    if airport:
        return airport

    # Create new airport with minimal info
    logger.info(f"Creating new airport: {iata_code} ({city})")
    airport = Airport(
        iata_code=iata_code,
        name=f"{city} Airport" if city else f"{iata_code} Airport",
        city=city or iata_code,
        distance_from_home=0,  # Unknown, will be updated later
        driving_time=0,  # Unknown, will be updated later
    )
    db.add(airport)
    await db.flush()  # Get the ID without committing
    return airport
