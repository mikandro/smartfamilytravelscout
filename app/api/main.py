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
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app import __version__, __app_name__
from app.config import settings
from app.database import check_db_connection, close_db_connections

logger = logging.getLogger(__name__)

# Store Redis client globally
redis_client = None


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def connect_to_redis() -> aioredis.Redis:
    """
    Connect to Redis with retry logic.

    Retries up to 5 times with exponential backoff (2-10 seconds).
    This helps handle race conditions during container startup when
    Redis might not be ready yet.

    Returns:
        Redis client instance

    Raises:
        Exception: If all retry attempts fail
    """
    try:
        client = await aioredis.from_url(
            str(settings.redis_url),
            encoding="utf-8",
            decode_responses=True,
        )
        await client.ping()
        logger.info("Redis connection established")
        return client
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise  # Re-raise to trigger retry


def validate_startup_config() -> None:
    """
    Validate configuration and warn about missing optional features.

    Note: Required settings (DATABASE_URL, REDIS_URL, ANTHROPIC_API_KEY, SECRET_KEY)
    are enforced by Pydantic and will cause import errors if missing.
    """
    warnings = []

    # Warn about optional API keys
    if not settings.kiwi_api_key and settings.use_kiwi_scraper:
        warnings.append("KIWI_API_KEY not set - Kiwi.com scraper will be disabled")

    if not settings.eventbrite_api_key:
        warnings.append("EVENTBRITE_API_KEY not set - Event scraping will be limited")

    # Check if at least one scraper is available
    available_scrapers = settings.get_available_scrapers()
    if not available_scrapers:
        warnings.append("No flight scrapers are enabled - enable at least one scraper")

    # Warn about SMTP configuration for notifications
    if settings.enable_notifications and (not settings.smtp_user or not settings.smtp_password):
        warnings.append("SMTP credentials not configured - email notifications will fail")

    # Log warnings
    if warnings:
        logger.warning("Startup configuration warnings:")
        for warning in warnings:
            logger.warning(f"  - {warning}")
    else:
        logger.info("Startup configuration validated successfully")

    # Log available scrapers
    if available_scrapers:
        logger.info(f"Available scrapers: {', '.join(available_scrapers)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events with proper validation and retry logic.
    """
    # Startup
    logger.info(f"Starting {__app_name__} v{__version__}")
    logger.info(f"Environment: {settings.environment}")

    # Validate configuration
    validate_startup_config()

    # Initialize Redis connection with retry
    global redis_client
    try:
        redis_client = await connect_to_redis()
    except Exception as e:
        # Enhanced error logging (Issue #57)
        logger.error(
            f"Failed to connect to Redis after retries: {e}\n"
            f"Redis URL (masked): {str(settings.redis_url).replace(settings.redis_url.password or '', '***') if settings.redis_url else 'not configured'}\n"
            f"To fix: Ensure Redis is running (docker-compose up -d redis) and REDIS_URL is correctly set in .env",
            exc_info=True
        )
        raise RuntimeError(f"Redis connection failed: {e}")

    # Check database connection with retry
    try:
        await check_db_connection()
        logger.info("Database connection established")
    except Exception as e:
        # Enhanced error logging (Issue #57)
        logger.error(
            f"Failed to connect to database after retries: {e}\n"
            "To fix:\n"
            "  1. Ensure PostgreSQL is running: docker-compose up -d postgres\n"
            "  2. Check logs: docker-compose logs postgres\n"
            "  3. Verify DATABASE_URL in .env file",
            exc_info=True
        )
        raise RuntimeError(f"Database connection failed: {e}")

    logger.info("Application startup complete - all dependencies healthy")

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

# Add CORS middleware for frontend cross-origin requests
# This enables frontend applications (e.g., React, Vue) to make API requests
# Configuration is controlled via ALLOWED_ORIGINS environment variable
# Default: http://localhost:3000,http://localhost:8000
# Production: Set to specific domain(s) for security (never use "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins_list(),  # Configured via env var
    allow_credentials=True,  # Allow cookies and authentication headers
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers (Content-Type, Authorization, etc.)
)

# Add GZip middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled exceptions."""
    logger.error(
        f"Unhandled exception during {request.method} {request.url.path}: {exc}",
        exc_info=True
    )

    # Provide more context in debug mode
    if settings.debug:
        content = {
            "error": "Internal server error",
            "message": str(exc),
            "type": exc.__class__.__name__,
            "path": str(request.url.path),
            "method": request.method,
        }
    else:
        content = {
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please check the logs or contact support.",
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
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
async def api_root() -> Dict[str, Any]:
    """API root endpoint with version information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "api_versions": {
            "v1": {
                "status": "stable",
                "prefix": "/api/v1",
                "endpoints": {
                    "version": "/api/v1/version",
                    "health": "/api/v1/health",
                    "deals": "/api/v1/deals",
                    "flights": "/api/v1/flights",
                    "packages": "/api/v1/packages",
                    "search": "/api/v1/search",
                    "stats": "/api/v1/stats",
                    "parent_escape": "/api/v1/parent-escape",
                    "price_history": "/api/v1/price-history",
                },
            },
        },
        "docs": "/docs",
        "health": "/health",
    }


# Import and include routers
from app.api.routes import web, notifications, parent_escape, price_history
from app.api.routes import api_deals, api_flights, api_packages, api_search, api_stats
from app.api.routes.v1 import router as v1_router

# Include web dashboard routes (handles /, /deals, /preferences, /stats)
app.include_router(web.router, tags=["Web Dashboard"])

# Include notification routes (unsubscribe, preferences)
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])

# Include API v1 versioning routes (version info, health check)
app.include_router(v1_router, prefix="/api/v1", tags=["API v1"])

# API routes for programmatic access
app.include_router(api_deals.router, prefix="/api/v1", tags=["API - Deals"])
app.include_router(api_flights.router, prefix="/api/v1", tags=["API - Flights"])
app.include_router(api_packages.router, prefix="/api/v1", tags=["API - Packages"])
app.include_router(api_search.router, prefix="/api/v1", tags=["API - Search"])
app.include_router(api_stats.router, prefix="/api/v1", tags=["API - Statistics"])
app.include_router(parent_escape.router, prefix="/api/v1/parent-escape", tags=["Parent Escape"])
app.include_router(price_history.router, prefix="/api/v1", tags=["Price History"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
