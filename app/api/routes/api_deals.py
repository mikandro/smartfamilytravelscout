"""
API routes for deals (trip packages).
Returns JSON responses for programmatic access.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models import TripPackage
from app.api.schemas.package import PackageResponse, PackageListResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/deals", response_model=PackageListResponse, status_code=status.HTTP_200_OK)
async def get_deals(
    limit: int = Query(20, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum AI score"),
    destination: Optional[str] = Query(None, description="Filter by destination city"),
    package_type: Optional[str] = Query(None, description="Filter by package type ('family' or 'parent_escape')"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price in EUR"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price in EUR"),
    db: AsyncSession = Depends(get_async_session),
) -> PackageListResponse:
    """
    Retrieve top-rated travel deals with optional filtering.

    Returns a paginated list of trip packages ordered by AI score (highest first).
    Supports filtering by score, destination, package type, and price range.
    """
    try:
        # Build base query
        query = select(TripPackage)

        # Apply filters
        if min_score is not None:
            query = query.where(TripPackage.ai_score >= min_score)

        if destination:
            query = query.where(TripPackage.destination_city == destination)

        if package_type:
            query = query.where(TripPackage.package_type == package_type)

        if min_price is not None:
            query = query.where(TripPackage.total_price >= min_price)

        if max_price is not None:
            query = query.where(TripPackage.total_price <= max_price)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Order by AI score descending
        query = query.order_by(desc(TripPackage.ai_score))

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(query)
        packages = result.scalars().all()

        # Convert to response models
        package_responses = []
        for pkg in packages:
            # Build response with computed properties
            pkg_dict = {
                "id": pkg.id,
                "package_type": pkg.package_type,
                "destination_city": pkg.destination_city,
                "departure_date": pkg.departure_date,
                "return_date": pkg.return_date,
                "num_nights": pkg.num_nights,
                "total_price": float(pkg.total_price),
                "ai_score": float(pkg.ai_score) if pkg.ai_score is not None else None,
                "ai_reasoning": pkg.ai_reasoning,
                "flights_json": pkg.flights_json,
                "events_json": pkg.events_json,
                "itinerary_json": pkg.itinerary_json,
                "accommodation": pkg.accommodation,
                "notified": pkg.notified,
                "duration_days": pkg.duration_days,
                "is_high_score": pkg.is_high_score,
                "price_per_person": pkg.price_per_person,
                "price_per_night": pkg.price_per_night,
            }
            package_responses.append(PackageResponse(**pkg_dict))

        return PackageListResponse(
            total=total,
            limit=limit,
            offset=offset,
            packages=package_responses,
        )

    except Exception as e:
        logger.error(f"Error fetching deals: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching deals: {str(e)}",
        )
