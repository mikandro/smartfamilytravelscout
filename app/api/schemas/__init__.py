"""
Pydantic schemas for API request/response models.
"""

from app.api.schemas.flight import FlightResponse, FlightSearchParams
from app.api.schemas.package import PackageResponse, PackageListResponse
from app.api.schemas.stats import StatsResponse
from app.api.schemas.search import SearchRequest, SearchResponse

__all__ = [
    "FlightResponse",
    "FlightSearchParams",
    "PackageResponse",
    "PackageListResponse",
    "StatsResponse",
    "SearchRequest",
    "SearchResponse",
]
