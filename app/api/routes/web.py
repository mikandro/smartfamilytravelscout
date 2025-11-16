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
    """Get database session."""
    async with AsyncSessionLocal() as session:
        yield session


async def get_stats(db: AsyncSession) -> dict:
    """Get dashboard statistics."""
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
    """Main dashboard with recent deals."""
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
    """Deals list with filters."""
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
    """View detailed information about a specific deal."""
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
    """User preferences configuration form."""
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
    """Update user preferences."""
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
    """Statistics and charts page."""
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
