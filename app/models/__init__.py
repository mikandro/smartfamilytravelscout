"""
SQLAlchemy models for SmartFamilyTravelScout.
Import all models here to ensure they are registered with SQLAlchemy.
"""

from app.models.accommodation import Accommodation
from app.models.airport import Airport
from app.models.api_cost import ApiCost
from app.models.base import Base, TimestampMixin
from app.models.email_delivery_log import EmailDeliveryLog
from app.models.event import Event
from app.models.flight import Flight
from app.models.model_pricing import ModelPricing
from app.models.price_history import PriceHistory
from app.models.school_holiday import SchoolHoliday
from app.models.scraping_job import ScrapingJob
from app.models.trip_package import TripPackage
from app.models.user_preference import UserPreference

__all__ = [
    "Base",
    "TimestampMixin",
    "Airport",
    "Flight",
    "Accommodation",
    "Event",
    "TripPackage",
    "UserPreference",
    "SchoolHoliday",
    "PriceHistory",
    "ScrapingJob",
    "ApiCost",
    "EmailDeliveryLog",
    "ModelPricing",
]
