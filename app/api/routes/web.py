"""
Web dashboard routes with Jinja2 template rendering.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import TripPackage, UserPreference, Flight, Accommodation, Event

logger = logging.getLogger(__name__)

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Create router
router = APIRouter()


async def get_db() -> AsyncSession:
    """
    Get async database session for dependency injection.

    Yields:
        AsyncSession: Active database session that automatically commits or rolls back

    Examples:
        >>> @router.get("/items")
        >>> async def read_items(db: AsyncSession = Depends(get_db)):
        >>>     result = await db.execute(select(Item))
        >>>     return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        yield session


async def get_stats(db: AsyncSession) -> dict:
    """
    Calculate and return dashboard statistics.

    Aggregates data from the trip_packages table to provide overview metrics
    including package counts, average scores and prices, and destination counts.

    Args:
        db: Async database session

    Returns:
        dict: Statistics dictionary with keys:
            - total_packages: Total number of trip packages
            - high_score_packages: Count of packages with AI score >= 70
            - avg_score: Average AI score across all packages
            - avg_price: Average total price across all packages
            - unique_destinations: Number of unique destination cities

    Examples:
        >>> stats = await get_stats(db)
        >>> print(stats['total_packages'])
        125
    """
    try:
        # Count packages
        total_packages = await db.scalar(select(func.count()).select_from(TripPackage))

        # Count high score packages (>= 70)
        high_score_packages = await db.scalar(
            select(func.count()).select_from(TripPackage).where(TripPackage.ai_score >= 70)
        )

        # Average score
        avg_score = await db.scalar(select(func.avg(TripPackage.ai_score)))

        # Average price
        avg_price = await db.scalar(select(func.avg(TripPackage.total_price)))

        # Count destinations
        unique_destinations = await db.scalar(
            select(func.count(func.distinct(TripPackage.destination_city)))
        )

        return {
            "total_packages": total_packages or 0,
            "high_score_packages": high_score_packages or 0,
            "avg_score": round(avg_score, 1) if avg_score else 0,
            "avg_price": round(avg_price, 0) if avg_price else 0,
            "unique_destinations": unique_destinations or 0,
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {
            "total_packages": 0,
            "high_score_packages": 0,
            "avg_score": 0,
            "avg_price": 0,
            "unique_destinations": 0,
        }


@router.get("/")
async def dashboard(request: Request):
    """
    Render the main dashboard page with recent top-scoring deals.

    Displays up to 12 recent trip packages sorted by AI score descending,
    along with aggregate statistics.

    Args:
        request: FastAPI Request object for template rendering

    Returns:
        TemplateResponse: Rendered dashboard.html template with context:
            - deals: List of up to 12 top-scoring TripPackage objects
            - stats: Dashboard statistics dict
            - page_title: Page title string
            - error: Error message (only if error occurs)

    Examples:
        Access via browser: GET http://localhost:8000/
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get recent deals ordered by AI score
            result = await db.execute(
                select(TripPackage)
                .order_by(desc(TripPackage.ai_score))
                .limit(12)
            )
            recent_deals = result.scalars().all()

            # Get stats
            stats = await get_stats(db)

            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "deals": recent_deals,
                "stats": stats,
                "page_title": "Dashboard",
            })
        except Exception as e:
            logger.error(f"Error loading dashboard: {e}")
            return templates.TemplateResponse("dashboard.html", {
                "request": request,
                "deals": [],
                "stats": {
                    "total_packages": 0,
                    "high_score_packages": 0,
                    "avg_score": 0,
                    "avg_price": 0,
                    "unique_destinations": 0,
                },
                "page_title": "Dashboard",
                "error": "Error loading dashboard data",
            })


@router.get("/deals")
async def deals_page(
    request: Request,
    min_score: Optional[int] = 0,
    destination: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    package_type: Optional[str] = None,
):
    """
    Render deals list page with optional filtering.

    Supports filtering by AI score, destination city, price range, and package type.
    Results are sorted by AI score descending.

    Args:
        request: FastAPI Request object for template rendering
        min_score: Minimum AI score filter (0-100), defaults to 0
        destination: Filter by destination city name
        min_price: Minimum total price filter in EUR
        max_price: Maximum total price filter in EUR
        package_type: Filter by package type ('family' or 'parent_escape')

    Returns:
        TemplateResponse: Rendered deals.html template with context:
            - deals: List of filtered TripPackage objects
            - destinations: List of unique destination cities for filter dropdown
            - filters: Dict of current filter values
            - page_title: Page title string
            - error: Error message (only if error occurs)

    Examples:
        GET /deals?min_score=70&destination=Barcelona&max_price=2000
    """
    async with AsyncSessionLocal() as db:
        try:
            # Build query
            query = select(TripPackage)

            # Apply filters
            if min_score and min_score > 0:
                query = query.where(TripPackage.ai_score >= min_score)

            if destination:
                query = query.where(TripPackage.destination_city == destination)

            if min_price:
                query = query.where(TripPackage.total_price >= min_price)

            if max_price:
                query = query.where(TripPackage.total_price <= max_price)

            if package_type:
                query = query.where(TripPackage.package_type == package_type)

            # Order by AI score descending
            query = query.order_by(desc(TripPackage.ai_score))

            # Execute query
            result = await db.execute(query)
            deals = result.scalars().all()

            # Get unique destinations for filter dropdown
            dest_result = await db.execute(
                select(TripPackage.destination_city)
                .distinct()
                .order_by(TripPackage.destination_city)
            )
            destinations = [d for d in dest_result.scalars().all() if d]

            return templates.TemplateResponse("deals.html", {
                "request": request,
                "deals": deals,
                "destinations": destinations,
                "filters": {
                    "min_score": min_score,
                    "destination": destination,
                    "min_price": min_price,
                    "max_price": max_price,
                    "package_type": package_type,
                },
                "page_title": "All Deals",
            })
        except Exception as e:
            logger.error(f"Error loading deals: {e}")
            return templates.TemplateResponse("deals.html", {
                "request": request,
                "deals": [],
                "destinations": [],
                "filters": {},
                "page_title": "All Deals",
                "error": "Error loading deals",
            })


@router.get("/deal/{package_id}")
async def deal_details(request: Request, package_id: int):
    """
    Render detailed view of a specific trip package.

    Displays comprehensive information about a trip package including
    flights, accommodation details, events, itinerary, and AI analysis.

    Args:
        request: FastAPI Request object for template rendering
        package_id: Integer ID of the TripPackage to display

    Returns:
        TemplateResponse: Rendered deal_details.html or error.html template with context:
            - deal: TripPackage object with full details
            - accommodation: Accommodation object if associated
            - page_title: Page title string
            - error: Error message (if package not found or error occurs)

    Examples:
        GET /deal/123
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get the package
            result = await db.execute(
                select(TripPackage).where(TripPackage.id == package_id)
            )
            deal = result.scalar_one_or_none()

            if not deal:
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "error": "Deal not found",
                    "page_title": "Error",
                })

            # Get accommodation details if available
            accommodation = None
            if deal.accommodation_id:
                acc_result = await db.execute(
                    select(Accommodation).where(Accommodation.id == deal.accommodation_id)
                )
                accommodation = acc_result.scalar_one_or_none()

            return templates.TemplateResponse("deal_details.html", {
                "request": request,
                "deal": deal,
                "accommodation": accommodation,
                "page_title": f"Deal: {deal.destination_city}",
            })
        except Exception as e:
            logger.error(f"Error loading deal details: {e}")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": f"Error loading deal: {str(e)}",
                "page_title": "Error",
            })


@router.get("/preferences")
async def preferences_page(request: Request):
    """
    Render user preferences configuration page.

    Displays a form for configuring user travel preferences including
    budget limits, destinations, interests, and notification settings.

    Args:
        request: FastAPI Request object for template rendering

    Returns:
        TemplateResponse: Rendered preferences.html template with context:
            - preferences: UserPreference object (or default if none exists)
            - page_title: Page title string
            - error: Error message (only if error occurs)

    Examples:
        GET /preferences
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get the first user preference (for now, single user system)
            result = await db.execute(
                select(UserPreference).order_by(UserPreference.id).limit(1)
            )
            prefs = result.scalar_one_or_none()

            # If no preferences exist, create default ones
            if not prefs:
                prefs = UserPreference(
                    user_id="default",
                    max_flight_price_family=800,
                    max_flight_price_parents=600,
                    max_total_budget_family=2000,
                    preferred_destinations=[],
                    avoid_destinations=[],
                    interests=[],
                    notification_threshold=70,
                    parent_escape_frequency="monthly",
                )

            return templates.TemplateResponse("preferences.html", {
                "request": request,
                "preferences": prefs,
                "page_title": "Preferences",
            })
        except Exception as e:
            logger.error(f"Error loading preferences: {e}")
            return templates.TemplateResponse("preferences.html", {
                "request": request,
                "preferences": None,
                "page_title": "Preferences",
                "error": "Error loading preferences",
            })


@router.post("/preferences")
async def update_preferences(
    request: Request,
    max_flight_price_family: int = Form(...),
    max_flight_price_parents: int = Form(...),
    max_total_budget_family: int = Form(...),
    notification_threshold: int = Form(...),
    parent_escape_frequency: str = Form(...),
    preferred_destinations: str = Form(""),
    avoid_destinations: str = Form(""),
    interests: str = Form(""),
):
    """
    Handle user preferences form submission and update database.

    Parses form data, converts comma-separated lists to arrays, and
    updates or creates UserPreference record in the database.

    Args:
        request: FastAPI Request object for template rendering
        max_flight_price_family: Maximum flight price for family trips in EUR
        max_flight_price_parents: Maximum flight price for parent-only trips in EUR
        max_total_budget_family: Maximum total budget for family trips in EUR
        notification_threshold: Minimum AI score (0-100) to trigger notifications
        parent_escape_frequency: How often to suggest parent-only trips ('weekly', 'monthly')
        preferred_destinations: Comma-separated list of preferred destination cities
        avoid_destinations: Comma-separated list of destinations to avoid
        interests: Comma-separated list of user interests (e.g., "museums, beaches, hiking")

    Returns:
        TemplateResponse: Rendered preferences.html template with context:
            - preferences: Updated UserPreference object
            - page_title: Page title string
            - success: Success message (if update successful)
            - error: Error message (only if error occurs)

    Examples:
        POST /preferences with form data
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get existing preferences
            result = await db.execute(
                select(UserPreference).order_by(UserPreference.id).limit(1)
            )
            prefs = result.scalar_one_or_none()

            # Parse comma-separated lists
            preferred_dest_list = [d.strip() for d in preferred_destinations.split(",") if d.strip()]
            avoid_dest_list = [d.strip() for d in avoid_destinations.split(",") if d.strip()]
            interests_list = [i.strip() for i in interests.split(",") if i.strip()]

            if prefs:
                # Update existing
                prefs.max_flight_price_family = max_flight_price_family
                prefs.max_flight_price_parents = max_flight_price_parents
                prefs.max_total_budget_family = max_total_budget_family
                prefs.notification_threshold = notification_threshold
                prefs.parent_escape_frequency = parent_escape_frequency
                prefs.preferred_destinations = preferred_dest_list
                prefs.avoid_destinations = avoid_dest_list
                prefs.interests = interests_list
            else:
                # Create new
                prefs = UserPreference(
                    user_id="default",
                    max_flight_price_family=max_flight_price_family,
                    max_flight_price_parents=max_flight_price_parents,
                    max_total_budget_family=max_total_budget_family,
                    notification_threshold=notification_threshold,
                    parent_escape_frequency=parent_escape_frequency,
                    preferred_destinations=preferred_dest_list,
                    avoid_destinations=avoid_dest_list,
                    interests=interests_list,
                )
                db.add(prefs)

            await db.commit()

            return templates.TemplateResponse("preferences.html", {
                "request": request,
                "preferences": prefs,
                "page_title": "Preferences",
                "success": "Preferences updated successfully!",
            })
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            await db.rollback()
            return templates.TemplateResponse("preferences.html", {
                "request": request,
                "preferences": None,
                "page_title": "Preferences",
                "error": f"Error updating preferences: {str(e)}",
            })


@router.get("/stats")
async def stats_page(request: Request):
    """
    Render statistics and analytics page with charts.

    Displays comprehensive analytics including price distributions,
    score distributions, and top destinations with aggregated data.

    Args:
        request: FastAPI Request object for template rendering

    Returns:
        TemplateResponse: Rendered stats.html template with context:
            - stats: Overall statistics dict (from get_stats)
            - price_data: List of (price, destination) tuples for price distribution
            - score_data: List of (score, destination) tuples for score distribution
            - top_destinations: List of (destination, count, avg_score) tuples
            - page_title: Page title string
            - error: Error message (only if error occurs)

    Examples:
        GET /stats
    """
    async with AsyncSessionLocal() as db:
        try:
            # Get overall stats
            stats = await get_stats(db)

            # Get price distribution
            result = await db.execute(
                select(TripPackage.total_price, TripPackage.destination_city)
                .order_by(TripPackage.total_price)
            )
            price_data = result.all()

            # Get score distribution
            score_result = await db.execute(
                select(TripPackage.ai_score, TripPackage.destination_city)
                .order_by(desc(TripPackage.ai_score))
            )
            score_data = score_result.all()

            # Get top destinations
            dest_result = await db.execute(
                select(
                    TripPackage.destination_city,
                    func.count().label("count"),
                    func.avg(TripPackage.ai_score).label("avg_score"),
                )
                .group_by(TripPackage.destination_city)
                .order_by(desc("count"))
                .limit(10)
            )
            top_destinations = dest_result.all()

            return templates.TemplateResponse("stats.html", {
                "request": request,
                "stats": stats,
                "price_data": price_data,
                "score_data": score_data,
                "top_destinations": top_destinations,
                "page_title": "Statistics",
            })
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
            return templates.TemplateResponse("stats.html", {
                "request": request,
                "stats": {},
                "price_data": [],
                "score_data": [],
                "top_destinations": [],
                "page_title": "Statistics",
                "error": "Error loading statistics",
            })
