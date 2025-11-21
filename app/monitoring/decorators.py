"""
Decorators for tracking metrics on scraping functions and API calls.
"""

import time
import functools
import logging
from typing import Callable, Any, TypeVar, ParamSpec

from app.monitoring.metrics import (
    scraper_requests_total,
    scraper_duration_seconds,
    scraping_errors_total,
    active_scraping_jobs,
    api_requests_total,
    api_duration_seconds,
    flights_discovered_total,
    accommodations_discovered_total,
    events_discovered_total,
)

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def track_scraper_metrics(scraper_name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to track metrics for scraping functions.

    Args:
        scraper_name: Name of the scraper (e.g., 'kiwi', 'skyscanner')

    Usage:
        @track_scraper_metrics('kiwi')
        async def scrape_flights(origin, destination, date_from, date_to):
            # scraping logic
            return flights
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Increment active jobs
            active_scraping_jobs.labels(scraper=scraper_name).inc()

            start_time = time.time()
            status = "success"
            result = None

            try:
                result = await func(*args, **kwargs)

                # Track discovered items based on result type
                if isinstance(result, list) and len(result) > 0:
                    # Try to determine what type of data was scraped
                    sample = result[0] if result else {}

                    # Flight data
                    if "price" in sample and ("origin" in sample or "departure_airport" in sample):
                        origin = sample.get("origin") or sample.get("departure_airport", "unknown")
                        destination = sample.get("destination") or sample.get(
                            "arrival_airport", "unknown"
                        )
                        flights_discovered_total.labels(
                            scraper=scraper_name, origin=origin, destination=destination
                        ).inc(len(result))

                    # Accommodation data
                    elif "name" in sample and ("city" in sample or "location" in sample):
                        city = sample.get("city") or sample.get("location", "unknown")
                        accommodations_discovered_total.labels(
                            scraper=scraper_name, city=city
                        ).inc(len(result))

                    # Event data
                    elif "title" in sample and ("city" in sample or "location" in sample):
                        city = sample.get("city") or sample.get("location", "unknown")
                        events_discovered_total.labels(scraper=scraper_name, city=city).inc(
                            len(result)
                        )

                return result

            except Exception as e:
                status = "failure"
                error_type = type(e).__name__
                scraping_errors_total.labels(scraper=scraper_name, error_type=error_type).inc()
                logger.error(f"Error in {scraper_name} scraper: {error_type} - {str(e)}")
                raise

            finally:
                # Record duration
                duration = time.time() - start_time
                scraper_duration_seconds.labels(scraper=scraper_name).observe(duration)

                # Record request
                scraper_requests_total.labels(scraper=scraper_name, status=status).inc()

                # Decrement active jobs
                active_scraping_jobs.labels(scraper=scraper_name).dec()

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Increment active jobs
            active_scraping_jobs.labels(scraper=scraper_name).inc()

            start_time = time.time()
            status = "success"
            result = None

            try:
                result = func(*args, **kwargs)

                # Track discovered items based on result type
                if isinstance(result, list) and len(result) > 0:
                    sample = result[0] if result else {}

                    if "price" in sample and ("origin" in sample or "departure_airport" in sample):
                        origin = sample.get("origin") or sample.get("departure_airport", "unknown")
                        destination = sample.get("destination") or sample.get(
                            "arrival_airport", "unknown"
                        )
                        flights_discovered_total.labels(
                            scraper=scraper_name, origin=origin, destination=destination
                        ).inc(len(result))

                    elif "name" in sample and ("city" in sample or "location" in sample):
                        city = sample.get("city") or sample.get("location", "unknown")
                        accommodations_discovered_total.labels(
                            scraper=scraper_name, city=city
                        ).inc(len(result))

                    elif "title" in sample and ("city" in sample or "location" in sample):
                        city = sample.get("city") or sample.get("location", "unknown")
                        events_discovered_total.labels(scraper=scraper_name, city=city).inc(
                            len(result)
                        )

                return result

            except Exception as e:
                status = "failure"
                error_type = type(e).__name__
                scraping_errors_total.labels(scraper=scraper_name, error_type=error_type).inc()
                logger.error(f"Error in {scraper_name} scraper: {error_type} - {str(e)}")
                raise

            finally:
                duration = time.time() - start_time
                scraper_duration_seconds.labels(scraper=scraper_name).observe(duration)
                scraper_requests_total.labels(scraper=scraper_name, status=status).inc()
                active_scraping_jobs.labels(scraper=scraper_name).dec()

        # Return appropriate wrapper based on whether function is async
        if functools.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def track_api_metrics(endpoint: str, method: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to track metrics for API endpoints.

    Args:
        endpoint: API endpoint path (e.g., '/api/flights')
        method: HTTP method (e.g., 'GET', 'POST')

    Usage:
        @track_api_metrics('/api/flights', 'GET')
        async def get_flights(db: Session):
            # API logic
            return flights
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.time()
            status = "200"

            try:
                result = await func(*args, **kwargs)
                return result

            except Exception as e:
                status = "500"
                logger.error(f"Error in {endpoint} {method}: {str(e)}")
                raise

            finally:
                duration = time.time() - start_time
                api_duration_seconds.labels(endpoint=endpoint, method=method).observe(duration)
                api_requests_total.labels(endpoint=endpoint, method=method, status=status).inc()

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.time()
            status = "200"

            try:
                result = func(*args, **kwargs)
                return result

            except Exception as e:
                status = "500"
                logger.error(f"Error in {endpoint} {method}: {str(e)}")
                raise

            finally:
                duration = time.time() - start_time
                api_duration_seconds.labels(endpoint=endpoint, method=method).observe(duration)
                api_requests_total.labels(endpoint=endpoint, method=method, status=status).inc()

        if functools.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator
