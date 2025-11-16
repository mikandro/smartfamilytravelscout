"""
Scrapers package for SmartFamilyTravelScout.

Provides web scrapers for flight, accommodation, and event data from various sources:
- Booking.com: Accommodation search (family-friendly focus)
- Skyscanner: Flight search aggregator
- WizzAir: Budget airline with routes to Eastern Europe
- Tourism boards: Official city tourism websites for local events
"""

from app.scrapers.barcelona_scraper import BarcelonaTourismScraper
from app.scrapers.booking_scraper import BookingClient, search_booking
from app.scrapers.lisbon_scraper import LisbonTourismScraper
from app.scrapers.prague_scraper import PragueTourismScraper
from app.scrapers.skyscanner_scraper import (
    CaptchaDetectedError,
    RateLimitExceededError,
    SkyscannerScraper,
)
from app.scrapers.tourism_db import get_events_by_city, get_events_by_source, save_events_to_db
from app.scrapers.tourism_scraper import BaseTourismScraper, TourismDateParser
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
    # Tourism boards
    "BaseTourismScraper",
    "TourismDateParser",
    "LisbonTourismScraper",
    "PragueTourismScraper",
    "BarcelonaTourismScraper",
    "save_events_to_db",
    "get_events_by_city",
    "get_events_by_source",
]
