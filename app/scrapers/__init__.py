"""
Scrapers package for SmartFamilyTravelScout.

Provides web scrapers for flight, accommodation, and event data from various sources:
- Skyscanner: Flight search aggregator
- WizzAir: Budget airline with routes to Eastern Europe
"""

from app.scrapers.skyscanner_scraper import (
    CaptchaDetectedError,
    RateLimitExceededError,
    SkyscannerScraper,
)
from app.scrapers.wizzair_scraper import (
    WizzAirAPIError,
    WizzAirRateLimitError,
    WizzAirScraper,
    scrape_wizzair_flights,
)

__all__ = [
    # Skyscanner
    "SkyscannerScraper",
    "RateLimitExceededError",
    "CaptchaDetectedError",
    # WizzAir
    "WizzAirScraper",
    "WizzAirAPIError",
    "WizzAirRateLimitError",
    "scrape_wizzair_flights",
]
