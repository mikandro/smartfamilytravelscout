"""
Prometheus metrics for monitoring application performance and health.

This module defines and tracks metrics for:
- Scraper performance (requests, duration, discoveries)
- API consumption (calls, costs)
- Data collection statistics

All metrics are exposed via the /metrics endpoint for Prometheus to scrape.
"""

import functools
import logging
import time
from typing import Any, Callable, Optional

from prometheus_client import Counter, Histogram, Gauge, Info

logger = logging.getLogger(__name__)

# =============================================================================
# Scraper Metrics
# =============================================================================

# Counter: Total scraper requests
scraper_requests_total = Counter(
    "scraper_requests_total",
    "Total number of scraper requests",
    ["scraper_name", "status"],  # Labels: scraper name, success/failure
)

# Histogram: Scraper request duration
scraper_duration_seconds = Histogram(
    "scraper_duration_seconds",
    "Duration of scraper requests in seconds",
    ["scraper_name"],  # Label: scraper name
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),  # Up to 1 hour
)

# Gauge: Total flights discovered by source
flights_discovered_total = Gauge(
    "flights_discovered_total",
    "Total number of flights discovered",
    ["source"],  # Label: data source (kiwi, skyscanner, ryanair, wizzair)
)

# Gauge: Total accommodations discovered by source
accommodations_discovered_total = Gauge(
    "accommodations_discovered_total",
    "Total number of accommodations discovered",
    ["source"],  # Label: data source (booking, airbnb)
)

# Gauge: Total events discovered by source
events_discovered_total = Gauge(
    "events_discovered_total",
    "Total number of events discovered",
    ["source"],  # Label: data source (eventbrite, barcelona, lisbon, prague)
)

# =============================================================================
# API Metrics
# =============================================================================

# Counter: Total API calls
api_calls_total = Counter(
    "api_calls_total",
    "Total number of API calls",
    ["service", "model"],  # Labels: service name (claude), model name
)

# Counter: Total API cost in USD
api_cost_total = Counter(
    "api_cost_usd_total",
    "Total API cost in USD",
    ["service", "model"],  # Labels: service name, model name
)

# =============================================================================
# Application Info
# =============================================================================

app_info = Info(
    "smartfamilytravelscout_app",
    "Application information",
)


# =============================================================================
# Helper Functions
# =============================================================================


def track_scraper_request(scraper_name: str, status: str) -> None:
    """
    Increment the scraper requests counter.

    Args:
        scraper_name: Name of the scraper (e.g., "kiwi", "skyscanner")
        status: Request status ("success" or "failure")
    """
    scraper_requests_total.labels(scraper_name=scraper_name, status=status).inc()
    logger.debug(f"Tracked scraper request: {scraper_name} - {status}")


def track_flights_discovered(source: str, count: int) -> None:
    """
    Set the gauge for flights discovered from a source.

    Args:
        source: Data source name (e.g., "kiwi", "skyscanner")
        count: Number of flights discovered
    """
    flights_discovered_total.labels(source=source).set(count)
    logger.debug(f"Tracked flights discovered: {source} - {count}")


def track_accommodations_discovered(source: str, count: int) -> None:
    """
    Set the gauge for accommodations discovered from a source.

    Args:
        source: Data source name (e.g., "booking", "airbnb")
        count: Number of accommodations discovered
    """
    accommodations_discovered_total.labels(source=source).set(count)
    logger.debug(f"Tracked accommodations discovered: {source} - {count}")


def track_events_discovered(source: str, count: int) -> None:
    """
    Set the gauge for events discovered from a source.

    Args:
        source: Data source name (e.g., "eventbrite", "barcelona")
        count: Number of events discovered
    """
    events_discovered_total.labels(source=source).set(count)
    logger.debug(f"Tracked events discovered: {source} - {count}")


def track_api_call(service: str, model: str, count: int = 1) -> None:
    """
    Increment the API calls counter.

    Args:
        service: Service name (e.g., "claude")
        model: Model name (e.g., "claude-3-5-sonnet-20241022")
        count: Number of calls to increment (default: 1)
    """
    api_calls_total.labels(service=service, model=model).inc(count)
    logger.debug(f"Tracked API call: {service}/{model} - {count}")


def track_api_cost(service: str, model: str, cost_usd: float) -> None:
    """
    Increment the API cost counter.

    Args:
        service: Service name (e.g., "claude")
        model: Model name (e.g., "claude-3-5-sonnet-20241022")
        cost_usd: Cost in USD to add
    """
    api_cost_total.labels(service=service, model=model).inc(cost_usd)
    logger.debug(f"Tracked API cost: {service}/{model} - ${cost_usd:.4f}")


# =============================================================================
# Decorators
# =============================================================================


def track_scraper_performance(scraper_name: str) -> Callable:
    """
    Decorator to track scraper performance metrics.

    This decorator:
    1. Measures execution time using a histogram
    2. Increments success/failure counters
    3. Handles both sync and async functions

    Args:
        scraper_name: Name of the scraper (e.g., "kiwi", "skyscanner")

    Returns:
        Decorated function

    Example:
        @track_scraper_performance("kiwi")
        async def scrape_flights(origin, destination):
            # scraping logic
            return flights
    """

    def decorator(func: Callable) -> Callable:
        # Check if function is async
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                status = "failure"
                try:
                    result = await func(*args, **kwargs)
                    status = "success"
                    return result
                except Exception as e:
                    logger.error(f"Scraper {scraper_name} failed: {e}")
                    raise
                finally:
                    duration = time.time() - start_time
                    scraper_duration_seconds.labels(scraper_name=scraper_name).observe(duration)
                    track_scraper_request(scraper_name, status)
                    logger.info(
                        f"Scraper {scraper_name} completed in {duration:.2f}s with status: {status}"
                    )

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                status = "failure"
                try:
                    result = func(*args, **kwargs)
                    status = "success"
                    return result
                except Exception as e:
                    logger.error(f"Scraper {scraper_name} failed: {e}")
                    raise
                finally:
                    duration = time.time() - start_time
                    scraper_duration_seconds.labels(scraper_name=scraper_name).observe(duration)
                    track_scraper_request(scraper_name, status)
                    logger.info(
                        f"Scraper {scraper_name} completed in {duration:.2f}s with status: {status}"
                    )

            return sync_wrapper

    return decorator


# Import asyncio at the end to avoid circular imports
import asyncio
