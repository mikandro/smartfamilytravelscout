"""
Price history API endpoints.

Provides REST API for querying price history, detecting price drops,
and getting trend analysis.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.services.price_history_service import PriceHistoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/price-history", tags=["price-history"])


# ============================================================================
# Request/Response Models
# ============================================================================


class PriceHistoryRecord(BaseModel):
    """Price history record response model."""

    id: int
    route: str
    price: float
    source: str
    scraped_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class PriceTrendResponse(BaseModel):
    """Price trend analysis response."""

    route: str
    source: str
    current_price: float
    min_price: float
    max_price: float
    avg_price: float
    trend: str = Field(..., description="'increasing', 'decreasing', 'stable', or 'insufficient_data'")
    data_points: int
    error: Optional[str] = None


class PriceDropResponse(BaseModel):
    """Price drop detection response."""

    route: str
    source: str
    current_price: float
    previous_avg_price: float
    drop_percent: float
    drop_amount: float


class BookingRecommendationResponse(BaseModel):
    """Booking recommendation response."""

    route: str
    recommendation: str
    current_price: float
    avg_price: float
    min_price: float
    price_vs_avg_percent: float
    price_vs_min_percent: float
    trend: str
    confidence: str = Field(..., description="'high', 'medium', or 'low'")
    data_points: int


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/history", response_model=List[PriceHistoryRecord])
async def get_price_history(
    route: Optional[str] = Query(None, description="Route code (e.g., 'MUC-LIS')"),
    origin: Optional[str] = Query(None, description="Origin airport IATA code"),
    destination: Optional[str] = Query(None, description="Destination airport IATA code"),
    source: Optional[str] = Query(None, description="Filter by source (kiwi, skyscanner, etc.)"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get price history for a specific route.

    Either provide `route` parameter OR both `origin` and `destination`.

    Example:
        GET /api/price-history/history?route=MUC-LIS&days=30
        GET /api/price-history/history?origin=MUC&destination=BCN&source=kiwi
    """
    # Validate inputs
    if not route and not (origin and destination):
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'route' or both 'origin' and 'destination'"
        )

    try:
        history = await PriceHistoryService.get_price_history(
            db=db,
            route=route,
            origin=origin,
            destination=destination,
            source=source,
            days=days,
            limit=limit,
        )

        return history

    except Exception as e:
        logger.error(f"Error retrieving price history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve price history")


@router.get("/trends/{route}", response_model=PriceTrendResponse)
async def get_price_trends(
    route: str,
    source: Optional[str] = Query(None, description="Filter by source"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get price trend analysis for a specific route.

    Example:
        GET /api/price-history/trends/MUC-LIS?days=60
        GET /api/price-history/trends/MUC-BCN?source=kiwi
    """
    try:
        trends = await PriceHistoryService.get_price_trends(
            db=db,
            route=route.upper(),
            source=source,
            days=days,
        )

        if "error" in trends:
            raise HTTPException(status_code=404, detail=trends["error"])

        # Remove price_points from response (too large for API)
        trends.pop("price_points", None)

        return trends

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing price trends: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to analyze price trends")


@router.get("/drops", response_model=List[PriceDropResponse])
async def detect_price_drops(
    threshold: float = Query(10.0, ge=1.0, le=100.0, description="Minimum price drop percentage"),
    days: int = Query(7, ge=1, le=90, description="Number of days to compare against"),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Detect significant price drops across all routes.

    Example:
        GET /api/price-history/drops?threshold=15&days=7
    """
    try:
        drops = await PriceHistoryService.detect_price_drops(
            db=db,
            threshold_percent=threshold,
            days=days,
        )

        return drops

    except Exception as e:
        logger.error(f"Error detecting price drops: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to detect price drops")


@router.get("/recommendation/{route}", response_model=BookingRecommendationResponse)
async def get_booking_recommendation(
    route: str,
    days: int = Query(90, ge=7, le=365, description="Days of historical data to analyze"),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get booking recommendation based on price history analysis.

    Example:
        GET /api/price-history/recommendation/MUC-LIS?days=90
    """
    try:
        recommendation = await PriceHistoryService.get_best_booking_time(
            db=db,
            route=route.upper(),
            days=days,
        )

        if "error" in recommendation:
            raise HTTPException(status_code=404, detail=recommendation.get("error", "Not found"))

        return recommendation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating booking recommendation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate booking recommendation")


@router.get("/routes", response_model=List[str])
async def get_tracked_routes(
    days: int = Query(30, ge=1, le=365, description="Get routes with data in last N days"),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get list of all routes with price history data.

    Example:
        GET /api/price-history/routes?days=30
    """
    try:
        from datetime import timedelta
        from sqlalchemy import distinct, select
        from app.models.price_history import PriceHistory

        cutoff_date = datetime.now() - timedelta(days=days)

        query = (
            select(distinct(PriceHistory.route))
            .where(PriceHistory.scraped_at >= cutoff_date)
            .order_by(PriceHistory.route)
        )

        result = await db.execute(query)
        routes = [row[0] for row in result.all()]

        return routes

    except Exception as e:
        logger.error(f"Error retrieving tracked routes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve tracked routes")


@router.get("/statistics")
async def get_price_statistics(
    db: AsyncSession = Depends(get_async_session),
):
    """
    Get overall price tracking statistics.

    Example:
        GET /api/price-history/statistics
    """
    try:
        from datetime import timedelta
        from sqlalchemy import func, select
        from app.models.price_history import PriceHistory

        # Total records
        total_query = select(func.count(PriceHistory.id))
        total_result = await db.execute(total_query)
        total_records = total_result.scalar() or 0

        # Records in last 24 hours
        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_query = select(func.count(PriceHistory.id)).where(
            PriceHistory.scraped_at >= recent_cutoff
        )
        recent_result = await db.execute(recent_query)
        recent_records = recent_result.scalar() or 0

        # Unique routes
        routes_query = select(func.count(func.distinct(PriceHistory.route)))
        routes_result = await db.execute(routes_query)
        unique_routes = routes_result.scalar() or 0

        # Unique sources
        sources_query = select(func.count(func.distinct(PriceHistory.source)))
        sources_result = await db.execute(sources_query)
        unique_sources = sources_result.scalar() or 0

        # Oldest record
        oldest_query = select(func.min(PriceHistory.scraped_at))
        oldest_result = await db.execute(oldest_query)
        oldest_date = oldest_result.scalar()

        return {
            "total_records": total_records,
            "recent_records_24h": recent_records,
            "unique_routes": unique_routes,
            "unique_sources": unique_sources,
            "oldest_record": oldest_date.isoformat() if oldest_date else None,
            "tracking_since": oldest_date.date().isoformat() if oldest_date else None,
        }

    except Exception as e:
        logger.error(f"Error retrieving price statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")
