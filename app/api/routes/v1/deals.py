"""
Deal-related API endpoints (v1).
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Query, Path, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import TripPackage, Accommodation

logger = logging.getLogger(__name__)

router = APIRouter()


# Response models
class DealResponse(BaseModel):
    """Response model for a single deal."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    destination_city: str
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    total_price: Optional[float] = None
    ai_score: Optional[int] = None
    ai_reasoning: Optional[str] = None
    package_type: Optional[str] = None
    created_at: datetime


class DealsListResponse(BaseModel):
    """Response model for list of deals."""
    deals: List[DealResponse]
    total_count: int
    filters_applied: Dict[str, Any]


class DealDetailResponse(BaseModel):
    """Detailed response model for a single deal."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    destination_city: str
    departure_date: Optional[str] = None
    return_date: Optional[str] = None
    total_price: Optional[float] = None
    ai_score: Optional[int] = None
    ai_reasoning: Optional[str] = None
    package_type: Optional[str] = None
    flights_json: Optional[Dict[str, Any]] = None
    events_json: Optional[List[Dict[str, Any]]] = None
    itinerary_json: Optional[Dict[str, Any]] = None
    accommodation: Optional[Dict[str, Any]] = None
    created_at: datetime


@router.get("", response_model=DealsListResponse)
async def get_deals(
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum AI score"),
    destination: Optional[str] = Query(None, description="Destination city"),
    min_price: Optional[int] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[int] = Query(None, ge=0, description="Maximum price"),
    package_type: Optional[str] = Query(None, description="Package type"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> DealsListResponse:
    """
    Get list of travel deals with optional filters.

    Args:
        min_score: Minimum AI score (0-100)
        destination: Filter by destination city
        min_price: Minimum total price
        max_price: Maximum total price
        package_type: Filter by package type
        limit: Maximum number of results (default 20, max 100)
        offset: Offset for pagination (default 0)

    Returns:
        List of deals matching filters
    """
    async with AsyncSessionLocal() as db:
        try:
            # Build query
            query = select(TripPackage)

            # Apply filters
            if min_score is not None:
                query = query.where(TripPackage.ai_score >= min_score)

            if destination:
                query = query.where(TripPackage.destination_city == destination)

            if min_price is not None:
                query = query.where(TripPackage.total_price >= min_price)

            if max_price is not None:
                query = query.where(TripPackage.total_price <= max_price)

            if package_type:
                query = query.where(TripPackage.package_type == package_type)

            # Order by AI score descending
            query = query.order_by(desc(TripPackage.ai_score))

            # Get total count before pagination
            count_query = select(TripPackage.id)
            if min_score is not None:
                count_query = count_query.where(TripPackage.ai_score >= min_score)
            if destination:
                count_query = count_query.where(TripPackage.destination_city == destination)
            if min_price is not None:
                count_query = count_query.where(TripPackage.total_price >= min_price)
            if max_price is not None:
                count_query = count_query.where(TripPackage.total_price <= max_price)
            if package_type:
                count_query = count_query.where(TripPackage.package_type == package_type)

            count_result = await db.execute(count_query)
            total_count = len(count_result.all())

            # Apply pagination
            query = query.limit(limit).offset(offset)

            # Execute query
            result = await db.execute(query)
            deals = result.scalars().all()

            # Convert to response models
            deal_responses = [
                DealResponse(
                    id=deal.id,
                    destination_city=deal.destination_city,
                    departure_date=deal.departure_date.isoformat() if deal.departure_date else None,
                    return_date=deal.return_date.isoformat() if deal.return_date else None,
                    total_price=deal.total_price,
                    ai_score=deal.ai_score,
                    ai_reasoning=deal.ai_reasoning,
                    package_type=deal.package_type,
                    created_at=deal.created_at,
                )
                for deal in deals
            ]

            return DealsListResponse(
                deals=deal_responses,
                total_count=total_count,
                filters_applied={
                    "min_score": min_score,
                    "destination": destination,
                    "min_price": min_price,
                    "max_price": max_price,
                    "package_type": package_type,
                    "limit": limit,
                    "offset": offset,
                },
            )

        except Exception as e:
            logger.error(f"Error fetching deals: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching deals: {str(e)}",
            )


@router.get("/{deal_id}", response_model=DealDetailResponse)
async def get_deal(deal_id: int) -> DealDetailResponse:
    """
    Get detailed information about a specific deal.

    Args:
        deal_id: The ID of the deal

    Returns:
        Detailed deal information
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get the package
            result = await db.execute(
                select(TripPackage).where(TripPackage.id == deal_id)
            )
            deal = result.scalar_one_or_none()

            if not deal:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Deal with ID {deal_id} not found",
                )

            # Get accommodation details if available
            accommodation_data = None
            if deal.accommodation_id:
                acc_result = await db.execute(
                    select(Accommodation).where(Accommodation.id == deal.accommodation_id)
                )
                accommodation = acc_result.scalar_one_or_none()
                if accommodation:
                    accommodation_data = {
                        "id": accommodation.id,
                        "name": accommodation.name,
                        "city": accommodation.city,
                        "price_per_night": accommodation.price_per_night,
                        "rating": accommodation.rating,
                        "url": accommodation.url,
                    }

            return DealDetailResponse(
                id=deal.id,
                destination_city=deal.destination_city,
                departure_date=deal.departure_date.isoformat() if deal.departure_date else None,
                return_date=deal.return_date.isoformat() if deal.return_date else None,
                total_price=deal.total_price,
                ai_score=deal.ai_score,
                ai_reasoning=deal.ai_reasoning,
                package_type=deal.package_type,
                flights_json=deal.flights_json,
                events_json=deal.events_json,
                itinerary_json=deal.itinerary_json,
                accommodation=accommodation_data,
                created_at=deal.created_at,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching deal {deal_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching deal: {str(e)}",
            )


@router.get("/top/{limit}", response_model=List[DealResponse])
async def get_top_deals(
    limit: int = Path(..., ge=1, le=50, description="Number of top deals to return"),
) -> List[DealResponse]:
    """
    Get top deals by AI score.

    Args:
        limit: Number of top deals to return (max 50)

    Returns:
        List of top-scored deals
    """
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(TripPackage)
                .order_by(desc(TripPackage.ai_score))
                .limit(limit)
            )
            deals = result.scalars().all()

            return [
                DealResponse(
                    id=deal.id,
                    destination_city=deal.destination_city,
                    departure_date=deal.departure_date.isoformat() if deal.departure_date else None,
                    return_date=deal.return_date.isoformat() if deal.return_date else None,
                    total_price=deal.total_price,
                    ai_score=deal.ai_score,
                    ai_reasoning=deal.ai_reasoning,
                    package_type=deal.package_type,
                    created_at=deal.created_at,
                )
                for deal in deals
            ]

        except Exception as e:
            logger.error(f"Error fetching top deals: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching top deals: {str(e)}",
            )
