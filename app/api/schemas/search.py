"""
Pydantic schemas for Search API endpoints.
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request body for triggering a new search."""

    origin: str = Field(description="Origin airport IATA code (e.g., MUC)")
    destination: str = Field(description="Destination airport IATA code (e.g., LIS)")
    departure_date_from: Optional[date] = Field(None, description="Earliest departure date")
    departure_date_to: Optional[date] = Field(None, description="Latest departure date")
    scraper: Optional[str] = Field(None, description="Specific scraper to use (optional, uses all if not provided)")


class SearchResponse(BaseModel):
    """Response for search operation."""

    status: str = Field(description="'queued', 'running', or 'completed'")
    message: str
    task_id: Optional[str] = Field(None, description="Celery task ID for tracking")
    results_count: Optional[int] = Field(None, description="Number of results found (if completed)")
