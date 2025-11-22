"""
Parent Escape API routes.

Provides REST API endpoints for finding and analyzing romantic getaway opportunities.
"""

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude_client import ClaudeClient
from app.ai.parent_escape_analyzer import ParentEscapeAnalyzer, TRAIN_DESTINATIONS
from app.database import get_async_session_context
from app.models.trip_package import TripPackage
from app.models.accommodation import Accommodation

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class ParentEscapeOpportunity(BaseModel):
    """Parent escape opportunity response model."""

    id: int
    destination: str
    country: str
    departure_date: str
    return_date: str
    nights: int
    total_cost: float
    escape_score: Optional[float] = None
    romantic_appeal: Optional[float] = None
    accessibility_score: Optional[float] = None
    event_timing_score: Optional[float] = None
    highlights: List[str] = []
    recommended_experiences: List[str] = []
    childcare_suggestions: List[str] = []
    best_time_to_go: Optional[str] = None
    recommendation: Optional[str] = None

    class Config:
        from_attributes = True


class DestinationInfo(BaseModel):
    """Destination information model."""

    name: str
    country: str
    travel_time_hours: float
    romantic_features: List[str]
    accessible: bool = True


class ParentEscapeSearchResponse(BaseModel):
    """Parent escape search response."""

    total_opportunities: int
    search_params: Dict
    opportunities: List[ParentEscapeOpportunity]


class DestinationAnalysisResponse(BaseModel):
    """Destination analysis response."""

    destination: str
    country: str
    escape_score: float
    romantic_appeal: float
    accessibility_score: float
    event_timing_score: float
    weekend_suitability: float
    highlights: List[str]
    recommended_experiences: List[str]
    childcare_suggestions: List[str]
    best_time_to_go: str
    recommendation: str


class AvailableDestinationsResponse(BaseModel):
    """Available destinations response."""

    total_destinations: int
    destinations: List[DestinationInfo]


# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "/destinations",
    response_model=AvailableDestinationsResponse,
    summary="Get available parent escape destinations",
    description="Returns list of all train-accessible romantic destinations from Munich",
)
async def get_available_destinations(
    max_train_hours: float = Query(
        6.0,
        description="Maximum train travel time in hours",
        ge=0,
        le=12,
    ),
) -> AvailableDestinationsResponse:
    """
    Get list of available parent escape destinations.

    Returns all train-accessible romantic destinations from Munich that meet
    the maximum travel time criteria.
    """
    # Filter destinations by max travel time
    eligible_destinations = []

    for city, info in TRAIN_DESTINATIONS.items():
        if info["travel_time_hours"] <= max_train_hours:
            eligible_destinations.append(
                DestinationInfo(
                    name=city,
                    country=info["country"],
                    travel_time_hours=info["travel_time_hours"],
                    romantic_features=info["romantic_features"],
                    accessible=True,
                )
            )

    # Sort by travel time
    eligible_destinations.sort(key=lambda d: d.travel_time_hours)

    return AvailableDestinationsResponse(
        total_destinations=len(eligible_destinations),
        destinations=eligible_destinations,
    )


@router.get(
    "/search",
    response_model=ParentEscapeSearchResponse,
    summary="Search for parent escape opportunities",
    description="Find romantic getaway opportunities based on search criteria",
)
async def search_parent_escapes(
    start_date: Optional[str] = Query(
        None,
        description="Start date for search (YYYY-MM-DD). Default: today",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    end_date: Optional[str] = Query(
        None,
        description="End date for search (YYYY-MM-DD). Default: 3 months from start",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    max_budget: float = Query(
        1200.0,
        description="Maximum total trip budget in EUR (for 2 people)",
        ge=200,
        le=10000,
    ),
    min_nights: int = Query(
        2,
        description="Minimum trip duration in nights",
        ge=1,
        le=7,
    ),
    max_nights: int = Query(
        3,
        description="Maximum trip duration in nights",
        ge=1,
        le=7,
    ),
    max_train_hours: float = Query(
        6.0,
        description="Maximum train travel time in hours",
        ge=0,
        le=12,
    ),
    limit: int = Query(
        10,
        description="Maximum number of results to return",
        ge=1,
        le=50,
    ),
) -> ParentEscapeSearchResponse:
    """
    Search for parent escape opportunities.

    Finds romantic getaway opportunities for parents based on:
    - Train-accessible destinations from Munich
    - Date range and trip duration
    - Budget constraints
    - Romantic features (wine, spa, culture)
    - Special events and timing

    Returns scored and ranked opportunities with AI analysis.
    """
    try:
        # Parse dates
        if start_date:
            start = date.fromisoformat(start_date)
        else:
            start = date.today()

        if end_date:
            end = date.fromisoformat(end_date)
        else:
            end = start + timedelta(days=90)

        # Validate date range
        if end <= start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date must be after start date",
            )

        if min_nights > max_nights:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Min nights must be <= max nights",
            )

        # Initialize analyzer
        claude_client = ClaudeClient()
        analyzer = ParentEscapeAnalyzer(claude_client)

        # Find opportunities
        async with get_async_session_context() as db:
            packages = await analyzer.find_escape_opportunities(
                db=db,
                date_range=(start, end),
                max_budget=max_budget,
                min_nights=min_nights,
                max_nights=max_nights,
                max_train_hours=max_train_hours,
            )

        # Sort by AI score
        sorted_packages = sorted(
            packages,
            key=lambda p: p.ai_score if p.ai_score else 0,
            reverse=True
        )

        # Convert to response models
        opportunities = []
        for pkg in sorted_packages[:limit]:
            # Extract country from flights_json
            country = "Unknown"
            if pkg.flights_json and "details" in pkg.flights_json:
                country = pkg.flights_json["details"].get("country", "Unknown")

            # Build opportunity object
            opportunity = ParentEscapeOpportunity(
                id=pkg.id if pkg.id else 0,
                destination=pkg.destination_city,
                country=country,
                departure_date=pkg.departure_date.isoformat(),
                return_date=pkg.return_date.isoformat(),
                nights=pkg.num_nights,
                total_cost=float(pkg.total_price),
                escape_score=float(pkg.ai_score) if pkg.ai_score else None,
                romantic_appeal=pkg.itinerary_json.get("romantic_appeal") if pkg.itinerary_json else None,
                accessibility_score=pkg.itinerary_json.get("accessibility_score") if pkg.itinerary_json else None,
                event_timing_score=pkg.itinerary_json.get("event_timing_score") if pkg.itinerary_json else None,
                highlights=pkg.itinerary_json.get("highlights", []) if pkg.itinerary_json else [],
                recommended_experiences=pkg.itinerary_json.get("recommended_experiences", []) if pkg.itinerary_json else [],
                childcare_suggestions=pkg.itinerary_json.get("childcare_suggestions", []) if pkg.itinerary_json else [],
                best_time_to_go=pkg.itinerary_json.get("best_time_to_go") if pkg.itinerary_json else None,
                recommendation=pkg.ai_reasoning,
            )
            opportunities.append(opportunity)

        # Build search params for response
        search_params = {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "max_budget": max_budget,
            "min_nights": min_nights,
            "max_nights": max_nights,
            "max_train_hours": max_train_hours,
        }

        return ParentEscapeSearchResponse(
            total_opportunities=len(opportunities),
            search_params=search_params,
            opportunities=opportunities,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error searching parent escapes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search parent escapes: {str(e)}",
        )


@router.get(
    "/{destination}",
    response_model=DestinationAnalysisResponse,
    summary="Analyze a specific destination for parent escape",
    description="Get detailed analysis of a destination's romantic getaway potential",
)
async def analyze_destination(
    destination: str,
    duration_nights: int = Query(
        2,
        description="Trip duration in nights",
        ge=1,
        le=7,
    ),
) -> DestinationAnalysisResponse:
    """
    Analyze a specific destination for parent escape suitability.

    Returns detailed AI analysis including:
    - Escape score (0-100)
    - Romantic appeal rating
    - Accessibility score
    - Event timing score
    - Weekend suitability
    - Highlights and recommendations
    - Childcare suggestions

    The destination must be a train-accessible city from Munich.
    """
    try:
        # Normalize destination name (capitalize first letter of each word)
        destination_normalized = destination.title()

        # Check if destination exists in our database
        if destination_normalized not in TRAIN_DESTINATIONS:
            # Try to find a close match
            available = list(TRAIN_DESTINATIONS.keys())
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Destination '{destination}' not found. Available destinations: {', '.join(available)}",
            )

        # Get destination info
        dest_info = TRAIN_DESTINATIONS[destination_normalized]

        # Find accommodations for this destination
        async with get_async_session_context() as db:
            stmt = (
                select(Accommodation)
                .where(Accommodation.destination_city == destination_normalized)
                .where(Accommodation.rating >= 7.5)
                .order_by(Accommodation.rating.desc())
                .limit(1)
            )
            result = await db.execute(stmt)
            accommodation = result.scalar_one_or_none()

        if not accommodation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No accommodations found for {destination_normalized}. Please try another destination.",
            )

        # Initialize analyzer and score the destination
        claude_client = ClaudeClient()
        analyzer = ParentEscapeAnalyzer(claude_client)

        # Calculate estimated cost
        train_cost_per_hour = 30.0
        train_cost = dest_info["travel_time_hours"] * train_cost_per_hour * 2  # Round trip
        accommodation_cost = float(accommodation.price_per_night) * duration_nights
        food_cost = analyzer.DAILY_FOOD_COST * duration_nights
        activities_cost = analyzer.DAILY_ACTIVITIES_COST * duration_nights
        total_cost = train_cost + accommodation_cost + food_cost + activities_cost

        # Score the escape
        score_result = await analyzer.score_escape(
            destination=destination_normalized,
            destination_info=dest_info,
            accommodation=accommodation,
            events=[],  # No specific events for general analysis
            duration_nights=duration_nights,
            total_cost=total_cost,
        )

        return DestinationAnalysisResponse(
            destination=destination_normalized,
            country=dest_info["country"],
            escape_score=score_result.get("escape_score", 0),
            romantic_appeal=score_result.get("romantic_appeal", 0),
            accessibility_score=score_result.get("accessibility_score", 0),
            event_timing_score=score_result.get("event_timing_score", 0),
            weekend_suitability=score_result.get("weekend_suitability", 0),
            highlights=score_result.get("highlights", []),
            recommended_experiences=score_result.get("recommended_experiences", []),
            childcare_suggestions=score_result.get("childcare_suggestions", []),
            best_time_to_go=score_result.get("best_time_to_go", "Any weekend works"),
            recommendation=score_result.get("recommendation", "A charming getaway destination"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing destination {destination}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze destination: {str(e)}",
        )
