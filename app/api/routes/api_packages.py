"""
API routes for trip packages.
Returns JSON responses for programmatic access.
"""

import logging

from fastapi import APIRouter, Depends, Path, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_async_session
from app.models import TripPackage
from app.api.schemas.package import PackageResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/packages/{package_id}", response_model=PackageResponse, status_code=status.HTTP_200_OK)
async def get_package(
    package_id: int = Path(..., description="Trip package ID"),
    db: AsyncSession = Depends(get_async_session),
) -> PackageResponse:
    """
    Retrieve specific trip package details by ID.

    Returns complete information about a trip package including
    flights, accommodation, events, and AI-generated itinerary.
    """
    try:
        # Query package with eager loading of accommodation
        query = select(TripPackage).options(
            selectinload(TripPackage.accommodation)
        ).where(TripPackage.id == package_id)

        result = await db.execute(query)
        package = result.scalar_one_or_none()

        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trip package with ID {package_id} not found",
            )

        # Build response with computed properties
        pkg_dict = {
            "id": package.id,
            "package_type": package.package_type,
            "destination_city": package.destination_city,
            "departure_date": package.departure_date,
            "return_date": package.return_date,
            "num_nights": package.num_nights,
            "total_price": float(package.total_price),
            "ai_score": float(package.ai_score) if package.ai_score is not None else None,
            "ai_reasoning": package.ai_reasoning,
            "flights_json": package.flights_json,
            "events_json": package.events_json,
            "itinerary_json": package.itinerary_json,
            "accommodation": package.accommodation,
            "notified": package.notified,
            "duration_days": package.duration_days,
            "is_high_score": package.is_high_score,
            "price_per_person": package.price_per_person,
            "price_per_night": package.price_per_night,
        }

        return PackageResponse(**pkg_dict)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error fetching package {package_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching package: {str(e)}",
        )
