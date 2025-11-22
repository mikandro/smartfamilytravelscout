"""
Statistics API endpoints (v1).
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import TripPackage

logger = logging.getLogger(__name__)

router = APIRouter()


# Response models
class StatsResponse(BaseModel):
    """Response model for statistics."""
    total_packages: int
    high_score_packages: int
    avg_score: float
    avg_price: float
    unique_destinations: int


class DestinationStats(BaseModel):
    """Statistics for a destination."""
    destination: str
    package_count: int
    avg_score: float


class DestinationStatsResponse(BaseModel):
    """Response model for destination statistics."""
    destinations: List[DestinationStats]
    total_destinations: int


@router.get("", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """
    Get overall statistics.

    Returns:
        Statistics about all packages
    """
    async with AsyncSessionLocal() as db:
        try:
            # Count packages
            total_packages = await db.scalar(
                select(func.count()).select_from(TripPackage)
            )

            # Count high score packages (>= 70)
            high_score_packages = await db.scalar(
                select(func.count())
                .select_from(TripPackage)
                .where(TripPackage.ai_score >= 70)
            )

            # Average score
            avg_score = await db.scalar(select(func.avg(TripPackage.ai_score)))

            # Average price
            avg_price = await db.scalar(select(func.avg(TripPackage.total_price)))

            # Count destinations
            unique_destinations = await db.scalar(
                select(func.count(func.distinct(TripPackage.destination_city)))
            )

            return StatsResponse(
                total_packages=total_packages or 0,
                high_score_packages=high_score_packages or 0,
                avg_score=round(avg_score, 1) if avg_score else 0.0,
                avg_price=round(avg_price, 0) if avg_price else 0.0,
                unique_destinations=unique_destinations or 0,
            )

        except Exception as e:
            logger.error(f"Error fetching statistics: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching statistics: {str(e)}",
            )


@router.get("/destinations", response_model=DestinationStatsResponse)
async def get_destination_stats(
    limit: int = 10,
) -> DestinationStatsResponse:
    """
    Get statistics by destination.

    Args:
        limit: Maximum number of destinations to return (default 10)

    Returns:
        Statistics grouped by destination
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get destination stats
            result = await db.execute(
                select(
                    TripPackage.destination_city,
                    func.count().label("count"),
                    func.avg(TripPackage.ai_score).label("avg_score"),
                )
                .group_by(TripPackage.destination_city)
                .order_by(desc("count"))
                .limit(limit)
            )
            destinations_data = result.all()

            # Get total count of unique destinations
            total_destinations = await db.scalar(
                select(func.count(func.distinct(TripPackage.destination_city)))
            )

            destinations = [
                DestinationStats(
                    destination=dest.destination_city,
                    package_count=dest.count,
                    avg_score=round(dest.avg_score, 1) if dest.avg_score else 0.0,
                )
                for dest in destinations_data
            ]

            return DestinationStatsResponse(
                destinations=destinations,
                total_destinations=total_destinations or 0,
            )

        except Exception as e:
            logger.error(f"Error fetching destination statistics: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching destination statistics: {str(e)}",
            )
