"""
Flight scrapers for various airlines and booking platforms.

This package contains scrapers that fetch flight data from different sources:
- WizzAir: Budget airline with routes to Eastern Europe
- (More scrapers to be added)
"""

from app.scrapers.wizzair_scraper import (
    WizzAirAPIError,
    WizzAirRateLimitError,
    WizzAirScraper,
    scrape_wizzair_flights,
)

__all__ = [
    "WizzAirScraper",
    "WizzAirAPIError",
    "WizzAirRateLimitError",
    "scrape_wizzair_flights",
]
