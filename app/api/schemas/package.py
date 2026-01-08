"""
Pydantic schemas for TripPackage API endpoints.
"""

from datetime import date
from typing import Any, Optional
from pydantic import BaseModel, Field


class AccommodationResponse(BaseModel):
    """Accommodation information in API responses."""

    id: int
    name: str
    city: str
    country: str
    accommodation_type: str
    price_per_night: float
    total_price: float
    rating: Optional[float] = None
    url: Optional[str] = None

    class Config:
        from_attributes = True


class PackageResponse(BaseModel):
    """Trip package information in API responses."""

    id: int
    package_type: str = Field(description="'family' or 'parent_escape'")
    destination_city: str
    departure_date: date
    return_date: date
    num_nights: int
    total_price: float = Field(description="Total package price in EUR")
    ai_score: Optional[float] = Field(None, description="AI-generated score from 0 to 100")
    ai_reasoning: Optional[str] = Field(None, description="AI explanation for the score")

    # JSONB fields
    flights_json: dict[str, Any] = Field(description="Flight data")
    events_json: Optional[dict[str, Any]] = Field(None, description="Event data")
    itinerary_json: Optional[dict[str, Any]] = Field(None, description="Day-by-day itinerary")

    # Accommodation (if available)
    accommodation: Optional[AccommodationResponse] = None

    # Notification status
    notified: bool

    # Computed properties
    duration_days: int
    is_high_score: bool
    price_per_person: float
    price_per_night: float

    class Config:
        from_attributes = True


class PackageListResponse(BaseModel):
    """Response for listing multiple packages."""

    total: int = Field(description="Total number of packages matching filters")
    limit: int
    offset: int
    packages: list[PackageResponse]
