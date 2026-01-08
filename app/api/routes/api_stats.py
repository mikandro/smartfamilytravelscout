"""
API routes for system statistics.
Returns JSON responses for programmatic access.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models import TripPackage, Flight, Accommodation, Event
from app.api.schemas.stats import StatsResponse, DestinationStats

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats", response_model=StatsResponse, status_code=status.HTTP_200_OK)
async def get_stats(
    db: AsyncSession = Depends(get_async_session),
) -> StatsResponse:
    """
    Access system statistics.

    Returns comprehensive statistics about packages, flights, accommodations,
    events, and top destinations.
    """
    try:
        # Count total packages
        total_packages = await db.scalar(
            select(func.count()).select_from(TripPackage)
        ) or 0

        # Count high score packages (>= 70)
        high_score_packages = await db.scalar(
            select(func.count()).select_from(TripPackage).where(TripPackage.ai_score >= 70)
        ) or 0

        # Average score
        avg_score = await db.scalar(
            select(func.avg(TripPackage.ai_score))
        ) or 0.0

        # Average price
        avg_price = await db.scalar(
            select(func.avg(TripPackage.total_price))
        ) or 0.0

        # Count unique destinations
        unique_destinations = await db.scalar(
            select(func.count(func.distinct(TripPackage.destination_city)))
        ) or 0

        # Count total flights
        total_flights = await db.scalar(
            select(func.count()).select_from(Flight)
        ) or 0

        # Count total accommodations
        total_accommodations = await db.scalar(
            select(func.count()).select_from(Accommodation)
        ) or 0

        # Count total events
        total_events = await db.scalar(
            select(func.count()).select_from(Event)
        ) or 0

        # Get top destinations
        top_dest_result = await db.execute(
            select(
                TripPackage.destination_city,
                func.count().label("count"),
                func.avg(TripPackage.ai_score).label("avg_score"),
                func.avg(TripPackage.total_price).label("avg_price"),
            )
            .group_by(TripPackage.destination_city)
            .order_by(func.count().desc())
            .limit(10)
        )

        top_destinations = []
        for row in top_dest_result.all():
            top_destinations.append(
                DestinationStats(
                    destination=row.destination_city,
                    package_count=row.count,
                    avg_score=round(float(row.avg_score), 1) if row.avg_score else 0.0,
                    avg_price=round(float(row.avg_price), 2) if row.avg_price else 0.0,
                )
            )

        return StatsResponse(
            total_packages=total_packages,
            high_score_packages=high_score_packages,
            avg_score=round(float(avg_score), 1),
            avg_price=round(float(avg_price), 2),
            unique_destinations=unique_destinations,
            total_flights=total_flights,
            total_accommodations=total_accommodations,
            total_events=total_events,
            top_destinations=top_destinations,
        )

    except Exception as e:
        logger.error(f"Error fetching statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching statistics: {str(e)}",
        )
