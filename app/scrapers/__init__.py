"""
Scrapers package for SmartFamilyTravelScout.

Provides web scrapers for flight, accommodation, and event data.
"""

from app.scrapers.skyscanner_scraper import (
    SkyscannerScraper,
    RateLimitExceededError,
    CaptchaDetectedError,
)

__all__ = [
    "SkyscannerScraper",
    "RateLimitExceededError",
    "CaptchaDetectedError",
]
