"""
Pydantic schemas for Flight API endpoints.
"""

from datetime import date, time, datetime
from typing import Optional
from pydantic import BaseModel, Field


class AirportResponse(BaseModel):
    """Airport information in API responses."""

    id: int
    iata_code: str
    city: str
    country: str
    name: Optional[str] = None

    class Config:
        from_attributes = True


class FlightResponse(BaseModel):
    """Flight information in API responses."""

    id: int
    origin_airport: AirportResponse
    destination_airport: AirportResponse
    airline: str
    departure_date: date
    departure_time: Optional[time] = None
    return_date: Optional[date] = None
    return_time: Optional[time] = None
    price_per_person: float = Field(description="Price in EUR per person")
    total_price: float = Field(description="Total price for 4 people in EUR")
    true_cost: Optional[float] = Field(None, description="True cost including airport costs")
    booking_class: Optional[str] = None
    direct_flight: bool
    source: str = Field(description="Data source (e.g., kiwi, skyscanner)")
    booking_url: Optional[str] = None
    scraped_at: datetime

    # Computed properties
    route: str = Field(description="Route code like 'MUC-LIS'")
    is_round_trip: bool
    duration_days: Optional[int] = None

    class Config:
        from_attributes = True


class FlightSearchParams(BaseModel):
    """Query parameters for flight search."""

    origin: Optional[str] = Field(None, description="Origin airport IATA code (e.g., MUC)")
    destination: Optional[str] = Field(None, description="Destination airport IATA code (e.g., LIS)")
    departure_date_from: Optional[date] = Field(None, description="Earliest departure date")
    departure_date_to: Optional[date] = Field(None, description="Latest departure date")
    max_price: Optional[float] = Field(None, description="Maximum price per person")
    direct_only: Optional[bool] = Field(False, description="Only show direct flights")
    source: Optional[str] = Field(None, description="Filter by specific source")
    limit: int = Field(50, ge=1, le=500, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")
