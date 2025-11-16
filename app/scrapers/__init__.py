"""
Scrapers module for SmartFamilyTravelScout.

This module contains web scrapers for various travel services:
- Booking.com (accommodations)
- Flight search engines (to be implemented)
- Event platforms (to be implemented)
"""

from app.scrapers.booking_scraper import BookingClient, search_booking

__all__ = [
    "BookingClient",
    "search_booking",
]
