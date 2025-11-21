"""
Monitoring and metrics collection module.

This module provides Prometheus metrics for monitoring the application's
operational health, scraper performance, and API consumption patterns.
"""

from app.monitoring.metrics import (
    scraper_requests_total,
    scraper_duration_seconds,
    flights_discovered_total,
    accommodations_discovered_total,
    events_discovered_total,
    api_calls_total,
    api_cost_total,
    track_scraper_request,
    track_flights_discovered,
    track_accommodations_discovered,
    track_events_discovered,
    track_api_call,
    track_api_cost,
)

__all__ = [
    "scraper_requests_total",
    "scraper_duration_seconds",
    "flights_discovered_total",
    "accommodations_discovered_total",
    "events_discovered_total",
    "api_calls_total",
    "api_cost_total",
    "track_scraper_request",
    "track_flights_discovered",
    "track_accommodations_discovered",
    "track_events_discovered",
    "track_api_call",
    "track_api_cost",
]
