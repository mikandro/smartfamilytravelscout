"""
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import redis.asyncio as aioredis

from app import __version__, __app_name__
from app.config import settings
from app.database import check_db_connection, close_db_connections

logger = logging.getLogger(__name__)

# Store Redis client globally
redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {__app_name__} v{__version__}")
    logger.info(f"Environment: {settings.environment}")

    # Initialize Redis connection
    global redis_client
    try:
        redis_client = await aioredis.from_url(
            str(settings.redis_url),
            encoding="utf-8",
            decode_responses=True,
        )
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        redis_client = None

    # Check database connection
    if await check_db_connection():
        logger.info("Database connection established")
    else:
        logger.error("Database connection failed")

    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Shutting down application")

    # Close Redis connection
    if redis_client:
        await redis_client.close()
        logger.info("Redis connection closed")

    # Close database connections
    await close_db_connections()

    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered family travel deal finder",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


# Health check endpoint
@app.get("/health", tags=["Health"], status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.

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
        "version": __version__,
        "environment": settings.environment,
        "dependencies": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy",
        },
    }

    return JSONResponse(content=response, status_code=status_code)


# API root endpoint (moved to /api)
@app.get("/api", tags=["Root"])
async def api_root() -> Dict[str, str]:
    """API root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


# Import and include routers
from app.api.routes import web

# Include web dashboard routes (handles /, /deals, /preferences, /stats)
app.include_router(web.router, tags=["Web Dashboard"])

# API routes (to be implemented)
# from app.api.routes import flights, accommodations, events, search
# app.include_router(flights.router, prefix="/api/v1/flights", tags=["Flights"])
# app.include_router(accommodations.router, prefix="/api/v1/accommodations", tags=["Accommodations"])
# app.include_router(events.router, prefix="/api/v1/events", tags=["Events"])
# app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
