"""
Trip package model for AI-generated complete trip suggestions.
"""

from datetime import date
from typing import Any, Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TripPackage(Base, TimestampMixin):
    """
    Model for AI-generated trip packages.
    Combines flights, accommodations, and events into complete trip suggestions.
    """

    __tablename__ = "trip_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Package type
    package_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="'family' or 'parent_escape'",
    )

    # Trip components (stored as JSONB for flexibility)
    flights_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Array of flight IDs or full flight data",
    )
    accommodation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("accommodations.id", ondelete="SET NULL"),
        nullable=True,
    )
    events_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Array of event IDs or full event data",
    )

    # Trip details
    destination_city: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="Primary destination city"
    )
    departure_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    return_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    num_nights: Mapped[int] = mapped_column(Integer, nullable=False)

    # Pricing
    total_price: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, comment="Total package price in EUR"
    )

    # AI scoring and reasoning
    ai_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        index=True,
        comment="AI-generated score from 0 to 100",
    )
    ai_reasoning: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI explanation for the score and package recommendation",
    )
    itinerary_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Day-by-day itinerary suggested by AI",
    )

    # Notification tracking
    notified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Whether user has been notified"
    )

    # Relationships
    accommodation: Mapped[Optional["Accommodation"]] = relationship(
        "Accommodation", foreign_keys=[accommodation_id]
    )

    def __repr__(self) -> str:
        return (
            f"<TripPackage(id={self.id}, type='{self.package_type}', "
            f"destination='{self.destination_city}', "
            f"dates={self.departure_date} to {self.return_date}, "
            f"score={self.ai_score}, price={self.total_price} EUR)>"
        )

    @property
    def duration_days(self) -> int:
        """Calculate trip duration in days."""
        return (self.return_date - self.departure_date).days

    @property
    def is_high_score(self) -> bool:
        """Check if package has high AI score (>= 80)."""
        if self.ai_score:
            return float(self.ai_score) >= 80.0
        return False

    @property
    def price_per_person(self) -> float:
        """Calculate price per person (assuming 4 people for family, 2 for parent escape)."""
        num_people = 4 if self.package_type == "family" else 2
        return float(self.total_price) / num_people

    @property
    def price_per_night(self) -> float:
        """Calculate average price per night."""
        if self.num_nights > 0:
            return float(self.total_price) / self.num_nights
        return 0.0
