"""
Pydantic schemas for Statistics API endpoints.
"""

from typing import Optional
from pydantic import BaseModel, Field


class DestinationStats(BaseModel):
    """Statistics for a specific destination."""

    destination: str
    package_count: int
    avg_score: float
    avg_price: float


class StatsResponse(BaseModel):
    """System statistics response."""

    total_packages: int = Field(description="Total number of trip packages")
    high_score_packages: int = Field(description="Number of packages with score >= 70")
    avg_score: float = Field(description="Average AI score across all packages")
    avg_price: float = Field(description="Average package price in EUR")
    unique_destinations: int = Field(description="Number of unique destination cities")

    total_flights: Optional[int] = Field(None, description="Total number of flights")
    total_accommodations: Optional[int] = Field(None, description="Total number of accommodations")
    total_events: Optional[int] = Field(None, description="Total number of events")

    top_destinations: Optional[list[DestinationStats]] = Field(None, description="Top destinations by package count")
