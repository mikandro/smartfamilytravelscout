"""
API routes for flight search.
Returns JSON responses for programmatic access.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_async_session
from app.models import Flight, Airport
from app.api.schemas.flight import FlightResponse, AirportResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/flights/search", response_model=list[FlightResponse], status_code=status.HTTP_200_OK)
async def search_flights(
    origin: Optional[str] = Query(None, description="Origin airport IATA code (e.g., MUC)"),
    destination: Optional[str] = Query(None, description="Destination airport IATA code (e.g., LIS)"),
    departure_date_from: Optional[str] = Query(None, description="Earliest departure date (YYYY-MM-DD)"),
    departure_date_to: Optional[str] = Query(None, description="Latest departure date (YYYY-MM-DD)"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price per person"),
    direct_only: bool = Query(False, description="Only show direct flights"),
    source: Optional[str] = Query(None, description="Filter by specific source"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_async_session),
) -> list[FlightResponse]:
    """
    Search flights by origin, destination, and date range.

    Returns a list of flights matching the search criteria,
    ordered by price (lowest first).
    """
    try:
        # Build base query with eager loading of airport relationships
        query = select(Flight).options(
            selectinload(Flight.origin_airport),
            selectinload(Flight.destination_airport),
        )

        # Apply filters
        filters = []

        if origin:
            # Look up origin airport by IATA code
            airport_result = await db.execute(
                select(Airport).where(Airport.iata_code == origin.upper())
            )
            origin_airport = airport_result.scalar_one_or_none()
            if origin_airport:
                filters.append(Flight.origin_airport_id == origin_airport.id)

        if destination:
            # Look up destination airport by IATA code
            airport_result = await db.execute(
                select(Airport).where(Airport.iata_code == destination.upper())
            )
            dest_airport = airport_result.scalar_one_or_none()
            if dest_airport:
                filters.append(Flight.destination_airport_id == dest_airport.id)

        if departure_date_from:
            from datetime import datetime
            date_from = datetime.strptime(departure_date_from, "%Y-%m-%d").date()
            filters.append(Flight.departure_date >= date_from)

        if departure_date_to:
            from datetime import datetime
            date_to = datetime.strptime(departure_date_to, "%Y-%m-%d").date()
            filters.append(Flight.departure_date <= date_to)

        if max_price is not None:
            filters.append(Flight.price_per_person <= max_price)

        if direct_only:
            filters.append(Flight.direct_flight == True)

        if source:
            filters.append(Flight.source == source)

        if filters:
            query = query.where(and_(*filters))

        # Order by price ascending (best deals first)
        query = query.order_by(Flight.price_per_person)

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(query)
        flights = result.scalars().all()

        # Convert to response models
        flight_responses = []
        for flight in flights:
            # Build airport responses
            origin_airport_data = {
                "id": flight.origin_airport.id,
                "iata_code": flight.origin_airport.iata_code,
                "city": flight.origin_airport.city,
                "country": flight.origin_airport.country,
                "name": flight.origin_airport.name,
            }
            dest_airport_data = {
                "id": flight.destination_airport.id,
                "iata_code": flight.destination_airport.iata_code,
                "city": flight.destination_airport.city,
                "country": flight.destination_airport.country,
                "name": flight.destination_airport.name,
            }

            # Build flight response
            flight_dict = {
                "id": flight.id,
                "origin_airport": AirportResponse(**origin_airport_data),
                "destination_airport": AirportResponse(**dest_airport_data),
                "airline": flight.airline,
                "departure_date": flight.departure_date,
                "departure_time": flight.departure_time,
                "return_date": flight.return_date,
                "return_time": flight.return_time,
                "price_per_person": float(flight.price_per_person),
                "total_price": float(flight.total_price),
                "true_cost": float(flight.true_cost) if flight.true_cost is not None else None,
                "booking_class": flight.booking_class,
                "direct_flight": flight.direct_flight,
                "source": flight.source,
                "booking_url": flight.booking_url,
                "scraped_at": flight.scraped_at,
                "route": flight.route,
                "is_round_trip": flight.is_round_trip,
                "duration_days": flight.duration_days,
            }
            flight_responses.append(FlightResponse(**flight_dict))

        return flight_responses

    except ValueError as e:
        # Handle date parsing errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {str(e)}. Use YYYY-MM-DD format.",
        )
    except Exception as e:
        logger.error(f"Error searching flights: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching flights: {str(e)}",
        )
