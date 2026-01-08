"""
API version information endpoints.
"""

from typing import Dict
from fastapi import APIRouter

from app import __version__, __app_name__
from app.config import settings

router = APIRouter()


@router.get("", response_model=Dict[str, str])
async def get_version() -> Dict[str, str]:
    """
    Get API version information.

    Returns:
        Dictionary with version details
    """
    return {
        "api_version": "1.0.0",
        "app_name": __app_name__,
        "app_version": __version__,
        "environment": settings.environment,
        "status": "stable",
    }
