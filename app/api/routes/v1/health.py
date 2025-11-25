"""
Health check API endpoints (v1).
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app import __version__
from app.config import settings
from app.database import check_db_connection
from app.api.main import redis_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", status_code=status.HTTP_200_OK)
async def health_check() -> JSONResponse:
    """
    Health check endpoint for API v1.

    Returns the application status and dependency health checks.
    """
    # Check database
    db_healthy = await check_db_connection()

    # Check Redis
    redis_healthy = False
    if redis_client:
        try:
            await redis_client.ping()
            redis_healthy = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")

    # Determine overall status
    is_healthy = db_healthy and redis_healthy
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    response = {
        "status": "healthy" if is_healthy else "unhealthy",
        "api_version": "1.0.0",
        "app_version": __version__,
        "environment": settings.environment,
        "dependencies": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy",
        },
    }

    return JSONResponse(content=response, status_code=status_code)
