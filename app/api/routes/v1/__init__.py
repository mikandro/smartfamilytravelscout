"""
API v1 routes aggregator.
"""

from fastapi import APIRouter

from app.api.routes.v1 import version, health

# Create v1 router
router = APIRouter()

# Include sub-routers
router.include_router(version.router, prefix="/version", tags=["Version"])
router.include_router(health.router, prefix="/health", tags=["Health"])
