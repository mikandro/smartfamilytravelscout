"""
Scrapers package for SmartFamilyTravelScout.

Provides web scrapers for flight, accommodation, and event data from various sources:
- Booking.com: Accommodation search (family-friendly focus)
- Skyscanner: Flight search aggregator
- WizzAir: Budget airline with routes to Eastern Europe
"""

from app.scrapers.booking_scraper import BookingClient, search_booking
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
    # Booking.com
    "BookingClient",
    "search_booking",
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
