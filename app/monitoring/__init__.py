"""
Monitoring module for metrics collection and observability.
"""

from app.monitoring.metrics import (
    metrics_registry,
    scraper_requests_total,
    scraper_duration_seconds,
    flights_discovered_total,
    accommodations_discovered_total,
    events_discovered_total,
    api_requests_total,
    api_duration_seconds,
    scraping_errors_total,
    active_scraping_jobs,
)
from app.monitoring.decorators import track_scraper_metrics, track_api_metrics

__all__ = [
    "metrics_registry",
    "scraper_requests_total",
    "scraper_duration_seconds",
    "flights_discovered_total",
    "accommodations_discovered_total",
    "events_discovered_total",
    "api_requests_total",
    "api_duration_seconds",
    "scraping_errors_total",
    "active_scraping_jobs",
    "track_scraper_metrics",
    "track_api_metrics",
]
